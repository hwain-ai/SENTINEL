import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from test_cli import SRC_ROOT, cli, install_bundle, make_bundle, module, workspace, write_json
from test_changed import git

sys.path.insert(0, SRC_ROOT)

from sentinel.admission import (  # noqa: E402
    ADMISSION_SCHEMA,
    Admission,
    is_admitted,
    load_admissions,
    parse_admissions,
    render_admissions,
)
from sentinel.bundle import Bundle  # noqa: E402
from sentinel.errors import SentinelError  # noqa: E402


def entry(language="python", version="1.2.3", digest="b" * 64, **overrides):
    value = {
        "language": language,
        "toolVersion": version,
        "entrypointSha256": digest,
        "source": {"repository": "hwain-ai/SENTINEL_PY", "commit": "c" * 40},
        "ci": {"workflow": "ci", "runUrl": "https://github.com/hwain-ai/SENTINEL_PY/actions/runs/1"},
        "admittedAt": "2026-09-13",
    }
    value.update(overrides)
    return value


def document(*entries):
    return {"schemaVersion": ADMISSION_SCHEMA, "admitted": list(entries)}


class AdmissionParsingTests(unittest.TestCase):
    def test_parses_entries_and_renders_them_sorted_and_stable(self):
        admissions = parse_admissions(document(entry(language="typescript"), entry()))
        self.assertEqual([item.language for item in admissions], ["typescript", "python"])
        rendered = render_admissions(admissions)
        self.assertEqual([item["language"] for item in json.loads(rendered)["admitted"]], ["python", "typescript"])
        self.assertEqual(render_admissions(parse_admissions(json.loads(rendered))), rendered)

    def test_rejects_shape_and_format_errors(self):
        cases = {
            "schema": {"schemaVersion": "other", "admitted": []},
            "extra field": document(entry(extra=1)),
            "language": document(entry(language="go")),
            "version": document(entry(version="1.2")),
            "digest": document(entry(digest="B" * 64)),
            "commit": document(entry(source={"repository": "hwain-ai/SENTINEL_PY", "commit": "short"})),
            "repository": document(entry(source={"repository": "nope", "commit": "c" * 40})),
            "run url": document(entry(ci={"workflow": "ci", "runUrl": "https://example.com/1"})),
            "date": document(entry(admittedAt="2026/09/13")),
            "duplicate": document(entry(), entry()),
        }
        for label, value in cases.items():
            with self.subTest(label=label):
                with self.assertRaises(SentinelError) as stopped:
                    parse_admissions(value)
                self.assertEqual(stopped.exception.code, "admissionInvalid")
                self.assertEqual(stopped.exception.exit_code, 3)

    def test_matches_a_bundle_by_language_version_and_entrypoint_digest(self):
        admissions = parse_admissions(document(entry(digest="d" * 64)))
        bundle = Bundle(Path("/x"), "python", "1.2.3", "e" * 64, "bin/sentinel-tool", {"bin/sentinel-tool": "d" * 64, "home": "f" * 64})
        self.assertTrue(is_admitted(admissions, bundle))
        self.assertFalse(is_admitted(admissions, Bundle(Path("/x"), "python", "1.2.4", "e" * 64, "bin/sentinel-tool", {"bin/sentinel-tool": "d" * 64})))
        self.assertFalse(is_admitted(admissions, Bundle(Path("/x"), "python", "1.2.3", "e" * 64, "bin/sentinel-tool", {"bin/sentinel-tool": "0" * 64})))
        self.assertFalse(is_admitted(admissions, Bundle(Path("/x"), "typescript", "1.2.3", "e" * 64, "bin/sentinel-tool", {"bin/sentinel-tool": "d" * 64})))

    def test_packaged_admission_file_is_valid(self):
        admissions = load_admissions()
        for item in admissions:
            self.assertIsInstance(item, Admission)


class AdmittedCheckTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.project = self.base / "project"
        self.project.mkdir()
        (self.project / "one").mkdir()
        (self.project / "two").mkdir()
        self.tools = self.base / "tools"
        self.admission = self.base / "admission.json"

    def tearDown(self):
        self.temporary.cleanup()

    def install(self, language, behavior="pass"):
        bundle, digest, _ = make_bundle(self.base, language=language, behavior=behavior)
        completed = install_bundle(bundle, digest, self.tools)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        entrypoint = hashlib.sha256((bundle / "bin" / "sentinel-tool").read_bytes()).hexdigest()
        return digest, entrypoint

    def run_command(self, command, *extra):
        return cli(command, "--project", str(self.project), "--tools", str(self.tools), "--admission", str(self.admission), "--format", "json", *extra)

    def test_admitted_bundle_reports_a_successful_full_check(self):
        digest, entrypoint = self.install("python")
        write_json(self.admission, document(entry(digest=entrypoint)))
        workspace(self.project, [module("one", "python", "one", digest=digest)])

        doctor = json.loads(self.run_command("doctor").stdout)
        self.assertEqual(doctor["results"][0]["admitted"], True)

        completed = self.run_command("check")
        payload = json.loads(completed.stdout)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(payload["results"][0]["status"], "passed")
        self.assertEqual(payload["results"][0]["admitted"], True)
        self.assertEqual(payload["exitCode"], 0)
        self.assertEqual(payload["schemaVersion"], "sentinel-workspace-result-v2")
        self.assertEqual(set(payload), {"schemaVersion", "command", "selection", "moduleCount", "results", "exitCode"})
        self.assertEqual(payload["selection"], "allConfigured")
        self.assertNotIn("certified", payload)
        self.assertEqual((self.base / "python-count").read_text(), "1")

    def test_unadmitted_bundle_never_starts_and_admitted_sibling_still_runs(self):
        python_digest, python_entrypoint = self.install("python")
        typescript_digest, _ = self.install("typescript")
        write_json(self.admission, document(entry(digest=python_entrypoint)))
        workspace(self.project, [module("one", "python", "one", digest=python_digest), module("two", "typescript", "two", digest=typescript_digest)])

        doctor = json.loads(self.run_command("doctor").stdout)
        self.assertEqual([item["admitted"] for item in doctor["results"]], [True, False])

        completed = self.run_command("check")
        payload = json.loads(completed.stdout)
        self.assertEqual(completed.returncode, 6)
        self.assertEqual([item["status"] for item in payload["results"]], ["passed", "backendNotAdmitted"])
        self.assertNotEqual(payload["exitCode"], 0)
        self.assertNotIn("certified", payload)
        self.assertEqual((self.base / "python-count").read_text(), "1")
        self.assertFalse((self.base / "typescript-count").exists())

        experimental = json.loads(self.run_command("check", "--experimental").stdout)
        self.assertEqual([item["status"] for item in experimental["results"]], ["passed", "passed"])
        self.assertNotIn("certified", experimental)
        self.assertEqual(experimental["exitCode"], 6)

    def test_quality_failure_is_a_command_failure_with_a_quality_verdict(self):
        digest, entrypoint = self.install("python", behavior="quality_failed")
        write_json(self.admission, document(entry(digest=entrypoint)))
        workspace(self.project, [module("one", "python", "one", digest=digest)])
        completed = self.run_command("check")
        payload = json.loads(completed.stdout)
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(payload["results"][0]["status"], "qualityFailed")
        self.assertEqual(payload["results"][0]["admitted"], True)
        self.assertNotEqual(payload["exitCode"], 0)
        self.assertNotIn("certified", payload)

    def test_changed_mode_is_partial_even_when_every_module_was_checked(self):
        python_digest, python_entrypoint = self.install("python")
        typescript_digest, typescript_entrypoint = self.install("typescript")
        write_json(self.admission, document(entry(digest=python_entrypoint),
                                           entry(language="typescript", digest=typescript_entrypoint)))
        workspace(self.project, [module("one", "python", "one", digest=python_digest),
                                 module("two", "typescript", "two", digest=typescript_digest)])
        (self.project / "one" / "source.py").write_text("x = 1\n")
        (self.project / "two" / "source.ts").write_text("const x = 1;\n")
        git(self.project, "init", "-q", "-b", "main")
        git(self.project, "add", ".")
        git(self.project, "commit", "-q", "-m", "base")
        unchanged = self.run_command("check", "--changed")
        payload = json.loads(unchanged.stdout)
        self.assertEqual(unchanged.returncode, 0, unchanged.stderr)
        self.assertEqual(payload["exitCode"], 0)
        self.assertNotIn("certified", payload)
        self.assertEqual([item["status"] for item in payload["results"]], ["noChanges", "noChanges"])
        self.assertEqual(payload["selection"], "partial")
        self.assertFalse((self.base / "python-count").exists())
        self.assertFalse((self.base / "typescript-count").exists())

        (self.project / "one" / "source.py").write_text("x = 2\n")
        mixed = self.run_command("check", "--changed")
        payload = json.loads(mixed.stdout)
        self.assertEqual(mixed.returncode, 0, mixed.stderr)
        self.assertEqual(payload["exitCode"], 0)
        self.assertNotIn("certified", payload)
        self.assertEqual([item["status"] for item in payload["results"]], ["passed", "noChanges"])
        self.assertEqual(payload["selection"], "partial")
        self.assertFalse((self.base / "typescript-count").exists())

        (self.project / "two" / "source.ts").write_text("const x = 2;\n")
        checked = self.run_command("check", "--changed")
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertEqual(json.loads(checked.stdout)["selection"], "partial")

    def test_module_selected_success_reports_partial_scope(self):
        digest, entrypoint = self.install("python")
        write_json(self.admission, document(entry(digest=entrypoint)))
        workspace(self.project, [module("one", "python", "one", digest=digest),
                                 module("two", "python", "two", digest=digest)])
        completed = self.run_command("check", "--module", "one")
        payload = json.loads(completed.stdout)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(payload["selection"], "partial")
        self.assertEqual(payload["results"][0]["status"], "passed")
        self.assertNotIn("certified", payload)

    def test_adapter_can_report_that_changed_files_contain_no_production_code(self):
        digest, entrypoint = self.install("python", behavior="no_changes")
        write_json(self.admission, document(entry(digest=entrypoint)))
        workspace(self.project, [module("one", "python", "one", digest=digest)])
        git(self.project, "init", "-q", "-b", "main")
        git(self.project, "add", ".")
        git(self.project, "commit", "-q", "-m", "base")
        (self.project / "one" / "README.md").write_text("Documentation change\n")
        completed = self.run_command("check", "--changed")
        payload = json.loads(completed.stdout)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(payload["results"][0]["status"], "noChanges")
        self.assertEqual(payload["exitCode"], 0)
        self.assertNotIn("certified", payload)
        self.assertEqual((self.base / "python-count").read_text(), "1")

        full = self.run_command("check")
        self.assertEqual(full.returncode, 6, full.stderr)
        self.assertEqual(json.loads(full.stdout)["results"][0]["status"], "backendError")

    def test_invalid_admission_file_is_a_usage_error_before_any_child(self):
        digest, _ = self.install("python")
        self.admission.write_text('{"schemaVersion":"sentinel-admission-v1","admitted":[{}]}', encoding="utf-8")
        workspace(self.project, [module("one", "python", "one", digest=digest)])
        completed = self.run_command("check")
        self.assertEqual(completed.returncode, 3)
        self.assertIn("admissionInvalid", completed.stderr)
        self.assertFalse((self.base / "python-count").exists())


if __name__ == "__main__":
    unittest.main()
