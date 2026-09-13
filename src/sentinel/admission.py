"""Admitted tool bundles: the exact adapters the default check may run.

An admission names a language, the adapter's tool version and the SHA-256 of
the adapter entrypoint (``sentinel-tool``) as recorded at a commit whose CI run
passed. The file ships inside the package, so a check needs no network: the
installed bundle's own manifest already carries the entrypoint digest that is
compared here.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Sequence, Tuple

from .bundle import Bundle
from .errors import SentinelError
from .workspace import MAX_CONFIG_BYTES, is_exact_semver, read_json


ADMISSION_SCHEMA = "sentinel-admission-v1"
DEFAULT_ADMISSION = Path(__file__).with_name("admission.json")
ADMISSIBLE_LANGUAGES = ("java", "python", "typescript")
ENTRY_KEYS = ("language", "toolVersion", "entrypointSha256", "source", "ci", "admittedAt")
SOURCE_KEYS = ("repository", "commit")
CI_KEYS = ("workflow", "runUrl")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")
REPOSITORY = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?/[A-Za-z0-9_.-]+$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
RUN_URL = re.compile(r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/actions/runs/\d+$")


@dataclass(frozen=True)
class Admission:
    language: str
    tool_version: str
    entrypoint_sha256: str
    repository: str
    commit: str
    workflow: str
    run_url: str
    admitted_at: str

    def as_json(self) -> Dict[str, object]:
        return {
            "language": self.language,
            "toolVersion": self.tool_version,
            "entrypointSha256": self.entrypoint_sha256,
            "source": {"repository": self.repository, "commit": self.commit},
            "ci": {"workflow": self.workflow, "runUrl": self.run_url},
            "admittedAt": self.admitted_at,
        }

    @property
    def key(self) -> Tuple[str, str, str]:
        return (self.language, self.tool_version, self.entrypoint_sha256)


def _invalid(message: str) -> SentinelError:
    return SentinelError("admissionInvalid", message, 3)


def _text(mapping: Dict[str, object], key: str, pattern: "re.Pattern[str]", label: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise _invalid(f"admission {label} is invalid")
    return value


def _exact(mapping: object, keys: Sequence[str], label: str) -> Dict[str, object]:
    if not isinstance(mapping, dict) or set(mapping) != set(keys):
        raise _invalid(f"admission {label} must have exactly the fields {', '.join(keys)}")
    return mapping


def parse_admission(value: object) -> Admission:
    entry = _exact(value, ENTRY_KEYS, "entry")
    language = entry.get("language")
    if language not in ADMISSIBLE_LANGUAGES:
        raise _invalid("admission language is not admissible")
    version = entry.get("toolVersion")
    if not isinstance(version, str) or not is_exact_semver(version):
        raise _invalid("admission toolVersion must be exact semver")
    source = _exact(entry.get("source"), SOURCE_KEYS, "source")
    ci = _exact(entry.get("ci"), CI_KEYS, "ci")
    workflow = ci.get("workflow")
    if not isinstance(workflow, str) or not workflow or len(workflow) > 64:
        raise _invalid("admission ci workflow name is invalid")
    return Admission(
        language=language,
        tool_version=version,
        entrypoint_sha256=_text(entry, "entrypointSha256", SHA256, "entrypointSha256"),
        repository=_text(source, "repository", REPOSITORY, "source repository"),
        commit=_text(source, "commit", COMMIT, "source commit"),
        workflow=workflow,
        run_url=_text(ci, "runUrl", RUN_URL, "ci runUrl"),
        admitted_at=_text(entry, "admittedAt", DATE, "admittedAt"),
    )


def parse_admissions(document: object) -> Tuple[Admission, ...]:
    payload = _exact(document, ("schemaVersion", "admitted"), "document")
    if payload.get("schemaVersion") != ADMISSION_SCHEMA:
        raise _invalid("admission schemaVersion is not supported")
    entries = payload.get("admitted")
    if not isinstance(entries, list):
        raise _invalid("admission admitted must be a list")
    admissions = tuple(parse_admission(item) for item in entries)
    keys = [item.key for item in admissions]
    if len(set(keys)) != len(keys):
        raise _invalid("admission entries must be unique per language, version and entrypoint")
    return admissions


def load_admissions(path: Path = DEFAULT_ADMISSION) -> Tuple[Admission, ...]:
    try:
        document = read_json(path, MAX_CONFIG_BYTES, "admission file")
    except SentinelError as error:
        raise _invalid("admission file could not be read") from error
    return parse_admissions(document)


def render_admissions(admissions: Iterable[Admission]) -> str:
    ordered = sorted(admissions, key=lambda item: (item.language, item.tool_version, item.admitted_at, item.entrypoint_sha256))
    document = {"schemaVersion": ADMISSION_SCHEMA, "admitted": [item.as_json() for item in ordered]}
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def is_admitted(admissions: Sequence[Admission], bundle: Bundle) -> bool:
    """True when the installed bundle's entrypoint digest is admitted for its language and version."""

    entrypoint_digest = bundle.files.get(bundle.entrypoint)
    if entrypoint_digest is None:
        return False
    return (bundle.language, bundle.version, entrypoint_digest) in {item.key for item in admissions}
