"""Assemble verified inputs for the closed Go container profile, not admission."""

from dataclasses import dataclass
import hashlib
import json
import os
from typing import Tuple

from . import content_root as content, oci
from .errors import SentinelError
from .go_runtime import GO_LOCK, GoRuntime, _verify_lock, release_tree_sha256


RUNTIME_PATH = "/opt/sentinel/go/toolchain/go-1.27.1"
STATE_PATH = "/opt/sentinel/go/toolchain/state"
ARTIFACT_PATH = "/opt/sentinel/go/artifact"
CORPUS_PATH = "/input/project"
PROJECT_PATH = "/work/project"
DESTINATIONS = (RUNTIME_PATH, ARTIFACT_PATH, STATE_PATH + "/module-cache", CORPUS_PATH)
NATIVE_IDENTITIES = {
    "bin/sentinel-go": "sentinel-go/0.1.0",
    "libexec/sentinel-go-test-runner": "sentinel-go-test-runner/1",
    "libexec/sentinel-mutate4go-bridge": "sentinel-mutate4go-bridge/1 upstream/9016c7adafc1c7e282b5e27768e732e477713af8",
}
SUPPORT_FILES = frozenset(("support/bin/make", "support/bin/sentinel-go-mutesting-probe",
                           "support/licenses/make-copyright", "support/licenses/go-mutesting-LICENSE"))
REFERENCE_RUNNER = "support/bin/sentinel-go-reference-runner"
_MAKE_SHA256 = "d78b8f1d099fbcfb6f2f49ab87223b9b68fb3956642f92d6ec6de812e8afa965"


@dataclass(frozen=True)
class GoPreparedInputs:
    runtime: GoRuntime
    artifact: content.PreparedRoot
    dependencies: content.PreparedRoot
    corpus: content.PreparedRoot
    uid: int
    gid: int
    release_hashes: Tuple[str, ...]
    support_schema: str = "sentinel-go-support-v1"


def _failure():
    return SentinelError("goInputsFailed", "Go input verification failed", 5)


def roots(inputs):
    return (inputs.runtime.content, inputs.artifact, inputs.dependencies, inputs.corpus)


def _support_schema(value):
    if type(value) is not str or value not in ("sentinel-go-support-v1", "sentinel-go-support-v2"):
        raise _failure()


def _require_support_profile(inputs, expected):
    # RISK(security): accepting v2 generically never enables it in legacy lanes.
    if type(getattr(inputs, "support_schema", None)) is not str or inputs.support_schema != expected:
        raise _failure()


def _record(root, name):
    try:
        entry = next((entry for entry in root._entries if entry.path == name), None)
        raw, _ = oci._read_regular(root.root / name, 64 * 1024)
        # Bind the bytes being interpreted to the sealed inventory, including
        # when another same-UID process replaces then restores this file.
        if entry is None or len(raw) != entry.bytes or hashlib.sha256(raw).hexdigest() != entry.sha256:
            raise _failure()
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=content._pairs)
        content._check_depth(value)
        return value
    except (SentinelError, OSError, UnicodeError, ValueError, TypeError, AttributeError, RecursionError):
        raise _failure() from None


def _artifact(inputs):
    entries = {entry.path: entry for entry in inputs.artifact._entries}
    reference = inputs.support_schema == "sentinel-go-support-v2"
    support_files = SUPPORT_FILES | ({REFERENCE_RUNNER} if reference else set())
    if set(entries) != set(NATIVE_IDENTITIES) | support_files | {"artifact.json", "support.json"}:
        raise _failure()
    record = _record(inputs.artifact, "artifact.json")
    fields = {"schemaVersion", "layoutVersion", "toolVersion", "buildSourceManifestSha256",
              "toolchainLockSha256", "backendLockSha256", "goModSha256", "goSumSha256",
              "runtimeTreeSha256", "files", "manifestSha256"}
    if type(record) is not dict or set(record) != fields:
        raise _failure()
    body = {key:value for key,value in record.items() if key != "manifestSha256"}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode() + b"\n"
    if (record["schemaVersion"] != "sentinel-go-artifact-v1" or record["layoutVersion"] != "sentinel-go-layout-v1"
            or record["toolVersion"] != "0.1.0" or record["runtimeTreeSha256"] != inputs.runtime.tree_sha256
            or record["toolchainLockSha256"] != inputs.runtime.lock_sha256
            or record["manifestSha256"] != hashlib.sha256(canonical).hexdigest()):
        raise _failure()
    for key in fields - {"schemaVersion", "layoutVersion", "toolVersion", "files"}:
        if type(record[key]) is not str or content.DIGEST.fullmatch(record[key]) is None:
            raise _failure()
    expected = [{"path":path, "mode":"0500", "bytes":entries[path].bytes,
                 "sha256":entries[path].sha256, "identity":identity}
                for path,identity in sorted(NATIVE_IDENTITIES.items())]
    if record["files"] != expected or any(type(row["bytes"]) is not int for row in record["files"]):
        raise _failure()
    for path in set(NATIVE_IDENTITIES) | {"support/bin/make", "support/bin/sentinel-go-mutesting-probe"} | ({REFERENCE_RUNNER} if reference else set()):
        if not entries[path].executable:
            raise _failure()
    support = _record(inputs.artifact, "support.json")
    support_fields = {"schemaVersion", "makePackage", "goMutesting", "files"}
    if reference:
        support_fields |= {"referenceRunner", "referenceOnly", "certified"}
    if type(support) is not dict or set(support) != support_fields:
        raise _failure()
    if (support["schemaVersion"] != inputs.support_schema
            or support["makePackage"] != {"version":"4.3-4.1build2", "sha256":"1fe6a815b56c7b6e9ce4086a363f09444bbd0a0d30e230c453d0b78e44b57a99"}
            or support["goMutesting"] != "v0.0.0-20251226130216-48d0401f00fb"):
        raise _failure()
    rows = support["files"]
    if (type(rows) is not list or len(rows) != len(support_files)
            or any(type(row) is not dict or set(row) != {"path","sha256"}
                   or type(row["path"]) is not str or type(row["sha256"]) is not str
                   or content.DIGEST.fullmatch(row["sha256"]) is None for row in rows)):
        raise _failure()
    if {row["path"]:row["sha256"] for row in rows} != {path:entries[path].sha256 for path in support_files}:
        raise _failure()
    if reference:
        expected_runner = {
            "path": REFERENCE_RUNNER, "identity": "sentinel-go-reference-runner/1",
            "executionSchema": "sentinel-go-reference-execution-v1", "profile": "replay-identity-v1",
            "buildSourceManifestSha256": record["buildSourceManifestSha256"],
            # The native body's manifestSha256 excludes its own field. This
            # companion instead binds the entire sealed artifact.json bytes.
            "nativeArtifactJsonSha256": entries["artifact.json"].sha256,
        }
        runner = support["referenceRunner"]
        if (support["referenceOnly"] is not True or support["certified"] is not False
                or rows != sorted(rows, key=lambda row: row["path"])
                or type(runner) is not dict or set(runner) != set(expected_runner)
                or any(type(runner[key]) is not str or runner[key] != value
                       for key, value in expected_runner.items())):
            raise _failure()
    if entries["support/bin/make"].sha256 != _MAKE_SHA256:
        raise _failure()


def _verify(inputs):
    if type(inputs) is not GoPreparedInputs:
        raise _failure()
    _support_schema(inputs.support_schema)
    if type(inputs.runtime) is not GoRuntime:
        raise _failure()
    _verify_lock(inputs.runtime._lock, inputs.runtime.lock_sha256)
    if (type(inputs.uid) is not int or type(inputs.gid) is not int
            or inputs.uid != os.geteuid() or inputs.gid != os.getegid()
            or inputs.uid in (0, 65534) or inputs.gid in (0, 65534)):
        raise _failure()
    all_roots = roots(inputs)
    if [root.kind for root in all_roots] != ["dependencies", "artifact", "dependencies", "corpus"]:
        raise _failure()
    for root in all_roots:
        # The execution controller needs raw interrupts; the public content API
        # deliberately erases their cause when creating its safe install error.
        content._recheck(root)
        if content._inside_git_work_tree(root.root) or any(character in str(root.root) for character in ',"\\'):
            raise _failure()
    if len({root.root for root in all_roots}) != 4:
        raise _failure()
    if (inputs.runtime.tree_sha256 != GO_LOCK["installedTreeSha256"]
            or inputs.runtime.binary_sha256 != GO_LOCK["binarySha256"]
            or content.DIGEST.fullmatch(inputs.runtime.lock_sha256) is None):
        raise _failure()
    _artifact(inputs)
    hashes = tuple(release_tree_sha256(root) for root in all_roots)
    if hashes[0] != GO_LOCK["installedTreeSha256"]:
        raise _failure()
    return hashes


def prepare_go_inputs(runtime, artifact, dependencies, corpus, *, support_schema="sentinel-go-support-v1") -> GoPreparedInputs:
    try:
        _support_schema(support_schema)
        inputs = GoPreparedInputs(runtime, artifact, dependencies, corpus, os.geteuid(), os.getegid(), (), support_schema)
        hashes = _verify(inputs)
        return GoPreparedInputs(runtime, artifact, dependencies, corpus, inputs.uid, inputs.gid, hashes, support_schema)
    except (SentinelError, OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError):
        raise _failure() from None


def recheck_go_inputs(inputs: GoPreparedInputs) -> None:
    try:
        hashes = _verify(inputs)
        if type(inputs.release_hashes) is not tuple or hashes != inputs.release_hashes:
            raise _failure()
    except (SentinelError, OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError):
        raise _failure() from None
