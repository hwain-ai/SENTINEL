import importlib.util
import dataclasses
from contextlib import contextmanager
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def manifest_for(files, kind="artifact"):
    records = []
    for relative, (data, executable) in sorted(files.items()):
        records.append(
            {
                "path": relative,
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "executable": executable,
            }
        )
    raw = canonical(
        {
            "schemaVersion": "sentinel-content-root-v1",
            "kind": kind,
            "files": records,
        }
    )
    return raw, hashlib.sha256(raw).hexdigest()


def changed_stat(metadata, **changes):
    fields = (
        "st_dev",
        "st_ino",
        "st_uid",
        "st_gid",
        "st_mode",
        "st_nlink",
        "st_size",
        "st_atime",
        "st_mtime",
        "st_ctime",
        "st_atime_ns",
        "st_mtime_ns",
        "st_ctime_ns",
    )
    values = {field: getattr(metadata, field) for field in fields}
    values.update(changes)
    return SimpleNamespace(**values)


def unseal(root):
    if not root.exists() or root.is_symlink():
        return
    for current, directories, files in os.walk(root, topdown=True, followlinks=False):
        try:
            os.chmod(current, 0o700, follow_symlinks=False)
        except OSError:
            pass
        for name in files:
            path = Path(current) / name
            if not path.is_symlink():
                try:
                    path.chmod(0o600)
                except OSError:
                    pass


class ContentRootApiTests(unittest.TestCase):
    def test_content_root_public_api_exists(self):
        spec = importlib.util.find_spec("sentinel.content_root")
        self.assertIsNotNone(spec, "sentinel.content_root is not implemented")
        module = __import__("sentinel.content_root", fromlist=["PreparedRoot"])
        self.assertTrue(hasattr(module, "PreparedRoot"), "PreparedRoot is not implemented")
        self.assertTrue(hasattr(module, "prepare_content_root"), "prepare_content_root is not implemented")
        self.assertTrue(hasattr(module, "recheck_content_root"), "recheck_content_root is not implemented")


class ContentRootTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name).resolve()
        self.base.chmod(0o700)
        self.source_parent = self.base / "source-parent"
        self.source_parent.mkdir(mode=0o700)
        self.destination_parent = self.base / "destination-parent"
        self.destination_parent.mkdir(mode=0o700)

    def tearDown(self):
        unseal(self.base)
        self.temporary.cleanup()

    @staticmethod
    def api():
        from sentinel import content_root

        return content_root

    def make_source(self, name="source", files=None):
        if files is None:
            files = {
                "bin/tool": (b"#!/bin/sh\nexit 0\n", True),
                "lib/data.txt": (b"verified-data\n", False),
            }
        source = self.source_parent / name
        source.mkdir(mode=0o700)
        for relative, (data, executable) in files.items():
            target = source.joinpath(*relative.split("/"))
            target.parent.mkdir(parents=True, exist_ok=True)
            current = target.parent
            while current != source:
                current.chmod(0o700)
                current = current.parent
            target.write_bytes(data)
            target.chmod(0o700 if executable else 0o600)
        return source, files

    def assert_safe_failure(self, callable_value):
        from sentinel.errors import SentinelError

        with self.assertRaises(SentinelError) as caught:
            callable_value()
        self.assertEqual(
            (caught.exception.code, caught.exception.message, caught.exception.exit_code),
            ("contentRootFailed", "Content root verification failed", 5),
        )
        return caught.exception

    def prepare(self, source, files, kind="artifact", destination_parent=None):
        raw, digest = manifest_for(files, kind)
        prepared = self.api().prepare_content_root(
            source,
            raw,
            digest,
            destination_parent or self.destination_parent,
        )
        return prepared, raw, digest

    def test_valid_install_rechecks_is_idempotent_and_frozen(self):
        source, files = self.make_source()
        before = {path: (source / path).read_bytes() for path in files}
        prepared, _raw, digest = self.prepare(source, files)

        self.assertEqual(prepared.kind, "artifact")
        self.assertEqual(prepared.root, self.destination_parent / f"artifact-{digest}")
        self.assertEqual(prepared.manifest_sha256, digest)
        self.assertEqual(prepared.file_count, 2)
        self.assertEqual(prepared.total_bytes, sum(len(value[0]) for value in files.values()))
        self.assertEqual(stat.S_IMODE(prepared.root.stat().st_mode), 0o500)
        self.assertEqual(stat.S_IMODE((prepared.root / "bin").stat().st_mode), 0o500)
        self.assertEqual(stat.S_IMODE((prepared.root / "bin/tool").stat().st_mode), 0o500)
        self.assertEqual(stat.S_IMODE((prepared.root / "lib/data.txt").stat().st_mode), 0o400)
        self.assertEqual({path: (source / path).read_bytes() for path in files}, before)
        self.api().recheck_content_root(prepared)

        inode = prepared.root.stat().st_ino
        repeated = self.api().prepare_content_root(source, _raw, digest, self.destination_parent)
        self.assertEqual(repeated.root.stat().st_ino, inode)
        self.assertEqual(repeated, prepared)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            prepared.kind = "corpus"
        representation = repr(prepared)
        self.assertNotIn("_entries", representation)
        self.assertNotIn(str(source), representation)

    def test_install_normalizes_permissions_under_restrictive_umask(self):
        source, files = self.make_source()
        previous = os.umask(0o777)
        try:
            prepared, _raw, _digest = self.prepare(source, files)
        finally:
            os.umask(previous)
        self.api().recheck_content_root(prepared)
        self.assertEqual(stat.S_IMODE(prepared.root.stat().st_mode), 0o500)
        self.assertEqual(stat.S_IMODE((prepared.root / "bin").stat().st_mode), 0o500)
        self.assertEqual(stat.S_IMODE((prepared.root / "bin/tool").stat().st_mode), 0o500)
        self.assertEqual(stat.S_IMODE((prepared.root / "lib/data.txt").stat().st_mode), 0o400)

    def test_manifest_rejects_structure_types_numbers_order_and_bounds(self):
        source, files = self.make_source()
        good_raw, good_digest = manifest_for(files)
        good = json.loads(good_raw)
        variants = []

        def add(value):
            raw = canonical(value)
            variants.append((raw, hashlib.sha256(raw).hexdigest()))

        variants.extend(
            [
                (b"", hashlib.sha256(b"").hexdigest()),
                (b"not-json", hashlib.sha256(b"not-json").hexdigest()),
                (b'{"schemaVersion":"sentinel-content-root-v1","schemaVersion":"sentinel-content-root-v1","kind":"artifact","files":[]}', "placeholder"),
                (b'{"schemaVersion":NaN,"kind":"artifact","files":[]}', "placeholder"),
                ((b"[" * 66) + b"0" + (b"]" * 66), "placeholder"),
            ]
        )
        variants = [(raw, hashlib.sha256(raw).hexdigest() if digest == "placeholder" else digest) for raw, digest in variants]
        add({**good, "unknown": True})
        add({"schemaVersion": good["schemaVersion"], "kind": "artifact"})
        add({**good, "schemaVersion": "other"})
        add({**good, "kind": "other"})
        add({**good, "files": []})
        add({**good, "files": True})
        add({**good, "files": list(reversed(good["files"]))})
        add({**good, "files": [good["files"][0], good["files"][0]]})
        add({**good, "files": [{**good["files"][0], "unknown": 1}]})
        add({**good, "files": [{key: value for key, value in good["files"][0].items() if key != "sha256"}]})
        add({**good, "files": [{**good["files"][0], "bytes": True}]})
        add({**good, "files": [{**good["files"][0], "bytes": -1}]})
        add({**good, "files": [{**good["files"][0], "bytes": 512 * 1024 * 1024 + 1}]})
        add({**good, "files": [{**good["files"][0], "sha256": "A" * 64}]})
        add({**good, "files": [{**good["files"][0], "executable": 1}]})
        oversized_total = []
        for index in range(9):
            oversized_total.append(
                {
                    "path": f"f{index}",
                    "bytes": 512 * 1024 * 1024,
                    "sha256": "0" * 64,
                    "executable": False,
                }
            )
        add({**good, "files": oversized_total})
        variants.append((b"x" * (16 * 1024 * 1024 + 1), "0" * 64))

        for index, (raw, digest) in enumerate(variants):
            with self.subTest(index=index):
                self.assert_safe_failure(
                    lambda raw=raw, digest=digest: self.api().prepare_content_root(
                        source, raw, digest, self.destination_parent
                    )
                )
        self.assert_safe_failure(
            lambda: self.api().prepare_content_root(source, bytearray(good_raw), good_digest, self.destination_parent)
        )
        self.assertEqual(list(self.destination_parent.iterdir()), [])

    def test_manifest_rejects_unsafe_paths(self):
        source, files = self.make_source()
        record = {
            "path": "placeholder",
            "bytes": 0,
            "sha256": hashlib.sha256(b"").hexdigest(),
            "executable": False,
        }
        unsafe = (
            "",
            ".",
            "..",
            "/absolute",
            "a\\b",
            "a//b",
            "a/./b",
            "a/../b",
            "trailing/",
            "line\nbreak",
            "tab\tname",
            "nul\x00name",
            "del\x7fname",
            ".git/config",
            "a/.git/config",
            "a" * 4097,
            "/".join("p" for _ in range(257)),
        )
        for relative in unsafe:
            with self.subTest(relative=repr(relative)):
                value = {
                    "schemaVersion": "sentinel-content-root-v1",
                    "kind": "artifact",
                    "files": [{**record, "path": relative}],
                }
                raw = canonical(value)
                self.assert_safe_failure(
                    lambda raw=raw: self.api().prepare_content_root(
                        source, raw, hashlib.sha256(raw).hexdigest(), self.destination_parent
                    )
                )
        self.assertEqual(list(self.destination_parent.iterdir()), [])

    def test_source_missing_extra_tampered_and_executable_mismatch_fail(self):
        cases = ("missing", "extra", "tampered", "executable")
        for index, case in enumerate(cases):
            with self.subTest(case=case):
                source, files = self.make_source(f"source-{index}")
                raw, digest = manifest_for(files)
                if case == "missing":
                    (source / "lib/data.txt").unlink()
                elif case == "extra":
                    (source / "extra.txt").write_bytes(b"extra")
                elif case == "tampered":
                    (source / "lib/data.txt").write_bytes(b"wrong-content\n")
                else:
                    (source / "bin/tool").chmod(0o600)
                self.assert_safe_failure(
                    lambda source=source, raw=raw, digest=digest: self.api().prepare_content_root(
                        source, raw, digest, self.destination_parent
                    )
                )
        self.assertEqual(list(self.destination_parent.iterdir()), [])

    def test_source_rejects_symlink_hardlink_fifo_and_unsafe_modes(self):
        cases = ("symlink", "hardlink", "fifo", "world-write", "directory-write", "unreadable")
        for index, case in enumerate(cases):
            with self.subTest(case=case):
                source, _files = self.make_source(f"unsafe-{index}", {"file": (b"data", False)})
                target = source / "file"
                if case == "symlink":
                    target.unlink()
                    target.symlink_to(self.base / "outside")
                elif case == "hardlink":
                    other = source / "other"
                    os.link(target, other)
                elif case == "fifo":
                    target.unlink()
                    os.mkfifo(target)
                elif case == "world-write":
                    target.chmod(0o602)
                elif case == "directory-write":
                    source.chmod(0o702)
                else:
                    target.chmod(0o000)
                raw, digest = manifest_for({"file": (b"data", False)})
                self.assert_safe_failure(
                    lambda source=source, raw=raw, digest=digest: self.api().prepare_content_root(
                        source, raw, digest, self.destination_parent
                    )
                )

    def test_source_rejects_foreign_owner_from_descriptor_evidence(self):
        module = self.api()
        source, files = self.make_source()
        raw, digest = manifest_for(files)
        target_metadata = os.lstat(source / "bin/tool")
        real_fstat = os.fstat

        def foreign_file(descriptor):
            metadata = real_fstat(descriptor)
            if metadata.st_dev == target_metadata.st_dev and metadata.st_ino == target_metadata.st_ino:
                return changed_stat(metadata, st_uid=os.geteuid() + 1)
            return metadata

        with mock.patch.object(module.os, "fstat", side_effect=foreign_file):
            self.assert_safe_failure(
                lambda: module.prepare_content_root(source, raw, digest, self.destination_parent)
            )
        self.assertEqual(list(self.destination_parent.iterdir()), [])

    def test_destination_rejects_unsafe_git_overlap_and_existing_mismatch(self):
        source, files = self.make_source()
        raw, digest = manifest_for(files)

        unsafe_mode = self.base / "unsafe-mode"
        unsafe_mode.mkdir(mode=0o755)
        git_parent = self.base / "git-parent"
        git_parent.mkdir(mode=0o700)
        (git_parent / ".git").mkdir()
        inside_source = source / "destination"
        inside_source.mkdir(mode=0o700)
        source_inside_destination = self.source_parent
        source_inside_destination.chmod(0o700)

        for destination in (unsafe_mode, git_parent, inside_source, source_inside_destination):
            with self.subTest(destination=destination.name):
                self.assert_safe_failure(
                    lambda destination=destination: self.api().prepare_content_root(
                        source, raw, digest, destination
                    )
                )

        target = self.destination_parent / f"artifact-{digest}"
        target.mkdir(mode=0o700)
        marker = target / "keep"
        marker.write_bytes(b"do-not-replace")
        marker.chmod(0o400)
        target.chmod(0o500)
        inode = target.stat().st_ino
        self.assert_safe_failure(
            lambda: self.api().prepare_content_root(source, raw, digest, self.destination_parent)
        )
        self.assertEqual(target.stat().st_ino, inode)
        self.assertEqual(marker.read_bytes(), b"do-not-replace")

    def test_bad_path_types_and_noncanonical_paths_fail_safely(self):
        source, files = self.make_source()
        raw, digest = manifest_for(files)
        aliases = self.source_parent / "alias"
        aliases.symlink_to(source, target_is_directory=True)
        relative_source = Path(os.path.relpath(source, Path.cwd()))

        calls = (
            lambda: self.api().prepare_content_root(str(source), raw, digest, self.destination_parent),
            lambda: self.api().prepare_content_root(source, raw, digest, str(self.destination_parent)),
            lambda: self.api().prepare_content_root(relative_source, raw, digest, self.destination_parent),
            lambda: self.api().prepare_content_root(aliases, raw, digest, self.destination_parent),
            lambda: self.api().prepare_content_root(source, raw, "A" * 64, self.destination_parent),
        )
        for index, call in enumerate(calls):
            with self.subTest(index=index):
                self.assert_safe_failure(call)
        self.assertEqual(list(self.destination_parent.iterdir()), [])

    def test_source_parent_and_destination_ownership_boundaries_fail_closed(self):
        module = self.api()
        source, files = self.make_source()
        raw, digest = manifest_for(files)

        self.source_parent.chmod(0o755)
        self.assert_safe_failure(
            lambda: module.prepare_content_root(source, raw, digest, self.destination_parent)
        )
        self.source_parent.chmod(0o700)

        alias = self.base / "destination-alias"
        alias.symlink_to(self.destination_parent, target_is_directory=True)
        self.assert_safe_failure(
            lambda: module.prepare_content_root(source, raw, digest, alias)
        )

        real_lstat = module.os.lstat
        destination_text = os.fspath(self.destination_parent)

        def foreign_destination(path, *args, **kwargs):
            metadata = real_lstat(path, *args, **kwargs)
            if os.fspath(path) == destination_text:
                return changed_stat(metadata, st_uid=os.geteuid() + 1)
            return metadata

        with mock.patch.object(module.os, "lstat", side_effect=foreign_destination):
            self.assert_safe_failure(
                lambda: module.prepare_content_root(source, raw, digest, self.destination_parent)
            )
        self.assertEqual(list(self.destination_parent.iterdir()), [])

    def test_copy_publish_fsync_and_cancellation_failures_leave_no_stage(self):
        module = self.api()
        failure_factories = (
            lambda: mock.patch.object(module.os, "write", side_effect=OSError("secret write failure")),
            lambda: mock.patch.object(module, "_publish_noreplace", side_effect=OSError("secret publish failure")),
            lambda: mock.patch.object(module.os, "fsync", side_effect=OSError("secret fsync failure")),
            lambda: mock.patch.object(module.os, "read", side_effect=KeyboardInterrupt()),
        )
        for index, patch_factory in enumerate(failure_factories):
            with self.subTest(index=index):
                source, files = self.make_source(f"failure-{index}")
                raw, digest = manifest_for(files)
                before = {path: (source / path).read_bytes() for path in files}
                descriptors_before = len(os.listdir("/proc/self/fd"))
                with patch_factory():
                    self.assert_safe_failure(
                        lambda: module.prepare_content_root(
                            source, raw, digest, self.destination_parent
                        )
                    )
                self.assertEqual({path: (source / path).read_bytes() for path in files}, before)
                self.assertEqual(list(self.destination_parent.iterdir()), [])
                self.assertLessEqual(len(os.listdir("/proc/self/fd")), descriptors_before)

    def test_failed_new_install_preserves_prior_exact_root(self):
        module = self.api()
        old_source, old_files = self.make_source("old", {"old": (b"old", False)})
        prior, _raw, _digest = self.prepare(old_source, old_files)
        prior_inode = prior.root.stat().st_ino
        new_source, new_files = self.make_source("new", {"new": (b"new", False)})
        new_raw, new_digest = manifest_for(new_files)
        with mock.patch.object(module.os, "write", side_effect=OSError("copy failed")):
            self.assert_safe_failure(
                lambda: module.prepare_content_root(
                    new_source, new_raw, new_digest, self.destination_parent
                )
            )
        self.assertEqual(prior.root.stat().st_ino, prior_inode)
        self.assertEqual((prior.root / "old").read_bytes(), b"old")
        self.assertEqual(sorted(path.name for path in self.destination_parent.iterdir()), [prior.root.name])

    def test_idempotent_target_does_not_hide_a_changed_source(self):
        module = self.api()
        source, files = self.make_source()
        prepared, raw, digest = self.prepare(source, files)
        inode = prepared.root.stat().st_ino
        source_file = source / "lib/data.txt"
        source_file.write_bytes(b"changed-value\n")
        source_file.chmod(0o600)
        self.assert_safe_failure(
            lambda: module.prepare_content_root(source, raw, digest, self.destination_parent)
        )
        self.assertEqual(prepared.root.stat().st_ino, inode)
        module.recheck_content_root(prepared)

    def test_source_replacement_during_read_fails_without_publication(self):
        module = self.api()
        source, files = self.make_source()
        raw, digest = manifest_for(files)
        watched = os.lstat(source / "lib/data.txt")
        real_read = os.read
        replaced = False

        def replace_after_read(descriptor, size):
            nonlocal replaced
            chunk = real_read(descriptor, size)
            metadata = os.fstat(descriptor)
            if not replaced and metadata.st_dev == watched.st_dev and metadata.st_ino == watched.st_ino:
                replaced = True
                replacement = source / "lib/replacement"
                replacement.write_bytes(b"verified-data\n")
                replacement.chmod(0o600)
                os.replace(replacement, source / "lib/data.txt")
            return chunk

        with mock.patch.object(module.os, "read", side_effect=replace_after_read):
            self.assert_safe_failure(
                lambda: module.prepare_content_root(source, raw, digest, self.destination_parent)
            )
        self.assertTrue(replaced)
        self.assertEqual(list(self.destination_parent.iterdir()), [])

    def test_source_and_destination_root_substitution_fail_before_publication(self):
        module = self.api()

        source, files = self.make_source("source-root-swap")
        raw, digest = manifest_for(files)
        source_backup = self.source_parent / "source-root-backup"
        real_copy = module._copy_entry
        source_swapped = False

        def swap_source(*args):
            nonlocal source_swapped
            real_copy(*args)
            if not source_swapped:
                source.rename(source_backup)
                source.mkdir(mode=0o700)
                source_swapped = True

        with mock.patch.object(module, "_copy_entry", side_effect=swap_source):
            self.assert_safe_failure(
                lambda: module.prepare_content_root(source, raw, digest, self.destination_parent)
            )
        self.assertTrue(source_swapped)
        self.assertEqual(list(self.destination_parent.iterdir()), [])

        second_source, second_files = self.make_source("destination-root-swap")
        second_raw, second_digest = manifest_for(second_files)
        second_destination = self.base / "destination-to-swap"
        second_destination.mkdir(mode=0o700)
        destination_backup = self.base / "destination-root-backup"
        destination_swapped = False

        def swap_destination(*args):
            nonlocal destination_swapped
            real_copy(*args)
            if not destination_swapped:
                second_destination.rename(destination_backup)
                second_destination.mkdir(mode=0o700)
                destination_swapped = True

        with mock.patch.object(module, "_copy_entry", side_effect=swap_destination):
            self.assert_safe_failure(
                lambda: module.prepare_content_root(
                    second_source, second_raw, second_digest, second_destination
                )
            )
        self.assertTrue(destination_swapped)
        self.assertEqual(list(second_destination.iterdir()), [])
        self.assertEqual(list(destination_backup.iterdir()), [])

    def test_intermediate_source_symlink_and_destination_mode_substitution_fail_closed(self):
        module = self.api()
        source, files = self.make_source("source-through-parent")
        raw, digest = manifest_for(files)
        source_parent_backup = self.base / "source-parent-backup"
        real_validate_source = module._validate_source

        def replace_source_parent(path):
            metadata = real_validate_source(path)
            self.source_parent.rename(source_parent_backup)
            self.source_parent.symlink_to(source_parent_backup, target_is_directory=True)
            return metadata

        try:
            with mock.patch.object(module, "_validate_source", side_effect=replace_source_parent):
                self.assert_safe_failure(
                    lambda: module.prepare_content_root(source, raw, digest, self.destination_parent)
                )
        finally:
            if self.source_parent.is_symlink():
                self.source_parent.unlink()
            if source_parent_backup.exists():
                source_parent_backup.rename(self.source_parent)
        self.assertFalse((self.destination_parent / f"artifact-{digest}").exists())

        second_source, second_files = self.make_source("destination-mode-source")
        second_raw, second_digest = manifest_for(second_files)
        unsafe_destination = self.base / "destination-mode-swap"
        unsafe_destination.mkdir(mode=0o700)
        real_validate_destination = module._validate_destination_parent

        def make_destination_unsafe(path):
            metadata = real_validate_destination(path)
            path.chmod(0o777)
            return metadata

        try:
            with mock.patch.object(
                module,
                "_validate_destination_parent",
                side_effect=make_destination_unsafe,
            ):
                self.assert_safe_failure(
                    lambda: module.prepare_content_root(
                        second_source,
                        second_raw,
                        second_digest,
                        unsafe_destination,
                    )
                )
        finally:
            unsafe_destination.chmod(0o700)
        self.assertFalse((unsafe_destination / f"artifact-{second_digest}").exists())

    def test_open_cancellation_closes_every_descriptor(self):
        module = self.api()
        source, _files = self.make_source()
        metadata = os.lstat(source)
        real_open = module.os.open
        real_fstat = module.os.fstat
        opened = []

        def tracked_open(*args, **kwargs):
            descriptor = real_open(*args, **kwargs)
            opened.append(descriptor)
            return descriptor

        with mock.patch.object(module.os, "open", side_effect=tracked_open):
            with mock.patch.object(module.os, "fstat", side_effect=KeyboardInterrupt()):
                with self.assertRaises(KeyboardInterrupt):
                    module._open_exact_directory(source, metadata)

        leaked = []
        for descriptor in set(opened):
            try:
                real_fstat(descriptor)
            except OSError:
                continue
            leaked.append(descriptor)
        for descriptor in leaked:
            os.close(descriptor)
        self.assertEqual(leaked, [])

    def test_open_and_staging_inspection_failures_close_and_clean_up(self):
        module = self.api()
        source, files = self.make_source()
        raw, digest = manifest_for(files)
        descriptors_before = len(os.listdir("/proc/self/fd"))
        real_open_exact = module._open_exact_directory
        open_calls = 0

        def fail_second_open(path, metadata):
            nonlocal open_calls
            open_calls += 1
            if open_calls == 2:
                raise module._failure()
            return real_open_exact(path, metadata)

        with mock.patch.object(module, "_open_exact_directory", side_effect=fail_second_open):
            self.assert_safe_failure(
                lambda: module.prepare_content_root(source, raw, digest, self.destination_parent)
            )
        self.assertLessEqual(len(os.listdir("/proc/self/fd")), descriptors_before)

        real_stat = module.os.stat
        failed = False

        def fail_staging_stat(path, *args, **kwargs):
            nonlocal failed
            if isinstance(path, str) and path.startswith(".content-root-") and not failed:
                failed = True
                raise OSError("private staging inspection failed")
            return real_stat(path, *args, **kwargs)

        with mock.patch.object(module.os, "stat", side_effect=fail_staging_stat):
            self.assert_safe_failure(
                lambda: module.prepare_content_root(source, raw, digest, self.destination_parent)
            )
        self.assertTrue(failed)
        self.assertEqual(list(self.destination_parent.iterdir()), [])

    def test_publish_collision_adopts_only_identical_complete_target(self):
        module = self.api()
        source, files = self.make_source()
        raw, digest = manifest_for(files)
        target = self.destination_parent / f"artifact-{digest}"
        real_publish = module._publish_noreplace

        def collide(parent_descriptor, staged_name, target_name, *identity):
            staged = self.destination_parent / staged_name
            shutil.copytree(staged, target)
            return real_publish(parent_descriptor, staged_name, target_name, *identity)

        with mock.patch.object(module, "_publish_noreplace", side_effect=collide):
            prepared = module.prepare_content_root(source, raw, digest, self.destination_parent)
        self.assertEqual(prepared.root, target)
        module.recheck_content_root(prepared)
        self.assertEqual(sorted(path.name for path in self.destination_parent.iterdir()), [target.name])

    def test_publish_revalidates_staging_identity_inside_noreplace_call(self):
        module = self.api()
        source, files = self.make_source()
        raw, digest = manifest_for(files)
        target = self.destination_parent / f"artifact-{digest}"
        real_publish = module._publish_noreplace
        created_identity = None

        def substitute_staging(parent_descriptor, staged_name, target_name, *identity):
            nonlocal created_identity
            staged = self.destination_parent / staged_name
            created_identity = (staged.stat().st_dev, staged.stat().st_ino)
            moved = self.destination_parent / (staged_name + "-moved")
            staged.rename(moved)
            staged.mkdir(mode=0o700)
            marker = staged / "unverified"
            marker.write_bytes(b"unverified")
            marker.chmod(0o600)
            return real_publish(parent_descriptor, staged_name, target_name, *identity)

        with mock.patch.object(module, "_publish_noreplace", side_effect=substitute_staging):
            self.assert_safe_failure(
                lambda: module.prepare_content_root(source, raw, digest, self.destination_parent)
            )
        self.assertFalse(target.exists())
        remaining_created = []
        for entry in self.destination_parent.iterdir():
            metadata = os.lstat(entry)
            if created_identity == (metadata.st_dev, metadata.st_ino):
                remaining_created.append(entry)
        self.assertEqual(remaining_created, [])

    def test_published_target_is_rolled_back_when_parent_fsync_fails(self):
        module = self.api()
        source, files = self.make_source()
        raw, digest = manifest_for(files)
        target = self.destination_parent / f"artifact-{digest}"
        real_publish = module._publish_noreplace
        real_fsync = module.os.fsync
        published = False

        def observe_publish(*args):
            nonlocal published
            result = real_publish(*args)
            published = result
            return result

        def fail_after_publish(descriptor):
            if published:
                raise OSError("parent fsync rejected")
            return real_fsync(descriptor)

        with mock.patch.object(module, "_publish_noreplace", side_effect=observe_publish):
            with mock.patch.object(module.os, "fsync", side_effect=fail_after_publish):
                self.assert_safe_failure(
                    lambda: module.prepare_content_root(source, raw, digest, self.destination_parent)
                )
        self.assertFalse(target.exists())
        self.assertEqual(list(self.destination_parent.iterdir()), [])

    def test_parent_substitution_during_publish_rolls_back_owned_target(self):
        module = self.api()
        source, files = self.make_source()
        raw, digest = manifest_for(files)
        backup = self.base / "published-parent-backup"
        real_publish = module._publish_noreplace

        def move_parent(*args):
            self.destination_parent.rename(backup)
            self.destination_parent.mkdir(mode=0o700)
            return real_publish(*args)

        with mock.patch.object(module, "_publish_noreplace", side_effect=move_parent):
            self.assert_safe_failure(
                lambda: module.prepare_content_root(source, raw, digest, self.destination_parent)
            )
        self.assertEqual(list(backup.iterdir()), [])
        self.assertEqual(list(self.destination_parent.iterdir()), [])

    def test_staging_cleanup_changes_permissions_only_through_bound_descriptors(self):
        module = self.api()
        stage = self.destination_parent / ".content-root-test-cleanup"
        nested = stage / "nested"
        nested.mkdir(parents=True, mode=0o700)
        payload = nested / "payload"
        payload.write_bytes(b"payload")
        payload.chmod(0o400)
        nested.chmod(0o500)
        stage.chmod(0o500)
        expected = module._snapshot(os.lstat(stage))
        parent_descriptor = os.open(self.destination_parent, module.OPEN_DIRECTORY)
        real_chmod = module.os.chmod

        def descriptor_chmod(path, mode, *, dir_fd=None):
            self.assertIsNotNone(dir_fd, "cleanup must not chmod a mutable filesystem path")
            self.assertIsInstance(path, str)
            self.assertTrue(path.isdecimal())
            self.assertTrue(os.path.samestat(os.fstat(dir_fd), os.stat("/proc/self/fd")))
            self.assertTrue(os.path.samestat(os.fstat(int(path)), os.stat(path, dir_fd=dir_fd)))
            real_chmod(path, mode, dir_fd=dir_fd)

        try:
            with mock.patch.object(module.os, "chmod", side_effect=descriptor_chmod):
                module._remove_staging(parent_descriptor, stage.name, expected)
        finally:
            os.close(parent_descriptor)
        self.assertFalse(stage.exists())

    def test_descriptor_permission_change_does_not_follow_a_replaced_project_path(self):
        module = self.api()
        original = self.destination_parent / "original"
        original.mkdir(mode=0o000)
        descriptor = os.open(original, module.OPEN_PATH_DIRECTORY)
        held = self.destination_parent / "held"
        original.rename(held)
        victim = self.destination_parent / "victim"
        victim.mkdir(mode=0o500)
        original.symlink_to(victim, target_is_directory=True)
        try:
            module._fchmod_path_descriptor(descriptor, 0o700)
            self.assertEqual(stat.S_IMODE(held.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(victim.stat().st_mode), 0o500)
            self.assertTrue(original.is_symlink())
        finally:
            os.close(descriptor)

    def test_descriptor_permission_change_rejects_a_mismatched_proc_entry(self):
        module = self.api()
        target = self.destination_parent / "target"
        target.mkdir(mode=0o000)
        descriptor = os.open(target, module.OPEN_PATH_DIRECTORY)
        before = len(os.listdir("/proc/self/fd"))
        try:
            with mock.patch.object(module.os, "stat", return_value=self.destination_parent.stat()):
                with mock.patch.object(module.os, "chmod") as chmod:
                    self.assert_safe_failure(lambda: module._fchmod_path_descriptor(descriptor, 0o700))
                chmod.assert_not_called()
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o000)
            self.assertEqual(len(os.listdir("/proc/self/fd")), before)
        finally:
            os.close(descriptor)

    def test_descriptor_permission_change_does_not_use_project_paths_if_proc_is_unavailable(self):
        module = self.api()
        target = self.destination_parent / "target"
        target.mkdir(mode=0o000)
        descriptor = os.open(target, module.OPEN_PATH_DIRECTORY)
        try:
            with mock.patch.object(module.os, "open", side_effect=FileNotFoundError("proc unavailable")):
                with mock.patch.object(module.os, "chmod") as chmod:
                    self.assert_safe_failure(lambda: module._fchmod_path_descriptor(descriptor, 0o700))
                chmod.assert_not_called()
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o000)
        finally:
            os.close(descriptor)

    def test_recheck_catches_byte_type_mode_extra_and_missing_changes(self):
        mutations = ("byte", "type", "mode", "extra", "missing")
        for index, mutation in enumerate(mutations):
            with self.subTest(mutation=mutation):
                source, files = self.make_source(f"recheck-source-{index}")
                destination = self.base / f"recheck-destination-{index}"
                destination.mkdir(mode=0o700)
                prepared, _raw, _digest = self.prepare(
                    source, files, destination_parent=destination
                )
                target = prepared.root / "lib/data.txt"
                if mutation == "byte":
                    target.chmod(0o600)
                    target.write_bytes(b"tampered-data\n")
                    target.chmod(0o400)
                elif mutation == "type":
                    (prepared.root / "lib").chmod(0o700)
                    target.unlink()
                    target.mkdir(mode=0o500)
                    (prepared.root / "lib").chmod(0o500)
                elif mutation == "mode":
                    target.chmod(0o600)
                elif mutation == "extra":
                    prepared.root.chmod(0o700)
                    extra = prepared.root / "extra"
                    extra.write_bytes(b"extra")
                    extra.chmod(0o400)
                    prepared.root.chmod(0o500)
                else:
                    (prepared.root / "lib").chmod(0o700)
                    target.unlink()
                    (prepared.root / "lib").chmod(0o500)
                self.assert_safe_failure(lambda prepared=prepared: self.api().recheck_content_root(prepared))

    def test_recheck_rejects_forged_or_inconsistent_result(self):
        module = self.api()
        source, files = self.make_source()
        prepared, _raw, _digest = self.prepare(source, files)
        inconsistent = dataclasses.replace(prepared, file_count=prepared.file_count + 1)
        wrong_root = dataclasses.replace(prepared, root=prepared.root.parent / "wrong-name")
        for candidate in (object(), inconsistent, wrong_root):
            with self.subTest(candidate=type(candidate).__name__):
                self.assert_safe_failure(lambda candidate=candidate: module.recheck_content_root(candidate))

    def test_recheck_binds_retained_entries_to_original_manifest_digest(self):
        module = self.api()
        source, files = self.make_source()
        prepared, _raw, _digest = self.prepare(source, files)
        changed = b"replaced-data\n"
        target = prepared.root / "lib/data.txt"
        target.chmod(0o600)
        target.write_bytes(changed)
        target.chmod(0o400)
        entries = tuple(
            dataclasses.replace(entry, sha256=hashlib.sha256(changed).hexdigest(), bytes=len(changed))
            if entry.path == "lib/data.txt" else entry
            for entry in prepared._entries
        )
        forged = dataclasses.replace(
            prepared,
            _entries=entries,
            total_bytes=sum(entry.bytes for entry in entries),
        )
        self.assert_safe_failure(lambda: module.recheck_content_root(forged))

    def test_recheck_rejects_root_path_substitution_after_open(self):
        module = self.api()
        source, files = self.make_source()
        prepared, _raw, _digest = self.prepare(source, files)
        backup = self.destination_parent / "root-swap-backup"
        real_verify = module._verify_open_tree

        def replace_root(descriptor, entries):
            prepared.root.rename(backup)
            prepared.root.mkdir(mode=0o500)
            return real_verify(descriptor, entries)

        with mock.patch.object(module, "_verify_open_tree", side_effect=replace_root):
            self.assert_safe_failure(lambda: module.recheck_content_root(prepared))

    def test_prepare_rejects_published_root_substitution_and_cleans_owned_inode(self):
        module = self.api()
        source, files = self.make_source()
        raw, digest = manifest_for(files)
        target = self.destination_parent / f"artifact-{digest}"
        backup = self.destination_parent / "published-root-backup"
        real_verify = module._verify_open_tree
        calls = 0

        def replace_published_root(descriptor, entries):
            nonlocal calls
            calls += 1
            if calls == 2:
                target.rename(backup)
                target.mkdir(mode=0o500)
            return real_verify(descriptor, entries)

        with mock.patch.object(module, "_verify_open_tree", side_effect=replace_published_root):
            self.assert_safe_failure(
                lambda: module.prepare_content_root(source, raw, digest, self.destination_parent)
            )
        self.assertEqual(calls, 2)
        self.assertTrue(target.is_dir())
        self.assertEqual(list(target.iterdir()), [])
        self.assertFalse(backup.exists())

    def test_recheck_matches_read_descriptor_to_initial_scanned_file(self):
        module = self.api()
        source, files = self.make_source(files={"a/b/data": (b"good", False)})
        prepared, _raw, _digest = self.prepare(source, files)
        branch = prepared.root / "a/b"
        parent = branch.parent
        (branch / "data").chmod(0o600)
        (branch / "data").write_bytes(b"evil")
        (branch / "data").chmod(0o400)
        replacement = self.base / "verified-branch"
        replacement.mkdir(mode=0o700)
        (replacement / "data").write_bytes(b"good")
        (replacement / "data").chmod(0o400)
        replacement.chmod(0o500)
        backup = self.base / "unverified-branch"
        real_directory = module._directory_at

        @contextmanager
        def swap_for_read(descriptor, parts):
            if list(parts) != ["a", "b"]:
                with real_directory(descriptor, parts) as opened:
                    yield opened
                return
            parent.chmod(0o700)
            branch.chmod(0o700)
            replacement.chmod(0o700)
            branch.rename(backup)
            replacement.rename(branch)
            branch.chmod(0o500)
            parent.chmod(0o500)
            try:
                with real_directory(descriptor, parts) as opened:
                    yield opened
            finally:
                parent.chmod(0o700)
                branch.chmod(0o700)
                branch.rename(replacement)
                backup.rename(branch)
                branch.chmod(0o500)
                replacement.chmod(0o500)
                parent.chmod(0o500)

        with mock.patch.object(module, "_directory_at", side_effect=swap_for_read):
            self.assert_safe_failure(lambda: module.recheck_content_root(prepared))
        self.assertEqual((branch / "data").read_bytes(), b"evil")

    def test_errors_do_not_disclose_paths_and_success_invokes_no_process_or_network(self):
        module = self.api()
        source, files = self.make_source("TOP-SECRET-CANARY")
        raw, digest = manifest_for(files)
        error = self.assert_safe_failure(
            lambda: module.prepare_content_root(source, raw, "0" * 64, self.destination_parent)
        )
        self.assertEqual(str(error), "Content root verification failed")
        self.assertNotIn("TOP-SECRET-CANARY", repr(error))
        self.assertNotIn(raw.decode("utf-8"), repr(error))

        missing = self.source_parent / "PRIVATE-MISSING-PATH"
        missing_error = self.assert_safe_failure(
            lambda: module.prepare_content_root(missing, raw, digest, self.destination_parent)
        )
        self.assertIsNone(missing_error.__cause__)
        self.assertIsNone(missing_error.__context__)

        with mock.patch.object(subprocess, "Popen") as process:
            import socket

            with mock.patch.object(socket, "socket") as network:
                prepared = module.prepare_content_root(source, raw, digest, self.destination_parent)
                module.recheck_content_root(prepared)
        process.assert_not_called()
        network.assert_not_called()


if __name__ == "__main__":
    unittest.main()
