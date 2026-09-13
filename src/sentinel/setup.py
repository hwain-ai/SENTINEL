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
from .gate import DEFAULT_GATE, Gate, override_gate
from .workspace import MAX_CONFIG_BYTES, is_exact_semver, read_json


SETUP_LANGUAGES = {"python": "SENTINEL_PY", "typescript": "SENTINEL_TS", "java": "SENTINEL_JAVA"}
SOURCE_REPOSITORIES = {
    language: f"https://github.com/hwain-hwang/{repository}.git"
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


def _install_python_requirements(repository: Path, project: Path, requirements: str) -> bool:
    """Install the project's requirements (wheels only) into <project>/.sentinel-deps; offline first."""

    requirement_path = project / requirements
    if not requirement_path.is_file():
        return False
    target = project / PYTHON_DEPENDENCY_DIRECTORY
    launcher = repository / "scripts" / "uv.sh"
    if _forward([str(launcher), "deps", str(target), str(requirement_path), "--offline"], repository):
        return True
    sys.stderr.write("sentinel: requirements are not cached, installing from the index online\n")
    return _forward([str(launcher), "deps", str(target), str(requirement_path)], repository)


def _install_java_dependencies(repository: Path, project: Path) -> bool:
    """Run the project's default test build online once so <project>/.sentinel-m2 serves later offline checks."""

    launcher = repository / "scripts" / "mvn.sh"
    return _forward([str(launcher), "deps", str(project)], repository)


def _setup_language(
    language: str,
    sources: Path,
    tools: Path,
    project: Path,
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
    if not _forward([str(tool_directory / TOOL_SETUP)], repository):
        result["status"] = "bootstrapFailed"
        return result
    if language == "python" and python_requirements is not None:
        if not _install_python_requirements(repository, project, python_requirements):
            result["status"] = "requirementsFailed"
            return result
        result["pythonRequirements"] = python_requirements
    if language == "java" and java_dependencies:
        if not _install_java_dependencies(repository, project):
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


def _existing_modules(path: Path, replaced: Sequence[str]) -> List[Dict[str, object]]:
    if not path.exists():
        return []
    payload = read_json(path, MAX_CONFIG_BYTES, "workspace config")
    modules = payload.get("modules") if isinstance(payload, dict) else None
    if not isinstance(modules, list):
        return []
    return [item for item in modules if isinstance(item, dict) and item.get("language") not in replaced]


def _replace_file(path: Path, document: Dict[str, object]) -> None:
    data = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def _write_workspace(project: Path, config_name: str, installed: Dict[str, Dict[str, object]], gate: Gate) -> None:
    path = project / config_name
    modules = _existing_modules(path, tuple(installed))
    for language, result in installed.items():
        module: Dict[str, object] = {
            "id": language,
            "language": language,
            "root": ".",
            "toolVersion": result["toolVersion"],
            "toolDigest": result["toolDigest"],
        }
        if language in CONFIGURED_LANGUAGES:
            module["config"] = PROJECT_CONFIG
        modules.append(module)
    _replace_file(path, {"schemaVersion": "sentinel-workspace-v1", "gate": gate.as_json(), "modules": modules})


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
    gate = override_gate(DEFAULT_GATE, args.crap_max, args.mutation_min)
    tools = Path(args.tools).absolute() if args.tools else project / ".sentinel-tools"
    sources = Path(args.sources).absolute() if args.sources else default_sources()
    languages = _unique(args.language)
    requirements = getattr(args, "python_requirements", None)
    if requirements is not None and "python" not in languages:
        raise SentinelError("usageError", "--python-requirements needs --language python", 3)
    java_dependencies = bool(getattr(args, "java_dependencies", False))
    if java_dependencies and "java" not in languages:
        raise SentinelError("usageError", "--java-dependencies needs --language java", 3)
    results = [
        _setup_language(language, sources, tools, project, requirements, java_dependencies)
        for language in languages
    ]
    installed = {item["language"]: item for item in results if item["status"] == "installed"}
    passed = len(installed) == len(languages)
    project_config = None
    if passed:
        _write_workspace(project, args.config, installed, gate)
        project_config = _ensure_project_config(project, languages)
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
