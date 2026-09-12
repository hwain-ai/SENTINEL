import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from tests.test_content_root import manifest_for, unseal

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sentinel.content_root import prepare_content_root
from sentinel.errors import SentinelError


class GoRuntimeTests(unittest.TestCase):
    def implementation(self):
        self.assertIsNotNone(importlib.util.find_spec("sentinel.go_runtime"), "Go release tree verifier is missing")
        from sentinel import go_runtime
        return go_runtime

    def test_release_serialization_matches_gnu_tar_before_permission_sealing(self):
        implementation = self.implementation()
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "source"
            target = base / "installed"
            source.mkdir(mode=0o755)
            source.chmod(0o755)
            target.mkdir(mode=0o700)
            files = {
                "bin/go": (b"executable fixture\n", True),
                "a.txt": (b"first\n", False),
                "a/z.txt": (b"nested\n", False),
                "lib/" + "x" * 120: (b"long GNU header\n", False),
                "src/한글.go": (b"unicode\n", False),
                "zero": (b"", False),
            }
            for relative, (raw, executable) in files.items():
                file = source / relative
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_bytes(raw)
                file.chmod(0o755 if executable else 0o644)
            for directory, _names, _files in os.walk(source):
                Path(directory).chmod(0o755)
            archive = subprocess.run([
                "/usr/bin/tar", "--create", "--format=gnu", "--sort=name",
                "--mtime=UTC 1970-01-01", "--owner=0", "--group=0", "--numeric-owner",
                "--file=-", "--directory=" + str(source), ".",
            ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"})
            self.assertEqual(archive.stderr, b"")
            manifest, digest = manifest_for(files, "dependencies")
            prepared = prepare_content_root(source, manifest, digest, target)
            try:
                actual = implementation.release_tree_sha256(prepared)
                self.assertEqual(actual, hashlib.sha256(archive.stdout).hexdigest())
                self.assertEqual((prepared.root / "bin/go").stat().st_mode & 0o777, 0o500)
                self.assertEqual((prepared.root / "a.txt").stat().st_mode & 0o777, 0o400)
                (prepared.root / "a.txt").chmod(0o600)
                (prepared.root / "a.txt").write_bytes(b"changed\n")
                with self.assertRaises(SentinelError):
                    implementation.release_tree_sha256(prepared)
            finally:
                unseal(prepared.root)

    def test_unknown_runtime_lock_is_rejected_without_execution(self):
        implementation = self.implementation()
        with self.assertRaises(SentinelError) as result:
            implementation.verify_go_runtime(None, b"{}", hashlib.sha256(b"{}").hexdigest())
        self.assertEqual(result.exception.exit_code, 5)

    def test_deep_runtime_lock_has_fixed_safe_error(self):
        implementation = self.implementation()
        lock = b"[" * 2000 + b"0" + b"]" * 2000
        try:
            implementation.verify_go_runtime(None, lock, hashlib.sha256(lock).hexdigest())
        except Exception as error:
            self.assertIsInstance(error, SentinelError)
            self.assertEqual((error.code, error.exit_code), ("goRuntimeFailed", 5))
        else:
            self.fail("deep lock was accepted")

    def test_runtime_content_os_error_is_safe_but_interrupt_is_preserved(self):
        implementation = self.implementation()
        lock = json.dumps({"repository": "SENTINEL_GO", "status": "locked",
                           "toolchains": {"go": implementation.GO_LOCK}}).encode()
        with mock.patch.object(implementation.content, '_recheck',
                               side_effect=FileNotFoundError('/private/runtime/changed')):
            try:
                implementation.verify_go_runtime(None, lock, hashlib.sha256(lock).hexdigest())
            except Exception as error:
                self.assertIsInstance(error, SentinelError)
                self.assertEqual((error.code, error.message, error.exit_code),
                                 ('goRuntimeFailed', 'Go runtime verification failed', 5))
            else:
                self.fail('missing runtime was accepted')


if __name__ == "__main__":
    unittest.main()
