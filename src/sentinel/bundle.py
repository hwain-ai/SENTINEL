import hashlib
import ctypes
import errno
import os
import secrets
import shutil
import stat
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List

from .errors import SentinelError
from .workspace import (
    DIGEST,
    SUPPORTED_LANGUAGES,
    is_exact_semver,
    parse_json_bytes,
    require_exact_keys,
    require_string,
)


MAX_FILES = 4096
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_BUNDLE_BYTES = 64 * 1024 * 1024
MAX_PATH_DEPTH = 256
AT_FDCWD = -100
RENAME_NOREPLACE = 1
RENAME_EXCL = 4


@dataclass(frozen=True)
class Bundle:
    source: Path
    language: str
    version: str
    digest: str
    entrypoint: str
    files: Dict[str, str]
    protocol_version: str = "sentinel-tool-protocol-v1"


def bundle_path(tools: Path, language: str, version: str, digest: str) -> Path:
    return tools / language / version / digest


def _absolute_path(path: Path) -> Path:
    if ".." in path.parts:
        raise SentinelError("unsafePath", "parent traversal is not allowed")
    try:
        return path.absolute()
    except (OSError, UnicodeError, ValueError):
        raise SentinelError("unsafePath", "path could not be resolved")


def _safe_relative(value: Any, label: str) -> str:
    text = require_string(value, label)
    path = PurePosixPath(text)
    if (
        not text
        or "\x00" in text
        or path.is_absolute()
        or "\\" in text
        or len(path.parts) > MAX_PATH_DEPTH
        or any(part in ("", ".", "..") for part in path.parts)
    ):
        raise SentinelError("invalidBundlePath", f"{label} is not a safe relative POSIX path")
    return text


def _read_regular_file(path: Path, label: str) -> tuple:
    try:
        metadata = os.lstat(path)
    except (OSError, ValueError):
        raise SentinelError("missingBundleFile", f"{label} is missing")
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        raise SentinelError("invalidBundleFile", f"{label} must be one regular, non-linked file")
    if metadata.st_size > MAX_FILE_BYTES:
        raise SentinelError("bundleFileTooLarge", f"{label} exceeds its size limit")
    try:
        descriptor = os.open(str(path), os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0))
        try:
            opened = os.fstat(descriptor)
            if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1 or opened.st_size > MAX_FILE_BYTES:
                raise SentinelError("invalidBundleFile", f"{label} must be one bounded regular file")
            chunks = []
            total = 0
            while True:
                chunk = os.read(descriptor, min(64 * 1024, MAX_FILE_BYTES + 1 - total))
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
                if total > MAX_FILE_BYTES:
                    raise SentinelError("bundleFileTooLarge", f"{label} exceeds its size limit")
            finished = os.fstat(descriptor)
            identity_before = (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns)
            identity_after = (finished.st_dev, finished.st_ino, finished.st_size, finished.st_mtime_ns)
            if identity_before != identity_after or total != opened.st_size:
                raise SentinelError("bundleFileChanged", f"{label} changed while it was read")
        finally:
            os.close(descriptor)
    except (OSError, ValueError):
        raise SentinelError("unreadableBundleFile", f"{label} could not be read")
    data = b"".join(chunks)
    return hashlib.sha256(data).hexdigest(), len(data), data


def _inventory_bundle(source: Path) -> tuple:
    found: Dict[str, os.stat_result] = {}
    found_directories: List[Path] = [source]
    directory_count = 0
    total_bytes = 0
    def reject_walk_error(_error: OSError) -> None:
        raise SentinelError("invalidBundleEntry", "bundle directory could not be inspected")

    for current, directories, filenames in os.walk(
        source, topdown=True, onerror=reject_walk_error, followlinks=False
    ):
        directory_count += len(directories)
        if directory_count > MAX_FILES:
            raise SentinelError("bundleTooLarge", "bundle contains too many directories")
        current_path = Path(current)
        try:
            if len(current_path.relative_to(source).parts) > MAX_PATH_DEPTH:
                raise SentinelError("bundlePathTooDeep", "bundle directory nesting is too deep")
        except ValueError:
            raise SentinelError("invalidBundleEntry", "bundle traversal escaped its source")
        for name in list(directories):
            path = current_path / name
            try:
                metadata = os.lstat(path)
            except (OSError, ValueError):
                raise SentinelError("invalidBundleEntry", "bundle directory could not be inspected")
            if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
                raise SentinelError("invalidBundleEntry", "bundle contains a non-directory or symbolic link")
            found_directories.append(path)
        for name in filenames:
            if len(found) >= MAX_FILES + 1:
                raise SentinelError("bundleTooLarge", "bundle contains too many files")
            path = current_path / name
            relative = path.relative_to(source).as_posix()
            try:
                metadata = os.lstat(path)
            except (OSError, ValueError):
                raise SentinelError("invalidBundleEntry", "bundle entry could not be inspected")
            if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                raise SentinelError("invalidBundleEntry", "bundle contains a non-regular or linked file")
            if metadata.st_size > MAX_FILE_BYTES:
                raise SentinelError("bundleFileTooLarge", "bundle file exceeds its size limit")
            total_bytes += metadata.st_size
            if total_bytes > MAX_BUNDLE_BYTES:
                raise SentinelError("bundleTooLarge", "bundle exceeds its total size limit")
            found[relative] = metadata
    return found, found_directories


def _write_restricted(path: Path, data: bytes, mode: int) -> None:
    try:
        descriptor = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
        try:
            written = 0
            while written < len(data):
                written += os.write(descriptor, data[written:])
        finally:
            os.close(descriptor)
    except OSError:
        raise SentinelError("bundleWriteFailed", "bundle file could not be installed")


def _validate_installed_modes(bundle: Bundle) -> None:
    try:
        for relative in bundle.files:
            expected = (
                0o700
                if bundle.protocol_version == "sentinel-tool-protocol-v1"
                and relative == bundle.entrypoint
                else 0o600
            )
            if stat.S_IMODE(os.lstat(bundle.source / PurePosixPath(relative)).st_mode) != expected:
                raise SentinelError("invalidInstalledMode", "installed bundle has unsafe file permissions")
        if stat.S_IMODE(os.lstat(bundle.source / "sentinel-tool.json").st_mode) != 0o600:
            raise SentinelError("invalidInstalledMode", "installed bundle has unsafe file permissions")
        _files, directories = _inventory_bundle(bundle.source)
        if any(stat.S_IMODE(os.lstat(path).st_mode) != 0o700 for path in directories):
            raise SentinelError("invalidInstalledMode", "installed bundle has unsafe directory permissions")
    except OSError:
        raise SentinelError("invalidInstalledMode", "installed bundle permissions could not be verified")


def validate_bundle(source_value: Path, expected_digest: str) -> Bundle:
    if not DIGEST.fullmatch(expected_digest):
        raise SentinelError("invalidDigest", "bundle digest must be lowercase SHA-256")
    source = _absolute_path(source_value)
    _reject_symlink_ancestors(source, require_directory=True)
    try:
        source_metadata = os.lstat(source)
    except OSError:
        raise SentinelError("missingBundle", "bundle directory does not exist")
    if stat.S_ISLNK(source_metadata.st_mode) or not stat.S_ISDIR(source_metadata.st_mode):
        raise SentinelError("invalidBundle", "bundle must be a real directory")
    manifest_path = source / "sentinel-tool.json"
    manifest_digest, manifest_size, manifest_raw = _read_regular_file(manifest_path, "bundle manifest")
    if not secrets.compare_digest(manifest_digest, expected_digest):
        raise SentinelError("bundleDigestMismatch", "bundle manifest digest does not match the pin")
    manifest = parse_json_bytes(manifest_raw, "bundle manifest")
    if not isinstance(manifest, dict):
        raise SentinelError("invalidType", "bundle manifest must be an object")
    require_exact_keys(
        manifest,
        ("schemaVersion", "protocolVersion", "language", "version", "entrypoint", "files"),
        (),
        "bundle manifest",
    )
    protocol_version = manifest["protocolVersion"]
    if manifest["schemaVersion"] != "sentinel-tool-bundle-v1" or protocol_version not in (
        "sentinel-tool-protocol-v1",
        "sentinel-go-oci-v1",
    ):
        raise SentinelError("unsupportedBundle", "bundle schema or protocol version is unsupported")
    language = require_string(manifest["language"], "bundle language")
    version = require_string(manifest["version"], "bundle version")
    if language not in SUPPORTED_LANGUAGES or not is_exact_semver(version):
        raise SentinelError("invalidBundleIdentity", "bundle language or version is invalid")
    if protocol_version == "sentinel-go-oci-v1" and (language, version) != ("go", "0.1.0"):
        raise SentinelError("invalidBundleIdentity", "native Go bundle identity is invalid")
    entrypoint = _safe_relative(manifest["entrypoint"], "bundle entrypoint")
    files = manifest["files"]
    if not isinstance(files, dict) or isinstance(files, bool) or not 1 <= len(files) <= MAX_FILES:
        raise SentinelError("invalidBundleFiles", "bundle files must be a non-empty bounded object")
    normalized: Dict[str, str] = {}
    for raw_path, raw_digest in files.items():
        relative = _safe_relative(raw_path, "bundle file path")
        digest = require_string(raw_digest, "bundle file digest")
        if relative == "sentinel-tool.json" or not DIGEST.fullmatch(digest):
            raise SentinelError("invalidBundleFiles", "bundle file record is invalid")
        normalized[relative] = digest
    if entrypoint not in normalized:
        raise SentinelError("missingEntrypoint", "bundle entrypoint must be listed in files")
    actual_files, _directories = _inventory_bundle(source)
    if set(actual_files) != set(normalized) | {"sentinel-tool.json"}:
        raise SentinelError("unlistedBundleFile", "bundle contains missing or unlisted files")
    if actual_files["sentinel-tool.json"].st_size != manifest_size:
        raise SentinelError("bundleFileChanged", "bundle manifest changed during validation")
    total_read = manifest_size
    for relative, digest in normalized.items():
        actual, size, _ = _read_regular_file(source / PurePosixPath(relative), "bundle file")
        if size != actual_files[relative].st_size:
            raise SentinelError("bundleFileChanged", "bundle file changed during validation")
        total_read += size
        if total_read > MAX_BUNDLE_BYTES:
            raise SentinelError("bundleTooLarge", "bundle exceeds its total size limit")
        if not secrets.compare_digest(actual, digest):
            raise SentinelError("bundleFileDigestMismatch", "a bundle file digest does not match")
    return Bundle(source, language, version, expected_digest, entrypoint, normalized, protocol_version)


def _reject_symlink_ancestors(path: Path, require_directory: bool = False) -> None:
    absolute = _absolute_path(path)
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current = current / part
        try:
            metadata = os.lstat(current)
        except FileNotFoundError:
            if require_directory:
                raise SentinelError("unsafePath", "required path does not exist")
            break
        except (OSError, ValueError):
            raise SentinelError("unsafePath", "path could not be validated")
        if stat.S_ISLNK(metadata.st_mode):
            raise SentinelError("unsafePath", "path contains a symbolic link")
        if current != absolute and not stat.S_ISDIR(metadata.st_mode):
            raise SentinelError("unsafePath", "path contains a non-directory ancestor")
        if current == absolute and require_directory and not stat.S_ISDIR(metadata.st_mode):
            raise SentinelError("unsafePath", "required path must be a directory")


def _make_private_directories(path: Path) -> None:
    absolute = _absolute_path(path)
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current = current / part
        try:
            metadata = os.lstat(current)
        except FileNotFoundError:
            try:
                os.mkdir(current, 0o700)
                metadata = os.lstat(current)
            except FileExistsError:
                try:
                    metadata = os.lstat(current)
                except OSError:
                    raise SentinelError("directoryCreateFailed", "concurrent install directory could not be verified")
            except OSError:
                raise SentinelError("directoryCreateFailed", "private install directory could not be created")
            if stat.S_IMODE(metadata.st_mode) != 0o700:
                raise SentinelError("unsafeDirectoryMode", "new install directory is not private")
        except (OSError, ValueError):
            raise SentinelError("unsafePath", "install path could not be validated")
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise SentinelError("unsafePath", "install path contains an unsafe component")


def _publish_noreplace(staged: Path, destination: Path) -> bool:
    # RISK(race): both native operations reject existing destinations atomically.
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        if sys.platform == "darwin":
            rename = libc.renamex_np
            rename.argtypes = (ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint)
            arguments = (os.fsencode(staged), os.fsencode(destination), RENAME_EXCL)
        elif sys.platform == "linux":
            rename = libc.renameat2
            rename.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
            arguments = (AT_FDCWD, os.fsencode(staged), AT_FDCWD, os.fsencode(destination), RENAME_NOREPLACE)
        else:
            raise SentinelError("atomicPublishUnavailable", "atomic no-replace publication is unavailable")
    except (AttributeError, OSError):
        raise SentinelError("atomicPublishUnavailable", "atomic no-replace publication is unavailable")
    rename.restype = ctypes.c_int
    result = rename(*arguments)
    if result == 0:
        return True
    error_number = ctypes.get_errno()
    if error_number == errno.EEXIST:
        return False
    raise SentinelError("atomicPublishFailed", "bundle could not be published atomically")


def install_bundle(source: Path, expected_digest: str, tools: Path) -> Bundle:
    bundle = validate_bundle(source, expected_digest)
    tools = _absolute_path(tools)
    _reject_symlink_ancestors(tools)
    destination = bundle_path(tools, bundle.language, bundle.version, bundle.digest)
    _reject_symlink_ancestors(destination)
    if destination.exists():
        installed = validate_bundle(destination, expected_digest)
        _validate_installed_modes(installed)
        return bundle
    parent = destination.parent
    _make_private_directories(parent)
    _reject_symlink_ancestors(parent, require_directory=True)
    temporary = parent / (".install-" + secrets.token_hex(12))
    try:
        _make_private_directories(temporary)
        manifest_digest, manifest_size, manifest_data = _read_regular_file(
            bundle.source / "sentinel-tool.json", "bundle manifest"
        )
        if not secrets.compare_digest(manifest_digest, bundle.digest):
            raise SentinelError("bundleDigestMismatch", "bundle manifest changed before installation")
        copied_bytes = manifest_size
        for relative, expected_file_digest in bundle.files.items():
            target = temporary / PurePosixPath(relative)
            _make_private_directories(target.parent)
            actual_digest, size, data = _read_regular_file(
                bundle.source / PurePosixPath(relative), "bundle file"
            )
            if not secrets.compare_digest(actual_digest, expected_file_digest):
                raise SentinelError("bundleFileDigestMismatch", "bundle file changed before installation")
            copied_bytes += size
            if copied_bytes > MAX_BUNDLE_BYTES:
                raise SentinelError("bundleTooLarge", "bundle exceeds its copy size limit")
            mode = (
                0o700
                if bundle.protocol_version == "sentinel-tool-protocol-v1"
                and relative == bundle.entrypoint
                else 0o600
            )
            _write_restricted(target, data, mode)
        manifest_target = temporary / "sentinel-tool.json"
        _write_restricted(manifest_target, manifest_data, 0o600)
        staged = validate_bundle(temporary, bundle.digest)
        _validate_installed_modes(staged)
        if not _publish_noreplace(temporary, destination):
            installed = validate_bundle(destination, bundle.digest)
            _validate_installed_modes(installed)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return bundle


def validate_installed_bundle(tools: Path, language: str, version: str, digest: str) -> Bundle:
    destination = bundle_path(_absolute_path(tools), language, version, digest)
    try:
        _reject_symlink_ancestors(destination, require_directory=True)
        bundle = validate_bundle(destination, digest)
        _validate_installed_modes(bundle)
    except SentinelError as error:
        raise SentinelError("bundleUnavailable", "a selected tool bundle is unavailable or corrupt", 5) from error
    if bundle.language != language or bundle.version != version:
        raise SentinelError("bundleIdentityMismatch", "a selected tool bundle identity does not match", 5)
    return bundle
