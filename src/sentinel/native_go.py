import hashlib
import json
import math
import os
import secrets
import signal
import stat
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Dict, Optional, Set, Tuple

from . import bundle as bundle_api
from . import content_root as content
from . import oci
from .bundle import Bundle
from .errors import SentinelError
from .go_inputs import GoPreparedInputs, prepare_go_inputs, recheck_go_inputs
from .go_runtime import verify_go_runtime
from .go_sandbox import GoRunObservation, GoRunRequest, GoSandbox
from .oci_image import verify_image
from .protocol import Observation, STATUS_CODES
from .workspace import MAX_CONFIG_BYTES, Module, parse_json_bytes, require_exact_keys


PROFILE_KEYS = (
    "schemaVersion",
    "runtimeManifest",
    "artifactManifest",
    "dependenciesManifest",
    "toolchainLock",
    "executorLock",
    "imageManifest",
    "imageConfig",
)
PROFILE_PATH_KEYS = PROFILE_KEYS[1:]
MAX_CORPUS_BYTES = 128 * 1024 * 1024


@dataclass(frozen=True)
class ModuleCorpus:
    module: Module
    corpus: content.PreparedRoot
    sources: Tuple[str, ...]
    mutant_timeout_ms: Optional[int]
    root_snapshot: content._Snapshot
    file_snapshots: Dict[str, content._Snapshot]
    directories: Set[str]


@dataclass(frozen=True)
class NativeGoPrepared:
    module: Module
    bundle: Bundle
    tools: Path
    profile_paths: Tuple[str, ...]
    profile_files: Tuple[bytes, ...]
    executor_lock_path: Path
    executor_lock_sha256: str
    image_manifest: bytes
    image_config: bytes
    inputs: GoPreparedInputs
    module_corpus: ModuleCorpus


class InstalledGoSandbox(GoSandbox):
    def _support_profile(self):
        return "sentinel-go-support-v2"


@dataclass
class _CancellationState:
    requested: bool = False


def _failure(exit_code=5):
    return SentinelError("nativeGoFailed", "Native Go validation failed", exit_code)


def is_native_go(bundle: Bundle) -> bool:
    return type(bundle) is Bundle and bundle.protocol_version == "sentinel-go-oci-v1"


def _bundle_file(bundle: Bundle, relative: str) -> bytes:
    try:
        if relative not in bundle.files:
            raise _failure()
        raw, _metadata = oci._read_regular(bundle.source / PurePosixPath(relative), bundle_api.MAX_FILE_BYTES)
        if not secrets.compare_digest(hashlib.sha256(raw).hexdigest(), bundle.files[relative]):
            raise _failure()
        return raw
    except SentinelError:
        raise _failure() from None
    except (OSError, ValueError, TypeError):
        raise _failure() from None


def _profile(bundle: Bundle) -> Tuple[Tuple[str, ...], Tuple[bytes, ...]]:
    try:
        if not is_native_go(bundle) or (bundle.language, bundle.version) != ("go", "0.1.0"):
            raise _failure()
        profile_raw = _bundle_file(bundle, bundle.entrypoint)
        value = parse_json_bytes(profile_raw, "native Go profile")
        if not isinstance(value, dict):
            raise _failure()
        require_exact_keys(value, PROFILE_KEYS, (), "native Go profile")
        if value["schemaVersion"] != "sentinel-go-oci-profile-v1":
            raise _failure()
        paths = []
        for key in PROFILE_PATH_KEYS:
            relative = bundle_api._safe_relative(value[key], key)
            if relative == bundle.entrypoint or relative not in bundle.files:
                raise _failure()
            paths.append(relative)
        if len(paths) != len(set(paths)):
            raise _failure()
        return (bundle.entrypoint, *paths), (profile_raw, *(_bundle_file(bundle, path) for path in paths))
    except SentinelError:
        raise _failure() from None
    except (KeyError, TypeError, ValueError, OSError, RecursionError):
        raise _failure() from None


def _installed_content(manifest: bytes, manifest_sha256: str, destination_parent: Path) -> content.PreparedRoot:
    try:
        kind, entries = content._parse_manifest(manifest, manifest_sha256)
        prepared = content._prepared(
            kind,
            destination_parent / f"{kind}-{manifest_sha256}",
            manifest_sha256,
            entries,
            manifest,
        )
        content._recheck(prepared)
        return prepared
    except (SentinelError, OSError, ValueError, TypeError, AttributeError, RecursionError):
        raise _failure() from None


def _read_source_file(root: Path, relative: str, expected: content._Snapshot) -> bytes:
    try:
        raw, metadata = oci._read_regular(root / PurePosixPath(relative), MAX_CORPUS_BYTES)
        if content._snapshot(metadata) != expected:
            raise _failure()
        return raw
    except SentinelError:
        raise _failure() from None
    except (OSError, ValueError, TypeError):
        raise _failure() from None


def _source_inventory(module: Module):
    descriptor = None
    try:
        if type(module) is not Module or module.language != "go" or module.config is None:
            raise _failure()
        root_metadata = content._validate_source(module.root)
        try:
            config_relative = module.config.relative_to(module.root).as_posix()
        except ValueError:
            raise _failure()
        content._safe_relative(config_relative)
        descriptor = content._open_exact_directory(module.root, root_metadata)
        root_snapshot, file_snapshots, directories = content._scan_tree(descriptor, False)
        all_paths = set(file_snapshots) | directories
        if any(part in (".git", ".sentinel") for path in all_paths for part in path.split("/")):
            raise _failure()
        if config_relative not in file_snapshots or not file_snapshots:
            raise _failure()
        total_bytes = sum(item.size for item in file_snapshots.values())
        if total_bytes > MAX_CORPUS_BYTES:
            raise _failure()
        raw_files = {
            relative: _read_source_file(module.root, relative, snapshot)
            for relative, snapshot in sorted(file_snapshots.items())
        }
        if content._scan_tree(descriptor, False) != (root_snapshot, file_snapshots, directories):
            raise _failure()
        content._require_open_path_identity(module.root, descriptor, root_metadata)
        return config_relative, raw_files, root_snapshot, file_snapshots, directories
    except SentinelError:
        raise _failure() from None
    except (OSError, UnicodeError, ValueError, TypeError, AttributeError, RecursionError):
        raise _failure() from None
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _module_config(raw: bytes, available: Set[str]) -> Tuple[Tuple[str, ...], Optional[int]]:
    try:
        if len(raw) > MAX_CONFIG_BYTES:
            raise _failure()
        value = parse_json_bytes(raw, "native Go module config")
        if not isinstance(value, dict):
            raise _failure()
        require_exact_keys(
            value,
            ("schemaVersion", "sources"),
            ("mutantTimeoutMs",),
            "native Go module config",
        )
        if value["schemaVersion"] != "sentinel-go-check-v1":
            raise _failure()
        sources = value["sources"]
        if (
            not isinstance(sources, list)
            or isinstance(sources, bool)
            or not 1 <= len(sources) <= 64
            or len(sources) != len(set(sources))
        ):
            raise _failure()
        normalized = []
        for source in sources:
            relative = content._safe_relative(source)
            if relative not in available or not relative.endswith(".go") or relative.endswith("_test.go"):
                raise _failure()
            normalized.append(relative)
        mutant_timeout = None
        if "mutantTimeoutMs" in value:
            mutant_timeout = value["mutantTimeoutMs"]
            if type(mutant_timeout) is not int or not 1 <= mutant_timeout <= 600000:
                raise _failure()
        return tuple(normalized), mutant_timeout
    except SentinelError:
        raise _failure() from None
    except (KeyError, TypeError, ValueError, UnicodeError, RecursionError):
        raise _failure() from None


def _prepare_module_content_root(
    source: Path,
    manifest: bytes,
    manifest_sha256: str,
    destination_parent: Path,
) -> content.PreparedRoot:
    cancellation = _CancellationState()
    try:
        with _cancellation_guard(cancellation):
            try:
                prepared = content._prepare_content_root(
                    source,
                    manifest,
                    manifest_sha256,
                    destination_parent,
                )
            except KeyboardInterrupt:
                cancellation.requested = True
                raise
    except KeyboardInterrupt:
        raise
    except Exception:
        if cancellation.requested:
            raise KeyboardInterrupt from None
        raise _failure() from None
    if cancellation.requested:
        raise KeyboardInterrupt
    return prepared


def prepare_module_corpus(module: Module, destination_parent: Path) -> ModuleCorpus:
    try:
        config_relative, raw_files, root_snapshot, file_snapshots, directories = _source_inventory(module)
        sources, mutant_timeout = _module_config(raw_files[config_relative], set(raw_files))
        records = [
            {
                "path": relative,
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "executable": bool(stat.S_IMODE(file_snapshots[relative].mode) & 0o111),
            }
            for relative, raw in sorted(raw_files.items())
        ]
        manifest = json.dumps(
            {"schemaVersion": "sentinel-content-root-v1", "kind": "corpus", "files": records},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
        manifest_sha256 = hashlib.sha256(manifest).hexdigest()
        corpus = _prepare_module_content_root(
            module.root,
            manifest,
            manifest_sha256,
            destination_parent,
        )
        prepared = ModuleCorpus(
            module,
            corpus,
            sources,
            mutant_timeout,
            root_snapshot,
            file_snapshots,
            directories,
        )
        recheck_module_source(prepared)
        return prepared
    except (SentinelError, OSError, ValueError, TypeError, AttributeError, RecursionError):
        raise _failure() from None


def recheck_module_source(prepared: ModuleCorpus) -> None:
    descriptor = None
    try:
        if type(prepared) is not ModuleCorpus:
            raise _failure()
        metadata = content._validate_source(prepared.module.root)
        descriptor = content._open_exact_directory(prepared.module.root, metadata)
        if content._scan_tree(descriptor, False) != (
            prepared.root_snapshot,
            prepared.file_snapshots,
            prepared.directories,
        ):
            raise _failure()
        for relative, snapshot in prepared.file_snapshots.items():
            raw = _read_source_file(prepared.module.root, relative, snapshot)
            entry = next(
                (entry for entry in prepared.corpus._entries if entry.path == relative),
                None,
            )
            if (
                entry is None
                or len(raw) != entry.bytes
                or not secrets.compare_digest(hashlib.sha256(raw).hexdigest(), entry.sha256)
            ):
                raise _failure()
        if content._scan_tree(descriptor, False) != (
            prepared.root_snapshot,
            prepared.file_snapshots,
            prepared.directories,
        ):
            raise _failure()
        content._require_open_path_identity(prepared.module.root, descriptor, metadata)
        content._recheck(prepared.corpus)
    except (SentinelError, OSError, ValueError, TypeError, AttributeError, RecursionError):
        raise _failure() from None
    finally:
        if descriptor is not None:
            os.close(descriptor)


def prepare_native_go(module: Module, bundle: Bundle, tools: Path) -> NativeGoPrepared:
    try:
        paths, files = _profile(bundle)
        records = dict(zip(paths, files))
        profile = parse_json_bytes(files[0], "native Go profile")
        content_parent = tools / "native-content"
        runtime_manifest = records[profile["runtimeManifest"]]
        artifact_manifest = records[profile["artifactManifest"]]
        dependencies_manifest = records[profile["dependenciesManifest"]]
        runtime_root = _installed_content(
            runtime_manifest,
            bundle.files[profile["runtimeManifest"]],
            content_parent,
        )
        artifact = _installed_content(
            artifact_manifest,
            bundle.files[profile["artifactManifest"]],
            content_parent,
        )
        dependencies = _installed_content(
            dependencies_manifest,
            bundle.files[profile["dependenciesManifest"]],
            content_parent,
        )
        toolchain_lock = records[profile["toolchainLock"]]
        toolchain_sha256 = bundle.files[profile["toolchainLock"]]
        runtime = verify_go_runtime(runtime_root, toolchain_lock, toolchain_sha256)
        module_corpus = prepare_module_corpus(module, content_parent)
        inputs = prepare_go_inputs(
            runtime,
            artifact,
            dependencies,
            module_corpus.corpus,
            support_schema="sentinel-go-support-v2",
        )
        executor_relative = profile["executorLock"]
        executor_path = bundle.source / PurePosixPath(executor_relative)
        executor_sha256 = bundle.files[executor_relative]
        lock = oci._load_lock(executor_path, executor_sha256)
        image_manifest = records[profile["imageManifest"]]
        image_config = records[profile["imageConfig"]]
        verify_image(lock["image"]["reference"], image_manifest, image_config)
        return NativeGoPrepared(
            module,
            bundle,
            tools,
            paths,
            files,
            executor_path,
            executor_sha256,
            image_manifest,
            image_config,
            inputs,
            module_corpus,
        )
    except KeyboardInterrupt:
        raise
    except (SentinelError, OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError):
        raise _failure() from None


def recheck_native_go(prepared: NativeGoPrepared) -> None:
    try:
        if type(prepared) is not NativeGoPrepared:
            raise _failure(6)
        current = bundle_api.validate_bundle(prepared.bundle.source, prepared.bundle.digest)
        bundle_api._validate_installed_modes(current)
        if current != prepared.bundle:
            raise _failure(6)
        paths, files = _profile(current)
        if paths != prepared.profile_paths or files != prepared.profile_files:
            raise _failure(6)
        recheck_go_inputs(prepared.inputs)
        recheck_module_source(prepared.module_corpus)
    except KeyboardInterrupt:
        raise
    except (SentinelError, OSError, ValueError, TypeError, AttributeError, RecursionError):
        raise _failure(6) from None


def observation_from_go(observation: GoRunObservation) -> Observation:
    reverse_status = {exit_code: status for status, exit_code in STATUS_CODES.items()}
    try:
        result = observation.sandbox
        exit_code = observation.command_exit_code
        if (
            type(observation) is not GoRunObservation
            or result.exit_code != 0
            or result.timed_out
            or result.oom_killed
            or not result.removed
            or not observation.input_integrity_verified
            or type(exit_code) is not int
            or exit_code not in reverse_status
        ):
            return Observation("backendError", 6)
        return Observation(reverse_status[exit_code], exit_code, exit_code == 8)
    except (AttributeError, TypeError):
        return Observation("backendError", 6)


def _private_runs_parent(tools: Path) -> Path:
    try:
        tools = tools.absolute()
        content._validate_destination_parent(tools)
        parent = tools / "native-runs"
        try:
            os.mkdir(parent, 0o700)
        except FileExistsError:
            pass
        content._validate_destination_parent(parent)
        return parent
    except (SentinelError, OSError, ValueError, TypeError):
        raise _failure(6) from None


def _deadline_remaining(deadline: float) -> None:
    if deadline <= time.monotonic():
        raise _failure(6)


@contextmanager
def _cancellation_guard(state: _CancellationState):
    if threading.current_thread() is not threading.main_thread():
        raise _failure(6)
    original = None
    restoring = False

    def interrupt(_signum, _frame):
        state.requested = True
        if not restoring:
            raise KeyboardInterrupt

    try:
        original = signal.signal(signal.SIGINT, interrupt)
        yield
    finally:
        restoring = True
        if original is not None:
            while True:
                try:
                    signal.signal(signal.SIGINT, original)
                    break
                except KeyboardInterrupt:
                    state.requested = True
                except (OSError, ValueError):
                    raise _failure(6) from None


def run_native_go(prepared: NativeGoPrepared, timeout: float) -> Observation:
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 900:
        raise SentinelError("usageError", "native Go timeout must be no more than 900 seconds", 3)
    deadline = time.monotonic() + timeout
    runner = None
    observation = None
    cancellation = _CancellationState()
    integrity_failed = False
    try:
        with _cancellation_guard(cancellation):
            recheck_native_go(prepared)
            _deadline_remaining(deadline)
            runs_parent = _private_runs_parent(prepared.tools)
            session_root = runs_parent / ("run-" + secrets.token_hex(16))
            session_sha256 = oci.prepare_session(
                prepared.executor_lock_path,
                prepared.executor_lock_sha256,
                session_root,
            )
            if cancellation.requested:
                raise KeyboardInterrupt
            _deadline_remaining(deadline)
            runner = InstalledGoSandbox(
                prepared.executor_lock_path,
                prepared.executor_lock_sha256,
                session_root,
                session_sha256,
                prepared.image_manifest,
                prepared.image_config,
                prepared.inputs,
            )
            request = GoRunRequest(
                "check",
                prepared.module_corpus.sources,
                timeout,
                prepared.module_corpus.mutant_timeout_ms,
            )
            observation = observation_from_go(runner.run(request, deadline=deadline))
            if runner.cancellation_requested:
                cancellation.requested = True
    except KeyboardInterrupt:
        cancellation.requested = True
        observation = Observation("cancelled", 8, True)
    except SentinelError as error:
        if error.code == "sandboxCancelled":
            cancellation.requested = True
            observation = Observation("cancelled", 8, True)
        else:
            if runner is not None and runner.cancellation_requested:
                cancellation.requested = True
            observation = Observation("backendError", 6, cancellation.requested)
    finally:
        try:
            recheck_module_source(prepared.module_corpus)
        except KeyboardInterrupt:
            cancellation.requested = True
            integrity_failed = True
        except SentinelError:
            integrity_failed = True
    if integrity_failed:
        return Observation("backendError", 6, cancellation.requested)
    if observation is None:
        return Observation("cancelled", 8, True) if cancellation.requested else Observation("backendError", 6)
    if cancellation.requested:
        if observation.exit_code == 0:
            return Observation("cancelled", 8, True)
        return Observation(observation.status, observation.exit_code, True)
    return observation
