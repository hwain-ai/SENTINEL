import importlib.util
import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from tests.test_oci_image import image_fixture
from sentinel.errors import SentinelError


def sandbox_module():
    spec = importlib.util.find_spec("sentinel.sandbox")
    if spec is None:
        raise AssertionError("sentinel.sandbox is not implemented")
    module = __import__("sentinel.sandbox", fromlist=["Sandbox"])
    if not hasattr(module, "Sandbox") or not hasattr(module, "SandboxResult"):
        raise AssertionError("Sandbox public types are not implemented")
    return module


class DockerScript:
    container_id = "c" * 64

    def __init__(
        self,
        case,
        identity,
        argv,
        mutation=None,
        create_failure=None,
        create_failure_stdout=b"",
        pull_failure=None,
        start_failure=None,
        rm_failure=None,
        ls_present=False,
        ls_output=None,
        terminal_status=None,
    ):
        self.case = case
        self.identity = identity
        self.target_argv = list(argv)
        self.mutation = mutation
        self.create_failure = create_failure
        self.create_failure_stdout = create_failure_stdout
        self.pull_failure = pull_failure
        self.start_failure = start_failure
        self.rm_failure = rm_failure
        self.ls_present = ls_present
        self.ls_output = ls_output
        self.terminal_status = terminal_status
        self.calls = []
        self.container_inspects = 0
        self.name = None
        self.nonce = None

    def popen(self, args, **kwargs):
        self.calls.append(list(args))
        self.case.assertIs(kwargs["shell"], False)
        self.case.assertEqual(kwargs["env"], {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"})
        self.case.assertIs(kwargs["start_new_session"], True)
        return SimpleNamespace(args=list(args), returncode=0)

    def collect(self, process, request, timeout):
        self.case.assertEqual(request, b"")
        command = process.args[5:]
        if command[:2] == ["image", "pull"]:
            return b"pulled", b"", self.pull_failure
        if command[:2] == ["image", "inspect"]:
            return self.image_inspect(), b"", None
        if command[:2] == ["container", "create"]:
            self.name = command[command.index("--name") + 1]
            self.nonce = command[command.index("--label") + 1].split("=", 1)[1]
            self.assert_create_contract(command)
            if self.create_failure == "interrupt":
                raise KeyboardInterrupt
            if self.create_failure:
                return self.create_failure_stdout, b"hidden daemon error", self.create_failure
            return self.create_failure_stdout or (self.container_id + "\n").encode(), b"", None
        if command[:2] == ["container", "inspect"]:
            self.container_inspects += 1
            target = command[-1]
            candidate = self.create_failure_stdout.decode("ascii", errors="ignore").strip()
            if candidate and target == candidate and candidate != self.container_id:
                return self.unrelated_container_inspect(candidate), b"", None
            status = "created" if self.container_inspects == 1 else (self.terminal_status or "exited")
            if self.create_failure:
                status = "created"
            return self.container_inspect(status), b"", None
        if command[:2] == ["container", "start"]:
            if self.start_failure == "interrupt":
                raise KeyboardInterrupt
            return b"hello", b"warning", self.start_failure
        if command[:2] == ["container", "rm"]:
            return b"", b"", self.rm_failure
        if command[:2] == ["container", "ls"]:
            stdout = self.ls_output
            if stdout is None:
                stdout = (self.container_id + "\n").encode() if self.ls_present else b""
            return stdout, b"", None
        raise AssertionError("unexpected Docker command: " + repr(command))

    def image_inspect(self):
        digest = self.identity.reference.split("@", 1)[1]
        value = {
            "Id": self.identity.image_id,
            "RepoDigests": ["ubuntu@" + digest],
            "Os": "linux",
            "Architecture": "amd64",
            "Config": {"Volumes": None},
        }
        if self.mutation and self.mutation[0] == "image":
            value[self.mutation[1]] = self.mutation[2]
        return json.dumps(value, separators=(",", ":")).encode()

    def container_inspect(self, status):
        value = {
            "Id": self.container_id,
            "Name": "/" + self.name,
            "Image": self.identity.image_id,
            "Path": "/usr/bin/env",
            "Args": ["-i", "--", "PATH=/usr/bin:/bin", "LANG=C.UTF-8", "LC_ALL=C.UTF-8", *self.target_argv],
            "Config": {
                "Image": self.identity.image_id,
                "Hostname": "sentinel-sandbox",
                "User": "65534:65534",
                "Env": ["PATH=/usr/bin:/bin", "LANG=C.UTF-8", "LC_ALL=C.UTF-8"],
                "Cmd": ["-i", "--", "PATH=/usr/bin:/bin", "LANG=C.UTF-8", "LC_ALL=C.UTF-8", *self.target_argv],
                "Entrypoint": ["/usr/bin/env"],
                "Labels": {"io.cognet9.sentinel.ownership": self.nonce},
                "WorkingDir": "/tmp",
                "Healthcheck": {"Test": ["NONE"]},
                "Volumes": None,
            },
            "HostConfig": {
                "NetworkMode": "none", "ReadonlyRootfs": True, "CapDrop": ["ALL"], "CapAdd": None,
                "SecurityOpt": ["no-new-privileges=true"], "CgroupnsMode": "private", "IpcMode": "none",
                "PidMode": "", "UTSMode": "", "Privileged": False, "Binds": None,
                "Devices": [], "DeviceRequests": None, "PortBindings": {}, "PublishAllPorts": False,
                "GroupAdd": None, "Links": None, "ExtraHosts": None, "VolumesFrom": None,
                "RestartPolicy": {"Name": "no", "MaximumRetryCount": 0},
                "LogConfig": {"Type": "none", "Config": {}},
                "NanoCpus": 500000000, "CpuPeriod": 0, "CpuQuota": 0, "Memory": 134217728,
                "MemorySwap": 134217728, "PidsLimit": 32,
                "Ulimits": [{"Name": "nofile", "Hard": 64, "Soft": 64}, {"Name": "core", "Hard": 0, "Soft": 0}],
                "OomKillDisable": False,
                "Tmpfs": {"/tmp": "rw,noexec,nosuid,nodev,size=33554432,mode=1777"},
            },
            "Mounts": [],
            "NetworkSettings": {"Ports": {}},
            "State": {
                "Status": status, "Running": status == "running", "Paused": False, "Restarting": False,
                "OOMKilled": False, "Dead": False, "ExitCode": 17 if status == "exited" else 0,
                "Pid": 123 if status == "running" else 0, "Error": "",
            },
        }
        if self.mutation and self.mutation[0] == "container":
            value["HostConfig"][self.mutation[1]] = self.mutation[2]
        if self.mutation and self.mutation[0] == "config":
            value["Config"][self.mutation[1]] = self.mutation[2]
        if self.mutation and self.mutation[0] == "delete-host":
            del value["HostConfig"][self.mutation[1]]
        if self.mutation and self.mutation[0] == "state":
            value["State"][self.mutation[1]] = self.mutation[2]
        if self.mutation and self.mutation[0] == "terminal-state" and self.container_inspects > 1:
            value["State"][self.mutation[1]] = self.mutation[2]
        if self.mutation and self.mutation[0] == "terminal-state-values" and self.container_inspects > 1:
            value["State"].update(self.mutation[1])
        if self.mutation and self.mutation[0] == "delete-terminal-state" and self.container_inspects > 1:
            del value["State"][self.mutation[1]]
        if self.mutation and self.mutation[0] == "delete-network":
            del value["NetworkSettings"][self.mutation[1]]
        if self.mutation and self.mutation[0] == "network":
            value["NetworkSettings"][self.mutation[1]] = self.mutation[2]
        return json.dumps(value, separators=(",", ":")).encode()

    def unrelated_container_inspect(self, candidate):
        value = json.loads(self.container_inspect("created"))
        value["Id"] = candidate
        value["Name"] = "/not-owned-by-sentinel"
        value["Config"]["Labels"]["io.cognet9.sentinel.ownership"] = "wrong-nonce"
        return json.dumps(value, separators=(",", ":")).encode()

    def assert_create_contract(self, command):
        required = {
            ("--pull", "never"), ("--network", "none"), ("--user", "65534:65534"),
            ("--hostname", "sentinel-sandbox"), ("--restart", "no"), ("--log-driver", "none"),
            ("--workdir", "/tmp"), ("--cpus", "0.5"), ("--memory", "134217728"),
            ("--memory-swap", "134217728"), ("--pids-limit", "32"),
            ("--cgroupns", "private"), ("--ipc", "none"), ("--entrypoint", "/usr/bin/env"),
        }
        self.case.assertTrue(required <= set(zip(command, command[1:])))
        self.case.assertIn("--read-only", command)
        self.case.assertIn("--no-healthcheck", command)
        self.case.assertEqual(command[-(6 + len(self.target_argv)) :], [
            self.identity.image_id, "-i", "--", "PATH=/usr/bin:/bin", "LANG=C.UTF-8", "LC_ALL=C.UTF-8", *self.target_argv
        ])


class SandboxContractTests(unittest.TestCase):
    def setUp(self):
        self.module = sandbox_module()
        self.reference, self.manifest, self.config = image_fixture()
        self.identity = __import__("sentinel.oci_image", fromlist=["verify_image"]).verify_image(
            self.reference, self.manifest, self.config
        )
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.lock = Path(self.temporary.name) / "lock.json"
        self.session = Path(self.temporary.name) / "session"
        lock_value = {"image": {"reference": self.reference, "os": "linux", "architecture": "amd64"}}
        patcher = mock.patch.object(self.module.oci, "_load_lock", return_value=lock_value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def make_sandbox(self):
        return self.module.Sandbox(self.lock, "a" * 64, self.session, "b" * 64, self.manifest, self.config)

    def run_script(self, script, operation="run"):
        with mock.patch.object(self.module.oci, "recheck_session"):
            with mock.patch.object(self.module.subprocess, "Popen", side_effect=script.popen):
                with mock.patch.object(self.module, "_collect", side_effect=script.collect):
                    instance = self.make_sandbox()
                    return instance.prepare_image() if operation == "prepare" else instance.run(script.target_argv)

    def test_sandbox_module_and_public_types_exist(self):
        self.assertTrue(hasattr(self.module, "Sandbox"))
        self.assertTrue(hasattr(self.module, "SandboxResult"))

    def test_invalid_argv_and_timeout_fail_before_docker_create(self):
        instance = self.make_sandbox()
        with self.assertRaises(SentinelError) as invalid_session:
            self.module.Sandbox(self.lock, "a" * 64, self.session, 1, self.manifest, self.config)
        self.assertEqual((invalid_session.exception.code, invalid_session.exception.exit_code), ("sandboxFailed", 6))
        invalid = [([], 1), (["relative"], 1), (["/bin/../sh"], 1), (["/bin/sh\x00"], 1), (["/bin/sh"], True), (["/bin/sh"], 61)]
        with mock.patch.object(self.module.subprocess, "Popen") as popen:
            for argv, timeout in invalid:
                with self.subTest(argv=argv, timeout=timeout):
                    with self.assertRaises(SentinelError) as caught:
                        instance.run(argv, timeout)
                    self.assertEqual((caught.exception.code, caught.exception.exit_code), ("sandboxFailed", 6))
            popen.assert_not_called()

    def test_cancellation_set_by_completed_recheck_stops_before_docker_child(self):
        instance = self.make_sandbox()

        def cancel_after_recheck(*_arguments):
            instance.cancellation_requested = True

        with mock.patch.object(self.module.oci, "recheck_session", side_effect=cancel_after_recheck):
            with mock.patch.object(
                self.module.subprocess, "Popen", side_effect=AssertionError("취소 뒤 실행 금지")
            ) as popen:
                with self.assertRaises(SentinelError) as caught:
                    instance.run(["/bin/true"])
        self.assertEqual((caught.exception.code, caught.exception.exit_code), ("sandboxCancelled", 8))
        popen.assert_not_called()

    def test_cancellation_during_inner_handler_install_stops_before_docker_child(self):
        for operation in ("prepare", "run"):
            with self.subTest(operation=operation):
                instance = self.make_sandbox()
                signal_calls = 0

                def signal_operation(_number, handler):
                    nonlocal signal_calls
                    signal_calls += 1
                    if signal_calls == 2:
                        handler(signal.SIGINT, None)
                    return signal.SIG_DFL

                with mock.patch.object(self.module.oci, "recheck_session"):
                    with mock.patch.object(
                        self.module.subprocess,
                        "Popen",
                        side_effect=OSError("must not launch after cancellation"),
                    ) as popen:
                        with mock.patch.object(self.module.signal, "signal", side_effect=signal_operation):
                            with self.assertRaises(SentinelError) as caught:
                                if operation == "prepare":
                                    instance.prepare_image()
                                else:
                                    instance.run(["/bin/true"])
                self.assertEqual((caught.exception.code, caught.exception.exit_code), ("sandboxCancelled", 8))
                self.assertTrue(instance.cancellation_requested)
                popen.assert_not_called()

    def test_prepare_checks_pull_and_exact_image_identity(self):
        script = DockerScript(self, self.identity, ["/bin/true"])
        self.assertEqual(self.run_script(script, "prepare"), self.identity)
        self.assertEqual(script.calls[0][5:], ["image", "pull", "--platform", "linux/amd64", self.reference])

    def test_prepare_rejects_wrong_repo_digest(self):
        script = DockerScript(self, self.identity, ["/bin/true"], mutation=("image", "RepoDigests", ["ubuntu@sha256:" + "0" * 64]))
        with self.assertRaises(SentinelError) as caught:
            self.run_script(script, "prepare")
        self.assertEqual((caught.exception.code, caught.exception.exit_code), ("ociImageFailed", 5))

    def test_prepare_cleanup_failure_is_sandbox_failure_and_sticky(self):
        script = DockerScript(self, self.identity, ["/bin/true"], pull_failure="cancelledCleanupError")
        instance = self.make_sandbox()
        with mock.patch.object(self.module.oci, "recheck_session"):
            with mock.patch.object(self.module.subprocess, "Popen", side_effect=script.popen):
                with mock.patch.object(self.module, "_collect", side_effect=script.collect):
                    with self.assertRaises(SentinelError) as caught:
                        instance.prepare_image()
                    self.assertEqual((caught.exception.code, caught.exception.exit_code), ("sandboxFailed", 6))
                    self.assertTrue(instance.cancellation_requested)
                    call_count = len(script.calls)
                    with self.assertRaises(SentinelError) as sticky:
                        instance.prepare_image()
                    self.assertEqual((sticky.exception.code, sticky.exception.exit_code), ("sandboxCancelled", 8))
                    self.assertEqual(len(script.calls), call_count)

    def test_prepare_preserves_sticky_cancel_when_postflight_also_fails(self):
        script = DockerScript(self, self.identity, ["/bin/true"], pull_failure="cancelledCleanupError")
        instance = self.make_sandbox()
        checks = [None, RuntimeError("postflight changed")]
        with mock.patch.object(self.module.oci, "recheck_session", side_effect=checks):
            with mock.patch.object(self.module.subprocess, "Popen", side_effect=script.popen):
                with mock.patch.object(self.module, "_collect", side_effect=script.collect):
                    with self.assertRaises(SentinelError) as caught:
                        instance.prepare_image()
        self.assertEqual((caught.exception.code, caught.exception.exit_code), ("sandboxFailed", 6))
        self.assertTrue(instance.cancellation_requested)

    def test_prepare_from_non_main_thread_is_sandbox_failure_without_launch(self):
        instance = self.make_sandbox()
        caught = []

        def prepare():
            try:
                instance.prepare_image()
            except SentinelError as error:
                caught.append(error)

        with mock.patch.object(self.module.subprocess, "Popen") as popen:
            worker = threading.Thread(target=prepare)
            worker.start()
            worker.join(timeout=2)
        self.assertFalse(worker.is_alive())
        self.assertEqual([(error.code, error.exit_code) for error in caught], [("sandboxFailed", 6)])
        popen.assert_not_called()

    def test_prepare_signal_handler_restore_failure_is_sandbox_failure(self):
        script = DockerScript(self, self.identity, ["/bin/true"])
        calls = 0

        def signal_operation(_number, _handler):
            nonlocal calls
            calls += 1
            if calls == 6:
                raise ValueError("restore rejected")
            return signal.SIG_DFL

        with mock.patch.object(self.module.oci, "recheck_session"):
            with mock.patch.object(self.module.subprocess, "Popen", side_effect=script.popen):
                with mock.patch.object(self.module, "_collect", side_effect=script.collect):
                    with mock.patch.object(self.module.signal, "signal", side_effect=signal_operation):
                        with self.assertRaises(SentinelError) as caught:
                            self.make_sandbox().prepare_image()
        self.assertEqual((caught.exception.code, caught.exception.exit_code), ("sandboxFailed", 6))

    def test_prepare_inner_signal_handler_restore_failure_is_sandbox_failure(self):
        script = DockerScript(self, self.identity, ["/bin/true"])
        signal_calls = 0
        collection_timeouts = []

        def signal_operation(_number, _handler):
            nonlocal signal_calls
            signal_calls += 1
            if signal_calls == 3:
                raise ValueError("inner restore rejected")
            return signal.SIG_DFL

        def collect(process, request, timeout):
            collection_timeouts.append(timeout)
            return script.collect(process, request, timeout)

        with mock.patch.object(self.module.oci, "recheck_session"):
            with mock.patch.object(self.module.subprocess, "Popen", side_effect=script.popen) as popen:
                with mock.patch.object(self.module, "_collect", side_effect=collect):
                    with mock.patch.object(self.module.signal, "signal", side_effect=signal_operation):
                        with self.assertRaises(SentinelError) as caught:
                            self.make_sandbox().prepare_image()
        self.assertEqual((caught.exception.code, caught.exception.exit_code), ("sandboxFailed", 6))
        self.assertEqual(popen.call_count, 1)
        self.assertEqual(collection_timeouts, [0.0])
        self.assertEqual(signal_calls, 4)

    def test_run_accepts_nonzero_container_exit_and_removes_exact_id(self):
        script = DockerScript(self, self.identity, ["/bin/false"])
        result = self.run_script(script)
        self.assertEqual(result.exit_code, 17)
        self.assertEqual((result.timed_out, result.oom_killed, result.removed), (False, False, True))
        self.assertEqual((result.stdout_bytes, result.stderr_bytes), (5, 7))
        self.assertEqual([call[-1] for call in script.calls if call[5:7] == ["container", "rm"]], [script.container_id])

    def test_runtime_environment_order_is_semantic_but_extra_values_are_rejected(self):
        reordered = DockerScript(
            self,
            self.identity,
            ["/bin/true"],
            mutation=("config", "Env", ["LC_ALL=C.UTF-8", "PATH=/usr/bin:/bin", "LANG=C.UTF-8"]),
        )
        self.assertEqual(self.run_script(reordered).exit_code, 17)

        extra = DockerScript(
            self,
            self.identity,
            ["/bin/true"],
            mutation=("config", "Env", ["PATH=/usr/bin:/bin", "LANG=C.UTF-8", "LC_ALL=C.UTF-8", "HOME=/root"]),
        )
        with self.assertRaises(SentinelError):
            self.run_script(extra)
        self.assertEqual([call for call in extra.calls if call[5:7] == ["container", "start"]], [])

    def test_security_mutation_prevents_start_and_still_removes(self):
        script = DockerScript(self, self.identity, ["/bin/true"], mutation=("container", "Privileged", True))
        with self.assertRaises(SentinelError):
            self.run_script(script)
        self.assertEqual([call for call in script.calls if call[5:7] == ["container", "start"]], [])
        self.assertEqual([call[-1] for call in script.calls if call[5:7] == ["container", "rm"]], [script.container_id])

    def test_missing_or_noncanonical_security_fields_prevent_start(self):
        mutations = [
            ("delete-host", "Devices", None),
            ("delete-host", "CapAdd", None),
            ("delete-network", "Ports", None),
            ("network", "Ports", None),
            ("container", "SecurityOpt", ["no-new-privileges"]),
            ("container", "Ulimits", [
                {"Name": "nofile", "Hard": 64, "Soft": 64},
                {"Name": "core", "Hard": 0, "Soft": 0},
                "ignored-extra",
            ]),
            ("state", "OOMKilled", True),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                script = DockerScript(self, self.identity, ["/bin/true"], mutation=mutation)
                with self.assertRaises(SentinelError):
                    self.run_script(script)
                self.assertEqual([call for call in script.calls if call[5:7] == ["container", "start"]], [])

    def test_boolean_and_integer_type_confusion_prevents_start_and_removes(self):
        mutations = [
            ("container", "ReadonlyRootfs", 1),
            ("container", "CpuPeriod", False),
            ("container", "CpuQuota", False),
            ("container", "RestartPolicy", {"Name": "no", "MaximumRetryCount": False}),
            ("container", "Ulimits", [
                {"Name": "nofile", "Hard": 64, "Soft": 64},
                {"Name": "core", "Hard": False, "Soft": False},
            ]),
            ("state", "Pid", False),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                script = DockerScript(self, self.identity, ["/bin/true"], mutation=mutation)
                with self.assertRaises(SentinelError) as caught:
                    self.run_script(script)
                self.assertEqual((caught.exception.code, caught.exception.exit_code), ("sandboxFailed", 6))
                self.assertEqual([call for call in script.calls if call[5:7] == ["container", "start"]], [])
                self.assertEqual(
                    [call[-1] for call in script.calls if call[5:7] == ["container", "rm"]],
                    [script.container_id],
                )

    def test_failed_create_stdout_is_untrusted_until_ownership_is_verified(self):
        unrelated_id = "d" * 64
        for failure in ("outputOverflow", "processIoError", "timeout"):
            with self.subTest(failure=failure):
                script = DockerScript(
                    self,
                    self.identity,
                    ["/bin/true"],
                    create_failure=failure,
                    create_failure_stdout=(unrelated_id + "\n").encode(),
                )
                with self.assertRaises(SentinelError) as caught:
                    self.run_script(script)
                self.assertEqual((caught.exception.code, caught.exception.exit_code), ("sandboxFailed", 6))
                removals = [call[-1] for call in script.calls if call[5:7] == ["container", "rm"]]
                self.assertNotIn(unrelated_id, removals)
                self.assertEqual(removals, [script.container_id])
                unrelated_inspect = next(
                    index for index, call in enumerate(script.calls)
                    if call[5:7] == ["container", "inspect"] and call[-1] == unrelated_id
                )
                removal = next(index for index, call in enumerate(script.calls) if call[5:7] == ["container", "rm"])
                self.assertLess(unrelated_inspect, removal)

    def test_failed_create_owned_stdout_is_inspected_before_exact_removal(self):
        script = DockerScript(
            self,
            self.identity,
            ["/bin/true"],
            create_failure="processIoError",
            create_failure_stdout=(DockerScript.container_id + "\n").encode(),
        )
        with self.assertRaises(SentinelError):
            self.run_script(script)
        inspect = next(index for index, call in enumerate(script.calls) if call[5:7] == ["container", "inspect"])
        removal = next(index for index, call in enumerate(script.calls) if call[5:7] == ["container", "rm"])
        self.assertLess(inspect, removal)
        self.assertEqual(script.calls[removal][-1], script.container_id)

    def test_successful_create_stdout_is_also_untrusted_until_ownership_is_verified(self):
        unrelated_id = "d" * 64
        script = DockerScript(
            self,
            self.identity,
            ["/bin/true"],
            create_failure_stdout=(unrelated_id + "\n").encode(),
        )
        with self.assertRaises(SentinelError) as caught:
            self.run_script(script)
        self.assertEqual((caught.exception.code, caught.exception.exit_code), ("sandboxFailed", 6))
        removals = [call[-1] for call in script.calls if call[5:7] == ["container", "rm"]]
        self.assertNotIn(unrelated_id, removals)
        self.assertEqual(removals, [script.container_id])

    def test_create_postflight_failure_never_removes_unverified_stdout_id(self):
        unrelated_id = "d" * 64
        script = DockerScript(
            self,
            self.identity,
            ["/bin/true"],
            create_failure_stdout=(unrelated_id + "\n").encode(),
        )
        checks = [None, None, None, RuntimeError("executor changed")]
        instance = self.make_sandbox()
        with mock.patch.object(self.module.oci, "recheck_session", side_effect=checks):
            with mock.patch.object(self.module.subprocess, "Popen", side_effect=script.popen):
                with mock.patch.object(self.module, "_collect", side_effect=script.collect):
                    with self.assertRaises(SentinelError) as caught:
                        instance.run(script.target_argv)
        self.assertEqual((caught.exception.code, caught.exception.exit_code), ("sandboxFailed", 6))
        self.assertNotIn(
            unrelated_id,
            [call[-1] for call in script.calls if call[5:7] == ["container", "rm"]],
        )

    def test_lost_create_response_recovers_owned_name_then_removes_id(self):
        script = DockerScript(self, self.identity, ["/bin/true"], create_failure="processIoError")
        with self.assertRaises(SentinelError):
            self.run_script(script)
        self.assertEqual([call[-1] for call in script.calls if call[5:7] == ["container", "rm"]], [script.container_id])

    def test_cancel_during_create_recovers_owned_name_then_removes_id(self):
        script = DockerScript(self, self.identity, ["/bin/true"], create_failure="interrupt")
        with self.assertRaises(SentinelError) as caught:
            self.run_script(script)
        self.assertEqual((caught.exception.code, caught.exception.exit_code), ("sandboxCancelled", 8))
        self.assertEqual([call[-1] for call in script.calls if call[5:7] == ["container", "rm"]], [script.container_id])

    def test_cancel_between_docker_calls_is_classified_and_removes_owned_id(self):
        script = DockerScript(self, self.identity, ["/bin/true"])
        instance = self.make_sandbox()
        with mock.patch.object(self.module.oci, "recheck_session"):
            with mock.patch.object(self.module.subprocess, "Popen", side_effect=script.popen):
                with mock.patch.object(self.module, "_collect", side_effect=script.collect):
                    with mock.patch.object(self.module, "_verify_created_container", side_effect=KeyboardInterrupt):
                        with self.assertRaises(SentinelError) as caught:
                            instance.run(script.target_argv)
        self.assertEqual((caught.exception.code, caught.exception.exit_code), ("sandboxCancelled", 8))
        self.assertTrue(instance.cancellation_requested)
        self.assertEqual([call[-1] for call in script.calls if call[5:7] == ["container", "rm"]], [script.container_id])

    def test_cancel_during_create_launch_recovers_by_owned_name_and_nonce(self):
        script = DockerScript(self, self.identity, ["/bin/true"])
        instance = self.make_sandbox()

        def interrupt_create(args, **kwargs):
            if args[5:7] == ["container", "create"]:
                script.calls.append(list(args))
                command = args[5:]
                script.name = command[command.index("--name") + 1]
                script.nonce = command[command.index("--label") + 1].split("=", 1)[1]
                instance.cancellation_requested = True
                raise KeyboardInterrupt
            return script.popen(args, **kwargs)

        with mock.patch.object(self.module.oci, "recheck_session"):
            with mock.patch.object(self.module.subprocess, "Popen", side_effect=interrupt_create):
                with mock.patch.object(self.module, "_collect", side_effect=script.collect):
                    with self.assertRaises(SentinelError) as caught:
                        instance.run(script.target_argv)
        self.assertEqual((caught.exception.code, caught.exception.exit_code), ("sandboxCancelled", 8))
        self.assertEqual([call[-1] for call in script.calls if call[5:7] == ["container", "rm"]], [script.container_id])

    def test_sigint_during_real_popen_handoff_kills_and_reaps_child(self):
        instance = self.make_sandbox()
        self.session.mkdir()
        marker = Path(self.temporary.name) / "late-side-effect"
        launched = []
        timers = []
        recovery_observations = []
        real_popen = subprocess.Popen
        original_handler = signal.getsignal(signal.SIGINT)

        def delayed_popen(_arguments, **kwargs):
            child = real_popen(
                [
                    sys.executable,
                    "-c",
                    "import pathlib,time;time.sleep(0.6);pathlib.Path(%r).write_text('late')" % str(marker),
                ],
                **kwargs,
            )
            launched.append(child)
            timer = threading.Timer(0.05, lambda: os.kill(os.getpid(), signal.SIGINT))
            timers.append(timer)
            timer.start()
            time.sleep(0.2)
            return child

        def recover_after_child(*_arguments, **_kwargs):
            recovery_observations.append((launched[0].poll(), marker.exists()))
            return None

        try:
            with mock.patch.object(self.module.oci, "recheck_session"):
                with mock.patch.object(self.module.subprocess, "Popen", side_effect=delayed_popen):
                    with mock.patch.object(instance, "_image_inspect"):
                        with mock.patch.object(instance, "_recover", side_effect=recover_after_child):
                            with self.assertRaises(SentinelError) as caught:
                                instance.run(["/bin/true"])
            self.assertEqual((caught.exception.code, caught.exception.exit_code), ("sandboxCancelled", 8))
            self.assertTrue(instance.cancellation_requested)
            time.sleep(0.7)
            self.assertFalse(marker.exists())
            self.assertEqual(len(launched), 1)
            self.assertIsNotNone(launched[0].poll())
            self.assertEqual(len(recovery_observations), 1)
            self.assertIsNotNone(recovery_observations[0][0])
            self.assertFalse(recovery_observations[0][1])
            with self.assertRaises(ChildProcessError):
                os.waitpid(launched[0].pid, os.WNOHANG)
            self.assertIs(signal.getsignal(signal.SIGINT), original_handler)
        finally:
            for timer in timers:
                timer.join(timeout=1)
            for child in launched:
                if child.poll() is None:
                    child.kill()
                child.wait(timeout=2)

    def test_timeout_is_observation_only_after_successful_removal(self):
        script = DockerScript(self, self.identity, ["/bin/sleep", "10"], start_failure="timeout")
        result = self.run_script(script)
        self.assertTrue(result.timed_out)
        self.assertIsNone(result.exit_code)
        self.assertTrue(result.removed)

    def test_attached_output_is_recorded_before_timeout_and_collection_failure(self):
        class RecordingSandbox(self.module.Sandbox):
            def __init__(self, *arguments):
                super().__init__(*arguments)
                self.attached = []

            def _record_attached_output(self, container_id, result):
                self.attached.append((container_id, result))

        for failure, expected_error in (
            ("timeout", self.module._DeadlineExpired),
            ("processIoError", self.module._CommandFailure),
        ):
            with self.subTest(failure=failure):
                script = DockerScript(self, self.identity, ["/bin/true"], start_failure=failure)
                instance = RecordingSandbox(
                    self.lock, "a" * 64, self.session, "b" * 64, self.manifest, self.config
                )
                options = {"_deadline": time.monotonic() + 1.0} if failure == "timeout" else {}
                with mock.patch.object(self.module.oci, "recheck_session"):
                    with mock.patch.object(self.module.subprocess, "Popen", side_effect=script.popen):
                        with mock.patch.object(self.module, "_collect", side_effect=script.collect):
                            with self.assertRaises(expected_error):
                                instance._command(
                                    ["container", "start", "--attach", script.container_id],
                                    10.0,
                                    allow_nonzero=True,
                                    **options,
                                )
                self.assertEqual(len(instance.attached), 1)
                container_id, result = instance.attached[0]
                self.assertEqual(container_id, script.container_id)
                self.assertEqual((result.stdout, result.stderr, result.collection_failure),
                                 (b"hello", b"warning", failure))

    def test_attached_output_is_recorded_before_cancellation_conversion(self):
        class RecordingSandbox(self.module.Sandbox):
            def __init__(self, *arguments):
                super().__init__(*arguments)
                self.attached = []

            def _record_attached_output(self, container_id, result):
                self.attached.append((container_id, result))

        script = DockerScript(self, self.identity, ["/bin/true"])
        process = script.popen([
            str(self.module.oci.DOCKER_PATH), "--config", str(self.session / "docker-config"),
            "--host", self.module.oci.DOCKER_HOST, "container", "start", "--attach", script.container_id,
        ], shell=False, start_new_session=True, cwd=str(self.session), env=self.module.DOCKER_ENV)
        stream = SimpleNamespace(closed=False)
        process.stdin = stream
        process.stdout = stream
        process.stderr = stream
        collections = iter((KeyboardInterrupt(), (b"partial", b"cancelled", None)))

        def collect(*_arguments):
            value = next(collections)
            if isinstance(value, BaseException):
                raise value
            return value

        instance = RecordingSandbox(
            self.lock, "a" * 64, self.session, "b" * 64, self.manifest, self.config
        )
        with mock.patch.object(self.module.oci, "recheck_session"):
            with mock.patch.object(self.module.subprocess, "Popen", return_value=process):
                with mock.patch.object(self.module, "_collect", side_effect=collect):
                    with self.assertRaises(self.module._Interrupted):
                        instance._command(
                            ["container", "start", "--attach", script.container_id],
                            10.0,
                            allow_nonzero=True,
                        )
        self.assertEqual(len(instance.attached), 1)
        self.assertEqual((instance.attached[0][1].stdout, instance.attached[0][1].stderr),
                         (b"partial", b"cancelled"))

    def test_attached_output_is_recorded_before_postflight_failure(self):
        class RecordingSandbox(self.module.Sandbox):
            def _record_attached_output(self, container_id, result):
                self.attached = (container_id, result)

        script = DockerScript(self, self.identity, ["/bin/true"])
        instance = RecordingSandbox(
            self.lock, "a" * 64, self.session, "b" * 64, self.manifest, self.config
        )
        with mock.patch.object(self.module.oci, "recheck_session", side_effect=[None, ValueError()]):
            with mock.patch.object(self.module.subprocess, "Popen", side_effect=script.popen):
                with mock.patch.object(self.module, "_collect", side_effect=script.collect):
                    with self.assertRaises(self.module._CommandFailure) as caught:
                        instance._command(
                            ["container", "start", "--attach", script.container_id], 10.0
                        )
        self.assertTrue(caught.exception.infrastructure)
        container_id, result = instance.attached
        self.assertEqual(container_id, script.container_id)
        self.assertEqual((result.stdout, result.stderr), (b"hello", b"warning"))
        self.assertIsNone(result.collection_failure)

    def test_control_and_cleanup_output_is_not_recorded(self):
        class RecordingSandbox(self.module.Sandbox):
            def __init__(self, *arguments):
                super().__init__(*arguments)
                self.attached = []

            def _record_attached_output(self, container_id, result):
                self.attached.append((container_id, result))

        script = DockerScript(self, self.identity, ["/bin/true"])
        instance = RecordingSandbox(
            self.lock, "a" * 64, self.session, "b" * 64, self.manifest, self.config
        )
        with mock.patch.object(self.module.oci, "recheck_session"):
            with mock.patch.object(self.module.subprocess, "Popen", side_effect=script.popen):
                with mock.patch.object(self.module, "_collect", side_effect=script.collect):
                    instance._command(
                        ["container", "ls", "--all", "--no-trunc", "--format", "{{.ID}}"],
                        10.0,
                    )
                    instance._command(
                        ["container", "rm", "--force", "--volumes", script.container_id],
                        10.0,
                        cleanup=True,
                    )
        self.assertEqual(instance.attached, [])

    def test_inconsistent_terminal_state_is_rejected_and_removed(self):
        mutations = [
            ("terminal-state", "Paused", True),
            ("terminal-state", "Pid", 42),
            ("terminal-state", "Error", "daemon-start-failed"),
            ("delete-terminal-state", "Pid", None),
            ("delete-terminal-state", "Error", None),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                script = DockerScript(self, self.identity, ["/bin/true"], mutation=mutation)
                with self.assertRaises(SentinelError):
                    self.run_script(script)
                self.assertEqual(
                    [call[-1] for call in script.calls if call[5:7] == ["container", "rm"]],
                    [script.container_id],
                )

    def test_timeout_accepts_only_closed_created_or_running_state_shapes(self):
        for status in ("created", "running"):
            with self.subTest(status=status):
                script = DockerScript(
                    self,
                    self.identity,
                    ["/bin/sleep", "10"],
                    start_failure="timeout",
                    terminal_status=status,
                )
                result = self.run_script(script)
                self.assertTrue(result.timed_out)
                self.assertIsNone(result.exit_code)

        rejected = [
            ("running", ("terminal-state", "Pid", 0)),
            ("running", ("terminal-state", "ExitCode", 9)),
            ("running", ("terminal-state", "OOMKilled", True)),
            ("created", ("terminal-state", "Pid", 7)),
            ("created", ("terminal-state", "ExitCode", 9)),
            ("created", ("terminal-state", "OOMKilled", True)),
        ]
        for status, mutation in rejected:
            with self.subTest(status=status, mutation=mutation):
                script = DockerScript(
                    self,
                    self.identity,
                    ["/bin/sleep", "10"],
                    mutation=mutation,
                    start_failure="timeout",
                    terminal_status=status,
                )
                with self.assertRaises(SentinelError):
                    self.run_script(script)

    def test_exited_oom_state_remains_valid_observation(self):
        script = DockerScript(
            self,
            self.identity,
            ["/bin/true"],
            mutation=("terminal-state-values", {"ExitCode": 137, "OOMKilled": True}),
        )
        result = self.run_script(script)
        self.assertEqual(result.exit_code, 137)
        self.assertTrue(result.oom_killed)

    def test_output_overflow_and_absence_proof_fail_closed(self):
        overflow = DockerScript(self, self.identity, ["/bin/true"], start_failure="outputOverflow")
        with self.assertRaises(SentinelError) as overflow_error:
            self.run_script(overflow)
        self.assertEqual((overflow_error.exception.code, overflow_error.exception.exit_code), ("sandboxFailed", 6))
        self.assertEqual(
            [call[-1] for call in overflow.calls if call[5:7] == ["container", "rm"]],
            [overflow.container_id],
        )

        still_present = DockerScript(self, self.identity, ["/bin/true"], ls_present=True)
        with self.assertRaises(SentinelError) as absence_error:
            self.run_script(still_present)
        self.assertEqual((absence_error.exception.code, absence_error.exception.exit_code), ("sandboxFailed", 6))

        removal_failed = DockerScript(self, self.identity, ["/bin/true"], rm_failure="processCleanupError")
        with self.assertRaises(SentinelError) as removal_error:
            self.run_script(removal_failed)
        self.assertEqual((removal_error.exception.code, removal_error.exception.exit_code), ("sandboxFailed", 6))

        whitespace = DockerScript(self, self.identity, ["/bin/true"], ls_output=b" \n")
        with self.assertRaises(SentinelError) as whitespace_error:
            self.run_script(whitespace)
        self.assertEqual((whitespace_error.exception.code, whitespace_error.exception.exit_code), ("sandboxFailed", 6))

        recovered = DockerScript(self, self.identity, ["/bin/true"])
        self.assertEqual(self.run_script(recovered).exit_code, 17)

    def test_cancelled_cleanup_failure_is_sticky_sandbox_failure(self):
        script = DockerScript(self, self.identity, ["/bin/sleep", "10"], start_failure="interrupt", rm_failure="processCleanupError")
        instance = self.make_sandbox()
        with mock.patch.object(self.module.oci, "recheck_session"):
            with mock.patch.object(self.module.subprocess, "Popen", side_effect=script.popen):
                with mock.patch.object(self.module, "_collect", side_effect=script.collect):
                    with self.assertRaises(SentinelError) as caught:
                        instance.run(script.target_argv)
                    self.assertEqual((caught.exception.code, caught.exception.exit_code), ("sandboxFailed", 6))
                    self.assertTrue(instance.cancellation_requested)
                    count = len(script.calls)
                    with self.assertRaises(SentinelError) as sticky:
                        instance.run(["/bin/true"])
                    self.assertEqual(sticky.exception.code, "sandboxCancelled")
                    self.assertEqual(len(script.calls), count)

    def test_repeated_cancel_during_cleanup_is_sticky_sandbox_failure(self):
        script = DockerScript(self, self.identity, ["/bin/true"])
        instance = self.make_sandbox()

        def interrupt_removal(args, **kwargs):
            if args[5:7] == ["container", "rm"]:
                script.calls.append(list(args))
                instance.cancellation_requested = True
                raise KeyboardInterrupt
            return script.popen(args, **kwargs)

        with mock.patch.object(self.module.oci, "recheck_session"):
            with mock.patch.object(self.module.subprocess, "Popen", side_effect=interrupt_removal):
                with mock.patch.object(self.module, "_collect", side_effect=script.collect):
                    with self.assertRaises(SentinelError) as caught:
                        instance.run(script.target_argv)
        self.assertEqual((caught.exception.code, caught.exception.exit_code), ("sandboxFailed", 6))
        self.assertTrue(instance.cancellation_requested)


if __name__ == "__main__":
    unittest.main()
