import ctypes
import errno
import hashlib
import json
import os
import re
import secrets
import stat
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Sequence, Set, Tuple

from .errors import SentinelError


MAX_MANIFEST_BYTES = 16 * 1024 * 1024
MAX_FILES = 65536
MAX_FILE_BYTES = 512 * 1024 * 1024
MAX_TOTAL_BYTES = 4 * 1024 * 1024 * 1024
MAX_PATH_BYTES = 4096
MAX_PATH_COMPONENTS = 256
MAX_JSON_DEPTH = 64
RENAME_NOREPLACE = 1
AT_EMPTY_PATH = 0x1000
SYS_FCHMODAT2 = 452
DIGEST = re.compile(r"^[0-9a-f]{64}$")
KINDS = frozenset(("artifact", "dependencies", "corpus"))
OPEN_DIRECTORY = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
OPEN_PATH_DIRECTORY = getattr(os, "O_PATH", 0) | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
OPEN_FILE = os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)


@dataclass(frozen=True)
class _Entry:
    path: str
    bytes: int
    sha256: str
    executable: bool


@dataclass(frozen=True)
class PreparedRoot:
    kind: str
    root: Path
    manifest_sha256: str
    file_count: int
    total_bytes: int
    _entries: Tuple[_Entry, ...] = field(default=(), repr=False)
    _manifest: bytes = field(default=b"", repr=False)


@dataclass(frozen=True)
class _Snapshot:
    device: int
    inode: int
    uid: int
    mode: int
    links: int
    size: int
    modified_ns: int
    changed_ns: int


def _failure() -> SentinelError:
    return SentinelError("contentRootFailed", "Content root verification failed", 5)


def _snapshot(metadata: os.stat_result) -> _Snapshot:
    return _Snapshot(
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_uid,
        metadata.st_mode,
        metadata.st_nlink,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _pairs(values: Sequence[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in values:
        if key in result:
            raise _failure()
        result[key] = value
    return result


def _check_depth(value: Any, depth: int = 0) -> None:
    if depth > MAX_JSON_DEPTH:
        raise _failure()
    if isinstance(value, dict):
        for item in value.values():
            _check_depth(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            _check_depth(item, depth + 1)


def _exact_keys(value: Any, keys: Tuple[str, ...]) -> Dict[str, Any]:
    if not isinstance(value, dict) or set(value) != set(keys):
        raise _failure()
    return value


def _safe_relative(value: Any) -> str:
    if not isinstance(value, str) or not value or value.startswith("/") or value.endswith("/"):
        raise _failure()
    try:
        encoded = value.encode("utf-8")
    except UnicodeError:
        raise _failure()
    if len(encoded) > MAX_PATH_BYTES or "\\" in value or "//" in value:
        raise _failure()
    if any(ord(character) < 32 or 127 <= ord(character) <= 159 for character in value):
        raise _failure()
    parts = value.split("/")
    if (
        len(parts) > MAX_PATH_COMPONENTS
        or any(part in ("", ".", "..", ".git") for part in parts)
    ):
        raise _failure()
    return value


def _parse_manifest(raw: bytes, expected_sha256: str) -> Tuple[str, Tuple[_Entry, ...]]:
    if (
        type(raw) is not bytes
        or not raw
        or len(raw) > MAX_MANIFEST_BYTES
        or not isinstance(expected_sha256, str)
        or DIGEST.fullmatch(expected_sha256) is None
        or not secrets.compare_digest(hashlib.sha256(raw).hexdigest(), expected_sha256)
    ):
        raise _failure()

    def reject_constant(_value: str) -> None:
        raise ValueError

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=reject_constant,
        )
        _check_depth(value)
    except SentinelError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, TypeError, ValueError):
        raise _failure()

    document = _exact_keys(value, ("schemaVersion", "kind", "files"))
    if document["schemaVersion"] != "sentinel-content-root-v1" or document["kind"] not in KINDS:
        raise _failure()
    files = document["files"]
    if not isinstance(files, list) or isinstance(files, bool) or not 1 <= len(files) <= MAX_FILES:
        raise _failure()
    entries: List[_Entry] = []
    total = 0
    for item in files:
        record = _exact_keys(item, ("path", "bytes", "sha256", "executable"))
        relative = _safe_relative(record["path"])
        size = record["bytes"]
        digest = record["sha256"]
        executable = record["executable"]
        if (
            type(size) is not int
            or not 0 <= size <= MAX_FILE_BYTES
            or not isinstance(digest, str)
            or DIGEST.fullmatch(digest) is None
            or type(executable) is not bool
        ):
            raise _failure()
        total += size
        if total > MAX_TOTAL_BYTES:
            raise _failure()
        entries.append(_Entry(relative, size, digest, executable))
    paths = [entry.path for entry in entries]
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise _failure()
    return document["kind"], tuple(entries)


def _path_text(path: Any) -> str:
    if not isinstance(path, Path):
        raise _failure()
    try:
        value = os.fspath(path)
        value.encode("utf-8")
    except (TypeError, UnicodeError, ValueError):
        raise _failure()
    if not path.is_absolute() or path != Path(os.path.normpath(value)):
        raise _failure()
    if any(ord(character) < 32 or 127 <= ord(character) <= 159 for character in value):
        raise _failure()
    return value


def _canonical_metadata(path: Path, require_directory: bool = True) -> os.stat_result:
    _path_text(path)
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current = current / part
        try:
            metadata = os.lstat(current)
        except (OSError, ValueError):
            raise _failure()
        if stat.S_ISLNK(metadata.st_mode):
            raise _failure()
        if current != path and not stat.S_ISDIR(metadata.st_mode):
            raise _failure()
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError, ValueError):
        raise _failure()
    if resolved != path:
        raise _failure()
    metadata = os.lstat(path)
    if require_directory and not stat.S_ISDIR(metadata.st_mode):
        raise _failure()
    return metadata


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _validate_source(source: Path) -> os.stat_result:
    metadata = _canonical_metadata(source)
    parent = _canonical_metadata(source.parent)
    uid = os.geteuid()
    if (
        metadata.st_uid != uid
        or parent.st_uid != uid
        or stat.S_IMODE(parent.st_mode) != 0o700
        or stat.S_IMODE(metadata.st_mode) & 0o022
    ):
        raise _failure()
    return metadata


def _inside_git_work_tree(path: Path) -> bool:
    current = path
    while True:
        try:
            os.lstat(current / ".git")
            return True
        except FileNotFoundError:
            pass
        except OSError:
            raise _failure()
        if current == current.parent:
            return False
        current = current.parent


def _validate_destination_parent(destination_parent: Path) -> os.stat_result:
    metadata = _canonical_metadata(destination_parent)
    if (
        metadata.st_uid != os.geteuid()
        or stat.S_IMODE(metadata.st_mode) != 0o700
        or _inside_git_work_tree(destination_parent)
    ):
        raise _failure()
    return metadata


def _open_exact_directory(path: Path, expected: os.stat_result) -> int:
    descriptors: List[int] = []
    try:
        current = os.open(path.anchor, OPEN_DIRECTORY)
        descriptors.append(current)
        for component in path.parts[1:]:
            current = os.open(component, OPEN_DIRECTORY, dir_fd=current)
            descriptors.append(current)
        opened = os.fstat(current)
        if not stat.S_ISDIR(opened.st_mode) or _snapshot(opened) != _snapshot(expected):
            raise _failure()
        descriptor = descriptors.pop()
        return descriptor
    except SentinelError:
        raise
    except (OSError, ValueError):
        raise _failure()
    finally:
        for descriptor in reversed(descriptors):
            try:
                os.close(descriptor)
            except OSError:
                pass


def _same_directory_identity(metadata: os.stat_result, expected: _Snapshot) -> bool:
    return (
        stat.S_ISDIR(metadata.st_mode)
        and metadata.st_dev == expected.device
        and metadata.st_ino == expected.inode
        and metadata.st_uid == os.geteuid()
    )


def _fchmod_path_descriptor(descriptor: int, mode: int) -> None:
    # RISK(platform): fchmodat2 is required for a directory created under umask
    # 0777. The pinned Linux executor supports it; unsupported kernels fail closed.
    if os.uname().sysname != "Linux" or os.uname().machine not in ("x86_64", "aarch64"):
        raise _failure()
    try:
        library = ctypes.CDLL(None, use_errno=True)
        syscall = library.syscall
        result = syscall(
            ctypes.c_long(SYS_FCHMODAT2),
            ctypes.c_int(descriptor),
            ctypes.c_char_p(b""),
            ctypes.c_uint(mode),
            ctypes.c_int(AT_EMPTY_PATH),
        )
    except (AttributeError, OSError, TypeError, ValueError):
        raise _failure()
    if result != 0:
        raise _failure()


def _open_directory_entry(
    parent_descriptor: int,
    name: str,
    expected: _Snapshot = None,
    normalize_mode: int = None,
) -> int:
    path_descriptor = None
    descriptor = None
    try:
        if not getattr(os, "O_PATH", 0) or not getattr(os, "O_NOFOLLOW", 0):
            raise _failure()
        path_descriptor = os.open(name, OPEN_PATH_DIRECTORY, dir_fd=parent_descriptor)
        before = os.fstat(path_descriptor)
        if not stat.S_ISDIR(before.st_mode) or before.st_uid != os.geteuid():
            raise _failure()
        if expected is not None and not _same_directory_identity(before, expected):
            raise _failure()
        if normalize_mode is not None:
            _fchmod_path_descriptor(path_descriptor, normalize_mode)
        normalized = os.fstat(path_descriptor)
        if (
            normalized.st_dev != before.st_dev
            or normalized.st_ino != before.st_ino
            or normalized.st_uid != before.st_uid
            or not stat.S_ISDIR(normalized.st_mode)
            or (
                normalize_mode is not None
                and stat.S_IMODE(normalized.st_mode) != normalize_mode
            )
        ):
            raise _failure()
        descriptor = os.open(name, OPEN_DIRECTORY, dir_fd=parent_descriptor)
        opened = os.fstat(descriptor)
        if _snapshot(opened) != _snapshot(normalized):
            raise _failure()
        result = descriptor
        descriptor = None
        return result
    except SentinelError:
        raise
    except (OSError, ValueError):
        raise _failure()
    finally:
        for candidate in (descriptor, path_descriptor):
            if candidate is not None:
                try:
                    os.close(candidate)
                except OSError:
                    pass


def _validate_directory_metadata(metadata: os.stat_result, installed: bool) -> None:
    if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.geteuid():
        raise _failure()
    mode = stat.S_IMODE(metadata.st_mode)
    if (installed and mode != 0o500) or (not installed and mode & 0o022):
        raise _failure()


def _validate_file_metadata(metadata: os.stat_result, installed: bool, entry: _Entry = None) -> None:
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or metadata.st_uid != os.geteuid()
    ):
        raise _failure()
    mode = stat.S_IMODE(metadata.st_mode)
    if installed:
        if entry is None and mode not in (0o400, 0o500):
            raise _failure()
        if entry is not None and mode != (0o500 if entry.executable else 0o400):
            raise _failure()
    elif mode & 0o022:
        raise _failure()


def _scan_tree(
    root_descriptor: int,
    installed: bool,
) -> Tuple[_Snapshot, Dict[str, _Snapshot], Set[str]]:
    files: Dict[str, _Snapshot] = {}
    directories: Set[str] = set()
    total_bytes = 0

    def visit(descriptor: int, prefix: str) -> None:
        nonlocal total_bytes
        before = os.fstat(descriptor)
        _validate_directory_metadata(before, installed)
        try:
            with os.scandir(descriptor) as iterator:
                names = sorted(item.name for item in iterator)
        except (OSError, UnicodeError, ValueError):
            raise _failure()
        for name in names:
            relative = _safe_relative(f"{prefix}/{name}" if prefix else name)
            try:
                metadata = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
            except (OSError, ValueError):
                raise _failure()
            if stat.S_ISDIR(metadata.st_mode):
                _validate_directory_metadata(metadata, installed)
                directories.add(relative)
                try:
                    child = os.open(name, OPEN_DIRECTORY, dir_fd=descriptor)
                except (OSError, ValueError):
                    raise _failure()
                try:
                    opened = os.fstat(child)
                    if _snapshot(opened) != _snapshot(metadata):
                        raise _failure()
                    visit(child, relative)
                    if _snapshot(os.fstat(child)) != _snapshot(opened):
                        raise _failure()
                finally:
                    os.close(child)
            elif stat.S_ISREG(metadata.st_mode):
                _validate_file_metadata(metadata, installed)
                if len(files) >= MAX_FILES:
                    raise _failure()
                total_bytes += metadata.st_size
                if metadata.st_size > MAX_FILE_BYTES or total_bytes > MAX_TOTAL_BYTES:
                    raise _failure()
                files[relative] = _snapshot(metadata)
            else:
                raise _failure()
        after = os.fstat(descriptor)
        if _snapshot(after) != _snapshot(before):
            raise _failure()

    root_before = os.fstat(root_descriptor)
    _validate_directory_metadata(root_before, installed)
    visit(root_descriptor, "")
    root_after = os.fstat(root_descriptor)
    if _snapshot(root_before) != _snapshot(root_after):
        raise _failure()
    return _snapshot(root_before), files, directories


def _expected_directories(entries: Tuple[_Entry, ...]) -> Set[str]:
    result: Set[str] = set()
    for entry in entries:
        parts = entry.path.split("/")[:-1]
        for index in range(1, len(parts) + 1):
            result.add("/".join(parts[:index]))
    return result


def _validate_inventory(
    entries: Tuple[_Entry, ...],
    files: Dict[str, _Snapshot],
    directories: Set[str],
    installed: bool,
) -> None:
    expected = {entry.path: entry for entry in entries}
    if set(files) != set(expected) or directories != _expected_directories(entries):
        raise _failure()
    for relative, metadata in files.items():
        entry = expected[relative]
        if metadata.size != entry.bytes:
            raise _failure()
        mode = stat.S_IMODE(metadata.mode)
        if installed:
            if mode != (0o500 if entry.executable else 0o400):
                raise _failure()
        elif bool(mode & 0o111) != entry.executable:
            raise _failure()


@contextmanager
def _directory_at(root_descriptor: int, parts: Sequence[str]) -> Iterator[int]:
    descriptors: List[int] = []
    try:
        current = os.dup(root_descriptor)
        descriptors.append(current)
        for part in parts:
            current = os.open(part, OPEN_DIRECTORY, dir_fd=current)
            descriptors.append(current)
        yield current
    except SentinelError:
        raise
    except (OSError, ValueError):
        raise _failure()
    finally:
        for descriptor in reversed(descriptors):
            try:
                os.close(descriptor)
            except OSError:
                pass


def _read_entry(
    source_descriptor: int,
    entry: _Entry,
    expected: _Snapshot,
    destination_descriptor: int = None,
) -> None:
    parts = entry.path.split("/")
    with _directory_at(source_descriptor, parts[:-1]) as parent:
        try:
            descriptor = os.open(parts[-1], OPEN_FILE, dir_fd=parent)
        except (OSError, ValueError):
            raise _failure()
        try:
            before = os.fstat(descriptor)
            _validate_file_metadata(before, False)
            if _snapshot(before) != expected:
                raise _failure()
            digest = hashlib.sha256()
            total = 0
            while True:
                chunk = os.read(descriptor, min(64 * 1024, entry.bytes + 1 - total))
                if not chunk:
                    break
                total += len(chunk)
                if total > entry.bytes:
                    raise _failure()
                digest.update(chunk)
                if destination_descriptor is not None:
                    offset = 0
                    while offset < len(chunk):
                        written = os.write(destination_descriptor, chunk[offset:])
                        if written <= 0:
                            raise _failure()
                        offset += written
            after = os.fstat(descriptor)
            if _snapshot(after) != _snapshot(before):
                raise _failure()
            if total != entry.bytes or not secrets.compare_digest(digest.hexdigest(), entry.sha256):
                raise _failure()
        finally:
            os.close(descriptor)


def _create_directories(root_descriptor: int, entries: Tuple[_Entry, ...]) -> None:
    directories = sorted(_expected_directories(entries), key=lambda value: (value.count("/"), value))
    for relative in directories:
        parts = relative.split("/")
        with _directory_at(root_descriptor, parts[:-1]) as parent:
            descriptor = None
            try:
                os.mkdir(parts[-1], 0o700, dir_fd=parent)
                descriptor = _open_directory_entry(
                    parent,
                    parts[-1],
                    normalize_mode=0o700,
                )
            except (OSError, ValueError):
                raise _failure()
            finally:
                if descriptor is not None:
                    os.close(descriptor)


def _copy_entry(
    source_descriptor: int,
    staging_descriptor: int,
    entry: _Entry,
    expected: _Snapshot,
) -> None:
    parts = entry.path.split("/")
    with _directory_at(staging_descriptor, parts[:-1]) as parent:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
        try:
            destination = os.open(parts[-1], flags, 0o600, dir_fd=parent)
        except (OSError, ValueError):
            raise _failure()
        try:
            _read_entry(source_descriptor, entry, expected, destination)
            os.fchmod(destination, 0o500 if entry.executable else 0o400)
            os.fsync(destination)
            metadata = os.fstat(destination)
            _validate_file_metadata(metadata, True, entry)
            if metadata.st_size != entry.bytes:
                raise _failure()
        finally:
            os.close(destination)


def _seal_directories(root_descriptor: int, entries: Tuple[_Entry, ...]) -> None:
    directories = sorted(
        _expected_directories(entries),
        key=lambda value: (-value.count("/"), value),
    )
    for relative in directories:
        with _directory_at(root_descriptor, relative.split("/")) as descriptor:
            os.fchmod(descriptor, 0o500)
            os.fsync(descriptor)
    os.fchmod(root_descriptor, 0o500)
    os.fsync(root_descriptor)


def _verify_open_tree(descriptor: int, entries: Tuple[_Entry, ...]) -> None:
    _root, files, directories = _scan_tree(descriptor, True)
    _validate_inventory(entries, files, directories, True)
    for entry in entries:
        parts = entry.path.split("/")
        with _directory_at(descriptor, parts[:-1]) as parent:
            try:
                file_descriptor = os.open(parts[-1], OPEN_FILE, dir_fd=parent)
            except (OSError, ValueError):
                raise _failure()
            try:
                before = os.fstat(file_descriptor)
                _validate_file_metadata(before, True, entry)
                if _snapshot(before) != files[entry.path]:
                    raise _failure()
                digest = hashlib.sha256()
                total = 0
                while True:
                    chunk = os.read(file_descriptor, min(64 * 1024, entry.bytes + 1 - total))
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > entry.bytes:
                        raise _failure()
                    digest.update(chunk)
                after = os.fstat(file_descriptor)
                if (
                    _snapshot(before) != _snapshot(after)
                    or total != entry.bytes
                    or not secrets.compare_digest(digest.hexdigest(), entry.sha256)
                ):
                    raise _failure()
            finally:
                os.close(file_descriptor)
    final_root, final_files, final_directories = _scan_tree(descriptor, True)
    if final_root != _root or final_files != files or final_directories != directories:
        raise _failure()


def _verify_tree(root: Path, entries: Tuple[_Entry, ...]) -> None:
    metadata = _canonical_metadata(root)
    if metadata.st_uid != os.geteuid() or stat.S_IMODE(metadata.st_mode) != 0o500:
        raise _failure()
    descriptor = _open_exact_directory(root, metadata)
    try:
        _verify_open_tree(descriptor, entries)
        _require_open_path_identity(root, descriptor, metadata)
    finally:
        os.close(descriptor)


def _rename_noreplace(parent_descriptor: int, source_name: str, target_name: str) -> bool:
    try:
        library = ctypes.CDLL(None, use_errno=True)
        renameat2 = library.renameat2
    except (AttributeError, OSError):
        raise _failure()
    renameat2.argtypes = (
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    )
    renameat2.restype = ctypes.c_int
    result = renameat2(
        parent_descriptor,
        os.fsencode(source_name),
        parent_descriptor,
        os.fsencode(target_name),
        RENAME_NOREPLACE,
    )
    if result == 0:
        return True
    if ctypes.get_errno() == errno.EEXIST:
        return False
    raise _failure()


def _publish_noreplace(
    parent_descriptor: int,
    staged_name: str,
    target_name: str,
    expected: _Snapshot,
) -> bool:
    try:
        metadata = os.stat(staged_name, dir_fd=parent_descriptor, follow_symlinks=False)
    except (OSError, ValueError):
        raise _failure()
    if type(expected) is not _Snapshot or _snapshot(metadata) != expected:
        raise _failure()
    return _rename_noreplace(parent_descriptor, staged_name, target_name)


def _require_open_path_identity(path: Path, descriptor: int, expected: os.stat_result) -> None:
    check_descriptor = None
    try:
        opened = os.fstat(descriptor)
        if (
            not _same_directory_identity(opened, _snapshot(expected))
            or opened.st_mode != expected.st_mode
        ):
            raise _failure()
        current = _canonical_metadata(path)
        check_descriptor = _open_exact_directory(path, current)
        if _snapshot(os.fstat(check_descriptor)) != _snapshot(opened):
            raise _failure()
    except SentinelError:
        raise
    except (OSError, ValueError):
        raise _failure()
    finally:
        if check_descriptor is not None:
            os.close(check_descriptor)


def _find_staging_name(
    parent_descriptor: int,
    preferred_name: str,
    expected: _Snapshot,
) -> str:
    candidates = [preferred_name]
    try:
        with os.scandir(parent_descriptor) as iterator:
            candidates.extend(sorted(entry.name for entry in iterator if entry.name != preferred_name))
    except (OSError, UnicodeError, ValueError):
        raise _failure()
    matches = []
    for name in candidates:
        try:
            metadata = os.stat(name, dir_fd=parent_descriptor, follow_symlinks=False)
        except FileNotFoundError:
            continue
        except (OSError, ValueError):
            raise _failure()
        if (
            stat.S_ISDIR(metadata.st_mode)
            and metadata.st_dev == expected.device
            and metadata.st_ino == expected.inode
            and metadata.st_uid == os.geteuid()
        ):
            matches.append(name)
    if len(matches) > 1:
        raise _failure()
    return matches[0] if matches else ""


def _rollback_published(
    parent_descriptor: int,
    target_name: str,
    expected: _Snapshot,
) -> None:
    try:
        metadata = os.stat(target_name, dir_fd=parent_descriptor, follow_symlinks=False)
    except (OSError, ValueError):
        raise _failure()
    if not _same_directory_identity(metadata, expected):
        raise _failure()
    rollback_name = ".content-root-rollback-" + secrets.token_hex(16)
    if not _rename_noreplace(parent_descriptor, target_name, rollback_name):
        raise _failure()
    try:
        rolled_back = os.stat(rollback_name, dir_fd=parent_descriptor, follow_symlinks=False)
    except (OSError, ValueError):
        raise _failure()
    if not _same_directory_identity(rolled_back, expected):
        raise _failure()


def _remove_staging(parent_descriptor: int, name: str, expected: _Snapshot) -> None:
    descriptor = None
    try:
        descriptor = _open_directory_entry(
            parent_descriptor,
            name,
            expected=expected,
            normalize_mode=0o700,
        )
    except SentinelError:
        try:
            os.stat(name, dir_fd=parent_descriptor, follow_symlinks=False)
        except FileNotFoundError:
            return
        except (OSError, ValueError):
            pass
        raise
    try:
        metadata = os.fstat(descriptor)
        if not _same_directory_identity(metadata, expected):
            raise _failure()

        def remove_contents(directory_descriptor: int) -> None:
            os.fchmod(directory_descriptor, 0o700)
            try:
                with os.scandir(directory_descriptor) as iterator:
                    names = sorted(item.name for item in iterator)
            except (OSError, UnicodeError, ValueError):
                raise _failure()
            for child_name in names:
                try:
                    child_metadata = os.stat(
                        child_name,
                        dir_fd=directory_descriptor,
                        follow_symlinks=False,
                    )
                except (OSError, ValueError):
                    raise _failure()
                if child_metadata.st_uid != os.geteuid():
                    raise _failure()
                if stat.S_ISDIR(child_metadata.st_mode):
                    child_descriptor = None
                    try:
                        child_descriptor = _open_directory_entry(
                            directory_descriptor,
                            child_name,
                            expected=_snapshot(child_metadata),
                            normalize_mode=0o700,
                        )
                    except SentinelError:
                        raise _failure()
                    try:
                        opened = os.fstat(child_descriptor)
                        if (
                            opened.st_dev != child_metadata.st_dev
                            or opened.st_ino != child_metadata.st_ino
                            or opened.st_uid != child_metadata.st_uid
                            or not stat.S_ISDIR(opened.st_mode)
                        ):
                            raise _failure()
                        remove_contents(child_descriptor)
                    finally:
                        os.close(child_descriptor)
                    os.rmdir(child_name, dir_fd=directory_descriptor)
                elif stat.S_ISREG(child_metadata.st_mode) and child_metadata.st_nlink == 1:
                    os.unlink(child_name, dir_fd=directory_descriptor)
                else:
                    raise _failure()

        remove_contents(descriptor)
    except SentinelError:
        raise
    except (OSError, ValueError):
        raise _failure()
    finally:
        os.close(descriptor)
    try:
        os.rmdir(name, dir_fd=parent_descriptor)
    except (OSError, ValueError):
        raise _failure()


def _prepared(kind: str, root: Path, manifest_sha256: str, entries: Tuple[_Entry, ...], manifest: bytes) -> PreparedRoot:
    return PreparedRoot(
        kind,
        root,
        manifest_sha256,
        len(entries),
        sum(entry.bytes for entry in entries),
        entries,
        manifest,
    )


def _validate_prepared(prepared: Any) -> PreparedRoot:
    if type(prepared) is not PreparedRoot:
        raise _failure()
    if (
        prepared.kind not in KINDS
        or not isinstance(prepared.root, Path)
        or not isinstance(prepared.manifest_sha256, str)
        or DIGEST.fullmatch(prepared.manifest_sha256) is None
        or type(prepared.file_count) is not int
        or type(prepared.total_bytes) is not int
        or type(prepared._entries) is not tuple
        or any(type(entry) is not _Entry for entry in prepared._entries)
        or prepared.file_count != len(prepared._entries)
        or prepared.total_bytes != sum(entry.bytes for entry in prepared._entries)
        or not prepared._entries
    ):
        raise _failure()
    paths = [entry.path for entry in prepared._entries]
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise _failure()
    kind, entries = _parse_manifest(prepared._manifest, prepared.manifest_sha256)
    if kind != prepared.kind or entries != prepared._entries:
        raise _failure()
    expected_name = f"{prepared.kind}-{prepared.manifest_sha256}"
    _path_text(prepared.root)
    if prepared.root.name != expected_name:
        raise _failure()
    return prepared


def _recheck(prepared: PreparedRoot) -> None:
    prepared = _validate_prepared(prepared)
    _validate_destination_parent(prepared.root.parent)
    _verify_tree(prepared.root, prepared._entries)


def _prepare_content_root(
    source: Path,
    manifest: bytes,
    manifest_sha256: str,
    destination_parent: Path,
) -> PreparedRoot:
    kind, entries = _parse_manifest(manifest, manifest_sha256)
    source_metadata = _validate_source(source)
    destination_metadata = _validate_destination_parent(destination_parent)
    if _inside(source, destination_parent) or _inside(destination_parent, source):
        raise _failure()

    source_descriptor = None
    parent_descriptor = None
    staging_descriptor = None
    staging_name = ".content-root-" + secrets.token_hex(16)
    staging_identity = None
    staging_created = False
    published = False
    accepted = False
    try:
        source_descriptor = _open_exact_directory(source, source_metadata)
        parent_descriptor = _open_exact_directory(destination_parent, destination_metadata)
        source_root, source_files, source_directories = _scan_tree(source_descriptor, False)
        _validate_inventory(entries, source_files, source_directories, False)
        target_name = f"{kind}-{manifest_sha256}"
        target = destination_parent / target_name
        try:
            existing = os.stat(target_name, dir_fd=parent_descriptor, follow_symlinks=False)
        except FileNotFoundError:
            existing = None
        if existing is not None:
            for entry in entries:
                _read_entry(source_descriptor, entry, source_files[entry.path])
            final_source = _scan_tree(source_descriptor, False)
            if final_source != (source_root, source_files, source_directories):
                raise _failure()
            _require_open_path_identity(source, source_descriptor, source_metadata)
            _require_open_path_identity(
                destination_parent,
                parent_descriptor,
                destination_metadata,
            )
            result = _prepared(kind, target, manifest_sha256, entries, manifest)
            _recheck(result)
            return result

        try:
            os.mkdir(staging_name, 0o700, dir_fd=parent_descriptor)
            staging_created = True
            stage_metadata = os.stat(staging_name, dir_fd=parent_descriptor, follow_symlinks=False)
            staging_identity = _snapshot(stage_metadata)
            staging_descriptor = _open_directory_entry(
                parent_descriptor,
                staging_name,
                expected=staging_identity,
                normalize_mode=0o700,
            )
        except (OSError, ValueError):
            raise _failure()
        _create_directories(staging_descriptor, entries)
        for entry in entries:
            _copy_entry(source_descriptor, staging_descriptor, entry, source_files[entry.path])
        final_source = _scan_tree(source_descriptor, False)
        if final_source != (source_root, source_files, source_directories):
            raise _failure()
        _seal_directories(staging_descriptor, entries)
        _verify_open_tree(staging_descriptor, entries)
        _validate_source(source)
        _validate_destination_parent(destination_parent)
        _require_open_path_identity(source, source_descriptor, source_metadata)
        _require_open_path_identity(
            destination_parent,
            parent_descriptor,
            destination_metadata,
        )
        sealed_identity = _snapshot(os.fstat(staging_descriptor))
        published = _publish_noreplace(parent_descriptor, staging_name, target_name, sealed_identity)
        if published:
            target_metadata = os.stat(target_name, dir_fd=parent_descriptor, follow_symlinks=False)
            if not _same_directory_identity(target_metadata, staging_identity):
                raise _failure()
            os.fsync(parent_descriptor)
        result = _prepared(kind, target, manifest_sha256, entries, manifest)
        _recheck(result)
        _require_open_path_identity(source, source_descriptor, source_metadata)
        _require_open_path_identity(destination_parent, parent_descriptor, destination_metadata)
        accepted = True
        return result
    finally:
        cleanup_failed = False
        if staging_created and (not published or not accepted) and parent_descriptor is not None:
            if staging_identity is None:
                try:
                    staging_identity = _snapshot(
                        os.stat(
                            staging_name,
                            dir_fd=parent_descriptor,
                            follow_symlinks=False,
                        )
                    )
                except OSError:
                    cleanup_failed = True
            if staging_identity is not None:
                if published and not accepted:
                    try:
                        _rollback_published(parent_descriptor, target_name, staging_identity)
                    except (Exception, KeyboardInterrupt):
                        cleanup_failed = True
                try:
                    owned_name = _find_staging_name(parent_descriptor, staging_name, staging_identity)
                    if owned_name:
                        _remove_staging(parent_descriptor, owned_name, staging_identity)
                except (Exception, KeyboardInterrupt):
                    cleanup_failed = True
        for descriptor in (staging_descriptor, source_descriptor, parent_descriptor):
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    cleanup_failed = True
        if cleanup_failed:
            raise _failure()


def prepare_content_root(
    source: Path,
    manifest: bytes,
    manifest_sha256: str,
    destination_parent: Path,
) -> PreparedRoot:
    try:
        return _prepare_content_root(source, manifest, manifest_sha256, destination_parent)
    except (Exception, KeyboardInterrupt):
        pass
    raise _failure()


def recheck_content_root(prepared: PreparedRoot) -> None:
    try:
        _recheck(prepared)
    except (Exception, KeyboardInterrupt):
        pass
    else:
        return
    raise _failure()
