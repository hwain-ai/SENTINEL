import json
import os
import stat
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from test_cli import cli


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
        "#!/usr/bin/bash\n"
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
        "#!/usr/bin/bash\n"
        "printf '%s\\n' \"$*\" >> \"$(dirname \"$0\")/../deps.log\"\n"
        "[ \"$1\" = deps ] || exit 2\n"
        "[ \"$4\" = --offline ] && exit 1\n"
        "mkdir -p \"$2\" && printf 'installed\\n' > \"$2/marker\"\n",
        encoding="utf-8",
    )
    launcher.chmod(0o700)
    maven = scripts / "mvn.sh"
    maven.write_text(
        "#!/usr/bin/bash\n"
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
            "--format",
            "json",
            *extra,
        )

    def test_setup_bootstraps_sources_installs_bundles_and_writes_both_configs(self):
        python_root = fake_language_source(self.sources, "SENTINEL_PY")
        completed = self.setup("--language", "python", "--crap-max", "10", "--mutation-min", "90")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["pass"])
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

    def test_doctor_and_experimental_check_use_the_installed_bundle_and_pass_the_gate(self):
        python_root = fake_language_source(self.sources, "SENTINEL_PY")
        self.assertEqual(self.setup("--language", "python", "--crap-max", "9").returncode, 0)
        doctor = cli("doctor", "--project", str(self.project), "--tools", str(self.tools), "--format", "json")
        self.assertEqual(doctor.returncode, 0, doctor.stderr)
        self.assertEqual([item["status"] for item in json.loads(doctor.stdout)["results"]], ["ready"])

        check = cli("check", "--project", str(self.project), "--tools", str(self.tools), "--experimental", "--format", "json")
        self.assertEqual(check.returncode, 2, check.stderr)
        request = json.loads((python_root / "last-request.json").read_text())
        self.assertEqual(request["gate"], {"crapMax": "9", "mutationMin": "100"})
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
        (self.project / "sentinel.config.json").write_text('{"specVersion":"1.0.0","modules":[]}\n')
        first = self.setup("--language", "python", "--language", "typescript")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(json.loads(first.stdout)["projectConfig"], "kept")
        before = (self.project / "sentinel.workspace.json").read_text()
        second = self.setup("--language", "typescript", "--language", "python")
        self.assertEqual(second.returncode, 0, second.stderr)
        after = json.loads((self.project / "sentinel.workspace.json").read_text())
        self.assertEqual(sorted(item["language"] for item in after["modules"]), ["python", "typescript"])
        self.assertEqual(json.loads(before)["gate"], after["gate"])
        self.assertEqual((self.project / "sentinel.config.json").read_text(), '{"specVersion":"1.0.0","modules":[]}\n')

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
