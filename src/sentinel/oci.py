import ctypes
import errno
import grp
import hashlib
import json
import os
import stat
import subprocess
import unicodedata
from pathlib import Path
from typing import Any, Dict, Iterable, Sequence, Tuple

from .errors import SentinelError
from .protocol import _collect


DOCKER_PATH = Path("/usr/bin/docker")
SOCKET_PATH = Path("/run/docker.sock")
DOCKER_HOST = "unix:///run/docker.sock"
MAX_LOCK_BYTES = 1024 * 1024
MAX_SESSION_BYTES = 1024 * 1024
MAX_BINARY_BYTES = 256 * 1024 * 1024
FAILURE_CODE = "ociPreflightFailed"
FAILURE_MESSAGE = "OCI executor preflight failed"
RENAME_NOREPLACE = 1
DIGEST_LENGTH = 64
LOCK_KEYS = {"schemaVersion", "client", "server", "socket", "image"}
CLIENT_LOCK_KEYS = {"path", "sha256", "version", "gitCommit", "apiVersion", "os", "architecture"}
SERVER_LOCK_KEYS = {"version", "gitCommit", "apiVersion", "os", "architecture"}
SOCKET_LOCK_KEYS = {"path", "owner", "group", "mode"}
IMAGE_LOCK_KEYS = {"reference", "os", "architecture"}
SESSION_KEYS = {"schemaVersion", "lockSha256", "effectiveUid", "root", "binary", "socket", "config", "version"}
ROOT_KEYS = {"device", "inode", "uid", "gid", "mode"}
BINARY_KEYS = {"path", "sha256", "device", "inode", "uid", "gid", "mode", "size", "mtimeNs", "ctimeNs"}
PATH_IDENTITY_KEYS = {"path", "device", "inode", "uid", "gid", "mode"}
CLIENT_VERSION_KEYS = {"version", "apiVersion", "gitCommit", "os", "architecture", "context"}
SERVER_VERSION_KEYS = {"version", "apiVersion", "gitCommit", "os", "architecture"}


def _failure() -> SentinelError:
    return SentinelError(FAILURE_CODE, FAILURE_MESSAGE, 5)


def _digest(value: Any) -> bool:
    return isinstance(value, str) and len(value) == DIGEST_LENGTH and all(character in "0123456789abcdef" for character in value)


def _bounded_string(value: Any, maximum: int = 256) -> bool:
    return (
        isinstance(value, str)
        and 0 < len(value) <= maximum
        and not any(unicodedata.category(character) == "Cc" for character in value)
    )


def _bounded_path_string(value: Any) -> bool:
    if not _bounded_string(value, 4096):
        return False
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _exact_keys(value: Any, keys: Iterable[str]) -> bool:
    return isinstance(value, dict) and set(value) == set(keys)


def _pairs(pairs: Sequence[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _failure()
        result[key] = value
    return result


def _strict_json(raw: bytes) -> Any:
    def reject_constant(_value: str) -> None:
        raise ValueError

    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=reject_constant,
        )
    except SentinelError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError, TypeError):
        raise _failure()


def _signature(metadata: os.stat_result) -> tuple:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_uid,
        metadata.st_gid,
        metadata.st_mode,
        metadata.st_nlink,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _absolute_without_links(path: Path) -> Path:
    if not isinstance(path, Path):
        raise _failure()
    try:
        absolute = path.absolute()
    except (OSError, ValueError, UnicodeError):
        raise _failure()
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current = current / part
        try:
            metadata = os.lstat(current)
        except (OSError, ValueError):
            raise _failure()
        if stat.S_ISLNK(metadata.st_mode):
            raise _failure()
    try:
        if absolute.resolve(strict=True) != absolute:
            raise _failure()
    except (OSError, RuntimeError, ValueError):
        raise _failure()
    return absolute


def _read_regular(path: Path, maximum: int) -> tuple:
    absolute = _absolute_without_links(path)
    try:
        before = os.lstat(absolute)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > maximum:
            raise _failure()
        descriptor = os.open(
            str(absolute),
            os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0),
        )
        try:
            opened = os.fstat(descriptor)
            if _signature(opened) != _signature(before):
                raise _failure()
            chunks = []
            total = 0
            while True:
                chunk = os.read(descriptor, min(64 * 1024, maximum + 1 - total))
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
                if total > maximum:
                    raise _failure()
            after_open = os.fstat(descriptor)
        finally:
            os.close(descriptor)
        after_path = os.lstat(absolute)
        if _signature(after_open) != _signature(before) or _signature(after_path) != _signature(before):
            raise _failure()
        return b"".join(chunks), before
    except SentinelError:
        raise
    except (OSError, ValueError, OverflowError):
        raise _failure()


def _load_lock(lock_path: Path, lock_sha256: str) -> Dict[str, Any]:
    if not _digest(lock_sha256):
        raise _failure()
    raw, _metadata = _read_regular(lock_path, MAX_LOCK_BYTES)
    if hashlib.sha256(raw).hexdigest() != lock_sha256:
        raise _failure()
    value = _strict_json(raw)
    if not _exact_keys(value, LOCK_KEYS) or value["schemaVersion"] != "sentinel-oci-executor-lock-v1":
        raise _failure()
    client = value["client"]
    server = value["server"]
    socket = value["socket"]
    image = value["image"]
    if not _exact_keys(client, CLIENT_LOCK_KEYS) or not _exact_keys(server, SERVER_LOCK_KEYS):
        raise _failure()
    if not _exact_keys(socket, SOCKET_LOCK_KEYS) or not _exact_keys(image, IMAGE_LOCK_KEYS):
        raise _failure()
    if client["path"] != str(DOCKER_PATH) or socket["path"] != str(SOCKET_PATH):
        raise _failure()
    if socket != {"path": str(SOCKET_PATH), "owner": "root", "group": "docker", "mode": "0660"}:
        raise _failure()
    if client["os"] != "linux" or client["architecture"] != "amd64":
        raise _failure()
    if server["os"] != "linux" or server["architecture"] != "amd64":
        raise _failure()
    if image["os"] != "linux" or image["architecture"] != "amd64":
        raise _failure()
    prefix = "docker.io/library/ubuntu@sha256:"
    if not isinstance(image["reference"], str) or not image["reference"].startswith(prefix) or not _digest(image["reference"][len(prefix) :]):
        raise _failure()
    if not _digest(client["sha256"]):
        raise _failure()
    for record, fields in (
        (client, ("version", "gitCommit", "apiVersion")),
        (server, ("version", "gitCommit", "apiVersion")),
    ):
        if any(not _bounded_string(record[field]) for field in fields):
            raise _failure()
    return value


def _inspect_binary() -> Dict[str, Any]:
    absolute = _absolute_without_links(DOCKER_PATH)
    try:
        before = os.lstat(absolute)
        mode = stat.S_IMODE(before.st_mode)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_uid != 0
            or mode & 0o022
            or not mode & 0o111
            or before.st_size > MAX_BINARY_BYTES
        ):
            raise _failure()
        descriptor = os.open(str(absolute), os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            opened = os.fstat(descriptor)
            if _signature(opened) != _signature(before):
                raise _failure()
            digest = hashlib.sha256()
            total = 0
            while True:
                chunk = os.read(descriptor, 64 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_BINARY_BYTES:
                    raise _failure()
                digest.update(chunk)
            after_open = os.fstat(descriptor)
        finally:
            os.close(descriptor)
        after_path = os.lstat(absolute)
        if _signature(after_open) != _signature(before) or _signature(after_path) != _signature(before):
            raise _failure()
    except SentinelError:
        raise
    except (OSError, ValueError, OverflowError):
        raise _failure()
    return {
        "path": str(absolute),
        "sha256": digest.hexdigest(),
        "device": before.st_dev,
        "inode": before.st_ino,
        "uid": before.st_uid,
        "gid": before.st_gid,
        "mode": stat.S_IMODE(before.st_mode),
        "size": before.st_size,
        "mtimeNs": str(before.st_mtime_ns),
        "ctimeNs": str(before.st_ctime_ns),
    }


def _inspect_socket() -> Dict[str, Any]:
    absolute = _absolute_without_links(SOCKET_PATH)
    try:
        docker_gid = grp.getgrnam("docker").gr_gid
        metadata = os.lstat(absolute)
    except (KeyError, OSError, ValueError):
        raise _failure()
    if (
        not stat.S_ISSOCK(metadata.st_mode)
        or metadata.st_uid != 0
        or metadata.st_gid != docker_gid
        or stat.S_IMODE(metadata.st_mode) != 0o660
    ):
        raise _failure()
    return {
        "path": str(absolute),
        "device": metadata.st_dev,
        "inode": metadata.st_ino,
        "uid": metadata.st_uid,
        "gid": metadata.st_gid,
        "mode": stat.S_IMODE(metadata.st_mode),
    }


def _version_record(value: Any, keys: Sequence[Tuple[str, str]]) -> Dict[str, str]:
    if not isinstance(value, dict):
        raise _failure()
    record: Dict[str, str] = {}
    for source, target in keys:
        item = value.get(source)
        if not _bounded_string(item):
            raise _failure()
        record[target] = item
    return record


def _parse_version(raw: bytes) -> Dict[str, Any]:
    value = _strict_json(raw)
    if not isinstance(value, dict):
        raise _failure()
    client_raw = value.get("Client")
    server_raw = value.get("Server")
    client = _version_record(
        client_raw,
        (("Version", "version"), ("ApiVersion", "apiVersion"), ("GitCommit", "gitCommit"), ("Os", "os"), ("Arch", "architecture"), ("Context", "context")),
    )
    server = _version_record(
        server_raw,
        (("Version", "version"), ("ApiVersion", "apiVersion"), ("GitCommit", "gitCommit"), ("Os", "os"), ("Arch", "architecture")),
    )
    components = server_raw.get("Components") if isinstance(server_raw, dict) else None
    if not isinstance(components, list):
        raise _failure()
    engines = [item for item in components if isinstance(item, dict) and item.get("Name") == "Engine"]
    if len(engines) != 1:
        raise _failure()
    engine = engines[0]
    details = engine.get("Details")
    engine_version = engine.get("Version")
    if not _bounded_string(engine_version) or not isinstance(details, dict):
        raise _failure()
    expected_engine = {
        "Version": server["version"],
        "ApiVersion": server["apiVersion"],
        "GitCommit": server["gitCommit"],
        "Os": server["os"],
        "Arch": server["architecture"],
    }
    actual_engine = {
        "Version": engine_version,
        "ApiVersion": details.get("ApiVersion"),
        "GitCommit": details.get("GitCommit"),
        "Os": details.get("Os"),
        "Arch": details.get("Arch"),
    }
    if actual_engine != expected_engine:
        raise _failure()
    return {"client": client, "server": server}


def _run_version(config: Path) -> Dict[str, Any]:
    argv = [
        str(DOCKER_PATH),
        "--config",
        str(config),
        "--host",
        DOCKER_HOST,
        "version",
        "--format",
        "{{json .}}",
    ]
    try:
        # RISK(security): this is the only admitted Docker child and it receives no ambient environment.
        process = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            start_new_session=True,
            cwd=str(config.parent),
            env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"},
        )
    except OSError:
        raise _failure()
    stdout, _stderr, collection_failure = _collect(process, b"", 10.0)
    if collection_failure is not None or process.returncode != 0:
        raise _failure()
    return _parse_version(stdout)


def _identity(metadata: os.stat_result) -> Dict[str, int]:
    return {
        "device": metadata.st_dev,
        "inode": metadata.st_ino,
        "uid": metadata.st_uid,
        "gid": metadata.st_gid,
        "mode": stat.S_IMODE(metadata.st_mode),
    }


def _outside_git(path: Path) -> None:
    current = path
    while True:
        try:
            os.lstat(current / ".git")
        except FileNotFoundError:
            pass
        except OSError:
            raise _failure()
        else:
            raise _failure()
        if current.parent == current:
            break
        current = current.parent


def _validate_parent_and_target(session_root: Path, must_be_new: bool) -> tuple:
    if (
        not isinstance(session_root, Path)
        or not _bounded_path_string(str(session_root))
        or not _bounded_path_string(str(session_root / "docker-config"))
        or not session_root.is_absolute()
        or ".." in session_root.parts
    ):
        raise _failure()
    if session_root.name in ("", ".", ".."):
        raise _failure()
    parent = _absolute_without_links(session_root.parent)
    if parent / session_root.name != session_root:
        raise _failure()
    try:
        parent_stat = os.lstat(parent)
    except OSError:
        raise _failure()
    if not stat.S_ISDIR(parent_stat.st_mode) or parent_stat.st_uid != os.getuid() or stat.S_IMODE(parent_stat.st_mode) != 0o700:
        raise _failure()
    _outside_git(parent)
    if must_be_new:
        try:
            os.lstat(session_root)
        except FileNotFoundError:
            pass
        except OSError:
            raise _failure()
        else:
            raise _failure()
    return parent, parent_stat


def _directory_evidence(path: Path, mode: int, include_path: bool = True) -> Dict[str, Any]:
    absolute = _absolute_without_links(path)
    try:
        metadata = os.lstat(absolute)
    except OSError:
        raise _failure()
    if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) != mode:
        raise _failure()
    result: Dict[str, Any] = _identity(metadata)
    if include_path:
        result = {"path": str(absolute), **result}
    return result


def _config_evidence(config: Path) -> Dict[str, Any]:
    evidence = _directory_evidence(config, 0o700)
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(str(config), flags)
        try:
            if os.listdir(descriptor):
                raise _failure()
            if {"path": str(config), **_identity(os.fstat(descriptor))} != evidence:
                raise _failure()
        finally:
            os.close(descriptor)
    except SentinelError:
        raise
    except (OSError, ValueError):
        raise _failure()
    return evidence


def _matches_lock(lock: Dict[str, Any], binary: Dict[str, Any], socket: Dict[str, Any], version: Dict[str, Any]) -> None:
    client = lock["client"]
    server = lock["server"]
    if binary["path"] != client["path"] or binary["sha256"] != client["sha256"]:
        raise _failure()
    if socket["path"] != lock["socket"]["path"] or socket["uid"] != 0 or socket["mode"] != 0o660:
        raise _failure()
    expected_client = {
        "version": client["version"],
        "apiVersion": client["apiVersion"],
        "gitCommit": client["gitCommit"],
        "os": client["os"],
        "architecture": client["architecture"],
        "context": "default",
    }
    expected_server = {
        "version": server["version"],
        "apiVersion": server["apiVersion"],
        "gitCommit": server["gitCommit"],
        "os": server["os"],
        "architecture": server["architecture"],
    }
    if version != {"client": expected_client, "server": expected_server}:
        raise _failure()


def _canonical(value: Dict[str, Any]) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8")


def _rename_noreplace(directory_fd: int, source: str, destination: str) -> None:
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        renameat2 = libc.renameat2
    except (AttributeError, OSError):
        raise _failure()
    renameat2.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    renameat2.restype = ctypes.c_int
    result = renameat2(
        directory_fd,
        os.fsencode(source),
        directory_fd,
        os.fsencode(destination),
        RENAME_NOREPLACE,
    )
    if result != 0:
        error_number = ctypes.get_errno()
        if error_number == errno.EEXIST:
            raise _failure()
        raise _failure()


def _same_inode(metadata: os.stat_result, expected: os.stat_result) -> bool:
    return metadata.st_dev == expected.st_dev and metadata.st_ino == expected.st_ino


def _remove_owned_record(directory_fd: int, expected: os.stat_result) -> None:
    try:
        current = os.stat("session.json", dir_fd=directory_fd, follow_symlinks=False)
    except (FileNotFoundError, OSError):
        return
    if not _same_inode(current, expected):
        return
    try:
        os.unlink("session.json", dir_fd=directory_fd)
        os.fsync(directory_fd)
    except OSError:
        return


def _verify_record_descriptor(descriptor: int, expected: os.stat_result, raw: bytes) -> None:
    current = os.fstat(descriptor)
    if (
        not _same_inode(current, expected)
        or not stat.S_ISREG(current.st_mode)
        or current.st_nlink != 1
        or current.st_uid != os.getuid()
        or stat.S_IMODE(current.st_mode) != 0o600
        or current.st_size != len(raw)
    ):
        raise _failure()
    os.lseek(descriptor, 0, os.SEEK_SET)
    chunks = []
    remaining = len(raw) + 1
    while remaining:
        chunk = os.read(descriptor, min(64 * 1024, remaining))
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    if b"".join(chunks) != raw:
        raise _failure()


def _write_record(root: Path, expected_root: Dict[str, int], value: Dict[str, Any]) -> str:
    raw = _canonical(value)
    digest = hashlib.sha256(raw).hexdigest()
    flags = os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = -1
    committed = False
    try:
        root_fd = os.open(str(root), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0))
        try:
            if _identity(os.fstat(root_fd)) != expected_root:
                raise _failure()
            descriptor = os.open(".session.json.tmp", flags, 0o600, dir_fd=root_fd)
            written = 0
            while written < len(raw):
                count = os.write(descriptor, raw[written:])
                if count <= 0:
                    raise _failure()
                written += count
            os.fsync(descriptor)
            staged = os.fstat(descriptor)
            _verify_record_descriptor(descriptor, staged, raw)
            try:
                # RISK(race): renameat2(NOREPLACE) prevents a concurrent record from being overwritten.
                _rename_noreplace(root_fd, ".session.json.tmp", "session.json")
                published = os.stat("session.json", dir_fd=root_fd, follow_symlinks=False)
                if not _same_inode(published, staged):
                    raise _failure()
                _verify_record_descriptor(descriptor, staged, raw)
                os.fsync(root_fd)
                published = os.stat("session.json", dir_fd=root_fd, follow_symlinks=False)
                if not _same_inode(published, staged):
                    raise _failure()
                _verify_record_descriptor(descriptor, staged, raw)
                if _directory_evidence(root, 0o700, include_path=False) != expected_root:
                    raise _failure()
                closing_descriptor = descriptor
                descriptor = -1
                os.close(closing_descriptor)
            except BaseException:
                _remove_owned_record(root_fd, staged)
                raise
            committed = True
        finally:
            try:
                if descriptor >= 0:
                    closing_descriptor = descriptor
                    descriptor = -1
                    os.close(closing_descriptor)
            finally:
                try:
                    closing_root_fd = root_fd
                    root_fd = -1
                    os.close(closing_root_fd)
                except (OSError, KeyboardInterrupt):
                    # RISK(side-effect): after commit, a read-only directory FD close error or
                    # cancellation cannot safely invalidate a verified record through its mutable path.
                    if not committed:
                        raise
    except SentinelError:
        raise
    except (OSError, ValueError):
        raise _failure()
    return digest


def _create_session_root(session_root: Path) -> tuple:
    parent, parent_stat = _validate_parent_and_target(session_root, True)
    parent_fd = -1
    root_fd = -1
    try:
        parent_fd = os.open(str(parent), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0))
        if _signature(os.fstat(parent_fd)) != _signature(parent_stat):
            raise _failure()
        # RISK(security): session publication must never adopt or replace a concurrently created path.
        os.mkdir(session_root.name, 0o700, dir_fd=parent_fd)
        os.fsync(parent_fd)
        root_fd = os.open(session_root.name, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0), dir_fd=parent_fd)
        root_stat = os.fstat(root_fd)
        if root_stat.st_uid != os.getuid() or stat.S_IMODE(root_stat.st_mode) != 0o700:
            raise _failure()
        os.mkdir("docker-config", 0o700, dir_fd=root_fd)
        config_fd = os.open("docker-config", os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0), dir_fd=root_fd)
        try:
            os.fsync(config_fd)
        finally:
            os.close(config_fd)
        os.fsync(root_fd)
        return _identity(root_stat), session_root / "docker-config"
    except SentinelError:
        raise
    except (OSError, ValueError):
        raise _failure()
    finally:
        try:
            if root_fd >= 0:
                closing_root_fd = root_fd
                root_fd = -1
                os.close(closing_root_fd)
        finally:
            if parent_fd >= 0:
                closing_parent_fd = parent_fd
                parent_fd = -1
                os.close(closing_parent_fd)


def _integer_fields(value: Any, keys: Iterable[str], integer_keys: Iterable[str]) -> bool:
    return _exact_keys(value, keys) and all(
        type(value[key]) is int and value[key] >= 0 for key in integer_keys
    )


def _validate_session_shape(value: Any) -> Dict[str, Any]:
    if not _exact_keys(value, SESSION_KEYS) or value["schemaVersion"] != "sentinel-oci-executor-session-v1":
        raise _failure()
    if not _digest(value["lockSha256"]) or type(value["effectiveUid"]) is not int or value["effectiveUid"] < 0:
        raise _failure()
    if not _integer_fields(value["root"], ROOT_KEYS, ROOT_KEYS):
        raise _failure()
    binary = value["binary"]
    socket = value["socket"]
    config = value["config"]
    if not _integer_fields(binary, BINARY_KEYS, ("device", "inode", "uid", "gid", "mode", "size")):
        raise _failure()
    if not _integer_fields(socket, PATH_IDENTITY_KEYS, PATH_IDENTITY_KEYS - {"path"}):
        raise _failure()
    if not _integer_fields(config, PATH_IDENTITY_KEYS, PATH_IDENTITY_KEYS - {"path"}):
        raise _failure()
    for item in (binary, socket, config):
        if not _bounded_path_string(item["path"]):
            raise _failure()
    if not _digest(binary["sha256"]) or not binary["mtimeNs"].isdigit() or not binary["ctimeNs"].isdigit():
        raise _failure()
    version = value["version"]
    if not _exact_keys(version, ("client", "server")):
        raise _failure()
    if not _exact_keys(version["client"], CLIENT_VERSION_KEYS) or not _exact_keys(version["server"], SERVER_VERSION_KEYS):
        raise _failure()
    if any(not _bounded_string(item) for record in (version["client"], version["server"]) for item in record.values()):
        raise _failure()
    return value


def _read_session(session_root: Path, session_sha256: str) -> Dict[str, Any]:
    if not _digest(session_sha256):
        raise _failure()
    raw, metadata = _read_regular(session_root / "session.json", MAX_SESSION_BYTES)
    if metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) != 0o600:
        raise _failure()
    if hashlib.sha256(raw).hexdigest() != session_sha256:
        raise _failure()
    return _validate_session_shape(_strict_json(raw))


def prepare_session(lock_path: Path, lock_sha256: str, session_root: Path) -> str:
    try:
        lock = _load_lock(lock_path, lock_sha256)
        binary_before = _inspect_binary()
        socket_before = _inspect_socket()
        if binary_before["sha256"] != lock["client"]["sha256"]:
            raise _failure()
        root, config_path = _create_session_root(session_root)
        config_before = _config_evidence(config_path)
        version = _run_version(config_path)
        binary_after = _inspect_binary()
        socket_after = _inspect_socket()
        config_after = _config_evidence(config_path)
        root_after = _directory_evidence(session_root, 0o700, include_path=False)
        if binary_after != binary_before or socket_after != socket_before or config_after != config_before or root_after != root:
            raise _failure()
        _matches_lock(lock, binary_after, socket_after, version)
        record = {
            "schemaVersion": "sentinel-oci-executor-session-v1",
            "lockSha256": lock_sha256,
            "effectiveUid": os.geteuid(),
            "root": root,
            "binary": binary_after,
            "socket": socket_after,
            "config": config_after,
            "version": version,
        }
        _validate_session_shape(record)
        return _write_record(session_root, root, record)
    except KeyboardInterrupt:
        raise
    except SentinelError as error:
        if error.code == FAILURE_CODE and error.exit_code == 5:
            raise
        raise _failure() from None
    except Exception:
        raise _failure() from None


def recheck_session(
    lock_path: Path,
    lock_sha256: str,
    session_root: Path,
    session_sha256: str,
) -> None:
    try:
        lock = _load_lock(lock_path, lock_sha256)
        _validate_parent_and_target(session_root, False)
        record = _read_session(session_root, session_sha256)
        root = _directory_evidence(session_root, 0o700, include_path=False)
        config_path = session_root / "docker-config"
        config_before = _config_evidence(config_path)
        binary_before = _inspect_binary()
        socket_before = _inspect_socket()
        expected_static = {
            "schemaVersion": "sentinel-oci-executor-session-v1",
            "lockSha256": lock_sha256,
            "effectiveUid": os.geteuid(),
            "root": root,
            "binary": binary_before,
            "socket": socket_before,
            "config": config_before,
            "version": record["version"],
        }
        if record != expected_static:
            raise _failure()
        _matches_lock(lock, binary_before, socket_before, record["version"])
        version = _run_version(config_path)
        binary_after = _inspect_binary()
        socket_after = _inspect_socket()
        config_after = _config_evidence(config_path)
        if binary_after != binary_before or socket_after != socket_before or config_after != config_before:
            raise _failure()
        if version != record["version"]:
            raise _failure()
        _matches_lock(lock, binary_after, socket_after, version)
        if _directory_evidence(session_root, 0o700, include_path=False) != root:
            raise _failure()
        if _read_session(session_root, session_sha256) != record:
            raise _failure()
    except KeyboardInterrupt:
        raise
    except SentinelError as error:
        if error.code == FAILURE_CODE and error.exit_code == 5:
            raise
        raise _failure() from None
    except Exception:
        raise _failure() from None
