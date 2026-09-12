import dataclasses
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from tests.test_content_root import manifest_for, unseal

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sentinel.errors import SentinelError
from sentinel import content_root, go_inputs, go_runtime


def sealed_fixture(base, name, files, kind):
    source = base / name
    source.mkdir(mode=0o700)
    for relative, (raw, executable) in files.items():
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        path.chmod(0o700 if executable else 0o600)
    for directory, _names, _files in os.walk(source):
        Path(directory).chmod(0o700)
    target = base / (name + "-installed")
    target.mkdir(mode=0o700)
    raw, digest = manifest_for(files, kind)
    return content_root.prepare_content_root(source, raw, digest, target)


class GoInputTests(unittest.TestCase):
    def test_inputs_reject_unverified_roots(self):
        self.assertIsNotNone(importlib.util.find_spec("sentinel.go_inputs"), "Go input assembly is missing")
        from sentinel.go_inputs import prepare_go_inputs
        with self.assertRaises(SentinelError) as result:
            prepare_go_inputs(None, None, None, None)
        self.assertEqual(result.exception.exit_code, 5)

    def test_recheck_rejects_untyped_input(self):
        self.assertIsNotNone(importlib.util.find_spec("sentinel.go_inputs"), "Go input recheck is missing")
        from sentinel.go_inputs import recheck_go_inputs
        with self.assertRaises(SentinelError):
            recheck_go_inputs({"uid": 1000})

    def test_read_only_verification_preserves_interrupt_for_execution_controller(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            try:
                sdk = sealed_fixture(base, "sdk", {"bin/go": (b"non-executed SDK fixture", True)}, "dependencies")
                artifact = sealed_fixture(base, "artifact", {"payload": (b"artifact fixture", False)}, "artifact")
                dependencies = sealed_fixture(base, "dependencies", {"module": (b"module fixture", False)}, "dependencies")
                corpus = sealed_fixture(base, "corpus", {"go.mod": (b"module example.test/fixture\n", False)}, "corpus")
                lock = json.dumps({"repository": "SENTINEL_GO", "status": "locked",
                                   "toolchains": {"go": go_runtime.GO_LOCK}}).encode()
                runtime = go_runtime.GoRuntime(sdk, hashlib.sha256(lock).hexdigest(),
                                               go_runtime.GO_LOCK['installedTreeSha256'],
                                               go_runtime.GO_LOCK['binarySha256'], lock)
                inputs = go_inputs.GoPreparedInputs(runtime, artifact, dependencies, corpus,
                                                    os.geteuid(), os.getegid(), ())
                operations = [lambda: go_runtime.verify_go_runtime(sdk, lock, runtime.lock_sha256),
                              lambda: go_runtime.release_tree_sha256(sdk),
                              lambda: go_inputs.prepare_go_inputs(runtime, artifact, dependencies, corpus),
                              lambda: go_inputs.recheck_go_inputs(inputs)]
                # No execution or successful SDK admission is implied: interrupt
                # the first real content verification before its file hashing.
                with mock.patch.object(content_root, '_verify_tree', side_effect=KeyboardInterrupt):
                    for index, operation in enumerate(operations):
                        with self.subTest(api=index):
                            try:
                                operation()
                            except BaseException as error:
                                self.assertIsInstance(error, KeyboardInterrupt)
                            else:
                                self.fail('interruption was ignored')
            finally:
                unseal(base)

    def assert_safe_failure(self, operation):
        try:
            operation()
        except Exception as error:
            self.assertIsInstance(error, SentinelError)
            self.assertEqual((error.code, error.exit_code), ("goInputsFailed", 5))
        else:
            self.fail("invalid Go input was accepted")

    def test_record_binds_parsed_bytes_to_content_entry(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            try:
                for name in ("artifact.json", "support.json"):
                    with self.subTest(record=name):
                        original = b'{"version":"9.9.9"}'
                        substitute = b'{"version":"0.1.0"}'
                        root = sealed_fixture(base, name, {name: (original, False)}, "artifact")
                        self.assertEqual(go_inputs._record(root, name), {"version": "9.9.9"})
                        path = root.root / name
                        read_regular = go_inputs.oci._read_regular

                        def replace_during_read(*args):
                            path.chmod(0o600)
                            path.write_bytes(substitute)
                            path.chmod(0o400)
                            try:
                                return read_regular(*args)
                            finally:
                                path.chmod(0o600)
                                path.write_bytes(original)
                                path.chmod(0o400)

                        with mock.patch.object(go_inputs.oci, "_read_regular", side_effect=replace_during_read):
                            self.assert_safe_failure(lambda: go_inputs._record(root, name))
                        content_root.recheck_content_root(root)
            finally:
                unseal(base)

    def test_deep_records_have_fixed_safe_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            try:
                for name in ("artifact.json", "support.json"):
                    with self.subTest(record=name):
                        raw = b"[" * 2000 + b"0" + b"]" * 2000
                        root = sealed_fixture(base, name, {name: (raw, False)}, "artifact")
                        self.assert_safe_failure(lambda: go_inputs._record(root, name))
            finally:
                unseal(base)

    def test_prepare_and_recheck_require_retained_lock_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            try:
                sdk = sealed_fixture(base, "sdk", {"bin/go": (b"non-executed SDK fixture", True)}, "dependencies")
                artifact = sealed_fixture(base, "artifact", {"payload": (b"artifact fixture", False)}, "artifact")
                dependencies = sealed_fixture(base, "dependencies", {"module": (b"module fixture", False)}, "dependencies")
                corpus = sealed_fixture(base, "corpus", {"go.mod": (b"module example.test/fixture\n", False)}, "corpus")
                pins = {"binarySha256": sdk._entries[0].sha256,
                        "installedTreeSha256": go_runtime.release_tree_sha256(sdk)}
                # Keep real sealed roots, lock parsing and release hashing. Only
                # the separate native artifact validator is outside this unit.
                with mock.patch.dict(go_runtime.GO_LOCK, pins), mock.patch.object(go_inputs, "_artifact"):
                    lock = json.dumps({"repository": "SENTINEL_GO", "status": "locked",
                                       "toolchains": {"go": go_runtime.GO_LOCK}}).encode()
                    runtime = go_runtime.verify_go_runtime(sdk, lock, hashlib.sha256(lock).hexdigest())
                    inputs = go_inputs.prepare_go_inputs(runtime, artifact, dependencies, corpus)
                    go_inputs.recheck_go_inputs(inputs)
                    forged = dataclasses.replace(runtime, lock_sha256="0" * 64)
                    self.assert_safe_failure(lambda: go_inputs.prepare_go_inputs(forged, artifact, dependencies, corpus))
                    self.assert_safe_failure(lambda: go_inputs.recheck_go_inputs(dataclasses.replace(inputs, runtime=forged)))
                    self.assertNotIn(lock.decode(), repr(runtime))
            finally:
                unseal(base)


if __name__ == "__main__":
    unittest.main()
