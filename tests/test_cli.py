import os
import hashlib
import json
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
SRC_ROOT = os.path.join(REPO_ROOT, "src")


def cli(*arguments, cwd=None):
    environment = os.environ.copy()
    environment["PYTHONPATH"] = SRC_ROOT
    return subprocess.run(
        [sys.executable, "-m", "sentinel", *arguments],
        cwd=cwd or REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def write_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def module(module_id, language, root, version="1.2.3", digest="a" * 64, config=None):
    value = {
        "id": module_id,
        "language": language,
        "root": root,
        "toolVersion": version,
        "toolDigest": digest,
    }
    if config is not None:
        value["config"] = config
    return value


def workspace(project, modules):
    write_json(
        project / "sentinel.workspace.json",
        {"schemaVersion": "sentinel-workspace-v1", "modules": modules},
    )


def make_bundle(parent, language="python", version="1.2.3", behavior="pass"):
    bundle = parent / (language + "-" + behavior + "-bundle")
    (bundle / "bin").mkdir(parents=True)
    counter = parent / (language + "-count")
    scripts = {
        "no_changes": """
            import json, sys
            request = json.load(sys.stdin)
            response = {key: request[key] for key in ('protocolVersion', 'requestId', 'command', 'moduleId', 'language')}
            response.update(toolVersion='1.2.3', status='noChanges', exitCode=0, passed=False)
            print(json.dumps(response))
        """,
        "pass": """
            import json, os, sys
            request = json.load(sys.stdin)
            response = {key: request[key] for key in ('protocolVersion', 'requestId', 'command', 'moduleId', 'language')}
            if os.getcwd() == request['projectRoot'] and set(os.environ) == {'PATH', 'LANG', 'LC_ALL'}:
                response.update(toolVersion='1.2.3', status='passed', exitCode=0, passed=True)
            else:
                response.update(toolVersion='1.2.3', status='backendError', exitCode=6, passed=False)
            print(json.dumps(response))
            raise SystemExit(response['exitCode'])
        """,
        "quality_failed": """
            import json, sys
            request = json.load(sys.stdin)
            response = {key: request[key] for key in ('protocolVersion', 'requestId', 'command', 'moduleId', 'language')}
            response.update(toolVersion='1.2.3', status='qualityFailed', exitCode=2, passed=False)
            print(json.dumps(response))
            raise SystemExit(2)
        """,
        "wrong_nonce": """
            import json, sys
            request = json.load(sys.stdin)
            response = {key: request[key] for key in ('protocolVersion', 'requestId', 'command', 'moduleId', 'language')}
            response.update(requestId='00000000-0000-0000-0000-000000000000', toolVersion='1.2.3', status='passed', exitCode=0, passed=True)
            print(json.dumps(response))
        """,
        "wrong_exit": """
            import json, sys
            request = json.load(sys.stdin)
            response = {key: request[key] for key in ('protocolVersion', 'requestId', 'command', 'moduleId', 'language')}
            response.update(toolVersion='1.2.3', status='qualityFailed', exitCode=2, passed=False)
            print(json.dumps(response))
            raise SystemExit(1)
        """,
        "wrong_type": """
            import json, sys
            request = json.load(sys.stdin)
            response = {key: request[key] for key in ('protocolVersion', 'requestId', 'command', 'moduleId', 'language')}
            response.update(toolVersion='1.2.3', status='passed', exitCode=0, passed=1)
            print(json.dumps(response))
        """,
        "duplicate_response": """
            import json, sys
            json.load(sys.stdin)
            print('{"protocolVersion":"sentinel-tool-protocol-v1","protocolVersion":"sentinel-tool-protocol-v1"}')
        """,
        "oversized": """
            import sys
            sys.stdout.write('x' * (16 * 1024 * 1024 + 1))
        """,
        "timeout": """
            import time
            time.sleep(5)
        """,
        "secret_stderr": """
            import sys
            sys.stderr.write('/private/secret/token-value')
            raise SystemExit(1)
        """,
        "quality_failed": """
            import json, sys
            request = json.load(sys.stdin)
            response = {key: request[key] for key in ('protocolVersion', 'requestId', 'command', 'moduleId', 'language')}
            response.update(toolVersion='1.2.3', status='qualityFailed', exitCode=2, passed=False)
            print(json.dumps(response))
            raise SystemExit(2)
        """,
        "descendant": f"""
            import json, subprocess, sys
            request = json.load(sys.stdin)
            child = subprocess.Popen([{sys.executable!r}, '-c', 'import time; time.sleep(30)'], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            Path({str(parent / 'descendant-pid')!r}).write_text(str(child.pid))
            response = {{key: request[key] for key in ('protocolVersion', 'requestId', 'command', 'moduleId', 'language')}}
            response.update(toolVersion='1.2.3', status='passed', exitCode=0, passed=True)
            print(json.dumps(response))
        """,
        "interrupt_wait": f"""
            import os, time
            Path({str(parent / 'child-pid')!r}).write_text(str(os.getpid()))
            time.sleep(30)
        """,
    }
    counter_code = (
        "from pathlib import Path\n"
        f"_counter = Path({str(counter)!r})\n"
        "_counter.write_text(str(int(_counter.read_text()) + 1) if _counter.exists() else '1')\n"
    )
    executable = "#!/usr/bin/python3\n" + counter_code + textwrap.dedent(scripts[behavior])
    entrypoint = bundle / "bin" / "sentinel-tool"
    entrypoint.write_text(executable, encoding="utf-8")
    entrypoint.chmod(0o700)
    file_digest = hashlib.sha256(entrypoint.read_bytes()).hexdigest()
    manifest = {
        "schemaVersion": "sentinel-tool-bundle-v1",
        "protocolVersion": "sentinel-tool-protocol-v1",
        "language": language,
        "version": version,
        "entrypoint": "bin/sentinel-tool",
        "files": {"bin/sentinel-tool": file_digest},
    }
    manifest_path = bundle / "sentinel-tool.json"
    write_json(manifest_path, manifest)
    digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    return bundle, digest, counter


def install_bundle(bundle, digest, tools):
    return cli("install", "--bundle", str(bundle), "--sha256", digest, "--tools", str(tools))


class CliBootstrapTests(unittest.TestCase):
    def test_help_is_available(self):
        completed = cli("--help")

        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_version_is_available(self):
        completed = cli("--version")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("0.3.0", completed.stdout)

    def test_help_does_not_resolve_the_current_project(self):
        environment = os.environ.copy()
        environment["PYTHONPATH"] = SRC_ROOT
        program = "import os; os.getcwd=lambda: (_ for _ in ()).throw(RuntimeError('read project')); from sentinel.cli import build_parser; build_parser().parse_args(['--help'])"
        completed = subprocess.run([sys.executable, "-c", program], cwd=REPO_ROOT, env=environment, capture_output=True, text=True, check=False)
        self.assertEqual(completed.returncode, 0, completed.stderr)


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.project = Path(self.temporary.name) / "project"
        self.project.mkdir()
        (self.project / "api").mkdir()
        (self.project / "web").mkdir()

    def tearDown(self):
        self.temporary.cleanup()

    def test_plan_selects_modules_without_writing_tools(self):
        workspace(self.project, [module("api", "python", "api"), module("web", "typescript", "web")])
        tools = self.project / "tools"
        completed = cli("plan", "--project", str(self.project), "--language", "python", "--tools", str(tools))
        payload = json.loads(completed.stdout)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(payload["selection"], "partial")
        self.assertEqual(payload["moduleCount"], 1)
        self.assertEqual(payload["schemaVersion"], "sentinel-workspace-result-v2")
        self.assertEqual(set(payload), {"schemaVersion", "command", "selection", "moduleCount", "results", "exitCode"})
        self.assertEqual(payload["results"], [{"moduleId": "api", "language": "python", "status": "planned", "exitCode": 0}])
        self.assertNotIn("certified", payload)
        self.assertFalse(tools.exists())

    def test_duplicate_json_key_is_usage_error(self):
        (self.project / "sentinel.workspace.json").write_text(
            '{"schemaVersion":"sentinel-workspace-v1","modules":[],"modules":[]}', encoding="utf-8"
        )
        completed = cli("plan", "--project", str(self.project), "--format", "json")
        self.assertEqual(completed.returncode, 3)

    def test_boolean_numeric_field_is_usage_error(self):
        workspace(self.project, [module("api", "python", "api", version=True)])
        completed = cli("plan", "--project", str(self.project), "--format", "json")
        self.assertEqual(completed.returncode, 3)

    def test_unknown_workspace_field_is_usage_error(self):
        write_json(self.project / "sentinel.workspace.json", {"schemaVersion": "sentinel-workspace-v1", "modules": [], "extra": 1})
        completed = cli("plan", "--project", str(self.project), "--format", "json")
        self.assertEqual(completed.returncode, 3)

    def test_symlink_module_root_is_rejected(self):
        (self.project / "linked").symlink_to(self.project / "api", target_is_directory=True)
        workspace(self.project, [module("api", "python", "linked")])
        completed = cli("plan", "--project", str(self.project), "--format", "json")
        self.assertEqual(completed.returncode, 3)

    def test_nested_module_roots_are_rejected(self):
        (self.project / "api" / "nested").mkdir()
        workspace(self.project, [module("api", "python", "api"), module("nested", "python", "api/nested")])
        completed = cli("plan", "--project", str(self.project), "--format", "json")
        self.assertEqual(completed.returncode, 3)

    def test_config_must_be_regular_file_inside_module(self):
        (self.project / "outside.json").write_text("{}", encoding="utf-8")
        workspace(self.project, [module("api", "python", "api", config="../outside.json")])
        completed = cli("plan", "--project", str(self.project), "--format", "json")
        self.assertEqual(completed.returncode, 3)

    def test_timeout_out_of_range_is_usage_error(self):
        workspace(self.project, [module("api", "python", "api")])
        for value in ("0", "86401", "nan"):
            with self.subTest(value=value):
                completed = cli("check", "--project", str(self.project), "--timeout-seconds", value)
                self.assertEqual(completed.returncode, 3)

    def test_rejects_unadmitted_language_and_numeric_prerelease(self):
        for language, version in (("ruby", "1.2.3"), ("python", "1.2.3-01")):
            with self.subTest(language=language, version=version):
                workspace(self.project, [module("api", language, "api", version=version)])
                completed = cli("plan", "--project", str(self.project))
                self.assertEqual(completed.returncode, 3)

    def test_unknown_flag_has_fixed_usage_error_without_reflection(self):
        completed = cli("plan", "--private-token-value")
        self.assertEqual(completed.returncode, 3)
        self.assertNotIn("private-token-value", completed.stderr)

    def test_project_with_symlinked_ancestor_is_rejected(self):
        actual_parent = Path(self.temporary.name) / "actual-parent"
        linked_parent = Path(self.temporary.name) / "linked-parent"
        self.project.rename(actual_parent)
        linked_parent.symlink_to(actual_parent, target_is_directory=True)
        linked_project = linked_parent
        completed = cli("plan", "--project", str(linked_project))
        self.assertEqual(completed.returncode, 3)

    def test_language_and_module_selectors_cannot_be_mixed(self):
        workspace(self.project, [module("api", "python", "api"), module("web", "typescript", "web")])
        completed = cli("plan", "--project", str(self.project), "--language", "python", "--module", "web")
        self.assertEqual(completed.returncode, 3)

    def test_hostile_paths_and_deep_json_return_fixed_usage_errors(self):
        hostile_values = ("bad\x00root", "x" * 5000)
        for value in hostile_values:
            with self.subTest(value=value[:20]):
                workspace(self.project, [module("api", "python", value)])
                completed = cli("plan", "--project", str(self.project))
                self.assertEqual(completed.returncode, 3)
                self.assertNotIn("Traceback", completed.stderr)
                self.assertNotIn("/src/sentinel", completed.stderr)
        deep = '[' * 1100 + '0' + ']' * 1100
        (self.project / "sentinel.workspace.json").write_text(deep, encoding="utf-8")
        completed = cli("plan", "--project", str(self.project))
        self.assertEqual(completed.returncode, 3)
        self.assertNotIn("Traceback", completed.stderr)


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.tools = self.base / "tools"

    def tearDown(self):
        self.temporary.cleanup()

    def test_installs_nested_bundle_with_restricted_modes_and_is_idempotent(self):
        bundle, digest, _ = make_bundle(self.base)
        first = install_bundle(bundle, digest, self.tools)
        second = install_bundle(bundle, digest, self.tools)
        destination = self.tools / "python" / "1.2.3" / digest
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(stat.S_IMODE((destination / "bin" / "sentinel-tool").stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((destination / "sentinel-tool.json").stat().st_mode), 0o600)

    def test_rejects_wrong_manifest_digest_without_writing(self):
        bundle, digest, _ = make_bundle(self.base)
        completed = install_bundle(bundle, "b" * 64, self.tools)
        self.assertNotEqual(completed.returncode, 0)
        self.assertFalse(self.tools.exists())

    def test_failed_reinstall_does_not_change_existing_install(self):
        bundle, digest, _ = make_bundle(self.base)
        self.assertEqual(install_bundle(bundle, digest, self.tools).returncode, 0)
        installed = self.tools / "python" / "1.2.3" / digest / "bin" / "sentinel-tool"
        before = installed.read_bytes()
        (bundle / "bin" / "sentinel-tool").write_text("tampered", encoding="utf-8")
        completed = install_bundle(bundle, digest, self.tools)
        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(installed.read_bytes(), before)

    def test_rejects_unlisted_file_and_symlink_tool_ancestor(self):
        bundle, digest, _ = make_bundle(self.base)
        (bundle / "unlisted").write_text("no", encoding="utf-8")
        self.assertNotEqual(install_bundle(bundle, digest, self.tools).returncode, 0)
        actual = self.base / "actual"
        actual.mkdir()
        self.tools.symlink_to(actual, target_is_directory=True)
        (bundle / "unlisted").unlink()
        self.assertNotEqual(install_bundle(bundle, digest, self.tools).returncode, 0)
        self.assertEqual(list(actual.iterdir()), [])

    def test_rejects_language_path_escape_in_manifest(self):
        bundle, _, _ = make_bundle(self.base)
        manifest_path = bundle / "sentinel-tool.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["language"] = "../../escape"
        write_json(manifest_path, manifest)
        digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        completed = install_bundle(bundle, digest, self.tools)
        self.assertNotEqual(completed.returncode, 0)
        self.assertFalse((self.base / "escape").exists())

    def test_rejects_symlink_hidden_in_tools_ancestor(self):
        bundle, digest, _ = make_bundle(self.base)
        actual = self.base / "actual"
        (actual / "existing").mkdir(parents=True)
        linked = self.base / "linked"
        linked.symlink_to(actual, target_is_directory=True)
        tools = linked / "existing" / "tools"
        completed = install_bundle(bundle, digest, tools)
        self.assertNotEqual(completed.returncode, 0)
        self.assertFalse((actual / "existing" / "tools").exists())

    def test_rejects_language_symlink_before_creating_external_version_directory(self):
        bundle, digest, _ = make_bundle(self.base)
        self.tools.mkdir()
        actual = self.base / "external"
        actual.mkdir()
        (self.tools / "python").symlink_to(actual, target_is_directory=True)
        completed = install_bundle(bundle, digest, self.tools)
        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(list(actual.iterdir()), [])

    def test_rejects_bundle_with_symlinked_source_ancestor(self):
        source_parent = self.base / "source"
        source_parent.mkdir()
        bundle, digest, _ = make_bundle(source_parent)
        linked = self.base / "linked-source"
        linked.symlink_to(source_parent, target_is_directory=True)
        linked_bundle = linked / bundle.name
        completed = install_bundle(linked_bundle, digest, self.tools)
        self.assertNotEqual(completed.returncode, 0)
        self.assertFalse(self.tools.exists())


class CheckTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.project = self.base / "project"
        self.project.mkdir()
        (self.project / "one").mkdir()
        (self.project / "two").mkdir()
        self.tools = self.base / "tools"

    def tearDown(self):
        self.temporary.cleanup()

    def install(self, language, behavior="pass"):
        bundle, digest, _ = make_bundle(self.base, language=language, behavior=behavior)
        completed = install_bundle(bundle, digest, self.tools)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return digest

    def run_check(self, *extra):
        return cli("check", "--project", str(self.project), "--tools", str(self.tools), *extra)

    def test_default_check_does_not_execute_and_is_not_admitted(self):
        digest = self.install("python")
        workspace(self.project, [module("one", "python", "one", digest=digest)])
        completed = self.run_check()
        payload = json.loads(completed.stdout)
        self.assertEqual(completed.returncode, 6)
        self.assertEqual(payload["results"][0]["status"], "backendNotAdmitted")
        self.assertNotEqual(payload["exitCode"], 0)
        self.assertNotIn("certified", payload)
        self.assertFalse((self.base / "python-count").exists())

    def test_doctor_verifies_bundle_without_quality_execution(self):
        digest = self.install("python")
        workspace(self.project, [module("one", "python", "one", digest=digest)])
        completed = cli("doctor", "--project", str(self.project), "--tools", str(self.tools))
        payload = json.loads(completed.stdout)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(payload["results"][0]["status"], "ready")
        self.assertEqual(payload["exitCode"], 0)
        self.assertNotIn("certified", payload)
        self.assertFalse((self.base / "python-count").exists())

    def test_doctor_rejects_installed_file_with_relaxed_mode(self):
        digest = self.install("python")
        workspace(self.project, [module("one", "python", "one", digest=digest)])
        entrypoint = self.tools / "python" / "1.2.3" / digest / "bin" / "sentinel-tool"
        entrypoint.chmod(0o755)
        completed = cli("doctor", "--project", str(self.project), "--tools", str(self.tools), "--format", "json")
        self.assertEqual(completed.returncode, 5)
        self.assertEqual(json.loads(completed.stdout)["results"][0]["status"], "dependencyError")

    def test_experimental_success_remains_a_nonzero_command_result(self):
        python_digest = self.install("python")
        typescript_digest = self.install("typescript")
        workspace(self.project, [module("one", "python", "one", digest=python_digest), module("two", "typescript", "two", digest=typescript_digest)])
        completed = self.run_check("--experimental")
        payload = json.loads(completed.stdout)
        self.assertEqual(completed.returncode, 6, completed.stderr)
        self.assertEqual(payload["selection"], "allConfigured")
        self.assertEqual([item["status"] for item in payload["results"]], ["passed", "passed"])
        self.assertEqual([item["exitCode"] for item in payload["results"]], [0, 0])
        self.assertNotEqual(payload["exitCode"], 0)
        self.assertNotIn("certified", payload)
        self.assertEqual((self.base / "python-count").read_text(), "1")
        self.assertEqual((self.base / "typescript-count").read_text(), "1")

    def test_missing_bundle_preflight_prevents_any_child(self):
        digest = self.install("python", behavior="secret_stderr")
        workspace(self.project, [module("one", "python", "one", digest=digest), module("two", "typescript", "two", digest="b" * 64)])
        completed = self.run_check("--experimental")
        self.assertNotIn("token-value", completed.stdout + completed.stderr)
        self.assertEqual(completed.returncode, 5)
        self.assertFalse((self.base / "python-count").exists())

    def test_invalid_child_responses_are_backend_errors_except_output_overflow(self):
        for behavior in ("wrong_nonce", "wrong_exit", "wrong_type", "duplicate_response", "oversized"):
            with self.subTest(behavior=behavior):
                if self.tools.exists():
                    import shutil
                    shutil.rmtree(self.tools)
                digest = self.install("python", behavior=behavior)
                workspace(self.project, [module("one", "python", "one", digest=digest)])
                completed = self.run_check("--experimental")
                payload = json.loads(completed.stdout)
                expected = 7 if behavior == "oversized" else 6
                self.assertEqual(completed.returncode, expected, completed.stderr)
                self.assertEqual(payload["results"][0]["status"], "evidenceError" if expected == 7 else "backendError")

    def test_timeout_is_typed_backend_error(self):
        digest = self.install("python", behavior="timeout")
        workspace(self.project, [module("one", "python", "one", digest=digest)])
        completed = self.run_check("--experimental", "--timeout-seconds", "0.1")
        payload = json.loads(completed.stdout)
        self.assertEqual(completed.returncode, 6)
        self.assertEqual(payload["results"][0]["status"], "backendError")

    def test_child_stderr_is_not_disclosed(self):
        digest = self.install("python", behavior="secret_stderr")
        workspace(self.project, [module("one", "python", "one", digest=digest)])
        completed = self.run_check("--experimental")
        self.assertNotIn("private", completed.stdout + completed.stderr)
        self.assertNotIn("token-value", completed.stdout + completed.stderr)
        self.assertEqual(completed.returncode, 1)

    def test_failure_priority_preserves_quality_failure_when_other_child_passes(self):
        python_digest = self.install("python", behavior="pass")
        typescript_digest = self.install("typescript", behavior="quality_failed")
        workspace(self.project, [module("one", "python", "one", digest=python_digest), module("two", "typescript", "two", digest=typescript_digest)])
        completed = self.run_check("--experimental")
        payload = json.loads(completed.stdout)
        self.assertEqual(completed.returncode, 2)
        self.assertEqual([item["exitCode"] for item in payload["results"]], [0, 2])
        self.assertEqual(payload["exitCode"], 2)

    def test_success_cleanup_kills_remaining_process_group_descendant(self):
        digest = self.install("python", behavior="descendant")
        workspace(self.project, [module("one", "python", "one", digest=digest)])
        completed = self.run_check("--experimental")
        self.assertEqual(completed.returncode, 6, completed.stderr)
        pid = int((self.base / "descendant-pid").read_text())
        def alive():
            process = subprocess.run(["ps", "-p", str(pid), "-o", "stat="], capture_output=True, text=True)
            return process.returncode == 0 and bool(process.stdout.strip()) and not process.stdout.strip().startswith("Z")
        for _ in range(20):
            if not alive():
                break
            import time
            time.sleep(0.05)
        self.assertFalse(alive(), "descendant process survived group cleanup")


if __name__ == "__main__":
    unittest.main()
