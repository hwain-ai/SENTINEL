import hashlib
import json
import os
import signal
import stat
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from sentinel.gate import DEFAULT_GATE
from sentinel import bundle as bundle_api
from sentinel.errors import SentinelError
from sentinel.go_sandbox import GoRunObservation
from sentinel.protocol import Observation
from sentinel.sandbox import SandboxResult
from sentinel.workspace import Module


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _native_bundle(source):
    files = {
        "profile.json": _canonical(
            {
                "schemaVersion": "sentinel-go-oci-profile-v1",
                "runtimeManifest": "runtime.json",
                "artifactManifest": "artifact.json",
                "dependenciesManifest": "dependencies.json",
                "toolchainLock": "toolchain.json",
                "executorLock": "executor.json",
                "imageManifest": "image-manifest.json",
                "imageConfig": "image-config.json",
            }
        ),
        "runtime.json": b"runtime",
        "artifact.json": b"artifact",
        "dependencies.json": b"dependencies",
        "toolchain.json": b"toolchain",
        "executor.json": b"executor",
        "image-manifest.json": b"image manifest",
        "image-config.json": b"image config",
    }
    source.mkdir(mode=0o700)
    for relative, raw in files.items():
        path = source / relative
        path.write_bytes(raw)
        path.chmod(0o600)
    manifest = {
        "schemaVersion": "sentinel-tool-bundle-v1",
        "protocolVersion": "sentinel-go-oci-v1",
        "language": "go",
        "version": "0.1.0",
        "entrypoint": "profile.json",
        "files": {name: hashlib.sha256(raw).hexdigest() for name, raw in files.items()},
    }
    manifest_raw = _canonical(manifest)
    (source / "sentinel-tool.json").write_bytes(manifest_raw)
    return hashlib.sha256(manifest_raw).hexdigest()


class NativeBundleTests(unittest.TestCase):
    def test_oci_profile_bundle_installs_every_data_file_without_execute_permission(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "bundle"
            digest = _native_bundle(source)

            validated = bundle_api.validate_bundle(source, digest)
            installed = bundle_api.install_bundle(source, digest, base / "tools")

            self.assertEqual(validated.protocol_version, "sentinel-go-oci-v1")
            destination = bundle_api.bundle_path(base / "tools", "go", "0.1.0", digest)
            self.assertEqual(installed.protocol_version, "sentinel-go-oci-v1")
            for relative in validated.files:
                self.assertEqual(stat.S_IMODE((destination / relative).stat().st_mode), 0o600)

    def test_oci_profile_protocol_is_only_valid_for_the_pinned_go_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            for language, version in (("python", "0.1.0"), ("go", "0.1.1")):
                with self.subTest(language=language, version=version):
                    source = base / (language + version)
                    digest = _native_bundle(source)
                    path = source / "sentinel-tool.json"
                    manifest = json.loads(path.read_text())
                    manifest["language"] = language
                    manifest["version"] = version
                    raw = _canonical(manifest)
                    path.write_bytes(raw)
                    with self.assertRaises(SentinelError):
                        bundle_api.validate_bundle(source, hashlib.sha256(raw).hexdigest())


class NativeModuleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name).resolve()
        self.base.chmod(0o700)
        self.project = self.base / "project"
        self.project.mkdir(mode=0o700)
        self.module_root = self.project / "module"
        self.module_root.mkdir(mode=0o700)
        (self.module_root / "go.mod").write_bytes(b"module example.test/native\n")
        (self.module_root / "main.go").write_bytes(b"package main\nfunc main() {}\n")
        self.config = self.module_root / "sentinel-go.json"
        self.config.write_bytes(
            _canonical(
                {
                    "schemaVersion": "sentinel-go-check-v1",
                    "sources": ["main.go"],
                    "mutantTimeoutMs": 1234,
                }
            )
        )
        for path in self.module_root.iterdir():
            path.chmod(0o600)
        self.module = Module("native", "go", self.module_root, "0.1.0", "a" * 64, self.config)
        self.content = self.base / "native-content"
        self.content.mkdir(mode=0o700)

    def tearDown(self):
        if self.base.exists():
            for current, _directories, files in os.walk(self.base):
                Path(current).chmod(0o700)
                for name in files:
                    (Path(current) / name).chmod(0o600)
        self.temporary.cleanup()

    def test_module_config_and_complete_project_are_bound_to_a_read_only_corpus(self):
        from sentinel.native_go import prepare_module_corpus, recheck_module_source

        prepared = prepare_module_corpus(self.module, self.content)

        self.assertEqual(prepared.sources, ("main.go",))
        self.assertEqual(prepared.mutant_timeout_ms, 1234)
        self.assertEqual({entry.path for entry in prepared.corpus._entries}, {"go.mod", "main.go", "sentinel-go.json"})
        self.assertEqual(stat.S_IMODE(prepared.corpus.root.stat().st_mode), 0o500)
        recheck_module_source(prepared)

    def test_git_metadata_rejects_the_whole_project_instead_of_being_ignored(self):
        from sentinel.native_go import prepare_module_corpus

        (self.module_root / ".git").mkdir(mode=0o700)
        with self.assertRaises(SentinelError):
            prepare_module_corpus(self.module, self.content)
        self.assertEqual(list(self.content.iterdir()), [])

    def test_invalid_module_config_is_rejected_before_corpus_publication(self):
        from sentinel.native_go import prepare_module_corpus

        self.config.write_bytes(_canonical({"schemaVersion": "sentinel-go-check-v1", "sources": ["main.go"], "command": "check"}))
        with self.assertRaises(SentinelError):
            prepare_module_corpus(self.module, self.content)
        self.assertEqual(list(self.content.iterdir()), [])

    def test_explicit_null_mutant_timeout_is_not_treated_as_omission(self):
        from sentinel.native_go import prepare_module_corpus

        self.config.write_bytes(
            _canonical(
                {
                    "schemaVersion": "sentinel-go-check-v1",
                    "sources": ["main.go"],
                    "mutantTimeoutMs": None,
                }
            )
        )
        with self.assertRaises(SentinelError):
            prepare_module_corpus(self.module, self.content)
        self.assertEqual(list(self.content.iterdir()), [])

    def test_source_recheck_compares_bytes_with_the_sealed_corpus_entry(self):
        from sentinel import native_go

        prepared = native_go.prepare_module_corpus(self.module, self.content)
        original = native_go._read_source_file

        def changed_bytes(root, relative, expected):
            raw = original(root, relative, expected)
            return b"changed" if relative == "main.go" else raw

        with mock.patch.object(native_go, "_read_source_file", side_effect=changed_bytes):
            with self.assertRaises(SentinelError):
                native_go.recheck_module_source(prepared)


class NativeObservationTests(unittest.TestCase):
    def test_native_exit_codes_reuse_the_public_status_mapping(self):
        from sentinel.native_go import observation_from_go

        sandbox = SandboxResult(0, False, False, 0, 0, hashlib.sha256(b"").hexdigest(), hashlib.sha256(b"").hexdigest(), True)
        for expected in range(9):
            with self.subTest(exit_code=expected):
                native = GoRunObservation(sandbox, expected, True, 0, 0, "a" * 64, "b" * 64, ("c" * 64,) * 4)
                observed = observation_from_go(native)
                self.assertEqual(observed.exit_code, expected)
                self.assertEqual(observed.cancellation_requested, expected == 8)

    def test_incomplete_native_observation_is_a_backend_error(self):
        from sentinel.native_go import observation_from_go

        incomplete = SandboxResult(None, True, False, 0, 0, "", "", False)
        native = GoRunObservation(incomplete, None, False, 0, 0, "", "", ("c" * 64,) * 4)
        self.assertEqual(observation_from_go(native), Observation("backendError", 6))

    def test_cleanup_failure_keeps_backend_error_and_sticky_cancellation(self):
        from sentinel import native_go

        prepared = SimpleNamespace(
            tools=Path("/tmp/tools"),
            executor_lock_path=Path("/tmp/lock"),
            executor_lock_sha256="a" * 64,
            image_manifest=b"manifest",
            image_config=b"config",
            inputs=object(),
            module_corpus=SimpleNamespace(sources=("main.go",), mutant_timeout_ms=None),
        )

        class FailedRunner:
            cancellation_requested = True

            def run(self, _request, *, deadline=None):
                raise SentinelError("sandboxFailed", "failed", 6)

        with (
            mock.patch.object(native_go, "recheck_native_go"),
            mock.patch.object(native_go, "recheck_module_source"),
            mock.patch.object(native_go, "_private_runs_parent", return_value=Path("/tmp/runs")),
            mock.patch.object(native_go.oci, "prepare_session", return_value="b" * 64),
            mock.patch.object(native_go, "InstalledGoSandbox", return_value=FailedRunner()),
        ):
            observed = native_go.run_native_go(prepared, 60.0)

        self.assertEqual(observed, Observation("backendError", 6, True))

    def test_swallowed_late_session_interrupt_blocks_container_start(self):
        from sentinel import native_go

        prepared = SimpleNamespace(
            tools=Path("/tmp/tools"),
            executor_lock_path=Path("/tmp/lock"),
            executor_lock_sha256="a" * 64,
            image_manifest=b"manifest",
            image_config=b"config",
            inputs=object(),
            module_corpus=SimpleNamespace(sources=("main.go",), mutant_timeout_ms=None),
        )

        def committed_session(*_arguments):
            try:
                signal.getsignal(signal.SIGINT)(signal.SIGINT, None)
            except KeyboardInterrupt:
                pass
            return "b" * 64

        with (
            mock.patch.object(native_go, "recheck_native_go"),
            mock.patch.object(native_go, "recheck_module_source"),
            mock.patch.object(native_go, "_private_runs_parent", return_value=Path("/tmp/runs")),
            mock.patch.object(native_go.oci, "prepare_session", side_effect=committed_session),
            mock.patch.object(native_go, "InstalledGoSandbox") as runner,
        ):
            observed = native_go.run_native_go(prepared, 60.0)

        runner.assert_not_called()
        self.assertEqual(observed, Observation("cancelled", 8, True))

    def test_module_deadline_is_computed_before_recheck_and_forwarded_unchanged(self):
        from sentinel import native_go

        prepared = SimpleNamespace(
            tools=Path("/tmp/tools"),
            executor_lock_path=Path("/tmp/lock"),
            executor_lock_sha256="a" * 64,
            image_manifest=b"manifest",
            image_config=b"config",
            inputs=object(),
            module_corpus=SimpleNamespace(sources=("main.go",), mutant_timeout_ms=1234),
        )
        received = {}
        sandbox = SandboxResult(0, False, False, 0, 0, "a" * 64, "b" * 64, True)
        native_observation = GoRunObservation(
            sandbox,
            0,
            True,
            0,
            0,
            "a" * 64,
            "b" * 64,
            ("c" * 64,) * 4,
        )

        class SuccessfulRunner:
            cancellation_requested = False

            def run(self, request, *, deadline=None):
                received["request"] = request
                received["deadline"] = deadline
                return native_observation

        with (
            mock.patch.object(native_go.time, "monotonic", return_value=100.0),
            mock.patch.object(native_go, "recheck_native_go"),
            mock.patch.object(native_go, "recheck_module_source"),
            mock.patch.object(native_go, "_private_runs_parent", return_value=Path("/tmp/runs")),
            mock.patch.object(native_go.oci, "prepare_session", return_value="b" * 64),
            mock.patch.object(native_go, "InstalledGoSandbox", return_value=SuccessfulRunner()),
        ):
            observed = native_go.run_native_go(prepared, 60.0)

        self.assertEqual(observed, Observation("passed", 0))
        self.assertEqual(received["deadline"], 160.0)
        self.assertEqual(
            received["request"],
            native_go.GoRunRequest("check", ("main.go",), 60.0, 1234),
        )


class NativeCliTests(unittest.TestCase):
    def _args(self):
        from sentinel.cli import build_parser

        return build_parser().parse_args([
            "check", "--project", "unused", "--tools", "unused",
            "--format", "json", "--timeout-seconds", "60", "--experimental",
        ])

    def test_native_preparation_failure_blocks_every_selected_checker(self):
        from sentinel import cli

        root = Path("/tmp/project")
        go_module = Module("go", "go", root, "0.1.0", "a" * 64, root / "go.json")
        py_module = Module("py", "python", root, "1.2.3", "b" * 64, None)
        native_bundle = bundle_api.Bundle(root, "go", "0.1.0", "a" * 64, "profile.json", {"profile.json": "c" * 64}, "sentinel-go-oci-v1")
        legacy_bundle = bundle_api.Bundle(root, "python", "1.2.3", "b" * 64, "tool", {"tool": "d" * 64})
        output = StringIO()
        with (
            mock.patch.object(cli, "_selected", return_value=(root, "allConfigured", [py_module, go_module], root / "tools", DEFAULT_GATE)),
            mock.patch.object(cli, "_preflight", return_value=({"py": legacy_bundle, "go": native_bundle}, [cli._result(py_module, "ready", 0), cli._result(go_module, "ready", 0)], False)),
            mock.patch.object(cli, "prepare_native_go", side_effect=SentinelError("nativeGoFailed", "failed", 5)),
            mock.patch.object(cli, "run_check") as legacy_run,
            mock.patch.object(cli.sys, "stdout", output),
        ):
            result = cli._run_workspace(self._args())

        self.assertEqual(result, 5)
        legacy_run.assert_not_called()
        payload = json.loads(output.getvalue())
        self.assertEqual([item["status"] for item in payload["results"]], ["ready", "dependencyError"])

    def test_native_cancellation_marks_and_skips_every_later_module(self):
        from sentinel import cli

        root = Path("/tmp/project")
        first = Module("first", "go", root, "0.1.0", "a" * 64, root / "go.json")
        second = Module("second", "python", root, "1.2.3", "b" * 64, None)
        native_bundle = bundle_api.Bundle(root, "go", "0.1.0", "a" * 64, "profile.json", {"profile.json": "c" * 64}, "sentinel-go-oci-v1")
        legacy_bundle = bundle_api.Bundle(root, "python", "1.2.3", "b" * 64, "tool", {"tool": "d" * 64})
        prepared = object()
        output = StringIO()
        with (
            mock.patch.object(cli, "_selected", return_value=(root, "allConfigured", [first, second], root / "tools", DEFAULT_GATE)),
            mock.patch.object(cli, "_preflight", return_value=({"first": native_bundle, "second": legacy_bundle}, [cli._result(first, "ready", 0), cli._result(second, "ready", 0)], False)),
            mock.patch.object(cli, "prepare_native_go", return_value=prepared),
            mock.patch.object(cli, "run_native_go", return_value=Observation("cancelled", 8, True)) as native_run,
            mock.patch.object(cli, "run_check") as legacy_run,
            mock.patch.object(cli.sys, "stdout", output),
        ):
            result = cli._run_workspace(self._args())

        self.assertEqual(result, 8)
        native_run.assert_called_once_with(prepared, 60.0)
        legacy_run.assert_not_called()
        payload = json.loads(output.getvalue())
        self.assertEqual([item["status"] for item in payload["results"]], ["cancelled", "cancelled"])

    def test_go_timeout_above_profile_limit_is_rejected_before_preparation(self):
        from sentinel import cli

        root = Path("/tmp/project")
        module = Module("go", "go", root, "0.1.0", "a" * 64, root / "go.json")
        native_bundle = bundle_api.Bundle(root, "go", "0.1.0", "a" * 64, "profile.json", {"profile.json": "c" * 64}, "sentinel-go-oci-v1")
        args = self._args()
        args.timeout_seconds = 901.0
        with (
            mock.patch.object(cli, "_selected", return_value=(root, "allConfigured", [module], root / "tools", DEFAULT_GATE)),
            mock.patch.object(cli, "_preflight", return_value=({"go": native_bundle}, [cli._result(module, "ready", 0)], False)),
            mock.patch.object(cli, "prepare_native_go") as prepare,
        ):
            with self.assertRaises(SentinelError) as caught:
                cli._run_workspace(args)
        self.assertEqual(caught.exception.exit_code, 3)
        prepare.assert_not_called()

    def test_content_copy_interrupt_stops_later_preparation_and_every_checker(self):
        from sentinel import cli, native_go

        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            base.chmod(0o700)
            project = base / "project"
            project.mkdir(mode=0o700)
            content_parent = base / "native-content"
            content_parent.mkdir(mode=0o700)
            modules = []
            bundles = {}
            for name, digest in (("first", "a" * 64), ("second", "b" * 64)):
                root = project / name
                root.mkdir(mode=0o700)
                (root / "main.go").write_bytes(b"package fixture\n")
                config = root / "sentinel-go.json"
                config.write_bytes(
                    _canonical(
                        {
                            "schemaVersion": "sentinel-go-check-v1",
                            "sources": ["main.go"],
                        }
                    )
                )
                for path in root.iterdir():
                    path.chmod(0o600)
                item = Module(name, "go", root, "0.1.0", digest, config)
                modules.append(item)
                bundles[name] = bundle_api.Bundle(
                    base,
                    "go",
                    "0.1.0",
                    digest,
                    "profile.json",
                    {"profile.json": "c" * 64},
                    "sentinel-go-oci-v1",
                )
            events = []

            def prepare(module, _bundle, _tools):
                events.append("prepare:" + module.module_id)
                return native_go.prepare_module_corpus(module, content_parent)

            output = StringIO()
            error = StringIO()
            with (
                mock.patch.object(cli, "_selected", return_value=(project, "allConfigured", modules, base, DEFAULT_GATE)),
                mock.patch.object(
                    cli,
                    "_preflight",
                    return_value=(
                        bundles,
                        [cli._result(item, "ready", 0) for item in modules],
                        False,
                    ),
                ),
                mock.patch.object(cli, "prepare_native_go", side_effect=prepare),
                mock.patch.object(native_go.content, "_prepare_content_root", side_effect=KeyboardInterrupt),
                mock.patch.object(cli, "run_native_go") as native_run,
                mock.patch.object(cli, "run_check") as legacy_run,
                mock.patch.object(cli.sys, "stdout", output),
                mock.patch.object(cli.sys, "stderr", error),
            ):
                result = cli._main(["check", "--experimental"])

            self.assertEqual(result, 8)
            self.assertEqual(events, ["prepare:first"])
            native_run.assert_not_called()
            legacy_run.assert_not_called()
            self.assertEqual(list(content_parent.iterdir()), [])

    def test_content_copy_signal_survives_cleanup_failure_and_stops_later_work(self):
        from sentinel import cli, native_go

        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            base.chmod(0o700)
            project = base / "project"
            project.mkdir(mode=0o700)
            content_parent = base / "native-content"
            content_parent.mkdir(mode=0o700)
            modules = []
            bundles = {}
            for name, digest in (("first", "a" * 64), ("second", "b" * 64)):
                root = project / name
                root.mkdir(mode=0o700)
                (root / "main.go").write_bytes(b"package fixture\n")
                config = root / "sentinel-go.json"
                config.write_bytes(
                    _canonical(
                        {
                            "schemaVersion": "sentinel-go-check-v1",
                            "sources": ["main.go"],
                        }
                    )
                )
                for path in root.iterdir():
                    path.chmod(0o600)
                item = Module(name, "go", root, "0.1.0", digest, config)
                modules.append(item)
                bundles[name] = bundle_api.Bundle(
                    base,
                    "go",
                    "0.1.0",
                    digest,
                    "profile.json",
                    {"profile.json": "c" * 64},
                    "sentinel-go-oci-v1",
                )
            events = []

            def prepare(module, _bundle, _tools):
                events.append("prepare:" + module.module_id)
                return native_go.prepare_module_corpus(module, content_parent)

            def interrupt_copy(*_arguments):
                os.kill(os.getpid(), signal.SIGINT)

            output = StringIO()
            error = StringIO()
            with (
                mock.patch.object(cli, "_selected", return_value=(project, "allConfigured", modules, base, DEFAULT_GATE)),
                mock.patch.object(
                    cli,
                    "_preflight",
                    return_value=(
                        bundles,
                        [cli._result(item, "ready", 0) for item in modules],
                        False,
                    ),
                ),
                mock.patch.object(cli, "prepare_native_go", side_effect=prepare),
                mock.patch.object(native_go.content, "_copy_entry", side_effect=interrupt_copy),
                mock.patch.object(native_go.content, "_remove_staging", side_effect=OSError),
                mock.patch.object(cli, "run_native_go") as native_run,
                mock.patch.object(cli, "run_check") as legacy_run,
                mock.patch.object(cli.sys, "stdout", output),
                mock.patch.object(cli.sys, "stderr", error),
            ):
                result = cli._main(["check", "--experimental"])

            self.assertEqual(result, 8)
            self.assertEqual(events, ["prepare:first"])
            native_run.assert_not_called()
            legacy_run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
