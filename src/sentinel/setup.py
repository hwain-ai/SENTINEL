"""First-run setup: language sources, pinned SDK bootstrap, tool bundles and workspace config."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from .bundle import install_bundle
from .errors import SentinelError
from .gate import DEFAULT_GATE, Gate, load_gate, override_gate
from .workspace import MAX_CONFIG_BYTES, is_exact_semver, parse_workspace, read_json_snapshot, require_exact_keys, workspace_config_path


SETUP_LANGUAGES = {"python": "SENTINEL_PY", "typescript": "SENTINEL_TS", "java": "SENTINEL_JAVA"}
SOURCE_REPOSITORIES = {
    language: f"https://github.com/hwain-ai/{repository}.git"
    for language, repository in SETUP_LANGUAGES.items()
}
TOOL_DIRECTORY = "sentinel-tool"
TOOL_ENTRYPOINT = "sentinel-tool"
TOOL_SETUP = "setup.sh"
TOOL_VERSION = "version"
TOOL_HOME = "home"
PROJECT_CONFIG = "sentinel.config.json"
# Where a Python project's own test requirements are installed by the checker's launcher.
PYTHON_DEPENDENCY_DIRECTORY = ".sentinel-deps"
# Where a Maven project's build dependencies are warmed by the checker's launcher for offline checks.
JAVA_DEPENDENCY_DIRECTORY = ".sentinel-m2"
# Languages whose checker reads a per-project config next to the workspace file.
CONFIGURED_LANGUAGES = ("python", "typescript")
DEFAULT_PROJECT_MODULES = {
    "python": {
        "id": "python",
        "language": "python",
        "root": ".",
        "production": ["src/**/*.py"],
        "testCommand": ["python", "-m", "pytest"],
        "coverage": {
            "command": ["python", "-m", "coverage", "json"],
            "format": "coverage-py-json",
            "report": "coverage.json",
        },
        "testRoots": ["tests"],
        "testPatterns": ["test_*.py"],
    },
    "typescript": {
        "id": "typescript",
        "language": "typescript",
        "root": ".",
        "production": ["src/**/*.ts"],
        "testCommand": ["vitest", "--run"],
        "coverage": {
            "command": ["vitest", "--run", "--coverage"],
            "format": "istanbul-json",
            "report": "coverage/coverage-final.json",
        },
        "testRoots": ["test"],
        "testPatterns": ["*.test.ts"],
    },
}


def default_sources() -> Path:
    return Path.home() / ".sentinel" / "sources"


def _unique(values: Sequence[str]) -> List[str]:
    ordered: List[str] = []
    for value in values:
        if value not in ordered:
            ordered.append(value)
    return ordered


def _forward(command: Sequence[str], cwd: Path) -> bool:
    """Run a trusted local command, forwarding its output to stderr only."""

    sys.stderr.flush()
    try:
        completed = subprocess.run(
            list(command),
            cwd=str(cwd),
            stdin=subprocess.DEVNULL,
            stdout=sys.stderr,
            stderr=sys.stderr,
            check=False,
        )
    except OSError:
        return False
    return completed.returncode == 0


def _clone(language: str, repository: Path) -> bool:
    repository.parent.mkdir(parents=True, exist_ok=True)
    return _forward(["git", "clone", "--quiet", SOURCE_REPOSITORIES[language], str(repository)], repository.parent)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_private(path: Path, data: bytes, mode: int) -> None:
    descriptor = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)


def _stage_bundle(language: str, repository: Path, tool_directory: Path, tools: Path, version: str) -> Tuple[Path, str]:
    staging = tools / ".staging" / language
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True, mode=0o700)
    entrypoint = staging / TOOL_ENTRYPOINT
    _write_private(entrypoint, (tool_directory / TOOL_ENTRYPOINT).read_bytes(), 0o700)
    home = staging / TOOL_HOME
    _write_private(home, (str(repository) + "\n").encode("utf-8"), 0o600)
    manifest = {
        "schemaVersion": "sentinel-tool-bundle-v1",
        "protocolVersion": "sentinel-tool-protocol-v1",
        "language": language,
        "version": version,
        "entrypoint": TOOL_ENTRYPOINT,
        "files": {TOOL_ENTRYPOINT: _sha256(entrypoint), TOOL_HOME: _sha256(home)},
    }
    manifest_bytes = json.dumps(manifest, separators=(",", ":"), sort_keys=True).encode("utf-8")
    _write_private(staging / "sentinel-tool.json", manifest_bytes, 0o600)
    return staging, hashlib.sha256(manifest_bytes).hexdigest()


def _launcher(repository: Path, script: str) -> List[str]:
    """The checker's cross-platform Python launcher run by this interpreter, or the legacy shell script."""

    python_launcher = repository / "scripts" / "toolchain.py"
    if python_launcher.is_file():
        return [sys.executable, "-I", "-B", str(python_launcher)]
    return [str(repository / "scripts" / script)]


def _install_python_requirements(repository: Path, project: Path, requirements: str) -> bool:
    """Install the project's requirements (wheels only) into <project>/.sentinel-deps; offline first."""

    requirement_path = project / requirements
    if not requirement_path.is_file():
        return False
    target = project / PYTHON_DEPENDENCY_DIRECTORY
    launcher = _launcher(repository, "uv.sh")
    if _forward([*launcher, "deps", str(target), str(requirement_path), "--offline"], repository):
        return True
    sys.stderr.write("sentinel: requirements are not cached, installing from the index online\n")
    return _forward([*launcher, "deps", str(target), str(requirement_path)], repository)


def _install_java_dependencies(repository: Path, project: Path) -> bool:
    """Run the project's default test build online once so <project>/.sentinel-m2 serves later offline checks."""

    launcher = repository / "scripts" / "mvn.sh"
    return _forward([str(launcher), "deps", str(project)], repository)


def _setup_language(
    language: str,
    sources: Path,
    tools: Path,
    projects: Sequence[Path],
    python_requirements: Optional[str],
    java_dependencies: bool,
) -> Dict[str, object]:
    result: Dict[str, object] = {"language": language}
    repository = sources / SETUP_LANGUAGES[language]
    if not repository.is_dir() and not _clone(language, repository):
        result["status"] = "sourceUnavailable"
        return result
    tool_directory = repository / TOOL_DIRECTORY
    if not all((tool_directory / name).is_file() for name in (TOOL_ENTRYPOINT, TOOL_SETUP, TOOL_VERSION)):
        result["status"] = "toolTemplateMissing"
        return result
    version = (tool_directory / TOOL_VERSION).read_text(encoding="utf-8").strip()
    if not is_exact_semver(version):
        result["status"] = "toolTemplateMissing"
        return result
    setup_command = [str(tool_directory / TOOL_SETUP)]
    if (repository / "scripts" / "toolchain.py").is_file():
        setup_command = [*_launcher(repository, TOOL_SETUP), "setup"]
    if not _forward(setup_command, repository):
        result["status"] = "bootstrapFailed"
        return result
    if language == "python" and python_requirements is not None:
        if not all(_install_python_requirements(repository, project, python_requirements) for project in projects):
            result["status"] = "requirementsFailed"
            return result
        result["pythonRequirements"] = python_requirements
    if language == "java" and java_dependencies:
        if not all(_install_java_dependencies(repository, project) for project in projects):
            result["status"] = "dependenciesFailed"
            return result
        result["javaDependencies"] = JAVA_DEPENDENCY_DIRECTORY
    staging, digest = _stage_bundle(language, repository, tool_directory, tools, version)
    try:
        install_bundle(staging, digest, tools)
    except SentinelError:
        result["status"] = "bundleInvalid"
        return result
    finally:
        shutil.rmtree(staging, ignore_errors=True)
        try:
            staging.parent.rmdir()
        except OSError:
            pass
    result.update(status="installed", toolVersion=version, toolDigest=digest)
    return result


def _prepare_workspace(project: Path, config_name: str, languages: Sequence[str], args) -> Tuple[Dict[str, object], Gate, Optional[bytes]]:
    """Resolve and validate the complete layout before downloading or installing anything."""

    path = workspace_config_path(project, config_name, allow_missing=True)
    original_bytes = None
    if path.exists():
        document, original_bytes = read_json_snapshot(path, MAX_CONFIG_BYTES, "workspace config")
        if not isinstance(document, dict):
            raise SentinelError("invalidType", "workspace config must be an object", 3)
        require_exact_keys(document, ("schemaVersion", "modules"), ("gate",), "workspace config")
        modules = document["modules"]
        if not isinstance(modules, list) or any(not isinstance(module, dict) for module in modules):
            raise SentinelError("invalidModules", "workspace modules must be objects", 3)
        existing_gate = load_gate(document.get("gate"))
    else:
        document = {"schemaVersion": "sentinel-workspace-v1", "modules": []}
        existing_gate = DEFAULT_GATE
    gate = override_gate(existing_gate, args.crap_max, args.mutation_min)
    roots = {}
    for mapping in getattr(args, "module_root", []):
        language, separator, root = mapping.partition("=")
        if not separator or language not in languages or not root or language in roots:
            raise SentinelError("usageError", "--module-root requires one selected language=relative/path per language", 3)
        roots[language] = root
    modules = document["modules"]
    for language in languages:
        existing = [module for module in modules if module.get("language") == language]
        if existing:
            if language in roots:
                if len(existing) != 1:
                    raise SentinelError("usageError", "--module-root is ambiguous for multiple modules of one language", 3)
                existing[0]["root"] = roots[language]
            continue
        root = roots.get(language)
        if root is None:
            if len(languages) != 1 or modules:
                raise SentinelError("usageError", f"set --module-root {language}=relative/path for each new language", 3)
            root = "."
        module = {"id": language, "language": language, "root": root, "toolVersion": "0.0.0", "toolDigest": "0" * 64}
        if language in CONFIGURED_LANGUAGES:
            module["config"] = PROJECT_CONFIG
        modules.append(module)
    document["gate"] = gate.as_json()
    # Default project configs are created only after setup succeeds; validate all other fields now.
    validation_modules = []
    for module in modules:
        validated = dict(module)
        if (module.get("language") in languages and module.get("config") == PROJECT_CONFIG
                and isinstance(module.get("root"), str)):
            config_path = project / module["root"] / PROJECT_CONFIG
            if not config_path.exists() and not config_path.is_symlink():
                validated.pop("config")
        validation_modules.append(validated)
    parse_workspace(project, dict(document, modules=validation_modules))
    return document, gate, original_bytes


def _replace_file(path: Path, document: Dict[str, object]) -> None:
    data = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def _require_unchanged_workspace(project: Path, config_name: str, original_bytes: Optional[bytes]) -> None:
    path = workspace_config_path(project, config_name, allow_missing=True)
    current = read_json_snapshot(path, MAX_CONFIG_BYTES, "workspace config")[1] if path.exists() else None
    if current != original_bytes:
        raise SentinelError("workspaceChanged", "workspace config changed during setup; kept the newer file, retry setup", 3)


def _write_workspace(project: Path, config_name: str, document: Dict[str, object], installed: Dict[str, Dict[str, object]], original_bytes: Optional[bytes]) -> None:
    for module in document["modules"]:
        result = installed.get(module["language"])
        if result is not None:
            module.update(toolVersion=result["toolVersion"], toolDigest=result["toolDigest"])
    parse_workspace(project, document)
    _require_unchanged_workspace(project, config_name, original_bytes)
    _replace_file(project / config_name, document)


def _ensure_project_config(project: Path, languages: Sequence[str]) -> Optional[str]:
    configured = [language for language in languages if language in CONFIGURED_LANGUAGES]
    if not configured:
        return None
    path = project / PROJECT_CONFIG
    if path.exists():
        return "kept"
    _replace_file(path, {"specVersion": "1.0.0", "modules": [DEFAULT_PROJECT_MODULES[language] for language in configured]})
    return "created"


def run_setup(args) -> Tuple[Dict[str, object], int]:
    project = Path(args.project or os.getcwd()).absolute()
    if not project.is_dir():
        raise SentinelError("missingProject", "project directory does not exist", 3)
    tools = Path(args.tools).absolute() if args.tools else project / ".sentinel-tools"
    sources = Path(args.sources).absolute() if args.sources else default_sources()
    languages = _unique(args.language) or sorted(SETUP_LANGUAGES)
    requirements = getattr(args, "python_requirements", None)
    if requirements is not None and "python" not in languages:
        raise SentinelError("usageError", "--python-requirements needs --language python", 3)
    java_dependencies = bool(getattr(args, "java_dependencies", False))
    if java_dependencies and "java" not in languages:
        raise SentinelError("usageError", "--java-dependencies needs --language java", 3)
    document, gate, original_bytes = _prepare_workspace(project, args.config, languages, args)
    results = [
        _setup_language(language, sources, tools,
                        [project / module["root"] for module in document["modules"] if module["language"] == language],
                        requirements, java_dependencies)
        for language in languages
    ]
    installed = {item["language"]: item for item in results if item["status"] == "installed"}
    passed = len(installed) == len(languages)
    project_config = None
    if passed:
        _require_unchanged_workspace(project, args.config, original_bytes)
        config_results = [
            _ensure_project_config(project / module["root"], [module["language"]])
            for module in document["modules"]
            if module["language"] in languages and module.get("config") == PROJECT_CONFIG
        ]
        project_config = "created" if "created" in config_results else "kept" if config_results else None
        _write_workspace(project, args.config, document, installed, original_bytes)
    payload = {
        "schemaVersion": "sentinel-setup-result-v1",
        "command": "setup",
        "gate": gate.as_json(),
        "results": results,
        "workspaceConfig": args.config if passed else None,
        "projectConfig": project_config,
        "pass": passed,
        "exitCode": 0 if passed else 5,
    }
    return payload, payload["exitCode"]
