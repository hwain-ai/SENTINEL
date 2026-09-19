import json
import os
import stat
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

from test_cli import cli
from sentinel.cli import build_parser
from sentinel.errors import SentinelError
from sentinel.setup import run_setup


TOOL_SCRIPT = textwrap.dedent(
    """\
    #!/usr/bin/python3
    import json, os, sys
    from pathlib import Path
    here = Path(__file__).resolve().parent
    manifest = json.loads((here / "sentinel-tool.json").read_text())
    home = (here / "home").read_text().rstrip("\\n")
    request = json.load(sys.stdin)
    Path(home, "last-request.json").write_text(json.dumps(request))
    response = {key: request[key] for key in ("protocolVersion", "requestId", "command", "moduleId", "language")}
    response.update(toolVersion=manifest["version"], status="qualityFailed", exitCode=2, passed=False)
    print(json.dumps(response))
    raise SystemExit(2)
    """
)


def fake_language_source(sources, repository, version="0.3.1", setup_exit=0):
    root = sources / repository
    tool = root / "sentinel-tool"
    tool.mkdir(parents=True)
    entrypoint = tool / "sentinel-tool"
    entrypoint.write_text(TOOL_SCRIPT, encoding="utf-8")
    entrypoint.chmod(0o700)
    setup = tool / "setup.sh"
    setup.write_text(
        "#!/bin/bash\n"
        f"echo bootstrapped >> \"$(dirname \"$0\")/../bootstrap.log\"\n"
        f"exit {setup_exit}\n",
        encoding="utf-8",
    )
    setup.chmod(0o700)
    (tool / "version").write_text(version + "\n", encoding="utf-8")
    scripts = root / "scripts"
    scripts.mkdir()
    launcher = scripts / "uv.sh"
    launcher.write_text(
        "#!/bin/bash\n"
        "printf '%s\\n' \"$*\" >> \"$(dirname \"$0\")/../deps.log\"\n"
        "[ \"$1\" = deps ] || exit 2\n"
        "[ \"$4\" = --offline ] && exit 1\n"
        "mkdir -p \"$2\" && printf 'installed\\n' > \"$2/marker\"\n",
        encoding="utf-8",
    )
    launcher.chmod(0o700)
    maven = scripts / "mvn.sh"
    maven.write_text(
        "#!/bin/bash\n"
        "printf '%s\\n' \"$*\" >> \"$(dirname \"$0\")/../maven.log\"\n"
        "[ \"$1\" = deps ] || exit 2\n"
        "[ -f \"$2/pom.xml\" ] || exit 1\n"
        "mkdir -p \"$2/.sentinel-m2\" && printf 'warmed\\n' > \"$2/.sentinel-m2/marker\"\n",
        encoding="utf-8",
    )
    maven.chmod(0o700)
    return root


class SetupCommandTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.project = self.base / "project"
        self.project.mkdir()
        self.sources = self.base / "sources"
        self.tools = self.base / "tools"

    def tearDown(self):
        self.temporary.cleanup()

    def setup(self, *extra):
        return cli(
            "setup",
            "--project",
            str(self.project),
            "--sources",
            str(self.sources),
            "--tools",
            str(self.tools),
            *extra,
        )

    def test_setup_bootstraps_sources_installs_bundles_and_writes_both_configs(self):
        python_root = fake_language_source(self.sources, "SENTINEL_PY")
        completed = self.setup("--language", "python", "--crap-max", "10", "--mutation-min", "90")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["exitCode"], 0)
        self.assertEqual(payload["schemaVersion"], "sentinel-setup-result-v2")
        self.assertEqual(set(payload), {"schemaVersion", "command", "gate", "results", "workspaceConfig", "projectConfig", "exitCode"})
        self.assertEqual(payload["gate"], {"crapMax": "10", "mutationMin": "90"})
        (result,) = payload["results"]
        self.assertEqual((result["language"], result["status"], result["toolVersion"]), ("python", "installed", "0.3.1"))
        self.assertEqual(payload["projectConfig"], "created")
        self.assertEqual((python_root / "bootstrap.log").read_text().count("bootstrapped"), 1)

        workspace = json.loads((self.project / "sentinel.workspace.json").read_text())
        self.assertEqual(workspace["gate"], {"crapMax": "10", "mutationMin": "90"})
        (module,) = workspace["modules"]
        self.assertEqual(module["language"], "python")
        self.assertEqual(module["config"], "sentinel.config.json")
        self.assertEqual(module["toolDigest"], result["toolDigest"])
        installed = self.tools / "python" / "0.3.1" / result["toolDigest"]
        self.assertTrue((installed / "sentinel-tool").is_file())
        self.assertEqual((installed / "home").read_text().rstrip("\n"), str(python_root))
        self.assertFalse((self.tools / ".staging").exists())
        project_config = json.loads((self.project / "sentinel.config.json").read_text())
        self.assertEqual([item["language"] for item in project_config["modules"]], ["python"])

    def test_version_and_experimental_check_use_the_installed_bundle_and_pass_the_gate(self):
        python_root = fake_language_source(self.sources, "SENTINEL_PY")
        self.assertEqual(self.setup("--language", "python", "--crap-max", "9").returncode, 0)
        version = cli("version", "--project", str(self.project), "--tools", str(self.tools), "--format", "json")
        self.assertEqual(version.returncode, 0, version.stderr)
        self.assertEqual([item["status"] for item in json.loads(version.stdout)["results"]], ["ready"])

        check = cli("check", "--project", str(self.project), "--tools", str(self.tools), "--experimental", "--format", "json")
        self.assertEqual(check.returncode, 2, check.stderr)
        request = json.loads((python_root / "last-request.json").read_text())
        self.assertEqual(request["gate"], {"crapMax": "9", "mutationMin": "90"})
        self.assertEqual(request["projectRoot"], str(self.project))
        self.assertEqual(request["config"], str(self.project / "sentinel.config.json"))

        overridden = cli(
            "check", "--project", str(self.project), "--tools", str(self.tools), "--experimental",
            "--mutation-min", "80", "--format", "json",
        )
        self.assertEqual(overridden.returncode, 2, overridden.stderr)
        request = json.loads((python_root / "last-request.json").read_text())
        self.assertEqual(request["gate"], {"crapMax": "9", "mutationMin": "80"})

    def test_setup_is_idempotent_and_keeps_an_existing_project_config(self):
        fake_language_source(self.sources, "SENTINEL_PY")
        fake_language_source(self.sources, "SENTINEL_TS", version="0.2.0")
        (self.project / "api").mkdir()
        (self.project / "web").mkdir()
        preserved = self.project / "api" / "sentinel.config.json"
        preserved.write_text('{"specVersion":"1.0.0","modules":[]}\n')
        first = self.setup("--language", "python", "--language", "typescript",
                           "--module-root", "python=api", "--module-root", "typescript=web",
                           "--crap-max", "9", "--mutation-min", "80")
        self.assertEqual(first.returncode, 0, first.stderr)
        before = (self.project / "sentinel.workspace.json").read_text()
        second = self.setup("--language", "typescript", "--language", "python")
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(json.loads(second.stdout)["projectConfig"], "kept")
        after = json.loads((self.project / "sentinel.workspace.json").read_text())
        self.assertEqual(sorted(item["language"] for item in after["modules"]), ["python", "typescript"])
        self.assertEqual(json.loads(before)["gate"], after["gate"])
        self.assertEqual(json.loads(before)["modules"], after["modules"])
        self.assertEqual(preserved.read_text(), '{"specVersion":"1.0.0","modules":[]}\n')

    def test_python_requirements_are_installed_into_the_project_dependency_directory(self):
        python_root = fake_language_source(self.sources, "SENTINEL_PY")
        (self.project / "requirements.txt").write_text("freezegun==1.4.0\n", encoding="utf-8")
        completed = self.setup("--language", "python", "--python-requirements", "requirements.txt")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["results"][0]["pythonRequirements"], "requirements.txt")
        self.assertEqual((self.project / ".sentinel-deps" / "marker").read_text(), "installed\n")
        calls = (python_root / "deps.log").read_text().splitlines()
        target = str(self.project / ".sentinel-deps")
        requirements = str(self.project / "requirements.txt")
        self.assertEqual(calls, [f"deps {target} {requirements} --offline", f"deps {target} {requirements}"])
        self.assertIn("installing from the index online", completed.stderr)

        missing = self.setup("--language", "python", "--python-requirements", "absent.txt")
        self.assertEqual(missing.returncode, 5, missing.stdout)
        self.assertEqual(json.loads(missing.stdout)["results"][0]["status"], "requirementsFailed")
        wrong = self.setup("--language", "typescript", "--python-requirements", "requirements.txt")
        self.assertEqual(wrong.returncode, 3, wrong.stdout)

    def test_java_dependencies_are_warmed_into_the_project_maven_repository(self):
        java_root = fake_language_source(self.sources, "SENTINEL_JAVA")
        failed = self.setup("--language", "java", "--java-dependencies")
        self.assertEqual(failed.returncode, 5, failed.stdout)
        self.assertEqual(json.loads(failed.stdout)["results"][0]["status"], "dependenciesFailed")
        (self.project / "pom.xml").write_text("<project/>\n", encoding="utf-8")
        completed = self.setup("--language", "java", "--java-dependencies")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["results"][0]["javaDependencies"], ".sentinel-m2")
        self.assertEqual((self.project / ".sentinel-m2" / "marker").read_text(), "warmed\n")
        self.assertEqual((java_root / "maven.log").read_text().splitlines(), [f"deps {self.project}"] * 2)
        wrong = self.setup("--language", "python", "--java-dependencies")
        self.assertEqual(wrong.returncode, 3, wrong.stdout)

    def test_setup_without_a_language_prepares_the_three_plugin_languages(self):
        for repository in ("SENTINEL_PY", "SENTINEL_TS", "SENTINEL_JAVA"):
            fake_language_source(self.sources, repository)
        for directory in ("api", "web", "server"):
            (self.project / directory).mkdir()
        completed = self.setup("--module-root", "python=api", "--module-root", "typescript=web",
                               "--module-root", "java=server")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual([item["language"] for item in payload["results"]], ["java", "python", "typescript"])
        workspace_document = json.loads((self.project / "sentinel.workspace.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(module["language"] for module in workspace_document["modules"]), ["java", "python", "typescript"])
        plan = cli("plan", "--project", str(self.project), "--format", "json")
        self.assertEqual(plan.returncode, 0, plan.stderr)
        self.assertEqual(json.loads(plan.stdout)["moduleCount"], 3)
        for language, directory in (("python", "api"), ("typescript", "web")):
            config = json.loads((self.project / directory / "sentinel.config.json").read_text())
            self.assertEqual([item["language"] for item in config["modules"]], [language])
            self.assertEqual(config["modules"][0]["root"], ".")

    def test_invalid_module_layout_is_rejected_before_bootstrap_or_writes(self):
        python = fake_language_source(self.sources, "SENTINEL_PY")
        typescript = fake_language_source(self.sources, "SENTINEL_TS")
        (self.project / "api" / "nested").mkdir(parents=True)
        (self.project / "web").mkdir()
        (self.project / "linked").symlink_to(self.project / "api", target_is_directory=True)
        cases = [
            (),
            ("--module-root", "python=api"),
            ("--module-root", "python=api", "--module-root", "typescript=api"),
            ("--module-root", "python=api", "--module-root", "typescript=api/nested"),
            ("--module-root", "python=../outside", "--module-root", "typescript=web"),
            ("--module-root", "python=/tmp", "--module-root", "typescript=web"),
            ("--module-root", "python=missing", "--module-root", "typescript=web"),
            ("--module-root", "python=linked", "--module-root", "typescript=web"),
            ("--module-root", "python=api", "--module-root", "python=web"),
            ("--module-root", "unknown=api", "--module-root", "typescript=web"),
            ("--module-root", "java=api", "--module-root", "typescript=web"),
            ("--module-root", "python", "--module-root", "typescript=web"),
        ]
        for options in cases:
            with self.subTest(options=options):
                completed = self.setup("--language", "python", "--language", "typescript", *options)
                self.assertEqual(completed.returncode, 3, completed.stdout)
                self.assertFalse((python / "bootstrap.log").exists())
                self.assertFalse((typescript / "bootstrap.log").exists())
                self.assertFalse((self.project / "sentinel.workspace.json").exists())
                self.assertFalse(self.tools.exists())

    def test_explicit_roots_repair_a_workspace_generated_by_the_previous_setup(self):
        fake_language_source(self.sources, "SENTINEL_PY")
        fake_language_source(self.sources, "SENTINEL_TS")
        (self.project / "api").mkdir()
        (self.project / "web").mkdir()
        (self.project / "sentinel.config.json").write_text('{"specVersion":"1.0.0","modules":[]}\n')
        path = self.project / "sentinel.workspace.json"
        path.write_text(json.dumps({
            "schemaVersion": "sentinel-workspace-v1", "gate": {"crapMax": "9", "mutationMin": "80"},
            "modules": [{"id": language, "language": language, "root": ".", "config": "sentinel.config.json",
                         "toolVersion": "0.3.1", "toolDigest": "a" * 64} for language in ("python", "typescript")],
        }))
        completed = self.setup("--language", "python", "--language", "typescript",
                               "--module-root", "python=api", "--module-root", "typescript=web")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(path.read_text())["gate"], {"crapMax": "9", "mutationMin": "80"})
        plan = cli("plan", "--project", str(self.project), "--format", "json")
        self.assertEqual(plan.returncode, 0, plan.stderr)

    def test_project_and_workspace_config_ancestors_are_validated_before_bootstrap(self):
        python = fake_language_source(self.sources, "SENTINEL_PY")
        outside = self.base / "outside"
        outside.mkdir()
        (self.project / "linked").symlink_to(outside, target_is_directory=True)
        alias = self.base / "alias"
        alias.symlink_to(self.project, target_is_directory=True)
        for options in (("--config", "linked/workspace.json"), ("--project", str(alias)),
                        ("--config", "../outside/workspace.json"), ("--config", "missing/workspace.json")):
            with self.subTest(options=options):
                completed = self.setup("--language", "python", *options)
                self.assertEqual(completed.returncode, 3, completed.stdout)
                self.assertFalse((python / "bootstrap.log").exists())
                self.assertFalse((outside / "workspace.json").exists())
                self.assertFalse(self.tools.exists())

    def test_multiple_existing_modules_of_one_language_keep_their_roots(self):
        fake_language_source(self.sources, "SENTINEL_PY")
        for name in ("first", "second"):
            (self.project / name).mkdir()
        path = self.project / "sentinel.workspace.json"
        path.write_text(json.dumps({
            "schemaVersion": "sentinel-workspace-v1",
            "modules": [{"id": name, "language": "python", "root": name,
                         "toolVersion": "0.0.1", "toolDigest": "a" * 64} for name in ("first", "second")],
        }))
        completed = self.setup("--language", "python")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        modules = json.loads(path.read_text())["modules"]
        self.assertEqual([(item["id"], item["root"]) for item in modules], [("first", "first"), ("second", "second")])
        self.assertTrue(all(item["toolVersion"] == "0.3.1" for item in modules))
        before = path.read_bytes()
        rejected = self.setup("--language", "python", "--module-root", "python=first")
        self.assertEqual(rejected.returncode, 3)
        self.assertEqual(path.read_bytes(), before)

    def test_explicit_root_can_follow_a_renamed_module_directory(self):
        fake_language_source(self.sources, "SENTINEL_JAVA")
        (self.project / "api").mkdir()
        first = self.setup("--language", "java", "--module-root", "java=api")
        self.assertEqual(first.returncode, 0, first.stderr)
        (self.project / "api").rename(self.project / "backend")
        second = self.setup("--language", "java", "--module-root", "java=backend")
        self.assertEqual(second.returncode, 0, second.stderr)
        document = json.loads((self.project / "sentinel.workspace.json").read_text())
        self.assertEqual(document["modules"][0]["root"], "backend")
        self.assertEqual(cli("plan", "--project", str(self.project)).returncode, 0)

    def test_setup_keeps_workspace_edits_made_during_bootstrap(self):
        fake_language_source(self.sources, "SENTINEL_JAVA")
        self.assertEqual(self.setup("--language", "java").returncode, 0)
        path = self.project / "sentinel.workspace.json"
        newer = json.loads(path.read_text())
        newer["gate"]["crapMax"] = "17"
        newer_bytes = (json.dumps(newer, indent=4) + "\n").encode("utf-8")

        def concurrent_edit(*args):
            path.write_bytes(newer_bytes)
            return {"language": "java", "status": "installed", "toolVersion": "9.9.9", "toolDigest": "b" * 64}

        args = build_parser().parse_args(["setup", "--project", str(self.project), "--language", "java"])
        with patch("sentinel.setup._setup_language", side_effect=concurrent_edit):
            with self.assertRaises(SentinelError) as stopped:
                run_setup(args)
        self.assertEqual(stopped.exception.code, "workspaceChanged")
        self.assertEqual(path.read_bytes(), newer_bytes)

    def test_existing_module_identity_config_and_other_language_are_preserved(self):
        fake_language_source(self.sources, "SENTINEL_PY")
        fake_language_source(self.sources, "SENTINEL_TS")
        (self.project / "api").mkdir()
        (self.project / "web").mkdir()
        initial = self.setup("--language", "python", "--language", "typescript",
                             "--module-root", "python=api", "--module-root", "typescript=web")
        self.assertEqual(initial.returncode, 0, initial.stderr)
        path = self.project / "sentinel.workspace.json"
        document = json.loads(path.read_text())
        document["modules"][0]["id"] = "backend"
        document["modules"][0]["config"] = "custom.json"
        (self.project / "api" / "sentinel.config.json").rename(self.project / "api" / "custom.json")
        path.write_text(json.dumps(document))
        completed = self.setup("--language", "python")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(path.read_text()), document)
        self.assertFalse((self.project / "api" / "sentinel.config.json").exists())

    def test_dependencies_follow_the_explicit_language_roots(self):
        python = fake_language_source(self.sources, "SENTINEL_PY")
        java = fake_language_source(self.sources, "SENTINEL_JAVA")
        (self.project / "api").mkdir()
        (self.project / "server").mkdir()
        (self.project / "api" / "requirements.txt").write_text("example==1.0.0\n")
        (self.project / "server" / "pom.xml").write_text("<project/>\n")
        completed = self.setup("--language", "python", "--language", "java",
                               "--module-root", "python=api", "--module-root", "java=server",
                               "--python-requirements", "requirements.txt", "--java-dependencies")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertTrue((self.project / "api" / ".sentinel-deps" / "marker").is_file())
        self.assertTrue((self.project / "server" / ".sentinel-m2" / "marker").is_file())
        self.assertFalse((self.project / ".sentinel-deps").exists())
        self.assertEqual((java / "maven.log").read_text().strip(), f"deps {self.project / 'server'}")

    def test_bootstrap_failure_or_missing_source_is_a_dependency_error_without_configs(self):
        fake_language_source(self.sources, "SENTINEL_PY", setup_exit=1)
        completed = self.setup("--language", "python")
        self.assertEqual(completed.returncode, 5, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["results"][0]["status"], "bootstrapFailed")
        self.assertIsNone(payload["workspaceConfig"])
        self.assertFalse((self.project / "sentinel.workspace.json").exists())
        self.assertFalse((self.project / "sentinel.config.json").exists())

    def test_invalid_gate_and_unsupported_language_are_usage_errors(self):
        fake_language_source(self.sources, "SENTINEL_PY")
        self.assertEqual(self.setup("--language", "python", "--crap-max", "8.").returncode, 3)
        self.assertEqual(self.setup("--language", "clojure").returncode, 3)
        self.assertFalse((self.project / "sentinel.workspace.json").exists())


if __name__ == "__main__":
    unittest.main()
