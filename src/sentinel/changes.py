"""Changed-file discovery for check --changed: Git differences against a base ref."""

import os
import subprocess
from pathlib import Path
from typing import List, Optional, Sequence

from .errors import SentinelError
from .workspace import Module


GIT_ENVIRONMENT = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "GIT_TERMINAL_PROMPT": "0"}
GIT_TIMEOUT_SECONDS = 60.0


def _git(project: Path, *arguments: str) -> bytes:
    try:
        completed = subprocess.run(
            ["git", "-C", str(project), *arguments],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=GIT_ENVIRONMENT,
            timeout=GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise SentinelError("gitUnavailable", "git could not be executed for changed-file discovery", 3)
    if completed.returncode != 0:
        raise SentinelError("gitFailed", "git could not list changes against the base ref", 3)
    return completed.stdout


def changed_files(project: Path, base: str) -> List[Path]:
    """Return absolute paths of files that differ from ``base`` or are untracked, existing only."""

    if not base or base.startswith("-"):
        raise SentinelError("invalidBase", "changed base must be a git ref", 3)
    top = _git(project, "rev-parse", "--show-toplevel").decode("utf-8", "surrogateescape").rstrip("\n")
    if not top:
        raise SentinelError("gitFailed", "project is not inside a git work tree", 3)
    top_path = Path(top)
    raw = _git(project, "diff", "--name-only", "-z", base, "--", ".")
    raw += _git(project, "ls-files", "--others", "--exclude-standard", "-z", "--", ".")
    found = []
    for entry in raw.split(b"\0"):
        if not entry:
            continue
        relative = os.fsdecode(entry)
        if _tool_owned(relative):
            continue
        candidate = top_path / relative
        if candidate.is_file() and not candidate.is_symlink():
            found.append(candidate.absolute())
    return sorted(set(found))


def _tool_owned(relative: str) -> bool:
    """SENTINEL's own untracked folders (.sentinel-tools, .sentinel-deps, .sentinel-m2, .sentinel) are never changes."""

    return any(part.startswith(".sentinel") for part in relative.split("/"))


def module_changes(module: Module, changed: Sequence[Path]) -> List[str]:
    """Module-root-relative POSIX paths of the changed files that live inside the module."""

    root = module.root.absolute()
    relative = []
    for path in changed:
        try:
            relative.append(path.relative_to(root).as_posix())
        except ValueError:
            continue
    return relative


def optional_changes(project: Path, base: Optional[str]) -> Optional[List[Path]]:
    return None if base is None else changed_files(project, base)
