"""폐쇄형 Go 컨테이너 생명주기의 실행 마감 동작을 검증한다.

Docker는 프로세스 경계에서 대체한다. 마지막 테스트는 컨테이너를 시작하지
않고 실제 자식 프로세스로 마감에 따른 process group 회수를 검증한다.
"""

import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import nullcontext
from types import SimpleNamespace
from unittest import mock


SENTINEL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SENTINEL_ROOT))
sys.path.insert(0, str(SENTINEL_ROOT / "src"))

from sentinel import go_sandbox, sandbox
from sentinel.errors import SentinelError
from sentinel.oci_image import verify_image
from tests.test_go_sandbox import DockerScript
from tests.test_go_sandbox_lifecycle import GoDockerScript, HASHES, HOST_ROOTS, RECORD
from tests.test_oci_image import image_fixture


class DeadlineDockerScript(GoDockerScript):
    def __init__(self, *args, after_start=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.timeouts = []
        self.after_start = after_start

    def collect(self, process, request, timeout):
        command = process.args[5:]
        self.timeouts.append((tuple(command[:2]), timeout))
        if command[:2] == ["container", "start"] and self.start_failure is None:
            if self.after_start is not None:
                self.after_start()
            return (
                json.dumps(RECORD).encode() + b"\nSENTINEL_PRIVATE_STDERR\n",
                b"",
                None,
            )
        return DockerScript.collect(self, process, request, timeout)


class GoExecutionDeadlineTests(unittest.TestCase):
    def setUp(self):
        reference, manifest, config = image_fixture()
        self.identity = verify_image(reference, manifest, config)
        self.roots = tuple(SimpleNamespace(root=Path(path)) for path in HOST_ROOTS)
        self.inputs = SimpleNamespace(
            uid=1000,
            gid=1000,
            release_hashes=HASHES,
            support_schema="sentinel-go-support-v1",
            corpus=SimpleNamespace(_entries=()),
        )
        lock = {"image": {"reference": reference, "os": "linux", "architecture": "amd64"}}
        with mock.patch.object(sandbox.oci, "_load_lock", return_value=lock):
            with mock.patch.object(go_sandbox, "recheck_go_inputs"):
                self.box = go_sandbox.GoSandbox(
                    Path("/tmp/mock-lock"),
                    "a" * 64,
                    Path("/tmp/mock-session"),
                    "b" * 64,
                    manifest,
                    config,
                    self.inputs,
                )
        self.argv = (
            "/usr/bin/bash",
            "--noprofile",
            "--norc",
            "-c",
            go_sandbox._BOOTSTRAP,
            "sentinel-go-closed",
            *HASHES,
            "1000",
            "1000",
            "0",
            "original",
        )

    def run_mocked(self, script, recheck, *, deadline=None, preflight=None, clock=None):
        preflight = preflight if preflight is not None else (lambda *_args: None)
        with mock.patch.object(go_sandbox, "roots", return_value=self.roots):
            with mock.patch.object(go_sandbox, "recheck_go_inputs", side_effect=recheck):
                with mock.patch.object(sandbox.oci, "recheck_session", side_effect=preflight):
                    with mock.patch.object(sandbox.subprocess, "Popen", side_effect=script.popen):
                        with mock.patch.object(sandbox, "_collect", side_effect=script.collect):
                            time_guard = (
                                mock.patch.object(sandbox.time, "monotonic", side_effect=clock)
                                if clock is not None
                                else nullcontext()
                            )
                            with time_guard:
                                return self.box.run(go_sandbox.GoRunRequest("original"), deadline=deadline)

    def test_expired_deadline_returns_timeout_without_creating_container(self):
        script = DeadlineDockerScript(self, self.identity, self.argv)
        result = self.run_mocked(script, lambda _value: None, deadline=time.monotonic() - 1)
        self.assertTrue(result.sandbox.timed_out)
        self.assertTrue(result.sandbox.removed)
        self.assertIsNone(result.command_exit_code)
        self.assertFalse(result.input_integrity_verified)
        self.assertFalse(any(call[5:7] == ["container", "create"] for call in script.calls))
        self.assertFalse(any(call[5:7] == ["container", "start"] for call in script.calls))

    def test_deadline_expiring_during_input_check_blocks_start_and_cleans(self):
        now = [100.0]
        checks = 0

        def recheck(_value):
            nonlocal checks
            checks += 1
            if checks == 2:
                now[0] = 106.0

        script = DeadlineDockerScript(self, self.identity, self.argv)
        result = self.run_mocked(script, recheck, deadline=105.0, clock=lambda: now[0])
        self.assertTrue(result.sandbox.timed_out)
        self.assertTrue(result.sandbox.removed)
        self.assertEqual(checks, 3)
        self.assertTrue(any(call[5:7] == ["container", "create"] for call in script.calls))
        self.assertFalse(any(call[5:7] == ["container", "start"] for call in script.calls))
        self.assertTrue(any(call[5:7] == ["container", "rm"] for call in script.calls))

    def test_each_non_cleanup_command_uses_remaining_deadline(self):
        now = [100.0]

        def recheck(_value):
            now[0] += 3.0

        def preflight(*_args):
            now[0] += 2.0

        script = DeadlineDockerScript(self, self.identity, self.argv)
        result = self.run_mocked(
            script,
            recheck,
            deadline=130.0,
            preflight=preflight,
            clock=lambda: now[0],
        )
        self.assertFalse(result.sandbox.timed_out)
        starts = [timeout for command, timeout in script.timeouts if command == ("container", "start")]
        terminal_inspects = [
            timeout for command, timeout in script.timeouts if command == ("container", "inspect")
        ]
        self.assertEqual(starts, [10.0])
        self.assertEqual(terminal_inspects, [10.0, 6.0])
        cleanup_timeouts = [
            timeout for command, timeout in script.timeouts if command in (("container", "rm"), ("container", "ls"))
        ]
        self.assertEqual(cleanup_timeouts, [sandbox.CLEANUP_TIMEOUT, sandbox.CLEANUP_TIMEOUT])

    def test_deadline_after_start_still_allows_bounded_cleanup(self):
        now = [100.0]
        script = DeadlineDockerScript(self, self.identity, self.argv, after_start=lambda: now.__setitem__(0, 111.0))
        result = self.run_mocked(script, lambda _value: None, deadline=110.0, clock=lambda: now[0])
        self.assertTrue(result.sandbox.timed_out)
        self.assertTrue(result.sandbox.removed)
        cleanup_timeouts = [
            timeout for command, timeout in script.timeouts if command in (("container", "rm"), ("container", "ls"))
        ]
        self.assertEqual(cleanup_timeouts, [sandbox.CLEANUP_TIMEOUT, sandbox.CLEANUP_TIMEOUT])

    def test_cleanup_failure_wins_over_deadline_and_preserves_cancellation(self):
        now = [100.0]
        checks = 0

        def recheck(_value):
            nonlocal checks
            checks += 1
            if checks == 2:
                now[0] = 106.0
                self.box.cancellation_requested = True

        script = DeadlineDockerScript(self, self.identity, self.argv, rm_failure="timeout")
        with self.assertRaises(SentinelError) as caught:
            self.run_mocked(script, recheck, deadline=105.0, clock=lambda: now[0])
        self.assertEqual((caught.exception.code, caught.exception.exit_code), ("sandboxFailed", 6))
        self.assertTrue(self.box.cancellation_requested)
        call_count = len(script.calls)
        with self.assertRaises(SentinelError) as sticky:
            self.run_mocked(script, lambda _value: None, deadline=None)
        self.assertEqual((sticky.exception.code, sticky.exception.exit_code), ("sandboxCancelled", 8))
        self.assertEqual(len(script.calls), call_count)

    def test_expired_deadline_does_not_stick_to_follow_up_call(self):
        expired = DeadlineDockerScript(self, self.identity, self.argv)
        first = self.run_mocked(expired, lambda _value: None, deadline=time.monotonic() - 1)
        self.assertTrue(first.sandbox.timed_out)

        successful = DeadlineDockerScript(self, self.identity, self.argv)
        second = self.run_mocked(successful, lambda _value: None)
        self.assertFalse(second.sandbox.timed_out)
        self.assertTrue(second.input_integrity_verified)

    def test_deadline_accepts_only_finite_non_boolean_numbers(self):
        script = DeadlineDockerScript(self, self.identity, self.argv)
        for value in (True, False, "later", object(), math.nan, math.inf, -math.inf):
            with self.subTest(value=value):
                with self.assertRaises(SentinelError) as caught:
                    self.run_mocked(script, lambda _value: None, deadline=value)
                self.assertEqual((caught.exception.code, caught.exception.exit_code), ("sandboxFailed", 6))
        self.assertEqual(script.calls, [])

    def test_large_finite_integer_deadline_keeps_existing_limits(self):
        script = DeadlineDockerScript(self, self.identity, self.argv)
        result = self.run_mocked(script, lambda _value: None, deadline=10 ** 1000)
        self.assertFalse(result.sandbox.timed_out)
        starts = [timeout for command, timeout in script.timeouts if command == ("container", "start")]
        self.assertEqual(starts, [900.0])

    def test_popen_time_is_removed_from_collector_budget(self):
        now = [100.0]
        collector_timeouts = []
        process = SimpleNamespace(returncode=-9)
        box = sandbox.Sandbox.__new__(sandbox.Sandbox)
        box._session_root = Path("/tmp/mock-session")
        box._executor_trusted = True
        box.cancellation_requested = False

        def launch(_arguments, **_kwargs):
            now[0] = 106.0
            return process

        def collect(_process, _request, timeout):
            collector_timeouts.append(timeout)
            return b"", b"", "timeout"

        with mock.patch.object(box, "_preflight"):
            with mock.patch.object(sandbox.time, "monotonic", side_effect=lambda: now[0]):
                with mock.patch.object(sandbox.subprocess, "Popen", side_effect=launch):
                    with mock.patch.object(sandbox, "_collect", side_effect=collect):
                        with self.assertRaises(sandbox._DeadlineExpired):
                            box._command(
                                ["image", "inspect", "fixture"],
                                10.0,
                                _deadline=105.0,
                            )
        self.assertEqual(collector_timeouts, [0.0])

    def test_real_process_is_killed_and_reaped_when_deadline_expires(self):
        real_popen = subprocess.Popen
        launched = []
        with tempfile.TemporaryDirectory() as temporary:
            box = sandbox.Sandbox.__new__(sandbox.Sandbox)
            box._session_root = Path(temporary)
            box._executor_trusted = True
            box.cancellation_requested = False

            def launch(_arguments, **kwargs):
                child = real_popen([sys.executable, "-c", "import time; time.sleep(30)"], **kwargs)
                launched.append(child)
                return child

            try:
                with mock.patch.object(box, "_preflight"):
                    with mock.patch.object(sandbox.subprocess, "Popen", side_effect=launch):
                        with self.assertRaises(sandbox._DeadlineExpired):
                            box._command(
                                ["image", "inspect", "fixture"],
                                10.0,
                                _deadline=time.monotonic() + 0.05,
                            )
                self.assertEqual(len(launched), 1)
                self.assertIsNotNone(launched[0].poll())
                with self.assertRaises(ChildProcessError):
                    os.waitpid(launched[0].pid, os.WNOHANG)
            finally:
                for child in launched:
                    if child.poll() is None:
                        child.kill()
                    child.wait(timeout=2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
