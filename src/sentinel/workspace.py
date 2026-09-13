import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .errors import SentinelError
from .gate import Gate, load_gate


MAX_CONFIG_BYTES = 1024 * 1024
MODULE_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
SEMVER = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)
DIGEST = re.compile(r"^[0-9a-f]{64}$")
SUPPORTED_LANGUAGES = frozenset(("python", "typescript", "go", "java", "clojure"))


@dataclass(frozen=True)
class Module:
    module_id: str
    language: str
    root: Path
    tool_version: str
    tool_digest: str
    config: Optional[Path]


def _reject_duplicate_keys(pairs: Sequence[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SentinelError("duplicateJsonKey", "configuration contains a duplicate JSON key")
        result[key] = value
    return result


def read_json(path: Path, maximum: int, label: str) -> Any:
    try:
        descriptor = os.open(str(path), os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0))
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise SentinelError("invalidFileType", f"{label} must be a regular file")
            if metadata.st_size > maximum:
                raise SentinelError("fileTooLarge", f"{label} exceeds its size limit")
            chunks = []
            total = 0
            while True:
                chunk = os.read(descriptor, min(64 * 1024, maximum + 1 - total))
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
                if total > maximum:
                    raise SentinelError("fileTooLarge", f"{label} exceeds its size limit")
            if os.fstat(descriptor).st_size != metadata.st_size:
                raise SentinelError("fileChanged", f"{label} changed while it was read")
            raw = b"".join(chunks)
        finally:
            os.close(descriptor)
    except SentinelError:
        raise
    except OSError:
        raise SentinelError("unreadableFile", f"{label} could not be read")
    return parse_json_bytes(raw, label)


def parse_json_bytes(raw: bytes, label: str) -> Any:
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except SentinelError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError):
        raise SentinelError("invalidJson", f"{label} is not valid UTF-8 JSON")


def require_exact_keys(value: Dict[str, Any], required: Iterable[str], optional: Iterable[str], label: str) -> None:
    required_set = set(required)
    allowed = required_set | set(optional)
    if set(value) - allowed or required_set - set(value):
        raise SentinelError("invalidFields", f"{label} has missing or unknown fields")


def require_string(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise SentinelError("invalidType", f"{label} must be a string")
    return value


def is_exact_semver(value: str) -> bool:
    match = SEMVER.fullmatch(value)
    if not match:
        return False
    prerelease = match.group(4)
    if prerelease:
        for identifier in prerelease.split("."):
            if identifier.isdigit() and len(identifier) > 1 and identifier.startswith("0"):
                return False
    return True


def _relative_posix(value: Any, label: str) -> PurePosixPath:
    text = require_string(value, label)
    path = PurePosixPath(text)
    if not text or "\x00" in text or path.is_absolute() or "\\" in text or any(part in ("", ".", "..") for part in path.parts):
        raise SentinelError("invalidPath", f"{label} must be a normalized relative POSIX path")
    return path


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _reject_path_ancestors(path: Path, label: str) -> None:
    absolute = path.absolute()
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current = current / part
        try:
            metadata = os.lstat(current)
        except (OSError, ValueError):
            raise SentinelError("missingPath", f"{label} does not exist")
        if stat.S_ISLNK(metadata.st_mode):
            raise SentinelError("symlinkRejected", f"{label} contains a symbolic link")
        if current != absolute and not stat.S_ISDIR(metadata.st_mode):
            raise SentinelError("invalidPath", f"{label} contains a non-directory ancestor")


def _reject_symlinks_between(parent: Path, relative: PurePosixPath, label: str) -> Path:
    current = parent
    for part in relative.parts:
        current = current / part
        try:
            metadata = os.lstat(current)
        except OSError:
            raise SentinelError("missingPath", f"{label} does not exist")
        if stat.S_ISLNK(metadata.st_mode):
            raise SentinelError("symlinkRejected", f"{label} contains a symbolic link")
    return current


def _load_module(value: Any, project: Path) -> Module:
    if not isinstance(value, dict):
        raise SentinelError("invalidType", "each module must be an object")
    require_exact_keys(value, ("id", "language", "root", "toolVersion", "toolDigest"), ("config",), "module")
    module_id = require_string(value["id"], "module id")
    language = require_string(value["language"], "module language")
    version = require_string(value["toolVersion"], "tool version")
    digest = require_string(value["toolDigest"], "tool digest")
    if not MODULE_ID.fullmatch(module_id):
        raise SentinelError("invalidModuleId", "module id is invalid")
    if language not in SUPPORTED_LANGUAGES:
        raise SentinelError("invalidLanguage", "module language is not admitted")
    if not is_exact_semver(version):
        raise SentinelError("invalidVersion", "tool version must be an exact semantic version")
    if not DIGEST.fullmatch(digest):
        raise SentinelError("invalidDigest", "tool digest must be lowercase SHA-256")
    root_relative = _relative_posix(value["root"], "module root")
    root = _reject_symlinks_between(project, root_relative, "module root")
    if not stat.S_ISDIR(os.lstat(root).st_mode):
        raise SentinelError("invalidFileType", "module root must be a directory")
    if not _inside(root.absolute(), project) or not _inside(root.resolve(), project.resolve()):
        raise SentinelError("outsideProject", "module root must be inside the project")
    config = None
    if "config" in value:
        config_relative = _relative_posix(value["config"], "module config")
        config = _reject_symlinks_between(root, config_relative, "module config")
        if not stat.S_ISREG(os.lstat(config).st_mode):
            raise SentinelError("invalidFileType", "module config must be a regular file")
        if not _inside(config.absolute(), root) or not _inside(config.resolve(), root.resolve()):
            raise SentinelError("outsideModule", "module config must be inside its module root")
    return Module(module_id, language, root, version, digest, config)


def load_workspace(project_value: str, config_value: str) -> Tuple[Path, List[Module], Gate]:
    project = Path(project_value).absolute()
    _reject_path_ancestors(project, "project")
    try:
        metadata = os.lstat(project)
    except OSError:
        raise SentinelError("missingProject", "project directory does not exist")
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise SentinelError("invalidProject", "project must be a real directory")
    config_relative = _relative_posix(config_value, "workspace config")
    config_path = _reject_symlinks_between(project, config_relative, "workspace config")
    payload = read_json(config_path, MAX_CONFIG_BYTES, "workspace config")
    if not isinstance(payload, dict):
        raise SentinelError("invalidType", "workspace config must be an object")
    require_exact_keys(payload, ("schemaVersion", "modules"), ("gate",), "workspace config")
    if payload["schemaVersion"] != "sentinel-workspace-v1":
        raise SentinelError("invalidSchemaVersion", "workspace schema version is unsupported")
    gate = load_gate(payload.get("gate"))
    values = payload["modules"]
    if not isinstance(values, list) or isinstance(values, bool) or not 1 <= len(values) <= 128:
        raise SentinelError("invalidModules", "workspace must contain 1 to 128 modules")
    modules = [_load_module(value, project) for value in values]
    identifiers = [item.module_id for item in modules]
    if len(identifiers) != len(set(identifiers)):
        raise SentinelError("duplicateModuleId", "module ids must be unique")
    roots = sorted((item.root.resolve(), item.module_id) for item in modules)
    for index, (root, _) in enumerate(roots):
        for other, _ in roots[index + 1 :]:
            if _inside(other, root):
                raise SentinelError("nestedModuleRoots", "module roots must not overlap")
    return project, modules, gate


def select_modules(modules: Sequence[Module], languages: Sequence[str], module_ids: Sequence[str]) -> Tuple[str, List[Module]]:
    if languages and module_ids:
        raise SentinelError("mixedSelection", "language and module selectors cannot be mixed")
    if not languages and not module_ids:
        return "allConfigured", list(modules)
    known_languages = {item.language for item in modules}
    known_ids = {item.module_id for item in modules}
    if set(languages) - known_languages or set(module_ids) - known_ids:
        raise SentinelError("unknownSelection", "a selected language or module is not configured")
    selected = [item for item in modules if item.language in languages or item.module_id in module_ids]
    return ("allConfigured" if len(selected) == len(modules) else "partial"), selected
