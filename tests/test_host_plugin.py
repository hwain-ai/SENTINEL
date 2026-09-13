import json
import os
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_cli import SRC_ROOT, install_bundle, make_bundle, module, workspace


REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "plugins" / "sentinel"
SKILL_PATH = PLUGIN_ROOT / "skills" / "sentinel" / "SKILL.md"


def command_templates(plugin_root=PLUGIN_ROOT):
    skill_path = plugin_root / "skills" / "sentinel" / "SKILL.md"
    if not skill_path.is_file():
        raise AssertionError("Shared SENTINEL skill is missing")
    commands = {}
    for line in skill_path.read_text(encoding="utf-8").splitlines():
        if not line.startswith('"$SENTINEL_EXECUTABLE" '):
            continue
        arguments = shlex.split(line)
        if len(arguments) > 1:
            if arguments[1] in commands:
                raise AssertionError(f"Duplicate documented command template: {arguments[1]}")
            commands[arguments[1]] = arguments
    return commands


def run_template(template, project, *extra):
    arguments = []
    for argument in template:
        if argument == "$SENTINEL_EXECUTABLE":
            arguments.extend((sys.executable, "-m", "sentinel"))
        elif argument == "$SENTINEL_PROJECT":
            arguments.append(str(project))
        elif argument == "$SENTINEL_LANGUAGE":
            arguments.append("python")
        else:
            arguments.append(argument)
    arguments.extend(extra)
    environment = os.environ.copy()
    environment["PYTHONPATH"] = SRC_ROOT
    return subprocess.run(
        arguments,
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


class HostPluginStructureTests(unittest.TestCase):
    def test_two_host_manifests_share_one_skill(self):
        manifests = (
            PLUGIN_ROOT / ".codex-plugin" / "plugin.json",
            PLUGIN_ROOT / ".claude-plugin" / "plugin.json",
        )
        for manifest_path in manifests:
            with self.subTest(manifest=manifest_path.parent.name):
                self.assertTrue(manifest_path.is_file(), f"{manifest_path.parent.name} plugin package is missing")
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                self.assertEqual(manifest["name"], "sentinel")
                self.assertEqual(manifest["version"], "0.1.0")
                self.assertEqual(manifest["skills"], "./skills/")
        self.assertTrue(SKILL_PATH.is_file(), "Shared SENTINEL skill is missing")

    def test_user_facing_descriptions_and_starter_prompts_are_korean(self):
        for host in (".codex-plugin", ".claude-plugin"):
            manifest = json.loads((PLUGIN_ROOT / host / "plugin.json").read_text(encoding="utf-8"))
            with self.subTest(host=host):
                self.assertRegex(manifest["description"], "[가-힣]")
        interface = json.loads((PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))["interface"]
        for field in ("shortDescription", "longDescription"):
            self.assertRegex(interface[field], "[가-힣]")
        prompts = interface["defaultPrompt"]
        self.assertIsInstance(prompts, list)
        self.assertTrue(1 <= len(prompts) <= 3)
        for prompt in prompts:
            self.assertLessEqual(len(prompt), 128)
            self.assertRegex(prompt, "[가-힣]")
        for capability in interface["capabilities"]:
            self.assertRegex(capability, "[가-힣]")

    def test_skill_exposes_exactly_four_portable_command_templates(self):
        commands = command_templates()
        self.assertEqual(set(commands), {"plan", "doctor", "check", "setup"})
        for command in ("plan", "doctor", "check"):
            with self.subTest(command=command):
                self.assertEqual(
                    commands[command],
                    [
                        "$SENTINEL_EXECUTABLE",
                        command,
                        "--project",
                        "$SENTINEL_PROJECT",
                        "--format",
                        "json",
                    ],
                )
        self.assertEqual(
            commands["setup"],
            [
                "$SENTINEL_EXECUTABLE",
                "setup",
                "--project",
                "$SENTINEL_PROJECT",
                "--language",
                "$SENTINEL_LANGUAGE",
                "--format",
                "json",
            ],
        )

    def test_duplicate_documented_command_templates_are_rejected(self):
        skill_lines = SKILL_PATH.read_text(encoding="utf-8").splitlines()
        for command in ("plan", "doctor", "check", "setup"):
            with self.subTest(command=command), tempfile.TemporaryDirectory() as directory:
                copied = Path(directory) / "sentinel"
                shutil.copytree(PLUGIN_ROOT, copied)
                command_line = next(
                    line
                    for line in skill_lines
                    if line.startswith('"$SENTINEL_EXECUTABLE" ') and shlex.split(line)[1:2] == [command]
                )
                copied_skill = copied / "skills" / "sentinel" / "SKILL.md"
                with copied_skill.open("a", encoding="utf-8") as stream:
                    stream.write(f"\n{command_line}\n")
                with self.assertRaises(AssertionError):
                    command_templates(copied)


class HostPluginCommandContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.project = self.base / "project"
        self.project.mkdir()
        (self.project / "api").mkdir()
        (self.project / "web").mkdir()
        self.tools = self.base / "tools"
        self.commands = command_templates()

    def tearDown(self):
        self.temporary.cleanup()

    def configure_two_modules(self, *, install_python=True, install_typescript=True):
        python_bundle, python_digest, python_counter = make_bundle(self.base, language="python")
        typescript_bundle, typescript_digest, typescript_counter = make_bundle(self.base, language="typescript")
        if install_python:
            completed = install_bundle(python_bundle, python_digest, self.tools)
            self.assertEqual(completed.returncode, 0, completed.stderr)
        if install_typescript:
            completed = install_bundle(typescript_bundle, typescript_digest, self.tools)
            self.assertEqual(completed.returncode, 0, completed.stderr)
        workspace(
            self.project,
            [
                module("api", "python", "api", digest=python_digest),
                module("web", "typescript", "web", digest=typescript_digest),
            ],
        )
        return python_digest, typescript_digest, python_counter, typescript_counter

    def run_command(self, command, *extra):
        return run_template(
            self.commands[command],
            self.project,
            "--tools",
            str(self.tools),
            *extra,
        )

    def test_plan_reports_all_configured_without_certification(self):
        self.configure_two_modules(install_python=False, install_typescript=False)
        completed = self.run_command("plan")
        payload = json.loads(completed.stdout)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(payload["selection"], "allConfigured")
        self.assertEqual(payload["moduleCount"], 2)
        self.assertEqual([item["status"] for item in payload["results"]], ["planned", "planned"])
        self.assertFalse(payload["certified"])

    def test_doctor_reports_installed_tools_ready_but_not_certified(self):
        _, _, python_counter, typescript_counter = self.configure_two_modules()
        completed = self.run_command("doctor")
        payload = json.loads(completed.stdout)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual([item["status"] for item in payload["results"]], ["ready", "ready"])
        self.assertTrue(payload["pass"])
        self.assertFalse(payload["certified"])
        self.assertFalse(python_counter.exists())
        self.assertFalse(typescript_counter.exists())

    def test_default_check_refuses_unadmitted_backends_without_execution(self):
        _, _, python_counter, typescript_counter = self.configure_two_modules()
        completed = self.run_command("check")
        payload = json.loads(completed.stdout)
        self.assertEqual(completed.returncode, 6, completed.stderr)
        self.assertEqual(payload["selection"], "allConfigured")
        self.assertEqual(
            [item["status"] for item in payload["results"]],
            ["backendNotAdmitted", "backendNotAdmitted"],
        )
        self.assertFalse(payload["pass"])
        self.assertFalse(payload["certified"])
        self.assertFalse(python_counter.exists())
        self.assertFalse(typescript_counter.exists())

    def test_missing_tool_is_dependency_error_without_execution(self):
        _, _, python_counter, typescript_counter = self.configure_two_modules(install_typescript=False)
        completed = self.run_command("check")
        payload = json.loads(completed.stdout)
        self.assertEqual(completed.returncode, 5, completed.stderr)
        self.assertEqual([item["status"] for item in payload["results"]], ["ready", "dependencyError"])
        self.assertFalse(payload["pass"])
        self.assertFalse(payload["certified"])
        self.assertFalse(python_counter.exists())
        self.assertFalse(typescript_counter.exists())

    def test_corrupt_tool_is_dependency_error_without_execution(self):
        _, typescript_digest, python_counter, typescript_counter = self.configure_two_modules()
        entrypoint = self.tools / "typescript" / "1.2.3" / typescript_digest / "bin" / "sentinel-tool"
        entrypoint.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP)
        completed = self.run_command("check")
        payload = json.loads(completed.stdout)
        self.assertEqual(completed.returncode, 5, completed.stderr)
        self.assertEqual([item["status"] for item in payload["results"]], ["ready", "dependencyError"])
        self.assertFalse(python_counter.exists())
        self.assertFalse(typescript_counter.exists())

    def test_language_selector_is_partial_and_returns_only_requested_module(self):
        self.configure_two_modules(install_python=False, install_typescript=False)
        completed = self.run_command("plan", "--language", "typescript")
        payload = json.loads(completed.stdout)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(payload["selection"], "partial")
        self.assertEqual(
            payload["results"],
            [{"moduleId": "web", "language": "typescript", "status": "planned", "exitCode": 0}],
        )
        self.assertFalse(payload["certified"])

    def test_relocated_plugin_and_project_paths_with_spaces_keep_argument_boundaries(self):
        relocated = self.base / "relocated plugin with spaces"
        shutil.copytree(PLUGIN_ROOT, relocated)
        project = self.base / "project with spaces"
        project.mkdir()
        (project / "api").mkdir()
        workspace(project, [module("api", "python", "api")])
        commands = command_templates(relocated)
        completed = run_template(commands["plan"], project)
        payload = json.loads(completed.stdout)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(payload["moduleCount"], 1)
        self.assertEqual(payload["results"][0]["moduleId"], "api")


if __name__ == "__main__":
    unittest.main()
