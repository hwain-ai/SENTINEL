#!/usr/bin/env python3
"""Maintain src/sentinel/admission.json, the list of adapters the default check may run.

    scripts/admission.py add --language python --commit <sha> [--repository owner/name]
        Looks up the commit's CI run on GitHub, requires it to have succeeded, reads the
        adapter's version and entrypoint at that commit and appends the entry.
    scripts/admission.py verify
        Re-checks every entry against GitHub (needs `gh` authentication).
    scripts/admission.py lint
        Checks the file offline: shape, formats, uniqueness.

`gh` (GitHub CLI) does the API calls, so the caller's own authentication is used.
"""

import argparse
import base64
import datetime
import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from sentinel.admission import (  # noqa: E402
    DEFAULT_ADMISSION,
    Admission,
    load_admissions,
    render_admissions,
)
from sentinel.errors import SentinelError  # noqa: E402
from sentinel.setup import SETUP_LANGUAGES  # noqa: E402

OWNER = "hwain-ai"
WORKFLOW = "ci"
ENTRYPOINT = "sentinel-tool/sentinel-tool"
VERSION = "sentinel-tool/version"


def gh_api(path: str) -> object:
    completed = subprocess.run(
        ["gh", "api", path],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise SystemExit(f"admission: GitHub API call failed for {path}: {completed.stderr.strip()}")
    return json.loads(completed.stdout)


def file_bytes(repository: str, commit: str, path: str) -> bytes:
    document = gh_api(f"repos/{repository}/contents/{path}?ref={commit}")
    if not isinstance(document, dict) or document.get("encoding") != "base64":
        raise SystemExit(f"admission: {repository}:{path}@{commit} is not a file")
    return base64.b64decode(document["content"])


def successful_run(repository: str, commit: str) -> str:
    document = gh_api(f"repos/{repository}/actions/runs?head_sha={commit}&per_page=50")
    runs = document.get("workflow_runs", []) if isinstance(document, dict) else []
    for run in runs:
        if run.get("name") == WORKFLOW and run.get("head_branch") == "main" and run.get("conclusion") == "success":
            return run["html_url"]
    raise SystemExit(f"admission: no successful '{WORKFLOW}' run on main for {repository}@{commit}")


def describe(repository: str, commit: str) -> tuple:
    version = file_bytes(repository, commit, VERSION).decode("utf-8").strip()
    entrypoint = hashlib.sha256(file_bytes(repository, commit, ENTRYPOINT)).hexdigest()
    return version, entrypoint, successful_run(repository, commit)


def command_add(arguments: argparse.Namespace) -> int:
    repository = arguments.repository or f"{OWNER}/{SETUP_LANGUAGES[arguments.language]}"
    commit = gh_api(f"repos/{repository}/commits/{arguments.commit}")["sha"]
    version, entrypoint, run_url = describe(repository, commit)
    entry = Admission(
        language=arguments.language,
        tool_version=version,
        entrypoint_sha256=entrypoint,
        repository=repository,
        commit=commit,
        workflow=WORKFLOW,
        run_url=run_url,
        admitted_at=datetime.date.today().isoformat(),
    )
    admissions = [item for item in load_admissions(arguments.file) if item.key != entry.key]
    admissions.append(entry)
    arguments.file.write_text(render_admissions(admissions), encoding="utf-8")
    print(f"admitted {entry.language} {entry.tool_version} {entry.entrypoint_sha256[:12]} from {repository}@{commit[:7]} ({run_url})")
    return 0


def command_verify(arguments: argparse.Namespace) -> int:
    failures = 0
    for item in load_admissions(arguments.file):
        version, entrypoint, run_url = describe(item.repository, item.commit)
        problems = []
        if version != item.tool_version:
            problems.append(f"version {version} != {item.tool_version}")
        if entrypoint != item.entrypoint_sha256:
            problems.append("entrypoint digest differs")
        if run_url != item.run_url:
            problems.append(f"successful run is {run_url}, recorded {item.run_url}")
        state = "ok" if not problems else "MISMATCH: " + "; ".join(problems)
        failures += bool(problems)
        print(f"{item.language} {item.tool_version} {item.repository}@{item.commit[:7]}: {state}")
    return 1 if failures else 0


def command_lint(arguments: argparse.Namespace) -> int:
    admissions = load_admissions(arguments.file)
    rendered = render_admissions(admissions)
    if arguments.file.read_text(encoding="utf-8") != rendered:
        print("admission: file is not in canonical form; run `scripts/admission.py lint --write`", file=sys.stderr)
        if not arguments.write:
            return 1
        arguments.file.write_text(rendered, encoding="utf-8")
    print(f"admission: {len(admissions)} entries valid")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="admission.py")
    parser.add_argument("--file", type=Path, default=DEFAULT_ADMISSION)
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser("add")
    add.add_argument("--language", required=True, choices=sorted(SETUP_LANGUAGES))
    add.add_argument("--commit", required=True)
    add.add_argument("--repository")
    commands.add_parser("verify")
    lint = commands.add_parser("lint")
    lint.add_argument("--write", action="store_true")
    arguments = parser.parse_args()
    try:
        return {"add": command_add, "verify": command_verify, "lint": command_lint}[arguments.command](arguments)
    except SentinelError as error:
        print(f"admission: {error.code}: {error.message}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
