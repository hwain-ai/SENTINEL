"""Exercise the standalone documentation gate against real temporary Git repos."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "docs_lint.py"
ZERO = "0" * 40


class DocsLintTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.git("init", "-q")
        self.git("config", "user.name", "Docs Test")
        self.git("config", "user.email", "docs@example.invalid")
        self.git("config", "core.autocrlf", "false")
        self.write("src/check.py", "value = 1\n")
        self.write("README.md", "# Usage\n\n[Reference](docs/reference.md)\n")
        self.write("docs/reference.md", "# Reference\n\nThe current value is 1.\n")
        self.write("docs/unrelated.md", "# Other documentation\n")
        self.manifest = {
            "version": 1,
            "documents": [
                {"path": "README.md", "summary": "설치와 실행 안내"},
                {"path": "docs/reference.md", "summary": "검사 명령과 결과"},
                {"path": "docs/unrelated.md", "summary": "별도 안내"},
            ],
            "rules": [{"id": "checker", "sources": ["src/**/*.py"], "documents": ["docs/reference.md"]}],
            "ignoreDocuments": ["third_party/**"],
        }
        self.save_manifest()
        self.run_lint("--write-index", expect=0)
        self.base = self.commit("initial")

    def write(self, path, text):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(text.encode("utf-8"))

    def save_manifest(self):
        self.write("docs/manifest.json", json.dumps(self.manifest, ensure_ascii=False))

    def git(self, *args):
        result = subprocess.run(
            ["git", "-c", "safe.directory=" + self.root.as_posix(), "-C", str(self.root), *args],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull},
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
        return result.stdout.decode("utf-8").strip()

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-qm", message)
        return self.git("rev-parse", "HEAD")

    def run_lint(self, *args, expect, stdin=None, environment=None):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(self.root), *args],
            input=stdin, encoding="utf-8", stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env={**os.environ, **(environment or {})},
        )
        self.assertEqual(result.returncode, expect, result.stdout + result.stderr)
        return result.stdout + result.stderr

    def source_edit(self):
        self.write("src/check.py", "value = 2\n")

    def doc_edit(self):
        self.write("docs/reference.md", "# Reference\n\nThe current value is 2.\n")

    def ci_environment(self, **overrides):
        return {
            "DOCS_EVENT": "push", "DOCS_BASE": self.base, "DOCS_HEAD": self.base,
            "DOCS_REF": "refs/heads/topic", "DOCS_DEFAULT_BRANCH": "main",
            "DOCS_DELETED": "false", **overrides,
        }

    def test_structure_and_unchanged_base_pass(self):
        self.run_lint("--check", expect=0)
        self.run_lint("--base", self.base, expect=0)

    def test_code_only_change_reports_exact_related_document(self):
        self.source_edit()
        output = self.run_lint("--base", self.base, expect=1)
        self.assertIn("src/check.py -> update at least one related document: docs/reference.md", output)

    def test_related_document_edit_passes(self):
        self.source_edit()
        self.doc_edit()
        self.run_lint("--base", self.base, expect=0)

    def test_unrelated_document_edit_does_not_pass(self):
        self.source_edit()
        self.write("docs/unrelated.md", "# Updated other documentation\n")
        self.run_lint("--base", self.base, expect=1)

    def test_source_rename_checks_old_path(self):
        self.git("mv", "src/check.py", "outside.py")
        output = self.run_lint("--base", self.base, expect=1)
        self.assertIn("src/check.py", output)
        self.doc_edit()
        self.run_lint("--base", self.base, expect=0)

    def test_source_deletion_requires_document_update(self):
        (self.root / "src/check.py").unlink()
        self.run_lint("--base", self.base, expect=1)
        self.doc_edit()
        self.run_lint("--base", self.base, expect=0)

    def test_untracked_source_is_checked(self):
        self.write("src/new.py", "value = 3\n")
        output = self.run_lint("--base", self.base, expect=1)
        self.assertIn("src/new.py", output)

    def test_staged_change_is_checked(self):
        self.source_edit()
        self.git("add", "src/check.py")
        self.run_lint("--base", self.base, expect=1)

    def test_untracked_document_must_be_registered(self):
        self.write("notes.md", "# Notes\n")
        output = self.run_lint("--check", expect=1)
        self.assertIn("Document is not indexed: notes.md", output)

    def test_ignored_and_third_party_documents_are_excluded(self):
        self.write(".gitignore", "private/\n")
        self.write("private/notes.md", "# Private notes\n")
        self.write("third_party/vendor/README.md", "# Dependency\n")
        self.run_lint("--check", expect=0)

    def test_stale_index_fails_and_regeneration_is_idempotent(self):
        self.manifest["documents"][0]["summary"] = "수정된 설치 안내"
        self.save_manifest()
        self.assertIn("docs/index.md is stale", self.run_lint("--check", expect=1))
        self.run_lint("--write-index", "--check", expect=0)
        first = (self.root / "docs/index.md").read_bytes()
        self.run_lint("--write-index", expect=0)
        self.assertEqual(first, (self.root / "docs/index.md").read_bytes())

    def test_index_only_edit_does_not_count_as_document_update(self):
        self.source_edit()
        self.manifest["documents"][0]["summary"] = "새 요약"
        self.save_manifest()
        self.run_lint("--write-index", expect=0)
        self.assertIn("update at least one", self.run_lint("--base", self.base, expect=1))

    def test_broken_links_fail_but_code_and_external_links_are_ignored(self):
        self.write("README.md", "# Usage\n[Bad](docs/missing.md)\n")
        self.assertIn("broken local link: docs/missing.md", self.run_lint("--check", expect=1))
        self.write("README.md", "# Usage\n[Web](https://example.invalid/no.md)\n[Here](#heading)\n`[Example](missing.md)`\n```markdown\n[Example](missing.md)\n```\n")
        self.run_lint("--check", expect=0)

    def test_reference_links_and_encoded_paths_are_checked(self):
        self.write("file with spaces.txt", "target")
        self.write("README.md", "# Usage\n[File](file%20with%20spaces.txt)\n[Reference][ref]\n\n[ref]: docs/absent.md \"Title\"\n")
        self.assertIn("docs/absent.md", self.run_lint("--check", expect=1))

    def test_duplicate_document_and_invalid_mapping_fail(self):
        self.manifest["documents"].append(dict(self.manifest["documents"][0]))
        self.save_manifest()
        self.assertIn("Duplicate document", self.run_lint("--check", expect=1))
        self.manifest["documents"].pop()
        self.manifest["rules"][0]["documents"] = ["docs/index.md"]
        self.save_manifest()
        self.assertIn("unmapped document", self.run_lint("--check", expect=1))

    def test_removed_rule_cannot_bypass_old_mapping(self):
        self.source_edit()
        self.manifest["rules"] = []
        self.save_manifest()
        self.run_lint("--write-index", expect=0)
        self.assertIn("[checker]", self.run_lint("--base", self.base, expect=1))

    def test_line_ending_conversion_does_not_count_as_doc_edit(self):
        self.source_edit()
        target = self.root / "docs/reference.md"
        target.write_bytes(target.read_bytes().replace(b"\n", b"\r\n"))
        self.assertIn("update at least one", self.run_lint("--base", self.base, expect=1))

    def test_whitespace_only_edit_does_not_count_as_doc_update(self):
        self.source_edit()
        target = self.root / "docs/reference.md"
        target.write_bytes(target.read_bytes().replace(b" ", b"  ") + b"\n\t\n")
        self.assertIn("update at least one", self.run_lint("--base", self.base, expect=1))

    def test_explicit_empty_tree_base_supports_first_push_ci(self):
        empty_tree = subprocess.run(
            ["git", "-c", "safe.directory=" + self.root.as_posix(), "-C", str(self.root), "hash-object", "-w", "-t", "tree", "--stdin"],
            input=b"", stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
        ).stdout.decode().strip()
        self.run_lint("--base", empty_tree, "--head", self.base, expect=0)

    def test_explicit_head_ignores_dirty_worktree(self):
        self.source_edit()
        stale = self.commit("code without docs")
        self.doc_edit()
        self.run_lint("--base", self.base, expect=0)
        self.run_lint("--base", self.base, "--head", stale, expect=1)

    def test_pre_push_checks_commit_not_dirty_document(self):
        self.source_edit()
        stale = self.commit("code without docs")
        self.doc_edit()
        line = "refs/heads/topic " + stale + " refs/heads/topic " + self.base + "\n"
        self.run_lint("--pre-push", stdin=line, expect=1)
        current = self.commit("documentation updated")
        line = "refs/heads/topic " + current + " refs/heads/topic " + self.base + "\n"
        self.run_lint("--pre-push", stdin=line, expect=0)

    def test_pre_push_checks_all_ref_updates(self):
        self.source_edit()
        stale = self.commit("code without docs")
        lines = "refs/heads/good " + self.base + " refs/heads/good " + self.base + "\n"
        lines += "refs/heads/bad " + stale + " refs/heads/bad " + self.base + "\n"
        output = self.run_lint("--pre-push", stdin=lines, expect=1)
        self.assertIn("refs/heads/bad", output)

    def test_new_branch_uses_remote_tracking_merge_base(self):
        self.git("update-ref", "refs/remotes/origin/main", self.base)
        self.source_edit()
        stale = self.commit("code without docs")
        line = "refs/heads/new " + stale + " refs/heads/new " + ZERO + "\n"
        self.run_lint("--pre-push", "--remote", "origin", stdin=line, expect=1)

    def test_new_branch_without_tracking_refs_uses_empty_tree(self):
        line = "refs/heads/new " + self.base + " refs/heads/new " + ZERO + "\n"
        self.run_lint("--pre-push", "--remote", "origin", stdin=line, expect=0)

    def test_deleted_branch_does_not_require_manifest(self):
        (self.root / "docs/manifest.json").unlink()
        line = "(delete) " + ZERO + " refs/heads/old " + self.base + "\n"
        self.run_lint("--pre-push", stdin=line, expect=0)

    def test_pre_push_bad_input_and_missing_commit_fail(self):
        self.run_lint("--pre-push", stdin="malformed\n", expect=1)
        line = "refs/heads/new " + self.base + " refs/heads/new " + "f" * 40 + "\n"
        self.run_lint("--pre-push", stdin=line, expect=1)

    def test_actual_git_push_hook_blocks_stale_commit(self):
        with tempfile.TemporaryDirectory() as remote:
            self.git("init", "--bare", "-q", remote)
            self.git("remote", "add", "origin", remote)
            self.write("scripts/docs_lint.py", SCRIPT.read_text(encoding="utf-8"))
            hook = self.root / ".githooks/pre-push"
            hook.parent.mkdir()
            shutil.copyfile(SCRIPT.parents[1] / ".githooks/pre-push", hook)
            hook.chmod(0o755)
            self.git("config", "core.hooksPath", ".githooks")
            self.commit("install documentation hook")
            self.git("push", "origin", "HEAD:refs/heads/main")
            self.source_edit()
            self.commit("code without docs")
            self.doc_edit()
            rejected = subprocess.run(
                ["git", "-c", "safe.directory=" + self.root.as_posix(), "-C", str(self.root), "push", "origin", "HEAD:refs/heads/main"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("docs-lint:", rejected.stderr.decode("utf-8", "replace"))
            self.assertIn("docs/reference.md", rejected.stderr.decode("utf-8", "replace"))
            self.commit("documentation updated")
            self.git("push", "origin", "HEAD:refs/heads/main")

    def test_ci_new_feature_branch_requires_its_own_document_update(self):
        self.git("update-ref", "refs/remotes/origin/main", self.base)
        self.source_edit()
        stale = self.commit("code without docs")
        self.doc_edit()
        environment = self.ci_environment(DOCS_BASE=ZERO, DOCS_HEAD=stale)
        self.run_lint("--ci", environment=environment, expect=1)
        updated = self.commit("documentation updated")
        environment["DOCS_HEAD"] = updated
        self.run_lint("--ci", environment=environment, expect=0)

    def test_ci_pull_request_ignores_target_branch_changes_since_divergence(self):
        self.git("checkout", "-qb", "topic", self.base)
        self.write("docs/unrelated.md", "# Feature branch documentation\n")
        feature = self.commit("feature documentation")
        self.git("checkout", "-qb", "target", self.base)
        self.source_edit()
        target = self.commit("independent target branch source change")
        environment = self.ci_environment(
            DOCS_EVENT="pull_request", DOCS_BASE=target, DOCS_HEAD=feature,
            DOCS_REF="refs/pull/42/merge",
        )
        self.run_lint("--ci", environment=environment, expect=0)
        self.git("checkout", "-q", "topic")
        self.write("src/check.py", "value = 3\n")
        environment["DOCS_HEAD"] = self.commit("feature source without relevant docs")
        self.run_lint("--ci", environment=environment, expect=1)

    def test_ci_regular_push_checks_submitted_commit_not_dirty_documents(self):
        self.source_edit()
        stale = self.commit("code without docs")
        self.doc_edit()
        self.run_lint("--ci", environment=self.ci_environment(DOCS_HEAD=stale), expect=1)

    def test_ci_deleted_push_skips_document_check(self):
        (self.root / "docs/manifest.json").unlink()
        environment = self.ci_environment(DOCS_HEAD=ZERO, DOCS_DELETED="true")
        output = self.run_lint("--ci", environment=environment, expect=0)
        self.assertIn("skipped deleted ref", output)

    def test_ci_initial_default_branch_uses_empty_tree(self):
        environment = self.ci_environment(DOCS_BASE=ZERO, DOCS_REF="refs/heads/main")
        self.run_lint("--ci", environment=environment, expect=0)

    def test_ci_new_feature_without_default_branch_baseline_fails(self):
        environment = self.ci_environment(DOCS_BASE=ZERO)
        output = self.run_lint("--ci", environment=environment, expect=1)
        self.assertIn("refs/remotes/origin/main is missing", output)

    def test_ci_unrelated_feature_history_has_no_empty_tree_fallback(self):
        self.git("update-ref", "refs/remotes/origin/main", self.base)
        tree = self.git("rev-parse", self.base + "^{tree}")
        unrelated = self.git("commit-tree", tree, "-m", "unrelated root")
        environment = self.ci_environment(DOCS_BASE=ZERO, DOCS_HEAD=unrelated)
        output = self.run_lint("--ci", environment=environment, expect=1)
        self.assertIn("empty-tree fallback is disabled", output)

    def test_ci_manual_run_checks_committed_structure_only(self):
        self.source_edit()
        head = self.commit("code without docs")
        self.write("README.md", "[Broken](missing.md)\n")
        environment = self.ci_environment(DOCS_EVENT="workflow_dispatch", DOCS_BASE="", DOCS_HEAD=head)
        self.run_lint("--ci", environment=environment, expect=0)

    def test_ci_rejects_invalid_environment_and_option_conflicts(self):
        for overrides in [
            {"DOCS_EVENT": ""}, {"DOCS_DELETED": "yes"}, {"DOCS_HEAD": "HEAD"},
            {"DOCS_BASE": ""}, {"DOCS_REF": "topic"}, {"DOCS_DEFAULT_BRANCH": "bad name"},
            {"DOCS_EVENT": "pull_request", "DOCS_DELETED": "true"},
            {"DOCS_EVENT": "pull_request", "DOCS_BASE": ZERO}, {"DOCS_HEAD": ZERO},
        ]:
            with self.subTest(overrides=overrides):
                self.run_lint("--ci", environment=self.ci_environment(**overrides), expect=1)
        for options in [("--check",), ("--base", "HEAD"), ("--head", "HEAD"), ("--write-index",), ("--pre-push",), ("--remote", "origin")]:
            with self.subTest(options=options):
                output = self.run_lint("--ci", *options, environment=self.ci_environment(), expect=2)
                self.assertIn("--ci cannot be combined", output)


if __name__ == "__main__":
    unittest.main()
