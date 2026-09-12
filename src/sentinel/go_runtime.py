"""Verify sealed Go SDK bytes using the release's original GNU tar identity."""

import hashlib
import json
import os
from dataclasses import dataclass, field
import tarfile

from . import content_root as content
from .errors import SentinelError


GO_LOCK = {
    "version": "1.27.1",
    "platform": "linux-amd64",
    "archiveUrl": "https://go.dev/dl/go1.27.1.linux-amd64.tar.gz",
    "archiveSize": 70553950,
    "archiveSha256": "63d339f0da5ab53635a56f2490a7984dfe12dfcff22ad749f63edaf590168445",
    "binarySha256": "30969f97169d7f43fe6a085873d75613adc21e30818a8c61d95bd27275df4624",
    "installedTreeAlgorithm": "gnu-tar-v1",
    "installedTreeSha256": "52dbc6ddf61a5f7019772085d134d610de7f3206ab5d3960d8b9ec63b3aa9564",
}


@dataclass(frozen=True)
class GoRuntime:
    content: content.PreparedRoot
    lock_sha256: str
    tree_sha256: str
    binary_sha256: str
    _lock: bytes = field(default=b"", repr=False)


def _failure():
    return SentinelError("goRuntimeFailed", "Go runtime verification failed", 5)


class _DigestWriter:
    def __init__(self):
        self.digest = hashlib.sha256()

    def write(self, data):
        self.digest.update(data)
        return len(data)


class _DigestReader:
    def __init__(self, descriptor):
        self.descriptor = descriptor
        self.digest = hashlib.sha256()
        self.size = 0

    def read(self, size):
        data = os.read(self.descriptor, size)
        self.digest.update(data)
        self.size += len(data)
        return data


class _ReleaseInfo(tarfile.TarInfo):
    def tobuf(self, *args, **kwargs):
        raw = super().tobuf(*args, **kwargs)
        # Python uses mode 0000 for its GNU long-name pseudo-entry; GNU tar
        # uses 0644. Both describe the same file, but the release lock pins bytes.
        if raw[156:157] == tarfile.GNUTYPE_LONGNAME:
            header = bytearray(raw[:512])
            header[100:108] = b"0000644\0"
            header[148:156] = b"        "
            header[148:156] = ("%06o\0 " % sum(header)).encode("ascii")
            raw = bytes(header) + raw[512:]
        return raw


def release_tree_sha256(prepared: content.PreparedRoot) -> str:
    """GNU tar v1, projecting sealed permissions back to release 0644/0755.

    This is only a serialization rule. No installed permission is changed.
    Empty directories are forbidden by the underlying content manifest contract.
    """
    descriptor = None
    try:
        # Reuse the same full verifier without the public install API's
        # interrupt-to-error normalization. The execution controller owns cancel.
        content._recheck(prepared)
        before = prepared.root.lstat()
        descriptor = content._open_exact_directory(prepared.root, before)
        root_snapshot, files, directories = content._scan_tree(descriptor, True)
        content._validate_inventory(prepared._entries, files, directories, True)
        entries = {entry.path: entry for entry in prepared._entries}
        children = {"": []}
        for relative in sorted(set(entries) | directories):
            parent = relative.rpartition("/")[0]
            children.setdefault(parent, []).append(relative)
            if relative in directories:
                children.setdefault(relative, [])
        writer = _DigestWriter()

        def add(archive, relative):
            is_directory = relative == "" or relative in directories
            info = _ReleaseInfo("./" + relative)
            info.uid = info.gid = info.mtime = 0
            info.uname = info.gname = ""
            info.mode = 0o755 if is_directory or entries[relative].executable else 0o644
            if is_directory:
                info.type = tarfile.DIRTYPE
                archive.addfile(info)
                for child in children[relative]:
                    add(archive, child)
                return
            entry = entries[relative]
            info.size = entry.bytes
            parts = relative.split("/")
            with content._directory_at(descriptor, parts[:-1]) as parent_descriptor:
                file_descriptor = os.open(parts[-1], content.OPEN_FILE, dir_fd=parent_descriptor)
                try:
                    opened = os.fstat(file_descriptor)
                    if content._snapshot(opened) != files[relative]:
                        raise _failure()
                    reader = _DigestReader(file_descriptor)
                    archive.addfile(info, reader)
                    if (
                        reader.size != entry.bytes
                        or reader.digest.hexdigest() != entry.sha256
                        or content._snapshot(os.fstat(file_descriptor)) != files[relative]
                    ):
                        raise _failure()
                finally:
                    os.close(file_descriptor)

        with tarfile.open(fileobj=writer, mode="w|", format=tarfile.GNU_FORMAT, encoding="utf-8") as archive:
            add(archive, "")
        if content._scan_tree(descriptor, True) != (root_snapshot, files, directories):
            raise _failure()
        content._require_open_path_identity(prepared.root, descriptor, before)
        content._recheck(prepared)
        return writer.digest.hexdigest()
    except SentinelError:
        raise _failure() from None
    except (OSError, ValueError, TypeError, KeyError, RecursionError, tarfile.TarError):
        raise _failure() from None
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _verify_lock(lock: bytes, lock_sha256: str) -> None:
    try:
        if (type(lock) is not bytes or len(lock) > 1024 * 1024
                or type(lock_sha256) is not str or hashlib.sha256(lock).hexdigest() != lock_sha256):
            raise _failure()
        value = json.loads(lock.decode("utf-8"), object_pairs_hook=content._pairs)
        content._check_depth(value)
        expected = {"repository": "SENTINEL_GO", "status": "locked", "toolchains": {"go": GO_LOCK}}
        if value != expected or type(value["toolchains"]["go"]["archiveSize"]) is not int:
            raise _failure()
    except (SentinelError, UnicodeError, ValueError, TypeError, KeyError, RecursionError):
        raise _failure() from None


def verify_go_runtime(prepared: content.PreparedRoot, lock: bytes, lock_sha256: str) -> GoRuntime:
    try:
        _verify_lock(lock, lock_sha256)
        content._recheck(prepared)
        if prepared.kind != "dependencies":
            raise _failure()
        binary = next((entry for entry in prepared._entries if entry.path == "bin/go"), None)
        if binary is None or not binary.executable or binary.sha256 != GO_LOCK["binarySha256"]:
            raise _failure()
        digest = release_tree_sha256(prepared)
        if digest != GO_LOCK["installedTreeSha256"]:
            raise _failure()
        return GoRuntime(prepared, lock_sha256, digest, binary.sha256, lock)
    except SentinelError:
        raise _failure() from None
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, AttributeError, RecursionError):
        raise _failure() from None
