import contextlib
import hashlib
import io
import json
import os
import select
import signal
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from sentinel import bundle as bundle_module
from sentinel import cli as cli_module
from sentinel import protocol
from sentinel.errors import SentinelError
from tests.test_cli import cli, install_bundle, make_bundle, module, workspace, write_json


class InstallReviewTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def test_parent_traversal_is_rejected_before_any_external_write(self):
        source, digest, _ = make_bundle(self.base)
        outside = self.base / "outside"
        outside.mkdir()
        (self.base / "linked").symlink_to(outside, target_is_directory=True)
        tools = self.base / "missing" / ".." / "linked"
        completed = install_bundle(source, digest, tools)
        self.assertEqual(completed.returncode, 3)
        self.assertEqual(list(outside.iterdir()), [])

    def test_every_new_install_directory_is_private(self):
        source, digest, _ = make_bundle(self.base)
        tools = self.base / "tools"
        previous = os.umask(0o002)
        try:
            completed = install_bundle(source, digest, tools)
        finally:
            os.umask(previous)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        destination = tools / "python" / "1.2.3" / digest
        for path in (tools, tools / "python", tools / "python" / "1.2.3", destination, destination / "bin"):
            with self.subTest(path=path.name):
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700)

    def test_existing_user_directory_mode_is_not_changed(self):
        source, digest, _ = make_bundle(self.base)
        tools = self.base / "tools"
        tools.mkdir(mode=0o755)
        self.assertEqual(install_bundle(source, digest, tools).returncode, 0)
        self.assertEqual(stat.S_IMODE(tools.stat().st_mode), 0o755)
        self.assertEqual(stat.S_IMODE((tools / "python").stat().st_mode), 0o700)

    def test_concurrent_private_directory_creation_is_adopted(self):
        target = self.base / "concurrent"
        real_mkdir = bundle_module.os.mkdir
        injected = False

        def concurrent_mkdir(path, mode):
            nonlocal injected
            if Path(path) == target and not injected:
                injected = True
                real_mkdir(path, 0o700)
                raise FileExistsError()
            return real_mkdir(path, mode)

        with mock.patch.object(bundle_module.os, "mkdir", side_effect=concurrent_mkdir):
            bundle_module._make_private_directories(target)
        self.assertTrue(target.is_dir())
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o700)

    def test_doctor_rejects_relaxed_nested_directory_mode(self):
        source, digest, _ = make_bundle(self.base)
        tools = self.base / "tools"
        self.assertEqual(install_bundle(source, digest, tools).returncode, 0)
        (tools / "python" / "1.2.3" / digest / "bin").chmod(0o755)
        project = self.base / "project"
        project.mkdir()
        (project / "one").mkdir()
        workspace(project, [module("one", "python", "one", digest=digest)])
        completed = cli("doctor", "--project", str(project), "--tools", str(tools), "--format", "json")
        self.assertEqual(completed.returncode, 5)

    def test_atomic_publish_preserves_empty_collision(self):
        source, digest, _ = make_bundle(self.base)
        tools = self.base / "tools"
        destination = tools / "python" / "1.2.3" / digest
        real_publish = bundle_module._publish_noreplace
        collision = {}

        def collide(staged, target):
            target.mkdir(mode=0o700)
            collision["inode"] = target.stat().st_ino
            return real_publish(staged, target)

        with mock.patch.object(bundle_module, "_publish_noreplace", side_effect=collide):
            with self.assertRaises(SentinelError):
                bundle_module.install_bundle(source, digest, tools)
        self.assertEqual(destination.stat().st_ino, collision["inode"])
        self.assertEqual(list(destination.iterdir()), [])

    def test_atomic_publish_adopts_identical_collision(self):
        source, digest, _ = make_bundle(self.base)
        tools = self.base / "tools"
        real_publish = bundle_module._publish_noreplace

        def collide(staged, target):
            import shutil
            shutil.copytree(staged, target)
            return real_publish(staged, target)

        with mock.patch.object(bundle_module, "_publish_noreplace", side_effect=collide):
            installed = bundle_module.install_bundle(source, digest, tools)
        self.assertEqual(installed.digest, digest)

    def test_atomic_publish_unavailable_has_no_rename_fallback(self):
        class MissingRenameat2:
            pass

        with mock.patch.object(bundle_module.ctypes, "CDLL", return_value=MissingRenameat2()):
            with mock.patch.object(bundle_module.os, "rename") as fallback:
                with self.assertRaises(SentinelError):
                    bundle_module._publish_noreplace(self.base / "staged", self.base / "destination")
        fallback.assert_not_called()

    def test_nested_symlink_is_rejected_before_external_file_read(self):
        source = self.base / "source"
        source.mkdir()
        outside = self.base / "outside"
        outside.mkdir()
        canary = b"local-canary-only"
        (outside / "canary").write_bytes(canary)
        (source / "linked").symlink_to(outside, target_is_directory=True)
        manifest = {
            "schemaVersion": "sentinel-tool-bundle-v1",
            "protocolVersion": "sentinel-tool-protocol-v1",
            "language": "python",
            "version": "1.2.3",
            "entrypoint": "linked/canary",
            "files": {"linked/canary": hashlib.sha256(canary).hexdigest()},
        }
        write_json(source / "sentinel-tool.json", manifest)
        digest = hashlib.sha256((source / "sentinel-tool.json").read_bytes()).hexdigest()
        real_read = bundle_module._read_regular_file
        external_bytes = []

        def tracked(path, label):
            result = real_read(path, label)
            if path == source / "linked" / "canary":
                external_bytes.append(result[1])
            return result

        with mock.patch.object(bundle_module, "_read_regular_file", side_effect=tracked):
            with self.assertRaises(SentinelError):
                bundle_module.validate_bundle(source, digest)
        self.assertEqual(sum(external_bytes), 0)

    def test_total_size_is_rejected_before_large_file_hashing(self):
        source = self.base / "large"
        source.mkdir()
        records = {}
        zero_digest = hashlib.sha256(bytes(16 * 1024 * 1024)).hexdigest()
        for index in range(5):
            path = source / f"sparse-{index}"
            with path.open("wb") as stream:
                stream.truncate(16 * 1024 * 1024)
            records[path.name] = zero_digest
        manifest = {
            "schemaVersion": "sentinel-tool-bundle-v1",
            "protocolVersion": "sentinel-tool-protocol-v1",
            "language": "python",
            "version": "1.2.3",
            "entrypoint": "sparse-0",
            "files": records,
        }
        write_json(source / "sentinel-tool.json", manifest)
        digest = hashlib.sha256((source / "sentinel-tool.json").read_bytes()).hexdigest()
        real_read = bundle_module._read_regular_file
        bytes_read = []

        def tracked(path, label):
            result = real_read(path, label)
            bytes_read.append(result[1])
            return result

        with mock.patch.object(bundle_module, "_read_regular_file", side_effect=tracked):
            with self.assertRaises(SentinelError):
                bundle_module.validate_bundle(source, digest)
        self.assertLess(sum(bytes_read), 1024 * 1024)

    def test_inventory_size_must_match_bytes_read(self):
        source, digest, _ = make_bundle(self.base)
        entrypoint = source / "bin" / "sentinel-tool"
        real_read = bundle_module._read_regular_file

        def mismatched_size(path, label):
            file_digest, size, data = real_read(path, label)
            if path == entrypoint:
                size += 1
            return file_digest, size, data

        with mock.patch.object(bundle_module, "_read_regular_file", side_effect=mismatched_size):
            with self.assertRaises(SentinelError):
                bundle_module.validate_bundle(source, digest)

    def test_source_growth_after_validation_is_rejected_before_copy(self):
        source = self.base / "changing"
        source.mkdir()
        records = {}
        for index in range(5):
            name = f"file-{index}"
            (source / name).write_bytes(b"x")
            records[name] = hashlib.sha256(b"x").hexdigest()
        manifest = {
            "schemaVersion": "sentinel-tool-bundle-v1",
            "protocolVersion": "sentinel-tool-protocol-v1",
            "language": "python",
            "version": "1.2.3",
            "entrypoint": "file-0",
            "files": records,
        }
        write_json(source / "sentinel-tool.json", manifest)
        digest = hashlib.sha256((source / "sentinel-tool.json").read_bytes()).hexdigest()
        real_validate = bundle_module.validate_bundle
        real_write = bundle_module._write_restricted
        changed = False
        copied = []

        def grow_after_validation(path, expected_digest):
            nonlocal changed
            result = real_validate(path, expected_digest)
            if path == source and not changed:
                changed = True
                for name in records:
                    with (source / name).open("wb") as stream:
                        stream.truncate(16 * 1024 * 1024)
            return result

        def track_copy(path, data, mode):
            copied.append(len(data))
            real_write(path, data, mode)

        with mock.patch.object(bundle_module, "validate_bundle", side_effect=grow_after_validation):
            with mock.patch.object(bundle_module, "_write_restricted", side_effect=track_copy):
                with self.assertRaises(SentinelError):
                    bundle_module.install_bundle(source, digest, self.base / "tools")
        self.assertEqual(sum(copied), 0)

    def test_deep_bundle_tree_returns_fixed_error_without_traceback(self):
        source = self.base / "deep"
        source.mkdir()
        directories = []
        current = source
        entrypoint = None
        try:
            # macOS PATH_MAX cannot represent 1050 levels; still exceed the bundle limit.
            depth = 1050 if sys.platform == "linux" else bundle_module.MAX_PATH_DEPTH + 1
            for _ in range(depth):
                current = current / "d"
                current.mkdir()
                directories.append(current)
            entrypoint = current / "run"
            content = b"#!/bin/sh\nexit 0\n"
            entrypoint.write_bytes(content)
            relative = entrypoint.relative_to(source).as_posix()
            manifest = {
                "schemaVersion": "sentinel-tool-bundle-v1",
                "protocolVersion": "sentinel-tool-protocol-v1",
                "language": "python",
                "version": "1.2.3",
                "entrypoint": relative,
                "files": {relative: hashlib.sha256(content).hexdigest()},
            }
            write_json(source / "sentinel-tool.json", manifest)
            digest = hashlib.sha256((source / "sentinel-tool.json").read_bytes()).hexdigest()
            completed = install_bundle(source, digest, self.base / "tools")
            self.assertEqual(completed.returncode, 3)
            self.assertNotIn("Traceback", completed.stderr)
        finally:
            if entrypoint and entrypoint.exists():
                entrypoint.unlink()
            manifest_path = source / "sentinel-tool.json"
            if manifest_path.exists():
                manifest_path.unlink()
            for directory in reversed(directories):
                directory.rmdir()


class InputReviewTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.project = Path(self.temporary.name) / "project"
        self.project.mkdir()
        (self.project / "one").mkdir()

    def tearDown(self):
        self.temporary.cleanup()

    def test_surrogate_path_and_huge_integer_are_fixed_usage_errors(self):
        digest = "a" * 64
        payload = {"schemaVersion": "sentinel-workspace-v1", "modules": [module("one", "python", "\ud800", digest=digest)]}
        write_json(self.project / "sentinel.workspace.json", payload)
        first = cli("plan", "--project", str(self.project))
        (self.project / "sentinel.workspace.json").write_text(
            '{"schemaVersion":"sentinel-workspace-v1","modules":' + "1" * 5000 + "}", encoding="utf-8"
        )
        second = cli("plan", "--project", str(self.project))
        for completed in (first, second):
            self.assertEqual(completed.returncode, 3)
            self.assertNotIn("Traceback", completed.stderr)
            self.assertNotIn("/src/sentinel", completed.stderr)

    def test_global_keyboard_interrupt_is_fixed_exit_8(self):
        stderr = io.StringIO()
        with mock.patch.object(cli_module, "install_bundle", side_effect=KeyboardInterrupt):
            with contextlib.redirect_stderr(stderr):
                code = cli_module.main(["install", "--bundle", "x", "--sha256", "a" * 64, "--tools", "y"])
        self.assertEqual(code, 8)
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_preflight_keyboard_interrupt_is_fixed_exit_8(self):
        workspace(self.project, [module("one", "python", "one")])
        stderr = io.StringIO()
        with mock.patch.object(cli_module, "validate_installed_bundle", side_effect=KeyboardInterrupt):
            with contextlib.redirect_stderr(stderr):
                code = cli_module.main(["doctor", "--project", str(self.project)])
        self.assertEqual(code, 8)
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_preflight_os_error_is_fixed_without_raw_detail(self):
        workspace(self.project, [module("one", "python", "one")])
        stderr = io.StringIO()
        with mock.patch.object(cli_module, "validate_installed_bundle", side_effect=OSError("private raw detail")):
            with contextlib.redirect_stderr(stderr):
                code = cli_module.main(["doctor", "--project", str(self.project)])
        self.assertEqual(code, 3)
        self.assertNotIn("private raw detail", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_closed_output_pipes_never_emit_raw_flush_tracebacks(self):
        workspace(self.project, [module("one", "python", "one")])
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(SRC_ROOT)
        cases = (
            ("plan-buffered", ["-B", "-m", "sentinel", "plan", "--project", str(self.project), "--format", "json"]),
            ("help-unbuffered", ["-B", "-u", "-m", "sentinel", "--help"]),
            ("version-unbuffered", ["-B", "-u", "-m", "sentinel", "--version"]),
            ("usage-unbuffered", ["-B", "-u", "-m", "sentinel", "plan", "--unknown"]),
        )
        for name, arguments in cases:
            with self.subTest(name=name):
                process = subprocess.Popen(
                    [sys.executable, *arguments],
                    cwd=REPO_ROOT,
                    env=environment,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                process.stdout.close()
                stderr = process.stderr.read().decode("utf-8", errors="replace")
                process.stderr.close()
                code = process.wait(timeout=3)
                self.assertEqual(code, 3)
                self.assertNotIn("Traceback", stderr)
                self.assertNotIn("BrokenPipeError", stderr)
                self.assertNotIn(str(REPO_ROOT), stderr)

    def test_closed_stderr_usage_and_both_closed_are_fixed_exit_3(self):
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(SRC_ROOT)
        for name, close_stdout in (("stderr", False), ("both", True)):
            with self.subTest(name=name):
                process = subprocess.Popen(
                    [sys.executable, "-B", "-u", "-m", "sentinel", "plan", "--unknown"],
                    cwd=REPO_ROOT,
                    env=environment,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                process.stderr.close()
                if close_stdout:
                    process.stdout.close()
                    stdout = b""
                else:
                    stdout = process.stdout.read()
                    process.stdout.close()
                self.assertEqual(process.wait(timeout=3), 3)
                self.assertNotIn(b"Traceback", stdout)
                self.assertNotIn(b"BrokenPipeError", stdout)
                self.assertNotIn(str(REPO_ROOT).encode(), stdout)

    def test_closed_stderr_does_not_replace_healthy_stdout(self):
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(SRC_ROOT)
        script = (
            "import os; from sentinel.cli import main; "
            "code=main(['plan','--unknown']); "
            "os.write(1,b'stdout-still-open\\n'); os._exit(code)"
        )
        process = subprocess.Popen(
            [sys.executable, "-B", "-u", "-c", script],
            cwd=REPO_ROOT,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        process.stderr.close()
        stdout = process.stdout.read()
        process.stdout.close()
        self.assertEqual(process.wait(timeout=3), 3)
        self.assertEqual(stdout, b"stdout-still-open\n")

    def test_absent_output_descriptors_at_startup_are_fixed_exit_3(self):
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(SRC_ROOT)
        for descriptors in ((1,), (2,), (1, 2)):
            with self.subTest(descriptors=descriptors):
                def close_descriptors():
                    for descriptor in descriptors:
                        os.close(descriptor)

                completed = subprocess.run(
                    [sys.executable, "-B", "-m", "sentinel", "--help"],
                    cwd=REPO_ROOT,
                    env=environment,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    preexec_fn=close_descriptors,
                    timeout=3,
                )
                output = completed.stdout + completed.stderr
                self.assertEqual(completed.returncode, 3)
                self.assertNotIn(b"Traceback", output)
                self.assertNotIn(b"AttributeError", output)
                self.assertNotIn(b"Bad file descriptor", output)
                self.assertNotIn(str(REPO_ROOT).encode(), output)

    def test_output_descriptors_closed_after_import_are_fixed_exit_3(self):
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(SRC_ROOT)
        for descriptors in ((1,), (2,), (1, 2)):
            with self.subTest(descriptors=descriptors):
                closes = "; ".join(f"os.close({descriptor})" for descriptor in descriptors)
                arguments = "['--help']" if descriptors == (1,) else "['plan','--unknown']"
                script = (
                    "import os; from sentinel.cli import main; "
                    f"{closes}; raise SystemExit(main({arguments}))"
                )
                completed = subprocess.run(
                    [sys.executable, "-B", "-c", script],
                    cwd=REPO_ROOT,
                    env=environment,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=3,
                )
                output = completed.stdout + completed.stderr
                self.assertEqual(completed.returncode, 3)
                self.assertNotIn(b"Traceback", output)
                self.assertNotIn(b"AttributeError", output)
                self.assertNotIn(b"Bad file descriptor", output)
                self.assertNotIn(str(REPO_ROOT).encode(), output)

    def test_normal_stringio_help_keeps_redirected_streams(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = cli_module.main(["--help"])
            self.assertIs(sys.stdout, stdout)
            self.assertIs(sys.stderr, stderr)
        self.assertEqual(code, 0)
        self.assertIn("usage: sentinel", stdout.getvalue())
        self.assertEqual(stderr.getvalue(), "")

    def test_parser_keyboard_interrupt_is_fixed_exit_8(self):
        stderr = io.StringIO()
        with mock.patch.object(cli_module, "build_parser", side_effect=KeyboardInterrupt):
            with contextlib.redirect_stderr(stderr):
                code = cli_module.main(["--version"])
        self.assertEqual(code, 8)
        self.assertEqual(stderr.getvalue(), "sentinel: cancelled\n")

    def test_final_flush_keyboard_interrupt_is_fixed_exit_8(self):
        class InterruptingFlush(io.StringIO):
            def flush(self):
                raise KeyboardInterrupt

        stdout = InterruptingFlush()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = cli_module.main(["--version"])
        self.assertEqual(code, 8)
        self.assertEqual(stderr.getvalue(), "sentinel: cancelled\n")

    def test_blocked_output_sigint_does_not_retry_at_interpreter_exit(self):
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(SRC_ROOT)
        for descriptor in (1, 2):
            with self.subTest(descriptor=descriptor):
                ready_descriptor = 3 - descriptor
                arguments = ["--help"] if descriptor == 1 else ["plan", "--unknown"]
                script = f"""
import os
from sentinel.cli import main
os.set_blocking({descriptor}, False)
try:
    while True:
        os.write({descriptor}, b'x' * 4096)
except BlockingIOError:
    pass
os.set_blocking({descriptor}, True)
os.write({ready_descriptor}, b'READY\\n')
raise SystemExit(main({arguments!r}))
"""
                process = subprocess.Popen(
                    [sys.executable, "-B", "-c", script],
                    cwd=REPO_ROOT,
                    env=environment,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                ready_stream = process.stderr if descriptor == 1 else process.stdout
                exited = False
                code = None
                try:
                    ready, _, _ = select.select([ready_stream], [], [], 3)
                    self.assertTrue(ready)
                    self.assertEqual(ready_stream.readline(), b"READY\n")
                    time.sleep(0.1)
                    process.send_signal(signal.SIGINT)
                    try:
                        code = process.wait(timeout=3)
                        exited = True
                    except subprocess.TimeoutExpired:
                        pass
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.wait(timeout=3)
                    process.stdout.close()
                    process.stderr.close()
                self.assertTrue(exited, "interpreter retried the cancelled output")
                self.assertEqual(code, 8)

    def test_blocked_error_diagnostic_first_sigint_exits_without_drain(self):
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(SRC_ROOT)
        for case in ("stdout-consumer-closed", "stdout-fd-missing"):
            with self.subTest(case=case):
                ready_read, ready_write = os.pipe()
                script = f"""
import os
from sentinel.cli import main

if {case!r} == 'stdout-fd-missing':
    os.close(1)
os.set_blocking(2, False)
try:
    while True:
        os.write(2, b'x' * 4096)
except BlockingIOError:
    pass
os.set_blocking(2, True)
os.write({ready_write}, b'READY\\n')
os.close({ready_write})
raise SystemExit(main(['--help']))
"""
                process = None
                try:
                    process = subprocess.Popen(
                        [sys.executable, "-B", "-c", script],
                        cwd=REPO_ROOT,
                        env=environment,
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        pass_fds=(ready_write,),
                    )
                    os.close(ready_write)
                    ready_write = -1
                    if case == "stdout-consumer-closed":
                        process.stdout.close()
                    self.assertTrue(select.select([ready_read], [], [], 3)[0])
                    self.assertEqual(os.read(ready_read, 4096), b"READY\n")
                    deadline = time.monotonic() + 3
                    while time.monotonic() < deadline:
                        if Path(f"/proc/{process.pid}/wchan").read_text().strip() == "anon_pipe_write":
                            break
                        time.sleep(0.01)
                    else:
                        self.fail("child did not block in stderr diagnostic")
                    process.send_signal(signal.SIGINT)
                    try:
                        code = process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        code = None
                    if code is not None:
                        stderr = process.stderr.read()
                        self.assertEqual(code, 8)
                        self.assertNotIn(b"Traceback", stderr)
                        self.assertNotIn(str(REPO_ROOT).encode(), stderr)
                    self.assertEqual(code, 8, "child required stderr drain after its first SIGINT")
                finally:
                    if process is not None:
                        if process.poll() is None:
                            process.kill()
                            process.wait(timeout=3)
                        for stream in (process.stdout, process.stderr):
                            if stream is not None and not stream.closed:
                                stream.close()
                    os.close(ready_read)
                    if ready_write >= 0:
                        os.close(ready_write)


class ProtocolReviewTests(unittest.TestCase):
    def tearDown(self):
        for process in getattr(self, "processes", []):
            if process.poll() is None:
                protocol._terminate_group(process)
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream and not stream.closed:
                    stream.close()

    def make_sleeping_process(self):
        process = subprocess.Popen(
            ["/usr/bin/python3", "-c", "import time; time.sleep(30)"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        self.processes = getattr(self, "processes", []) + [process]
        return process

    def test_selector_setup_failure_reaps_child_and_closes_all_pipes(self):
        process = self.make_sleeping_process()
        with mock.patch.object(protocol.selectors.DefaultSelector, "register", side_effect=OSError("injected")):
            stdout, stderr, failure = protocol._collect(process, b"{}", 0.1)
        self.assertEqual((stdout, stderr, failure), (b"", b"", "processIoError"))
        self.assertIsNotNone(process.poll())
        self.assertTrue(all(stream.closed for stream in (process.stdin, process.stdout, process.stderr)))

    def test_large_unread_stdin_times_out_and_reaps_child(self):
        process = self.make_sleeping_process()
        stdout, stderr, failure = protocol._collect(process, b"x" * (2 * 1024 * 1024), 0.1)
        self.assertEqual((stdout, stderr, failure), (b"", b"", "timeout"))
        self.assertIsNotNone(process.poll())
        self.assertTrue(all(stream.closed for stream in (process.stdin, process.stdout, process.stderr)))

    def test_one_stream_close_failure_does_not_skip_other_cleanup(self):
        process = self.make_sleeping_process()
        real_close = process.stdin.close

        def close_then_fail():
            real_close()
            raise RuntimeError("injected cleanup failure")

        with mock.patch.object(process.stdin, "close", side_effect=close_then_fail):
            stdout, stderr, failure = protocol._collect(process, b"x" * (2 * 1024 * 1024), 0.05)
        self.assertEqual((stdout, stderr, failure), (b"", b"", "processCleanupError"))
        self.assertIsNotNone(process.poll())
        self.assertTrue(process.stdout.closed)
        self.assertTrue(process.stderr.closed)

    def test_process_group_cleanup_error_is_reported_after_direct_reap(self):
        process = self.make_sleeping_process()
        with mock.patch.object(protocol.os, "killpg", side_effect=PermissionError("injected")):
            stdout, stderr, failure = protocol._collect(process, b"x" * (2 * 1024 * 1024), 0.05)
        self.assertEqual((stdout, stderr, failure), (b"", b"", "processCleanupError"))
        self.assertIsNotNone(process.poll())
        self.assertTrue(all(stream.closed for stream in (process.stdin, process.stdout, process.stderr)))

    def test_first_sigint_at_each_cleanup_phase_finishes_all_cleanup(self):
        original_handler = signal.getsignal(signal.SIGINT)
        for phase in ("selector-close", "group-kill", "wait", "pipe-close"):
            with self.subTest(phase=phase):
                process = self.make_sleeping_process()
                real_selector_close = protocol.selectors.DefaultSelector.close
                real_killpg = protocol.os.killpg
                real_wait = process.wait
                real_stdin_close = process.stdin.close
                signals_sent = 0

                def interrupt_once():
                    nonlocal signals_sent
                    if not signals_sent:
                        signals_sent += 1
                        os.kill(os.getpid(), signal.SIGINT)

                def close_selector(selector):
                    real_selector_close(selector)
                    interrupt_once()

                def kill_group(pid, sent_signal):
                    interrupt_once()
                    real_killpg(pid, sent_signal)

                def close_stdin():
                    interrupt_once()
                    real_stdin_close()

                def wait_process(*arguments, **keywords):
                    interrupt_once()
                    return real_wait(*arguments, **keywords)

                with contextlib.ExitStack() as stack:
                    if phase == "selector-close":
                        stack.enter_context(mock.patch.object(protocol.selectors.DefaultSelector, "close", new=close_selector))
                    elif phase == "group-kill":
                        stack.enter_context(mock.patch.object(protocol.os, "killpg", new=kill_group))
                    elif phase == "wait":
                        stack.enter_context(mock.patch.object(process, "wait", new=wait_process))
                    elif phase == "pipe-close":
                        stack.enter_context(mock.patch.object(process.stdin, "close", new=close_stdin))
                    with self.assertRaises(KeyboardInterrupt):
                        protocol._collect(process, b"x" * (2 * 1024 * 1024), 0.05)
                self.assertEqual(signals_sent, 1)
                self.assertIsNotNone(process.poll())
                self.assertTrue(all(stream.closed for stream in (process.stdin, process.stdout, process.stderr)))
                self.assertIs(signal.getsignal(signal.SIGINT), original_handler)

    def test_cleanup_error_is_preserved_before_or_after_cleanup_sigint(self):
        for timing in ("before", "after"):
            with self.subTest(timing=timing):
                process = self.make_sleeping_process()
                real_selector_close = protocol.selectors.DefaultSelector.close
                real_killpg = protocol.os.killpg
                real_stdin_close = process.stdin.close
                signals_sent = 0

                def interrupt_once():
                    nonlocal signals_sent
                    if not signals_sent:
                        signals_sent += 1
                        os.kill(os.getpid(), signal.SIGINT)

                def selector_error(selector):
                    real_selector_close(selector)
                    raise OSError("injected error before cancellation")

                def interrupt_group(pid, sent_signal):
                    interrupt_once()
                    real_killpg(pid, sent_signal)

                def interrupt_selector(selector):
                    real_selector_close(selector)
                    interrupt_once()

                def close_error():
                    real_stdin_close()
                    raise OSError("injected error after cancellation")

                with contextlib.ExitStack() as stack:
                    if timing == "before":
                        stack.enter_context(mock.patch.object(protocol.selectors.DefaultSelector, "close", new=selector_error))
                        stack.enter_context(mock.patch.object(protocol.os, "killpg", new=interrupt_group))
                    else:
                        stack.enter_context(mock.patch.object(protocol.selectors.DefaultSelector, "close", new=interrupt_selector))
                        stack.enter_context(mock.patch.object(process.stdin, "close", new=close_error))
                    stdout, stderr, failure = protocol._collect(process, b"x" * (2 * 1024 * 1024), 0.05)
                self.assertEqual((stdout, stderr, failure), (b"", b"", "cancelledCleanupError"))
                self.assertEqual(signals_sent, 1)
                self.assertIsNotNone(process.poll())
                self.assertTrue(all(stream.closed for stream in (process.stdin, process.stdout, process.stderr)))

    def test_cleanup_sigint_and_error_cancel_remaining_modules(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            project = base / "project"
            project.mkdir()
            (project / "one").mkdir()
            (project / "two").mkdir()
            tools = base / "tools"
            first, first_digest, _ = make_bundle(base, language="python", behavior="interrupt_wait")
            second, second_digest, second_counter = make_bundle(base, language="typescript", behavior="pass")
            self.assertEqual(install_bundle(first, first_digest, tools).returncode, 0)
            self.assertEqual(install_bundle(second, second_digest, tools).returncode, 0)
            workspace(
                project,
                [module("one", "python", "one", digest=first_digest), module("two", "typescript", "two", digest=second_digest)],
            )
            real_killpg = protocol.os.killpg
            real_popen = protocol.subprocess.Popen
            calls = 0
            children = []

            def interrupt_then_fail(pid, sent_signal):
                nonlocal calls
                calls += 1
                if calls == 1:
                    os.kill(os.getpid(), signal.SIGINT)
                    raise PermissionError("injected cleanup failure")
                real_killpg(pid, sent_signal)

            def track_popen(*arguments, **keywords):
                child = real_popen(*arguments, **keywords)
                children.append(child)
                return child

            stdout = io.StringIO()
            stderr = io.StringIO()
            try:
                with mock.patch.object(protocol.os, "killpg", new=interrupt_then_fail):
                    with mock.patch.object(protocol.subprocess, "Popen", side_effect=track_popen):
                        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                            code = cli_module.main(
                                [
                                    "check", "--project", str(project), "--tools", str(tools),
                                    "--experimental", "--format", "json", "--timeout-seconds", "0.05",
                                ]
                            )
                cli_reaped_children = len(children) == 1 and all(child.poll() is not None for child in children)
                cli_closed_pipes = len(children) == 1 and all(
                    stream.closed for child in children for stream in (child.stdin, child.stdout, child.stderr)
                )
            finally:
                for child in children:
                    if child.poll() is None:
                        child.kill()
                        child.wait(timeout=3)
                    for stream in (child.stdin, child.stdout, child.stderr):
                        if stream is not None and not stream.closed:
                            stream.close()
            payload = json.loads(stdout.getvalue())
            self.assertEqual(code, 6, stderr.getvalue())
            self.assertEqual(
                [(item["status"], item["exitCode"]) for item in payload["results"]],
                [("backendError", 6), ("cancelled", 8)],
            )
            self.assertFalse(second_counter.exists())
            self.assertEqual(len(children), 1)
            self.assertTrue(cli_reaped_children)
            self.assertTrue(cli_closed_pipes)

    def test_nonempty_malformed_response_is_backend_error_even_on_nonzero_exit(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, digest, _ = make_bundle(Path(temporary))
            selected = bundle_module.validate_bundle(source, digest)
            observation = protocol._parse_response(b'{"requestId":"a","requestId":"b"}', {}, selected, 2)
        self.assertEqual((observation.status, observation.exit_code), ("backendError", 6))

    def test_sigint_returns_cancelled_and_reaps_active_child(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            project = base / "project"
            project.mkdir()
            (project / "one").mkdir()
            tools = base / "tools"
            source, digest, _ = make_bundle(base, behavior="interrupt_wait")
            self.assertEqual(install_bundle(source, digest, tools).returncode, 0)
            workspace(project, [module("one", "python", "one", digest=digest)])
            environment = os.environ.copy()
            environment["PYTHONPATH"] = str(SRC_ROOT)
            process = subprocess.Popen(
                [sys.executable, "-m", "sentinel", "check", "--project", str(project), "--tools", str(tools), "--experimental", "--format", "json"],
                cwd=REPO_ROOT,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            pid_file = base / "child-pid"
            for _ in range(100):
                if pid_file.exists():
                    break
                time.sleep(0.02)
            self.assertTrue(pid_file.exists(), "fixture child did not start")
            child_pid = int(pid_file.read_text())
            process.send_signal(signal.SIGINT)
            stdout, stderr = process.communicate(timeout=5)
            self.assertEqual(process.returncode, 8, stderr)
            self.assertEqual(json.loads(stdout)["results"][0]["status"], "cancelled")
            self.assertFalse(Path(f"/proc/{child_pid}").exists())

    def test_sigint_with_cleanup_error_cancels_remaining_modules(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            project = base / "project"
            project.mkdir()
            (project / "one").mkdir()
            (project / "two").mkdir()
            tools = base / "tools"
            first, first_digest, _ = make_bundle(base, language="python", behavior="interrupt_wait")
            second, second_digest, second_counter = make_bundle(base, language="typescript", behavior="pass")
            self.assertEqual(install_bundle(first, first_digest, tools).returncode, 0)
            self.assertEqual(install_bundle(second, second_digest, tools).returncode, 0)
            workspace(
                project,
                [module("one", "python", "one", digest=first_digest), module("two", "typescript", "two", digest=second_digest)],
            )
            real_select = protocol.selectors.DefaultSelector.select
            real_killpg = protocol.os.killpg
            real_popen = protocol.subprocess.Popen
            state = {"interrupted": False, "cleanup_failed": False}
            children = []

            def interrupt_once(selector, timeout=None):
                if not state["interrupted"]:
                    state["interrupted"] = True
                    os.kill(os.getpid(), signal.SIGINT)
                return real_select(selector, timeout)

            def fail_first_kill(pid, sent_signal):
                if not state["cleanup_failed"]:
                    state["cleanup_failed"] = True
                    raise PermissionError("injected cleanup error")
                return real_killpg(pid, sent_signal)

            def track_popen(*arguments, **keywords):
                child = real_popen(*arguments, **keywords)
                children.append(child)
                return child

            stdout = io.StringIO()
            stderr = io.StringIO()
            with mock.patch.object(protocol.selectors.DefaultSelector, "select", new=interrupt_once):
                with mock.patch.object(protocol.os, "killpg", side_effect=fail_first_kill):
                    with mock.patch.object(protocol.subprocess, "Popen", side_effect=track_popen):
                        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                            code = cli_module.main(
                                ["check", "--project", str(project), "--tools", str(tools), "--experimental", "--format", "json"]
                            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(code, 6, stderr.getvalue())
            self.assertEqual(
                [(item["status"], item["exitCode"]) for item in payload["results"]],
                [("backendError", 6), ("cancelled", 8)],
            )
            self.assertFalse(second_counter.exists())
            self.assertEqual(len(children), 1)
            self.assertTrue(all(child.poll() is not None for child in children))


if __name__ == "__main__":
    unittest.main()
