import hashlib
import json
import math
import posixpath
import signal
import subprocess
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple

from . import oci
from .errors import SentinelError
from .oci_image import ImageIdentity, verify_image
from .protocol import MAX_OUTPUT_BYTES, _collect, _collect_reference


DOCKER_ENV = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}
OWNERSHIP_LABEL = "io.github.hwain-ai.sentinel.ownership"
INSPECT_TIMEOUT = 10.0
CLEANUP_TIMEOUT = 10.0
PULL_TIMEOUT = 120.0
MAX_ARGUMENT_BYTES = 8192
MAX_ARGUMENTS_BYTES = 64 * 1024
MAX_ARGUMENTS = 128


@dataclass(frozen=True)
class _ExecutionProfile:
    user: str = "65534:65534"
    nano_cpus: int = 500000000
    memory: int = 134217728
    pids: int = 32
    nofile: int = 64
    tmpfs: Tuple[Tuple[str, str], ...] = (("/tmp", "rw,noexec,nosuid,nodev,size=33554432,mode=1777"),)
    mounts: Tuple[Tuple[str, str], ...] = ()


_NO_MOUNTS = _ExecutionProfile()


def _host_mounts(profile):
    return [{"Type":"bind", "Source":source, "Target":destination, "ReadOnly":True,
             "BindOptions":{"Propagation":"rprivate", "NonRecursive":True}}
            for source,destination in profile.mounts]


def _inspected_mounts(profile):
    return [{"Type":"bind", "Source":source, "Destination":destination, "Mode":"", "RW":False,
             "Propagation":"rprivate"} for source,destination in profile.mounts]


@dataclass(frozen=True)
class SandboxResult:
    exit_code: Optional[int]
    timed_out: bool
    oom_killed: bool
    stdout_bytes: int
    stderr_bytes: int
    stdout_sha256: str
    stderr_sha256: str
    removed: bool


@dataclass(frozen=True)
class _CommandResult:
    stdout: bytes
    stderr: bytes
    returncode: int
    collection_failure: Optional[str]


class _CommandFailure(Exception):
    def __init__(
        self,
        result: Optional[_CommandResult] = None,
        invoked: bool = False,
        infrastructure: bool = False,
    ):
        super().__init__()
        self.result = result
        self.invoked = invoked
        self.infrastructure = infrastructure


class _Interrupted(Exception):
    pass


class _DeadlineExpired(Exception):
    pass


def _image_failure() -> SentinelError:
    return SentinelError("ociImageFailed", "OCI image verification failed", 5)


def _sandbox_failure() -> SentinelError:
    return SentinelError("sandboxFailed", "Sandbox execution failed", 6)


def _cancelled() -> SentinelError:
    return SentinelError("sandboxCancelled", "Sandbox execution cancelled", 8)


def _pairs(pairs: Sequence[Tuple[str, Any]]) -> Dict[str, Any]:
    value: Dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError
        value[key] = item
    return value


def _json(raw: bytes) -> Any:
    if type(raw) is not bytes or not raw or len(raw) > MAX_OUTPUT_BYTES:
        raise ValueError

    def reject_constant(_value: str) -> None:
        raise ValueError

    value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=reject_constant)

    def check_depth(item: Any, depth: int = 0) -> None:
        if depth > 64:
            raise ValueError
        if isinstance(item, dict):
            for child in item.values():
                check_depth(child, depth + 1)
        elif isinstance(item, list):
            for child in item:
                check_depth(child, depth + 1)

    check_depth(value)
    return value


def _sha256_digest(value: Any) -> bool:
    return (
        isinstance(value, str)
        and value.startswith("sha256:")
        and len(value) == 71
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def _container_id(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _empty(value: Any) -> bool:
    return value is None or value == [] or value == {}


def _exact_json_value(actual: Any, expected: Any) -> bool:
    if type(expected) is dict:
        return (
            type(actual) is dict
            and set(actual) == set(expected)
            and all(_exact_json_value(actual[key], expected[key]) for key in expected)
        )
    if type(expected) is list:
        return (
            type(actual) is list
            and len(actual) == len(expected)
            and all(_exact_json_value(left, right) for left, right in zip(actual, expected))
        )
    return type(actual) is type(expected) and actual == expected


def _exact_environment(value: Any) -> bool:
    expected = {"PATH=/usr/bin:/bin", "LANG=C.UTF-8", "LC_ALL=C.UTF-8"}
    return isinstance(value, list) and len(value) == len(expected) and set(value) == expected


def _validate_argv(argv: Sequence[str], timeout: float) -> Tuple[str, ...]:
    if not isinstance(argv, (list, tuple)) or not argv or len(argv) > MAX_ARGUMENTS:
        raise _sandbox_failure()
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0 or timeout > 60:
        raise _sandbox_failure()
    result = []
    total = 0
    for item in argv:
        if not isinstance(item, str) or "\x00" in item:
            raise _sandbox_failure()
        try:
            encoded = item.encode("utf-8")
        except UnicodeEncodeError:
            raise _sandbox_failure()
        if len(encoded) > MAX_ARGUMENT_BYTES:
            raise _sandbox_failure()
        total += len(encoded)
        if total > MAX_ARGUMENTS_BYTES:
            raise _sandbox_failure()
        result.append(item)
    executable = result[0]
    if (
        not executable.startswith("/")
        or executable.startswith("//")
        or executable == "/"
        or executable.endswith("/")
        or posixpath.normpath(executable) != executable
        or any(part in (".", "..") for part in executable.split("/"))
    ):
        raise _sandbox_failure()
    return tuple(result)


def _repo_digest_matches(reference: str, value: Any) -> bool:
    digest = reference.split("@", 1)[1]
    repositories = ("ubuntu", "library/ubuntu", "docker.io/library/ubuntu", "index.docker.io/library/ubuntu")
    return isinstance(value, str) and value in {repository + "@" + digest for repository in repositories}


def _verify_image_inspect(identity: ImageIdentity, raw: bytes) -> None:
    try:
        value = _json(raw)
        if not isinstance(value, dict):
            raise ValueError
        config = value.get("Config")
        repo_digests = value.get("RepoDigests")
        if (
            value.get("Id") != identity.image_id
            or value.get("Os") != identity.os
            or value.get("Architecture") != identity.architecture
            or not isinstance(repo_digests, list)
            or not any(_repo_digest_matches(identity.reference, item) for item in repo_digests)
            or not isinstance(config, dict)
            or not _empty(config.get("Volumes"))
        ):
            raise ValueError
    except (KeyError, TypeError, ValueError, UnicodeError, json.JSONDecodeError):
        raise _image_failure() from None


def _expected_command(argv: Sequence[str]) -> list:
    return ["-i", "--", "PATH=/usr/bin:/bin", "LANG=C.UTF-8", "LC_ALL=C.UTF-8", *argv]


def _state(value: Any, statuses: set) -> Dict[str, Any]:
    if not isinstance(value, dict) or value.get("Status") not in statuses:
        raise ValueError
    for key in ("Running", "Paused", "Restarting", "OOMKilled", "Dead"):
        if type(value.get(key)) is not bool:
            raise ValueError
    if type(value.get("ExitCode")) is not int:
        raise ValueError
    return value


def _verify_ownership(value: Any, identity: ImageIdentity, container_id: Optional[str], name: str, nonce: str) -> str:
    if not isinstance(value, dict):
        raise ValueError
    actual_id = value.get("Id")
    config = value.get("Config")
    labels = config.get("Labels") if isinstance(config, dict) else None
    if (
        not _container_id(actual_id)
        or (container_id is not None and actual_id != container_id)
        or value.get("Name") != "/" + name
        or value.get("Image") != identity.image_id
        or not isinstance(labels, dict)
        or labels.get(OWNERSHIP_LABEL) != nonce
    ):
        raise ValueError
    return actual_id


def _verify_created_container(identity: ImageIdentity, container_id: str, name: str, nonce: str, argv: Sequence[str], raw: bytes, profile: _ExecutionProfile = _NO_MOUNTS) -> None:
    try:
        value = _json(raw)
        _verify_ownership(value, identity, container_id, name, nonce)
        config = value["Config"]
        host = value["HostConfig"]
        state = _state(value.get("State"), {"created"})
        expected_command = _expected_command(argv)
        if state["Running"] or state["Paused"] or state["Restarting"] or state["Dead"]:
            raise ValueError
        if (
            state["OOMKilled"]
            or state["ExitCode"] != 0
            or type(state.get("Pid")) is not int
            or state["Pid"] != 0
            or type(state.get("Error")) is not str
            or state["Error"] != ""
        ):
            raise ValueError
        if (
            value.get("Path") != "/usr/bin/env"
            or value.get("Args") != expected_command
            or config.get("Image") != identity.image_id
            or config.get("Hostname") != "sentinel-sandbox"
            or config.get("User") != profile.user
            or not _exact_environment(config.get("Env"))
            or config.get("Cmd") != expected_command
            or config.get("Entrypoint") != ["/usr/bin/env"]
            or config.get("WorkingDir") != "/tmp"
            or config.get("Healthcheck") != {"Test": ["NONE"]}
            or "Volumes" not in config
            or config["Volumes"] is not None
            or "ExposedPorts" in config
        ):
            raise ValueError
        expected_host = {
            "NetworkMode": "none", "ReadonlyRootfs": True, "CapDrop": ["ALL"], "CapAdd": None,
            "CgroupnsMode": "private", "IpcMode": "none", "PidMode": "", "UTSMode": "",
            "Privileged": False, "PublishAllPorts": False, "NanoCpus": profile.nano_cpus, "CpuPeriod": 0, "CpuQuota": 0,
            "Memory": profile.memory, "MemorySwap": profile.memory, "PidsLimit": profile.pids,
        }
        if any(key not in host or not _exact_json_value(host[key], expected) for key, expected in expected_host.items()):
            raise ValueError
        absent_host_features = {
            "Binds": None,
            "Devices": [],
            "DeviceRequests": None,
            "PortBindings": {},
            "GroupAdd": None,
            "Links": None,
            "ExtraHosts": None,
            "VolumesFrom": None,
        }
        if any(
            key not in host or not _exact_json_value(host[key], expected)
            for key, expected in absent_host_features.items()
        ):
            raise ValueError
        if profile.mounts:
            if not _exact_json_value(host.get("Mounts"), _host_mounts(profile)):
                raise ValueError
        elif "Mounts" in host:
            raise ValueError
        security_opt = host.get("SecurityOpt")
        if security_opt != ["no-new-privileges=true"]:
            raise ValueError
        if not _exact_json_value(host.get("RestartPolicy"), {"Name": "no", "MaximumRetryCount": 0}):
            raise ValueError
        if not _exact_json_value(host.get("LogConfig"), {"Type": "none", "Config": {}}):
            raise ValueError
        if host.get("OomKillDisable") is not False:
            raise ValueError
        if not _exact_json_value(host.get("Tmpfs"), dict(profile.tmpfs)):
            raise ValueError
        ulimits = host.get("Ulimits")
        if (
            not isinstance(ulimits, list)
            or len(ulimits) != 2
            or any(
                type(item) is not dict
                or set(item) != {"Name", "Soft", "Hard"}
                or type(item["Name"]) is not str
                or type(item["Soft"]) is not int
                or type(item["Hard"]) is not int
                for item in ulimits
            )
            or {(item["Name"], item["Soft"], item["Hard"]) for item in ulimits}
            != {("nofile", profile.nofile, profile.nofile), ("core", 0, 0)}
        ):
            raise ValueError
        actual_mounts = value.get("Mounts")
        if type(actual_mounts) is not list or not _exact_json_value(
            sorted(actual_mounts, key=lambda item:item["Destination"]),
            sorted(_inspected_mounts(profile), key=lambda item:item["Destination"]),
        ):
            raise ValueError
        network = value.get("NetworkSettings")
        if not isinstance(network, dict) or "Ports" not in network or network["Ports"] != {}:
            raise ValueError
    except (KeyError, TypeError, ValueError, UnicodeError, json.JSONDecodeError):
        raise _sandbox_failure() from None


def _terminal_state(raw: bytes, identity: ImageIdentity, container_id: str, name: str, nonce: str, allow_running: bool) -> Dict[str, Any]:
    try:
        value = _json(raw)
        _verify_ownership(value, identity, container_id, name, nonce)
        state = _state(value.get("State"), {"created", "exited", "running"})
        if state["Paused"] or state["Restarting"] or state["Dead"]:
            raise ValueError
        if state["Running"] is not (state["Status"] == "running"):
            raise ValueError
        if not allow_running and state["Status"] != "exited":
            raise ValueError
        if "Pid" not in state or type(state["Pid"]) is not int or "Error" not in state or state["Error"] != "":
            raise ValueError
        if state["Status"] == "running":
            if state["Pid"] <= 0 or state["ExitCode"] != 0 or state["OOMKilled"]:
                raise ValueError
        elif state["Pid"] != 0:
            raise ValueError
        if state["Status"] == "created" and (state["ExitCode"] != 0 or state["OOMKilled"]):
            raise ValueError
        return state
    except (KeyError, TypeError, ValueError, UnicodeError, json.JSONDecodeError):
        raise _sandbox_failure() from None


class Sandbox:
    def __init__(self, lock_path: Path, lock_sha256: str, session_root: Path, session_sha256: str, manifest: bytes, config: bytes):
        if (
            not isinstance(lock_path, Path)
            or not isinstance(session_root, Path)
            or not isinstance(session_sha256, str)
            or not _sha256_digest("sha256:" + session_sha256)
        ):
            raise _sandbox_failure()
        try:
            lock = oci._load_lock(lock_path, lock_sha256)
            identity = verify_image(lock["image"]["reference"], manifest, config)
            if lock["image"] != {"reference": identity.reference, "os": identity.os, "architecture": identity.architecture}:
                raise _image_failure()
        except SentinelError as error:
            if error.code == "sandboxFailed":
                raise
            raise _image_failure() from None
        self._lock_path = lock_path
        self._lock_sha256 = lock_sha256
        self._session_root = session_root
        self._session_sha256 = session_sha256
        self._manifest = manifest
        self._config = config
        self._identity = identity
        self.cancellation_requested = False
        self._executor_trusted = True

    @contextmanager
    def _signal_guard(self):
        if threading.current_thread() is not threading.main_thread():
            raise _sandbox_failure()
        if self.cancellation_requested:
            raise _cancelled()
        original = None
        restoring = False
        primary_error = None

        def interrupt(_signum, _frame):
            self.cancellation_requested = True
            if not restoring:
                raise KeyboardInterrupt

        try:
            original = signal.signal(signal.SIGINT, interrupt)
        except (OSError, ValueError):
            raise _sandbox_failure() from None
        try:
            yield
        except BaseException as error:
            primary_error = error
            raise
        finally:
            # RISK(cancellation): record signals without raising while restoring
            # the caller's handler. A late cancel cannot replace a pending
            # execution/cleanup failure or leave our handler installed.
            restoring = True
            try:
                signal.signal(signal.SIGINT, original)
            except KeyboardInterrupt:
                self.cancellation_requested = True
                try:
                    signal.signal(signal.SIGINT, original)
                except (KeyboardInterrupt, OSError, ValueError):
                    raise _sandbox_failure() from None
            except (OSError, ValueError):
                raise _sandbox_failure() from None
            if self.cancellation_requested and primary_error is None:
                raise _Interrupted()

    def _preflight(self, cleanup: bool) -> None:
        if not cleanup and self.cancellation_requested:
            raise _Interrupted()
        if not self._executor_trusted:
            raise _CommandFailure(infrastructure=True)
        try:
            oci.recheck_session(self._lock_path, self._lock_sha256, self._session_root, self._session_sha256)
        except KeyboardInterrupt:
            self.cancellation_requested = True
            raise _Interrupted() from None
        except Exception:
            self._executor_trusted = False
            raise _CommandFailure(infrastructure=True) from None
        if not cleanup and self.cancellation_requested:
            raise _Interrupted()

    def _record_attached_output(self, container_id: str, result: _CommandResult) -> None:
        pass

    def _command(self, arguments: Sequence[str], timeout: float, allow_nonzero: bool = False, cleanup: bool = False,
                 *, _output_policy=None, _deadline=None) -> _CommandResult:
        # RISK(resources): only an explicitly selected, exact attached start
        # gets the larger fixed collector. Control and cleanup stay at 1 MiB.
        if _output_policy is not None and (type(_output_policy) is not str or _output_policy != "reference"
                or cleanup or len(arguments) != 4 or list(arguments[:3]) != ["container", "start", "--attach"]
                or not _container_id(arguments[3])):
            raise _CommandFailure(infrastructure=True)
        collector = _collect_reference if _output_policy == "reference" else _collect
        # RISK(race): 절대 마감은 호출 안에서만 전달한다. 실행 시간이
        # 끝난 뒤에도 정리는 기존의 고정 제한 시간을 유지해야 한다.
        if not cleanup and _deadline is not None and _deadline <= time.monotonic():
            raise _DeadlineExpired()
        self._preflight(cleanup)
        deadline_limited = False
        if not cleanup and _deadline is not None:
            now = time.monotonic()
            if _deadline <= now:
                raise _DeadlineExpired()
            if _deadline <= now + timeout:
                deadline_limited = True
                timeout = _deadline - now
        argv = [str(oci.DOCKER_PATH), "--config", str(self._session_root / "docker-config"), "--host", oci.DOCKER_HOST, *arguments]
        process = None
        launch_interrupted = False
        launch_restore_failed = False
        launch_infrastructure_failed = False
        original = None

        def defer_interrupt(_signum, _frame):
            nonlocal launch_interrupted
            launch_interrupted = True
            self.cancellation_requested = True

        def restore_handler() -> None:
            nonlocal launch_interrupted, launch_restore_failed
            try:
                signal.signal(signal.SIGINT, original)
            except KeyboardInterrupt:
                self.cancellation_requested = True
                launch_interrupted = True
                launch_restore_failed = True
            except (OSError, ValueError):
                launch_restore_failed = True

        try:
            original = signal.signal(signal.SIGINT, defer_interrupt)
        except KeyboardInterrupt:
            self.cancellation_requested = True
            raise _Interrupted() from None
        except (OSError, ValueError):
            raise _CommandFailure(invoked=False, infrastructure=True) from None
        if not cleanup and (launch_interrupted or self.cancellation_requested):
            restore_handler()
            if launch_restore_failed:
                raise _CommandFailure(invoked=False, infrastructure=True)
            raise _Interrupted()
        try:
            process = subprocess.Popen(
                argv,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                start_new_session=True,
                cwd=str(self._session_root),
                env=DOCKER_ENV,
            )
        except KeyboardInterrupt:
            self.cancellation_requested = True
            launch_interrupted = True
        except OSError:
            launch_infrastructure_failed = True
        except Exception:
            launch_infrastructure_failed = True
        if process is None:
            restore_handler()
            if launch_restore_failed:
                raise _CommandFailure(invoked=False, infrastructure=True)
            if launch_interrupted:
                raise _Interrupted()
            raise _CommandFailure(invoked=False, infrastructure=launch_infrastructure_failed)

        result = None
        interrupted = launch_interrupted
        try:
            # RISK(race): the non-raising handler remains active until the child handle
            # is retained. From restoration through collector entry, this try owns the
            # handle and can synchronously terminate and reap it on interruption.
            restore_handler()
            collection_timeout = 0.0 if launch_interrupted or launch_restore_failed else timeout
            if collection_timeout > 0 and not cleanup and _deadline is not None:
                now = time.monotonic()
                if _deadline <= now:
                    deadline_limited = True
                    collection_timeout = 0.0
                elif _deadline <= now + collection_timeout:
                    deadline_limited = True
                    collection_timeout = _deadline - now
            stdout, stderr, collection_failure = collector(process, b"", collection_timeout)
            result = _CommandResult(stdout, stderr, process.returncode, collection_failure)
        except KeyboardInterrupt:
            self.cancellation_requested = True
            interrupted = True
            streams = (
                getattr(process, "stdin", None),
                getattr(process, "stdout", None),
                getattr(process, "stderr", None),
            )
            if result is None and any(stream is not None and not stream.closed for stream in streams):
                try:
                    stdout, stderr, collection_failure = collector(process, b"", 0.0)
                    result = _CommandResult(stdout, stderr, process.returncode, collection_failure)
                except KeyboardInterrupt:
                    self.cancellation_requested = True
        # 실제 attach 출력만 상태 변환 전에 닫힌 실행 연결로 전달한다.
        if (
            result is not None
            and not cleanup
            and len(arguments) == 4
            and list(arguments[:3]) == ["container", "start", "--attach"]
            and _container_id(arguments[3])
        ):
            self._record_attached_output(arguments[3], result)
        if result is not None and result.collection_failure == "cancelledCleanupError":
            self.cancellation_requested = True
        try:
            self._preflight(cleanup=True)
        except _Interrupted:
            self.cancellation_requested = True
            interrupted = True
        except _CommandFailure:
            raise _CommandFailure(result, invoked=True, infrastructure=True) from None
        if result is not None and result.collection_failure in ("processCleanupError", "cancelledCleanupError"):
            raise _CommandFailure(result, invoked=True)
        if launch_restore_failed:
            raise _CommandFailure(result, invoked=True, infrastructure=True)
        if interrupted:
            raise _Interrupted()
        if deadline_limited and result is not None and result.collection_failure == "timeout":
            raise _DeadlineExpired()
        if result is None or result.collection_failure is not None or (result.returncode != 0 and not allow_nonzero):
            raise _CommandFailure(result, invoked=True)
        if self.cancellation_requested and not cleanup:
            raise _Interrupted()
        return result

    def _image_inspect(self, deadline=None) -> None:
        result = self._command(
            ["image", "inspect", "--format", "{{json .}}", self._identity.reference],
            INSPECT_TIMEOUT,
            _deadline=deadline,
        )
        _verify_image_inspect(self._identity, result.stdout)

    def prepare_image(self) -> ImageIdentity:
        try:
            with self._signal_guard():
                self._command(["image", "pull", "--platform", "linux/amd64", self._identity.reference], PULL_TIMEOUT)
                self._image_inspect()
                return self._identity
        except (_Interrupted, KeyboardInterrupt):
            self.cancellation_requested = True
            raise _cancelled() from None
        except SentinelError as error:
            if error.code in ("sandboxCancelled", "sandboxFailed"):
                raise
            raise _image_failure() from None
        except _CommandFailure as error:
            collection_failure = error.result.collection_failure if error.result is not None else None
            if (
                not error.invoked
                or error.infrastructure
                or not self._executor_trusted
                or collection_failure in (
                    "childInputError",
                    "processIoError",
                    "processCleanupError",
                    "cancelledCleanupError",
                )
            ):
                raise _sandbox_failure() from None
            raise _image_failure() from None
        except Exception:
            raise _sandbox_failure() from None

    def _execution_profile(self) -> _ExecutionProfile:
        return _NO_MOUNTS

    def _create_arguments(self, name: str, nonce: str, argv: Sequence[str]) -> list:
        profile = self._execution_profile()
        mounts = []
        for source, destination in profile.mounts:
            mounts.extend(["--mount", "type=bind,src=" + source + ",dst=" + destination + ",readonly,bind-propagation=rprivate,bind-recursive=disabled"])
        temporary = []
        for destination, options in profile.tmpfs:
            temporary.extend(["--tmpfs", destination + ":" + options])
        return [
            "container", "create", "--name", name, "--label", OWNERSHIP_LABEL + "=" + nonce,
            "--pull", "never", "--network", "none", "--read-only", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges=true", "--cgroupns", "private", "--ipc", "none",
            "--user", profile.user, "--hostname", "sentinel-sandbox", "--restart", "no",
            "--no-healthcheck", "--log-driver", "none", "--workdir", "/tmp", "--cpus", str(profile.nano_cpus / 1000000000),
            "--memory", str(profile.memory), "--memory-swap", str(profile.memory), "--pids-limit", str(profile.pids),
            "--ulimit", "nofile=" + str(profile.nofile) + ":" + str(profile.nofile), "--ulimit", "core=0:0",
            *temporary, *mounts,
            "--entrypoint", "/usr/bin/env", "--env", "PATH=/usr/bin:/bin", "--env", "LANG=C.UTF-8",
            "--env", "LC_ALL=C.UTF-8", self._identity.image_id, *_expected_command(argv),
        ]

    def _inspect_container(self, target: str, cleanup: bool = False, deadline=None) -> bytes:
        return self._command(
            ["container", "inspect", "--format", "{{json .}}", target],
            INSPECT_TIMEOUT,
            cleanup=cleanup,
            _deadline=deadline,
        ).stdout

    def _recover(self, name: str, nonce: str, cleanup: bool = False, deadline=None) -> Optional[str]:
        try:
            raw = self._inspect_container(name, cleanup=cleanup, deadline=deadline)
            value = _json(raw)
            return _verify_ownership(value, self._identity, None, name, nonce)
        except _CommandFailure as error:
            if error.result is not None and error.result.returncode != 0 and error.result.collection_failure is None:
                listing = self._command(
                    [
                        "container", "ls", "--all", "--no-trunc",
                        "--filter", "name=^/" + name + "$",
                        "--filter", "label=" + OWNERSHIP_LABEL + "=" + nonce,
                        "--format", "{{.ID}}",
                    ],
                    CLEANUP_TIMEOUT,
                    cleanup=cleanup,
                    _deadline=deadline,
                )
                lines = listing.stdout.decode("ascii").splitlines()
                if not lines:
                    return None
                if len(lines) != 1 or not _container_id(lines[0]):
                    raise _CommandFailure() from None
                raw = self._inspect_container(lines[0], cleanup=cleanup, deadline=deadline)
                value = _json(raw)
                return _verify_ownership(value, self._identity, lines[0], name, nonce)
            raise
        except (TypeError, ValueError, UnicodeError, json.JSONDecodeError):
            raise _CommandFailure() from None

    def _confirm_owned(self, target: str, name: str, nonce: str, cleanup: bool = False, deadline=None) -> str:
        try:
            raw = self._inspect_container(target, cleanup=cleanup, deadline=deadline)
            value = _json(raw)
            return _verify_ownership(value, self._identity, target, name, nonce)
        except _CommandFailure:
            raise
        except (TypeError, ValueError, UnicodeError, json.JSONDecodeError):
            raise _CommandFailure() from None

    def _cleanup(self, container_id: str) -> bool:
        if not _container_id(container_id):
            return False
        try:
            self._command(["container", "rm", "--force", "--volumes", container_id], CLEANUP_TIMEOUT, cleanup=True)
            result = self._command(
                ["container", "ls", "--all", "--no-trunc", "--filter", "id=" + container_id, "--format", "{{.ID}}"],
                CLEANUP_TIMEOUT,
                cleanup=True,
            )
            return result.stdout == b""
        except KeyboardInterrupt:
            self.cancellation_requested = True
            return False
        except (_CommandFailure, _Interrupted):
            return False

    def run(self, argv: Sequence[str], timeout: float = 10.0) -> SandboxResult:
        if self.cancellation_requested:
            raise _cancelled()
        arguments = _validate_argv(argv, timeout)
        return self._run_validated(arguments, timeout)

    def _observation(self, start_result, state, timed_out):
        return SandboxResult(
            exit_code=None if timed_out else state["ExitCode"], timed_out=timed_out,
            oom_killed=state["OOMKilled"], stdout_bytes=len(start_result.stdout),
            stderr_bytes=len(start_result.stderr), stdout_sha256=hashlib.sha256(start_result.stdout).hexdigest(),
            stderr_sha256=hashlib.sha256(start_result.stderr).hexdigest(), removed=True,
        )

    def _before_start(self):
        pass

    def _run_validated(self, arguments: Sequence[str], timeout: float, *, _start_policy=None, _observe=None,
                       _deadline=None):
        # RISK(execution): only the no-mount public API and the separately
        # validated closed language profile enter this shared lifecycle.
        container_id = None
        name = "sentinel-" + uuid.uuid4().hex
        nonce = uuid.uuid4().hex
        start_result = None
        timed_out = False
        state = None
        create_attempted = False
        try:
            with self._signal_guard():
                self._image_inspect(_deadline)
                try:
                    create_attempted = True
                    created = self._command(
                        self._create_arguments(name, nonce, arguments),
                        INSPECT_TIMEOUT,
                        _deadline=_deadline,
                    )
                    candidate = created.stdout.decode("ascii").strip()
                    if not _container_id(candidate):
                        raise _CommandFailure(created, invoked=True)
                    created_raw = self._inspect_container(candidate, deadline=_deadline)
                    _verify_created_container(self._identity, candidate, name, nonce, arguments, created_raw, self._execution_profile())
                    container_id = candidate
                except _CommandFailure as create_error:
                    if (
                        create_error.result is not None
                        and create_error.result.collection_failure in ("processCleanupError", "cancelledCleanupError")
                    ):
                        raise _sandbox_failure()
                    candidate = ""
                    if create_error.result is not None:
                        try:
                            candidate = create_error.result.stdout.decode("ascii").strip()
                        except UnicodeDecodeError:
                            candidate = ""
                        if _container_id(candidate):
                            try:
                                container_id = self._confirm_owned(
                                    candidate,
                                    name,
                                    nonce,
                                    cleanup=_deadline is not None,
                                    deadline=_deadline,
                                )
                            except _CommandFailure:
                                container_id = None
                    if container_id is None and create_error.invoked:
                        container_id = self._recover(
                            name,
                            nonce,
                            cleanup=_deadline is not None,
                            deadline=_deadline,
                        )
                    raise _sandbox_failure()
                try:
                    self._before_start()
                    start_arguments = ["container", "start", "--attach", container_id]
                    if _start_policy is None:
                        start_result = self._command(
                            start_arguments,
                            timeout,
                            allow_nonzero=True,
                            _deadline=_deadline,
                        )
                    else:
                        start_result = self._command(
                            start_arguments,
                            timeout,
                            allow_nonzero=True,
                            _output_policy=_start_policy,
                            _deadline=_deadline,
                        )
                except _CommandFailure as start_error:
                    start_result = start_error.result
                    timed_out = start_result is not None and start_result.collection_failure == "timeout"
                    if not timed_out:
                        raise
                terminal_raw = self._inspect_container(container_id, deadline=_deadline)
                state = _terminal_state(terminal_raw, self._identity, container_id, name, nonce, allow_running=timed_out)
                if not self._cleanup(container_id):
                    container_id = None
                    raise _sandbox_failure()
                container_id = None
                if start_result is None:
                    raise _sandbox_failure()
                observe = self._observation if _observe is None else _observe
                return observe(start_result, state, timed_out)
        except _DeadlineExpired:
            if container_id is None and create_attempted:
                try:
                    container_id = self._recover(name, nonce, cleanup=True)
                except KeyboardInterrupt:
                    self.cancellation_requested = True
                    raise _sandbox_failure() from None
                except Exception:
                    raise _sandbox_failure() from None
            if container_id is not None:
                cleaned = self._cleanup(container_id)
                container_id = None
                if not cleaned:
                    raise _sandbox_failure() from None
            if self.cancellation_requested:
                raise _cancelled() from None
            observe = self._observation if _observe is None else _observe
            return observe(
                _CommandResult(b"", b"", 0, None),
                {"ExitCode": 0, "OOMKilled": False},
                True,
            )
        except (_Interrupted, KeyboardInterrupt):
            self.cancellation_requested = True
            if container_id is None and create_attempted:
                try:
                    container_id = self._recover(name, nonce, cleanup=True)
                except KeyboardInterrupt:
                    self.cancellation_requested = True
                    raise _sandbox_failure() from None
                except Exception:
                    raise _sandbox_failure() from None
            if container_id is not None and not self._cleanup(container_id):
                container_id = None
                raise _sandbox_failure() from None
            container_id = None
            raise _cancelled() from None
        except SentinelError as error:
            if container_id is None and create_attempted:
                try:
                    container_id = self._recover(name, nonce, cleanup=True)
                except KeyboardInterrupt:
                    self.cancellation_requested = True
                    raise _sandbox_failure() from None
                except Exception:
                    raise _sandbox_failure() from None
            if container_id is not None:
                cleaned = self._cleanup(container_id)
                container_id = None
                if not cleaned:
                    raise _sandbox_failure() from None
            if error.code in ("sandboxFailed", "sandboxCancelled"):
                raise
            raise _sandbox_failure() from None
        except Exception:
            if container_id is None and create_attempted:
                try:
                    container_id = self._recover(name, nonce, cleanup=True)
                except KeyboardInterrupt:
                    self.cancellation_requested = True
                    raise _sandbox_failure() from None
                except Exception:
                    raise _sandbox_failure() from None
            if container_id is not None:
                cleaned = self._cleanup(container_id)
                container_id = None
                if not cleaned:
                    raise _sandbox_failure() from None
            raise _sandbox_failure() from None
