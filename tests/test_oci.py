import hashlib
import json
import os
import socket
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

import sentinel.oci as oci
from sentinel.errors import SentinelError


CLIENT_SHA = "c0b4d78635d4e2171a36fcfa1cdee696167ad87e2f7775220f95e7fcb024557a"
IMAGE_SHA = "1e0a86e57d247923571b75e0aaf48a1449cf8c543d51fb3e07a4a7d7bfa79316"


def lock_value():
    return {
        "schemaVersion": "sentinel-oci-executor-lock-v1",
        "client": {"path": "/usr/bin/docker", "sha256": CLIENT_SHA, "version": "25.0.14", "gitCommit": "0bab007", "apiVersion": "1.44", "os": "linux", "architecture": "amd64"},
        "server": {"version": "25.0.16", "gitCommit": "6fdf0a6", "apiVersion": "1.44", "os": "linux", "architecture": "amd64"},
        "socket": {"path": "/run/docker.sock", "owner": "root", "group": "docker", "mode": "0660"},
        "image": {"reference": "docker.io/library/ubuntu@sha256:" + IMAGE_SHA, "os": "linux", "architecture": "amd64"},
    }


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def binary_evidence():
    return {"path": "/usr/bin/docker", "sha256": CLIENT_SHA, "device": 1, "inode": 2, "uid": 0, "gid": 0, "mode": 0o755, "size": 100, "mtimeNs": "10", "ctimeNs": "11"}


def socket_evidence():
    return {"path": "/run/docker.sock", "device": 3, "inode": 4, "uid": 0, "gid": 992, "mode": 0o660}


def version_evidence():
    return {
        "client": {"version": "25.0.14", "apiVersion": "1.44", "gitCommit": "0bab007", "os": "linux", "architecture": "amd64", "context": "default"},
        "server": {"version": "25.0.16", "apiVersion": "1.44", "gitCommit": "6fdf0a6", "os": "linux", "architecture": "amd64"},
    }


STAT_FIELDS = (
    "st_dev", "st_ino", "st_uid", "st_gid", "st_mode", "st_nlink",
    "st_size", "st_mtime_ns", "st_ctime_ns",
)


def changed_stat(metadata, **changes):
    values = {field: getattr(metadata, field) for field in STAT_FIELDS}
    values.update(changes)
    return SimpleNamespace(**values)


def ownership_boundary_patches(target, uid=0, gid=None):
    real_lstat = os.lstat
    real_fstat = os.fstat
    original = real_lstat(target)
    target_text = os.fspath(target)

    def lstat(candidate, *args, **kwargs):
        metadata = real_lstat(candidate, *args, **kwargs)
        if os.fspath(candidate) == target_text:
            changes = {"st_uid": uid}
            if gid is not None:
                changes["st_gid"] = gid
            return changed_stat(metadata, **changes)
        return metadata

    def fstat(descriptor):
        metadata = real_fstat(descriptor)
        if metadata.st_dev == original.st_dev and metadata.st_ino == original.st_ino:
            changes = {"st_uid": uid}
            if gid is not None:
                changes["st_gid"] = gid
            return changed_stat(metadata, **changes)
        return metadata

    return mock.patch.object(oci.os, "lstat", side_effect=lstat), mock.patch.object(oci.os, "fstat", side_effect=fstat)


class OciSessionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.parent = self.base / "private"
        self.parent.mkdir(mode=0o700)
        self.lock = self.base / "lock.json"
        self.lock.write_bytes(canonical(lock_value()))
        self.lock_sha = hashlib.sha256(self.lock.read_bytes()).hexdigest()
        self.session = self.parent / "session"
        self.patches = [
            mock.patch.object(oci, "_inspect_binary", return_value=binary_evidence()),
            mock.patch.object(oci, "_inspect_socket", return_value=socket_evidence()),
            mock.patch.object(oci, "_run_version", return_value=version_evidence()),
        ]
        for patcher in self.patches:
            patcher.start()

    def tearDown(self):
        for patcher in reversed(self.patches):
            patcher.stop()
        self.temporary.cleanup()

    def test_prepare_session_seals_private_canonical_record(self):
        digest = oci.prepare_session(self.lock, self.lock_sha, self.session)
        record_path = self.session / "session.json"
        raw = record_path.read_bytes()
        self.assertEqual(digest, hashlib.sha256(raw).hexdigest())
        self.assertEqual(raw, canonical(json.loads(raw)))
        self.assertEqual(stat.S_IMODE(self.session.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((self.session / "docker-config").stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(record_path.stat().st_mode), 0o600)
        self.assertEqual(list((self.session / "docker-config").iterdir()), [])
        record = json.loads(raw)
        eyeball = {"schemaVersion", "lockSha256", "effectiveUid", "root", "binary", "socket", "config", "version"}
        self.assertEqual(set(record), eyeball)
        self.assertEqual(record["schemaVersion"], "sentinel-oci-executor-session-v1")

    def test_invalid_lock_fails_before_docker_and_session_creation(self):
        variants = []
        remote = lock_value()
        remote["client"]["path"] = "/tmp/docker"
        variants.append(canonical(remote))
        remote_socket = lock_value()
        remote_socket["socket"]["path"] = "/tmp/docker.sock"
        variants.append(canonical(remote_socket))
        unknown = lock_value()
        unknown["extra"] = True
        variants.append(canonical(unknown))
        variants.append(self.lock.read_bytes().replace(b'"client":{', b'"client":{},"client":{', 1))
        variants.append(b'{"schemaVersion":NaN}')
        for index, raw in enumerate(variants):
            with self.subTest(index=index):
                self.lock.write_bytes(raw)
                target = self.parent / f"bad-{index}"
                with self.assertRaises(SentinelError) as caught:
                    oci.prepare_session(self.lock, hashlib.sha256(raw).hexdigest(), target)
                self.assertEqual(caught.exception.exit_code, 5)
                self.assertFalse(target.exists())
        oci._run_version.assert_not_called()

    def test_symlink_hardlink_special_and_oversize_lock_are_rejected(self):
        symlink = self.base / "symlink"
        symlink.symlink_to(self.lock)
        hardlink = self.base / "hardlink"
        os.link(self.lock, hardlink)
        fifo = self.base / "fifo"
        os.mkfifo(fifo)
        oversized = self.base / "oversized"
        with oversized.open("wb") as stream:
            stream.truncate(oci.MAX_LOCK_BYTES + 1)
        for index, path in enumerate((symlink, hardlink, fifo, oversized)):
            with self.subTest(path=path.name):
                with self.assertRaises(SentinelError):
                    oci.prepare_session(path, "0" * 64, self.parent / f"unsafe-{index}")
        oci._run_version.assert_not_called()

    def test_existing_session_is_never_overwritten(self):
        self.session.mkdir(mode=0o700)
        marker = self.session / "session.json"
        marker.write_text("keep", encoding="utf-8")
        with self.assertRaises(SentinelError):
            oci.prepare_session(self.lock, self.lock_sha, self.session)
        self.assertEqual(marker.read_text(encoding="utf-8"), "keep")
        oci._run_version.assert_not_called()

    def test_invalid_session_path_domain_fails_before_child_or_creation(self):
        invalid_names = ("line\nbreak", "tab\tname", "nul\x00name", "del\x7fname", "surrogate\ud800name")
        for name in invalid_names:
            with self.subTest(name=repr(name)):
                before = sorted(path.name for path in self.parent.iterdir())
                calls = oci._run_version.call_count
                with self.assertRaises(SentinelError) as caught:
                    oci.prepare_session(self.lock, self.lock_sha, self.parent / name)
                self.assertEqual(caught.exception.exit_code, 5)
                self.assertEqual(oci._run_version.call_count, calls)
                self.assertEqual(sorted(path.name for path in self.parent.iterdir()), before)

    def test_unicode_session_path_round_trips_without_record_write(self):
        target = self.parent / "한글 세션"
        digest = oci.prepare_session(self.lock, self.lock_sha, target)
        record = target / "session.json"
        before = record.read_bytes()
        oci.recheck_session(self.lock, self.lock_sha, target, digest)
        self.assertEqual(record.read_bytes(), before)
        self.assertEqual(oci._run_version.call_count, 2)

    def test_invalid_derived_config_path_fails_before_child_or_creation(self):
        real_bounded_path = oci._bounded_path_string

        def reject_only_derived_path(value):
            if value.endswith("/docker-config"):
                return False
            return real_bounded_path(value)

        with mock.patch.object(oci, "_bounded_path_string", side_effect=reject_only_derived_path):
            with self.assertRaises(SentinelError):
                oci.prepare_session(self.lock, self.lock_sha, self.session)
        oci._run_version.assert_not_called()
        self.assertFalse(self.session.exists())

    def test_config_or_binary_change_during_query_rejects_success_record(self):
        def dirty_config(config):
            (config / "credential").write_text("unexpected", encoding="utf-8")
            return version_evidence()

        oci._run_version.side_effect = dirty_config
        with self.assertRaises(SentinelError):
            oci.prepare_session(self.lock, self.lock_sha, self.session)
        self.assertFalse((self.session / "session.json").exists())

    def test_version_contract_mismatch_is_rejected(self):
        bad = version_evidence()
        bad["client"]["context"] = "remote"
        oci._run_version.return_value = bad
        with self.assertRaises(SentinelError):
            oci.prepare_session(self.lock, self.lock_sha, self.session)
        self.assertFalse((self.session / "session.json").exists())

    def test_binary_or_socket_identity_swap_after_query_is_rejected(self):
        for name in ("binary", "socket"):
            with self.subTest(name=name):
                target = self.parent / ("swap-" + name)
                if name == "binary":
                    oci._inspect_binary.side_effect = [binary_evidence(), dict(binary_evidence(), inode=99)]
                else:
                    oci._inspect_socket.side_effect = [socket_evidence(), dict(socket_evidence(), inode=99)]
                with self.assertRaises(SentinelError):
                    oci.prepare_session(self.lock, self.lock_sha, target)
                self.assertFalse((target / "session.json").exists())
                oci._inspect_binary.side_effect = None
                oci._inspect_socket.side_effect = None
                oci._inspect_binary.return_value = binary_evidence()
                oci._inspect_socket.return_value = socket_evidence()

    def test_each_version_identity_mismatch_is_rejected(self):
        mutations = (("client", "version"), ("client", "apiVersion"), ("client", "os"), ("client", "architecture"), ("server", "version"), ("server", "gitCommit"))
        for index, (side, field) in enumerate(mutations):
            with self.subTest(side=side, field=field):
                bad = version_evidence()
                bad[side][field] = "wrong"
                oci._run_version.return_value = bad
                target = self.parent / f"version-{index}"
                with self.assertRaises(SentinelError):
                    oci.prepare_session(self.lock, self.lock_sha, target)
                self.assertFalse((target / "session.json").exists())

    def test_recheck_accepts_unchanged_session_without_writing(self):
        digest = oci.prepare_session(self.lock, self.lock_sha, self.session)
        record = self.session / "session.json"
        before = (record.stat().st_mtime_ns, record.read_bytes())
        oci.recheck_session(self.lock, self.lock_sha, self.session, digest)
        self.assertEqual((record.stat().st_mtime_ns, record.read_bytes()), before)
        self.assertEqual(oci._run_version.call_count, 2)

    def test_recheck_rejects_record_digest_mode_config_and_lock_tamper(self):
        digest = oci.prepare_session(self.lock, self.lock_sha, self.session)
        record = self.session / "session.json"
        with self.assertRaises(SentinelError):
            oci.recheck_session(self.lock, self.lock_sha, self.session, "0" * 64)
        record.chmod(0o644)
        with self.assertRaises(SentinelError):
            oci.recheck_session(self.lock, self.lock_sha, self.session, digest)
        record.chmod(0o600)
        (self.session / "docker-config" / "credential").write_text("x", encoding="utf-8")
        with self.assertRaises(SentinelError):
            oci.recheck_session(self.lock, self.lock_sha, self.session, digest)
        self.assertEqual(oci._run_version.call_count, 1)

    def test_recheck_rejects_config_identity_session_link_and_lock_tamper_before_query(self):
        digest = oci.prepare_session(self.lock, self.lock_sha, self.session)
        oci._run_version.reset_mock()
        config = self.session / "docker-config"
        old_config = self.session / "old-config"
        config.rename(old_config)
        config.mkdir(mode=0o700)
        with self.assertRaises(SentinelError):
            oci.recheck_session(self.lock, self.lock_sha, self.session, digest)
        oci._run_version.assert_not_called()
        config.rmdir()
        old_config.rename(config)
        linked = self.session / "linked-record"
        os.link(self.session / "session.json", linked)
        with self.assertRaises(SentinelError):
            oci.recheck_session(self.lock, self.lock_sha, self.session, digest)
        oci._run_version.assert_not_called()
        linked.unlink()
        self.lock.write_bytes(self.lock.read_bytes() + b" ")
        with self.assertRaises(SentinelError):
            oci.recheck_session(self.lock, self.lock_sha, self.session, digest)
        oci._run_version.assert_not_called()

    def test_prepare_root_swap_does_not_publish_to_replacement(self):
        original = self.parent / "original"

        def swap_root(_config):
            self.session.rename(original)
            self.session.mkdir(mode=0o700)
            (original / "docker-config").rename(self.session / "docker-config")
            return version_evidence()

        oci._run_version.side_effect = swap_root
        with self.assertRaises(SentinelError):
            oci.prepare_session(self.lock, self.lock_sha, self.session)
        self.assertFalse((self.session / "session.json").exists())
        self.assertFalse((original / "session.json").exists())

    def test_recheck_rejects_record_changed_during_version_query(self):
        digest = oci.prepare_session(self.lock, self.lock_sha, self.session)

        def tamper_record(_config):
            (self.session / "session.json").write_bytes(b"changed-during-recheck\n")
            return version_evidence()

        oci._run_version.side_effect = tamper_record
        with self.assertRaises(SentinelError):
            oci.recheck_session(self.lock, self.lock_sha, self.session, digest)

    def test_file_fsync_failure_leaves_no_final_session_record(self):
        real_fsync = os.fsync

        def fail_regular(descriptor):
            if stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise OSError("injected")
            return real_fsync(descriptor)

        with mock.patch.object(oci.os, "fsync", side_effect=fail_regular):
            with self.assertRaises(SentinelError):
                oci.prepare_session(self.lock, self.lock_sha, self.session)
        self.assertFalse((self.session / "session.json").exists())

    def test_directory_fsync_failure_removes_only_owned_final_record(self):
        real_fsync = os.fsync

        def fail_published_directory(descriptor):
            if stat.S_ISDIR(os.fstat(descriptor).st_mode) and (self.session / "session.json").exists():
                raise OSError("injected")
            return real_fsync(descriptor)

        with mock.patch.object(oci.os, "fsync", side_effect=fail_published_directory):
            with self.assertRaises(SentinelError):
                oci.prepare_session(self.lock, self.lock_sha, self.session)
        self.assertFalse((self.session / "session.json").exists())

    def test_final_root_check_failure_removes_owned_success_record(self):
        real_directory_evidence = oci._directory_evidence
        root_checks = 0

        def fail_second_root_check(path, mode, include_path=True):
            nonlocal root_checks
            if path == self.session and not include_path:
                root_checks += 1
                if root_checks == 2:
                    raise oci._failure()
            return real_directory_evidence(path, mode, include_path)

        with mock.patch.object(oci, "_directory_evidence", side_effect=fail_second_root_check):
            with self.assertRaises(SentinelError):
                oci.prepare_session(self.lock, self.lock_sha, self.session)
        self.assertEqual(root_checks, 2)
        self.assertFalse((self.session / "session.json").exists())

    def test_record_descriptor_close_failure_removes_owned_success_record(self):
        real_close = os.close
        record_descriptor = None
        repeated_record_close = 0
        root_close_after_failure = 0
        descriptors_before = set(os.listdir("/proc/self/fd"))

        def fail_published_record_close(descriptor):
            nonlocal record_descriptor, repeated_record_close, root_close_after_failure
            try:
                metadata = os.fstat(descriptor)
            except OSError:
                if descriptor == record_descriptor:
                    repeated_record_close += 1
                    raise OSError("repeated close")
                return real_close(descriptor)
            if record_descriptor is not None and stat.S_ISDIR(metadata.st_mode):
                if metadata.st_ino == self.session.stat().st_ino:
                    root_close_after_failure += 1
            if record_descriptor is None and stat.S_ISREG(metadata.st_mode) and (self.session / "session.json").exists():
                record_descriptor = descriptor
                real_close(descriptor)
                raise OSError("closed then injected")
            return real_close(descriptor)

        with mock.patch.object(oci.os, "close", side_effect=fail_published_record_close):
            with self.assertRaises(SentinelError):
                oci.prepare_session(self.lock, self.lock_sha, self.session)
        self.assertFalse((self.session / "session.json").exists())
        self.assertEqual(repeated_record_close, 0)
        self.assertEqual(root_close_after_failure, 1)
        self.assertEqual(set(os.listdir("/proc/self/fd")), descriptors_before)

    def test_prepublication_cleanup_closes_root_after_record_close_error(self):
        real_close = os.close
        real_fsync = os.fsync
        staged_descriptor = None
        injected = False

        def fail_record_fsync(descriptor):
            nonlocal staged_descriptor
            if stat.S_ISREG(os.fstat(descriptor).st_mode):
                staged_descriptor = descriptor
                raise OSError("injected fsync failure")
            return real_fsync(descriptor)

        def close_record_then_fail(descriptor):
            nonlocal injected
            if descriptor == staged_descriptor and not injected:
                injected = True
                real_close(descriptor)
                raise OSError("closed then injected")
            return real_close(descriptor)

        with mock.patch.object(oci.os, "fsync", side_effect=fail_record_fsync):
            with mock.patch.object(oci.os, "close", side_effect=close_record_then_fail):
                with self.assertRaises(SentinelError):
                    oci.prepare_session(self.lock, self.lock_sha, self.session)
        leaked = self.open_descriptors_for(self.session)
        for descriptor in leaked:
            real_close(descriptor)
        self.assertTrue(injected)
        self.assertFalse((self.session / "session.json").exists())
        self.assertEqual(leaked, [])

    def test_creation_cleanup_closes_parent_after_root_close_error(self):
        real_close = os.close
        injected = False

        def close_root_then_fail(descriptor):
            nonlocal injected
            target = os.readlink("/proc/self/fd/" + str(descriptor))
            if target == str(self.session) and not injected:
                injected = True
                real_close(descriptor)
                raise OSError("closed then injected")
            return real_close(descriptor)

        with mock.patch.object(oci.os, "close", side_effect=close_root_then_fail):
            with self.assertRaises(SentinelError):
                oci.prepare_session(self.lock, self.lock_sha, self.session)
        leaked = self.open_descriptors_for(self.parent)
        for descriptor in leaked:
            real_close(descriptor)
        self.assertTrue(injected)
        self.assertFalse((self.session / "session.json").exists())
        oci._run_version.assert_not_called()
        self.assertEqual(leaked, [])

    @staticmethod
    def open_descriptors_for(path):
        descriptors = []
        for entry in Path("/proc/self/fd").iterdir():
            try:
                if os.readlink(entry) == str(path):
                    descriptors.append(int(entry.name))
            except FileNotFoundError:
                pass
        return descriptors

    def test_committed_record_survives_read_only_root_close_error(self):
        real_close = os.close
        injected = False
        descriptors_before = set(os.listdir("/proc/self/fd"))

        def close_root_then_fail(descriptor):
            nonlocal injected
            metadata = os.fstat(descriptor)
            if (
                not injected
                and stat.S_ISDIR(metadata.st_mode)
                and self.session.exists()
                and metadata.st_ino == self.session.stat().st_ino
                and (self.session / "session.json").exists()
            ):
                injected = True
                real_close(descriptor)
                raise OSError("closed then injected")
            return real_close(descriptor)

        with mock.patch.object(oci.os, "close", side_effect=close_root_then_fail):
            digest = oci.prepare_session(self.lock, self.lock_sha, self.session)
        self.assertTrue(injected)
        self.assertEqual(set(os.listdir("/proc/self/fd")), descriptors_before)
        oci.recheck_session(self.lock, self.lock_sha, self.session, digest)

    def test_committed_record_survives_read_only_root_close_interrupt(self):
        real_close = os.close
        root_descriptor = None
        repeated_close = 0
        descriptors_before = set(os.listdir("/proc/self/fd"))

        def close_root_then_interrupt(descriptor):
            nonlocal root_descriptor, repeated_close
            try:
                metadata = os.fstat(descriptor)
            except OSError:
                if descriptor == root_descriptor:
                    repeated_close += 1
                raise
            if (
                root_descriptor is None
                and stat.S_ISDIR(metadata.st_mode)
                and self.session.exists()
                and metadata.st_ino == self.session.stat().st_ino
                and (self.session / "session.json").exists()
            ):
                root_descriptor = descriptor
                real_close(descriptor)
                raise KeyboardInterrupt
            return real_close(descriptor)

        interrupted = False
        digest = None
        try:
            with mock.patch.object(oci.os, "close", side_effect=close_root_then_interrupt):
                digest = oci.prepare_session(self.lock, self.lock_sha, self.session)
        except KeyboardInterrupt:
            interrupted = True
        self.assertFalse(interrupted, "a completed prepare must preserve its digest result")
        self.assertIsNotNone(digest)
        record = self.session / "session.json"
        self.assertEqual(digest, hashlib.sha256(record.read_bytes()).hexdigest())
        self.assertEqual(repeated_close, 0)
        self.assertEqual(set(os.listdir("/proc/self/fd")), descriptors_before)
        oci.recheck_session(self.lock, self.lock_sha, self.session, digest)

    def test_precommit_record_close_interrupt_removes_record_and_propagates(self):
        real_close = os.close
        record_descriptor = None
        repeated_close = 0
        descriptors_before = set(os.listdir("/proc/self/fd"))

        def close_record_then_interrupt(descriptor):
            nonlocal record_descriptor, repeated_close
            try:
                metadata = os.fstat(descriptor)
            except OSError:
                if descriptor == record_descriptor:
                    repeated_close += 1
                raise
            if record_descriptor is None and stat.S_ISREG(metadata.st_mode) and (self.session / "session.json").exists():
                record_descriptor = descriptor
                real_close(descriptor)
                raise KeyboardInterrupt
            return real_close(descriptor)

        with mock.patch.object(oci.os, "close", side_effect=close_record_then_interrupt):
            with self.assertRaises(KeyboardInterrupt):
                oci.prepare_session(self.lock, self.lock_sha, self.session)
        self.assertFalse((self.session / "session.json").exists())
        self.assertEqual(repeated_close, 0)
        self.assertEqual(set(os.listdir("/proc/self/fd")), descriptors_before)

    def test_temporary_record_swap_is_rejected_without_deleting_replacement(self):
        real_publish = oci._rename_noreplace
        replacement = b"changed-before-publication\n"

        def swap_temporary(directory_fd, source, destination):
            os.rename(source, "original-temporary", src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
            descriptor = os.open(source, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=directory_fd)
            try:
                os.write(descriptor, replacement)
            finally:
                os.close(descriptor)
            real_publish(directory_fd, source, destination)

        with mock.patch.object(oci, "_rename_noreplace", side_effect=swap_temporary):
            with self.assertRaises(SentinelError):
                oci.prepare_session(self.lock, self.lock_sha, self.session)
        self.assertEqual((self.session / "session.json").read_bytes(), replacement)


class BinaryValidatorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def inspect_root_owned(self, path):
        lstat_patch, fstat_patch = ownership_boundary_patches(path)
        with mock.patch.object(oci, "DOCKER_PATH", path), lstat_patch, fstat_patch:
            return oci._inspect_binary()

    def test_streams_binary_and_returns_its_actual_digest(self):
        binary = self.base / "docker"
        raw = b"a" * (70 * 1024) + b"last"
        binary.write_bytes(raw)
        binary.chmod(0o755)

        evidence = self.inspect_root_owned(binary)

        self.assertEqual(evidence["path"], str(binary))
        self.assertEqual(evidence["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(evidence["size"], len(raw))

    def test_rejects_non_root_binary_owner(self):
        binary = self.base / "docker"
        binary.write_bytes(b"binary")
        binary.chmod(0o755)
        lstat_patch, fstat_patch = ownership_boundary_patches(binary, uid=1)
        with mock.patch.object(oci, "DOCKER_PATH", binary), lstat_patch, fstat_patch:
            with self.assertRaises(SentinelError):
                oci._inspect_binary()

    def test_rejects_non_executable_and_writable_binary_modes(self):
        for index, mode in enumerate((0o644, 0o775, 0o757)):
            with self.subTest(mode=oct(mode)):
                binary = self.base / f"docker-{index}"
                binary.write_bytes(b"binary")
                binary.chmod(mode)
                with self.assertRaises(SentinelError):
                    self.inspect_root_owned(binary)

    def test_rejects_hardlinked_binary(self):
        binary = self.base / "docker"
        linked = self.base / "docker-link"
        binary.write_bytes(b"binary")
        binary.chmod(0o755)
        os.link(binary, linked)
        with self.assertRaises(SentinelError):
            self.inspect_root_owned(binary)

    def test_rejects_special_binary_type(self):
        binary = self.base / "docker"
        os.mkfifo(binary, 0o755)
        with self.assertRaises(SentinelError):
            self.inspect_root_owned(binary)

    def test_rejects_binary_larger_than_limit(self):
        binary = self.base / "docker"
        with binary.open("wb") as stream:
            stream.truncate(oci.MAX_BINARY_BYTES + 1)
        binary.chmod(0o755)
        with self.assertRaises(SentinelError):
            self.inspect_root_owned(binary)

    def test_rejects_path_replaced_during_streaming_digest(self):
        binary = self.base / "docker"
        replaced = self.base / "docker-original"
        binary.write_bytes(b"a" * (70 * 1024))
        binary.chmod(0o755)
        real_read = os.read
        replaced_path = False

        def replace_after_first_read(descriptor, size):
            nonlocal replaced_path
            chunk = real_read(descriptor, size)
            if chunk and not replaced_path:
                replaced_path = True
                binary.rename(replaced)
                binary.write_bytes(b"replacement")
                binary.chmod(0o755)
            return chunk

        lstat_patch, fstat_patch = ownership_boundary_patches(binary)
        with mock.patch.object(oci, "DOCKER_PATH", binary), lstat_patch, fstat_patch:
            with mock.patch.object(oci.os, "read", side_effect=replace_after_first_read):
                with self.assertRaises(SentinelError):
                    oci._inspect_binary()
        self.assertTrue(replaced_path)


class SocketValidatorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def inspect_root_owned(self, path, docker_gid):
        lstat_patch, _fstat_patch = ownership_boundary_patches(path, uid=0)
        group = SimpleNamespace(gr_gid=docker_gid)
        with mock.patch.object(oci, "SOCKET_PATH", path), lstat_patch:
            with mock.patch.object(oci.grp, "getgrnam", return_value=group):
                return oci._inspect_socket()

    def test_accepts_real_unix_socket_with_required_owner_group_and_mode(self):
        socket_path = self.base / "docker.sock"
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            listener.bind(str(socket_path))
            socket_path.chmod(0o660)
            metadata = socket_path.lstat()
            evidence = self.inspect_root_owned(socket_path, metadata.st_gid)
        self.assertEqual(evidence["path"], str(socket_path))
        self.assertEqual(evidence["mode"], 0o660)

    def test_rejects_regular_file_as_socket(self):
        socket_path = self.base / "docker.sock"
        socket_path.write_bytes(b"not a socket")
        socket_path.chmod(0o660)
        with self.assertRaises(SentinelError):
            self.inspect_root_owned(socket_path, socket_path.stat().st_gid)

    def test_rejects_socket_owner_group_and_mode_mismatches(self):
        for mismatch in ("owner", "group", "mode"):
            with self.subTest(mismatch=mismatch):
                socket_path = self.base / ("docker-" + mismatch + ".sock")
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
                    listener.bind(str(socket_path))
                    socket_path.chmod(0o600 if mismatch == "mode" else 0o660)
                    metadata = socket_path.lstat()
                    uid = 1 if mismatch == "owner" else 0
                    docker_gid = metadata.st_gid + 1 if mismatch == "group" else metadata.st_gid
                    lstat_patch, _fstat_patch = ownership_boundary_patches(socket_path, uid=uid)
                    group = SimpleNamespace(gr_gid=docker_gid)
                    with mock.patch.object(oci, "SOCKET_PATH", socket_path), lstat_patch:
                        with mock.patch.object(oci.grp, "getgrnam", return_value=group):
                            with self.assertRaises(SentinelError):
                                oci._inspect_socket()

    def test_rejects_missing_docker_group_lookup(self):
        socket_path = self.base / "docker.sock"
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            listener.bind(str(socket_path))
            socket_path.chmod(0o660)
            lstat_patch, _fstat_patch = ownership_boundary_patches(socket_path, uid=0)
            with mock.patch.object(oci, "SOCKET_PATH", socket_path), lstat_patch:
                with mock.patch.object(oci.grp, "getgrnam", side_effect=KeyError("docker")):
                    with self.assertRaises(SentinelError):
                        oci._inspect_socket()


class VersionResponseTests(unittest.TestCase):
    def docker_response(self):
        return {
            "Client": {"Version": "25.0.14", "ApiVersion": "1.44", "GitCommit": "0bab007", "Os": "linux", "Arch": "amd64", "Context": "default"},
            "Server": {
                "Version": "25.0.16", "ApiVersion": "1.44", "GitCommit": "6fdf0a6", "Os": "linux", "Arch": "amd64",
                "Components": [{"Name": "Engine", "Version": "25.0.16", "Details": {"ApiVersion": "1.44", "GitCommit": "6fdf0a6", "Os": "linux", "Arch": "amd64"}}],
            },
        }

    def test_docker_response_requires_consistent_engine_component(self):
        response = self.docker_response()
        self.assertEqual(oci._parse_version(canonical(response)), version_evidence())
        response["Server"]["Components"][0]["Details"]["ApiVersion"] = "1.43"
        with self.assertRaises(SentinelError):
            oci._parse_version(canonical(response))

    def test_malformed_duplicate_and_wrong_shape_responses_are_rejected(self):
        for raw in (b"not-json", b'{"Client":{},"Client":{}}', b'{"Client":NaN}', b"[]"):
            with self.subTest(raw=raw):
                with self.assertRaises(SentinelError):
                    oci._parse_version(raw)

    def test_every_engine_contract_field_must_match_top_level(self):
        for field in ("Version", "ApiVersion", "GitCommit", "Os", "Arch"):
            with self.subTest(field=field):
                response = self.docker_response()
                if field == "Version":
                    response["Server"]["Components"][0][field] = "wrong"
                else:
                    response["Server"]["Components"][0]["Details"][field] = "wrong"
                with self.assertRaises(SentinelError):
                    oci._parse_version(canonical(response))


class DockerInvocationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.config = self.root / "docker-config"
        self.config.mkdir()
        self.response = VersionResponseTests().docker_response()

    def tearDown(self):
        self.temporary.cleanup()

    def test_version_query_uses_exact_argv_cwd_and_sealed_environment(self):
        process = mock.Mock(returncode=0)
        with mock.patch.object(oci.subprocess, "Popen", return_value=process) as popen:
            with mock.patch.object(oci, "_collect", return_value=(canonical(self.response), b"secret", None)) as collect:
                result = oci._run_version(self.config)
        self.assertEqual(result, version_evidence())
        popen.assert_called_once_with(
            ["/usr/bin/docker", "--config", str(self.config), "--host", "unix:///run/docker.sock", "version", "--format", "{{json .}}"],
            stdin=oci.subprocess.PIPE,
            stdout=oci.subprocess.PIPE,
            stderr=oci.subprocess.PIPE,
            shell=False,
            start_new_session=True,
            cwd=str(self.root),
            env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"},
        )
        collect.assert_called_once_with(process, b"", 10.0)

    def test_nonzero_timeout_and_output_overflow_are_fixed_failures(self):
        cases = ((1, None), (0, "timeout"), (0, "outputOverflow"))
        for returncode, failure in cases:
            with self.subTest(returncode=returncode, failure=failure):
                process = mock.Mock(returncode=returncode)
                with mock.patch.object(oci.subprocess, "Popen", return_value=process):
                    with mock.patch.object(oci, "_collect", return_value=(b"raw", b"private", failure)):
                        with self.assertRaises(SentinelError) as caught:
                            oci._run_version(self.config)
                self.assertEqual(caught.exception.message, "OCI executor preflight failed")

    def test_cancellation_is_repropagated_after_collector_cleanup(self):
        process = mock.Mock(returncode=None)
        with mock.patch.object(oci.subprocess, "Popen", return_value=process):
            with mock.patch.object(oci, "_collect", side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):
                    oci._run_version(self.config)


if __name__ == "__main__":
    unittest.main()
