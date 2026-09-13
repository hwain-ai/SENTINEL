import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_cli import cli, install_bundle, make_bundle, module, workspace
from test_setup import TOOL_SCRIPT


GIT_ENV = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "HOME": "/nonexistent"}


def git(cwd, *arguments):
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false", *arguments],
        cwd=str(cwd), env=GIT_ENV, check=True, stdin=subprocess.DEVNULL, capture_output=True,
    )


def recording_bundle(parent, language):
    """A tool that records its request next to the bundle and reports qualityFailed."""
    bundle = parent / (language + "-recording-bundle")
    bundle.mkdir()
    entrypoint = bundle / "sentinel-tool"
    entrypoint.write_text(TOOL_SCRIPT, encoding="utf-8")
    entrypoint.chmod(0o700)
    home = parent / (language + "-home")
    home.mkdir()
    (bundle / "home").write_text(str(home) + "\n", encoding="utf-8")
    import hashlib
    files = {name: hashlib.sha256((bundle / name).read_bytes()).hexdigest() for name in ("sentinel-tool", "home")}
    manifest = {
        "schemaVersion": "sentinel-tool-bundle-v1", "protocolVersion": "sentinel-tool-protocol-v1",
        "language": language, "version": "1.2.3", "entrypoint": "sentinel-tool", "files": files,
    }
    (bundle / "sentinel-tool.json").write_text(json.dumps(manifest), encoding="utf-8")
    digest = hashlib.sha256((bundle / "sentinel-tool.json").read_bytes()).hexdigest()
    return bundle, digest, home


class ChangedModeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.project = self.base / "project"
        (self.project / "api" / "src").mkdir(parents=True)
        (self.project / "web" / "src").mkdir(parents=True)
        self.tools = self.base / "tools"
        (self.project / "api" / "src" / "a.py").write_text("A = 1\n")
        (self.project / "web" / "src" / "w.ts").write_text("export const w = 1;\n")
        git(self.project, "init", "-q", "-b", "main")
        git(self.project, "add", ".")
        git(self.project, "commit", "-q", "-m", "base")
        python_bundle, python_digest, self.python_home = recording_bundle(self.base, "python")
        typescript_bundle, typescript_digest, self.typescript_home = recording_bundle(self.base, "typescript")
        for bundle, digest in ((python_bundle, python_digest), (typescript_bundle, typescript_digest)):
            completed = install_bundle(bundle, digest, self.tools)
            self.assertEqual(completed.returncode, 0, completed.stderr)
        workspace(self.project, [
            module("api", "python", "api", digest=python_digest),
            module("web", "typescript", "web", digest=typescript_digest),
        ])

    def tearDown(self):
        self.temporary.cleanup()

    def check(self, *extra):
        return cli("check", "--project", str(self.project), "--tools", str(self.tools), "--experimental",
                   "--changed", "--format", "json", *extra)

    def request(self, home):
        return json.loads((home / "last-request.json").read_text())

    def test_only_modules_with_changes_run_and_receive_module_relative_paths(self):
        (self.project / "api" / "src" / "a.py").write_text("A = 2\n")
        (self.project / "api" / "src" / "new.py").write_text("B = 1\n")
        completed = self.check()
        payload = json.loads(completed.stdout)
        self.assertEqual(completed.returncode, 2, completed.stderr)
        self.assertEqual(
            [(item["moduleId"], item["status"], item["exitCode"]) for item in payload["results"]],
            [("api", "qualityFailed", 2), ("web", "noChanges", 0)],
        )
        self.assertEqual(self.request(self.python_home)["changedFiles"], ["src/a.py", "src/new.py"])
        self.assertFalse((self.typescript_home / "last-request.json").exists())

    def test_base_ref_selects_committed_changes_and_deleted_files_are_skipped(self):
        (self.project / "web" / "src" / "w.ts").write_text("export const w = 2;\n")
        (self.project / "api" / "src" / "a.py").unlink()
        git(self.project, "add", "-A")
        git(self.project, "commit", "-q", "-m", "second")
        clean = self.check()
        self.assertEqual([item["status"] for item in json.loads(clean.stdout)["results"]], ["noChanges", "noChanges"])
        against_base = self.check("--changed-base", "HEAD~1")
        payload = json.loads(against_base.stdout)
        self.assertEqual([item["status"] for item in payload["results"]], ["noChanges", "qualityFailed"])
        self.assertEqual(self.request(self.typescript_home)["changedFiles"], ["src/w.ts"])

    def test_without_changed_flag_the_request_carries_no_change_list(self):
        completed = cli("check", "--project", str(self.project), "--tools", str(self.tools), "--experimental",
                        "--format", "json")
        self.assertEqual(completed.returncode, 2, completed.stderr)
        self.assertNotIn("changedFiles", self.request(self.python_home))

    def test_outside_a_git_work_tree_or_bad_base_is_a_usage_error(self):
        bad = self.check("--changed-base", "--not-a-ref")
        self.assertEqual(bad.returncode, 3, bad.stdout)
        missing = self.check("--changed-base", "no-such-ref")
        self.assertEqual(missing.returncode, 3, missing.stdout)
        subprocess.run(["rm", "-rf", str(self.project / ".git")], check=True)
        outside = self.check()
        self.assertEqual(outside.returncode, 3, outside.stdout)
        self.assertFalse((self.python_home / "last-request.json").exists())


if __name__ == "__main__":
    unittest.main()
