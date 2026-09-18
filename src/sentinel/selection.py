"""Resolve explicit source/test paths before starting a checker."""

from pathlib import Path

from .errors import SentinelError


def _path(project, value):
    raw = Path(value)
    candidate = raw if raw.is_absolute() else project / raw
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(project.resolve())
    except (OSError, ValueError):
        raise SentinelError("invalidSelection", "selected file must exist inside the project", 3)
    if not resolved.is_file() or candidate.is_symlink():
        raise SentinelError("invalidSelection", "selection requires a regular file", 3)
    return resolved


def resolve_selection(project, modules, files, functions, tests, changed=False, all_files=False):
    if (changed and (files or all_files)) or (all_files and files):
        raise SentinelError("mixedSelection", "choose --all, --changed, or --file", 3)
    if functions and len(files) != 1:
        raise SentinelError("invalidSelection", "--function requires exactly one --file", 3)
    if any(not name or any(char in name for char in "()\n\r\0") for name in functions):
        raise SentinelError("invalidSelection", "use a function name without parentheses", 3)
    selections = {module.module_id: {"files": [], "functions": list(functions), "tests": []} for module in modules}
    for field, values in (("files", files), ("tests", tests)):
        for value in values:
            path = _path(project, value)
            owners = [module for module in modules if path.is_relative_to(module.root.resolve())]
            if len(owners) != 1:
                raise SentinelError("invalidSelection", "selected file must belong to one selected module", 3)
            owner = owners[0]
            relative = path.relative_to(owner.root.resolve()).as_posix()
            if relative not in selections[owner.module_id][field]:
                selections[owner.module_id][field].append(relative)
    selected = [module for module in modules if not files or selections[module.module_id]["files"]]
    if any(value["tests"] and module_id not in {module.module_id for module in selected}
           for module_id, value in selections.items()):
        raise SentinelError("invalidSelection", "tests must belong to a module containing selected source files", 3)
    return selected, selections if files or functions or tests else {}
