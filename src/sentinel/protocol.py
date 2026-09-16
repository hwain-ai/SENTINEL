import json
import os
import selectors
import signal
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .bundle import Bundle
from .errors import SentinelError
from .gate import DEFAULT_GATE, Gate
from .workspace import Module, parse_json_bytes


MAX_OUTPUT_BYTES = 1024 * 1024
_REFERENCE_OUTPUT_BYTES = 16777216 + 65536 + 4096
STATUS_CODES = {
    "passed": 0,
    "noChanges": 0,
    "toolError": 1,
    "qualityFailed": 2,
    "usageConfigError": 3,
    "baselineFailed": 4,
    "dependencyError": 5,
    "backendError": 6,
    "evidenceError": 7,
    "cancelled": 8,
}
RESPONSE_KEYS = {
    "protocolVersion",
    "requestId",
    "command",
    "moduleId",
    "language",
    "toolVersion",
    "status",
    "exitCode",
    "passed",
}


@dataclass(frozen=True)
class Observation:
    status: str
    exit_code: int
    cancellation_requested: bool = False


@dataclass
class _CleanupState:
    interrupted: bool = False
    failed: bool = False


def _retry_cleanup(operation, cleanup: _CleanupState):
    # RISK(race): a KeyboardInterrupt may arrive after a cleanup side effect; only idempotent operations belong here.
    while True:
        try:
            return operation()
        except KeyboardInterrupt:
            cleanup.interrupted = True


def _terminate_group(process: subprocess.Popen, cleanup: Optional[_CleanupState] = None) -> bool:
    # RISK(security): group kill is best-effort; any non-ESRCH cleanup error must become a typed failure.
    state = cleanup if cleanup is not None else _CleanupState()
    local_failed = False
    group_failed = False
    try:
        _retry_cleanup(lambda: os.killpg(process.pid, signal.SIGKILL), state)
    except ProcessLookupError:
        pass
    except OSError:
        state.failed = True
        local_failed = True
        group_failed = True
    if group_failed or _retry_cleanup(process.poll, state) is None:
        try:
            _retry_cleanup(process.kill, state)
        except ProcessLookupError:
            pass
        except OSError:
            state.failed = True
            local_failed = True
    try:
        _retry_cleanup(lambda: process.wait(timeout=1), state)
    except subprocess.TimeoutExpired:
        state.failed = True
        local_failed = True
    except ChildProcessError:
        pass
    except OSError:
        state.failed = True
        local_failed = True
    return not local_failed


def _close_stream(stream) -> bool:
    if not stream or stream.closed:
        return True
    try:
        stream.close()
        return True
    except Exception:
        return False


def _collect(process: subprocess.Popen, request: bytes, timeout: float) -> tuple:
    return _collect_core(process, request, timeout, MAX_OUTPUT_BYTES, False)


def _collect_reference(process: subprocess.Popen, request: bytes, timeout: float) -> tuple:
    return _collect_core(process, request, timeout, _REFERENCE_OUTPUT_BYTES, True)


def _collect_core(process, request, timeout, output_limit, strict_retention):
    streams = {process.stdout: bytearray(), process.stderr: bytearray()}
    deadline = time.monotonic() + timeout
    failure: Optional[str] = None
    written = 0
    selector = None
    interrupted = False
    try:
        selector = selectors.DefaultSelector()
        os.set_blocking(process.stdin.fileno(), False)
        selector.register(process.stdin, selectors.EVENT_WRITE, "stdin")
        for stream in streams:
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, "output")
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                failure = "timeout"
                break
            events = selector.select(min(remaining, 0.1))
            for key, _ in events:
                if key.data == "stdin":
                    try:
                        written += os.write(key.fileobj.fileno(), request[written:])
                    except BlockingIOError:
                        continue
                    except (BrokenPipeError, OSError):
                        failure = "childInputError"
                        break
                    if written == len(request):
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                    continue
                try:
                    chunk = os.read(key.fileobj.fileno(), 64 * 1024)
                except BlockingIOError:
                    continue
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                retained = sum(len(value) for value in streams.values())
                # RISK(resources): the reference lane retains no extra read on
                # overflow; the default lane deliberately preserves its policy.
                streams[key.fileobj].extend(chunk[:max(0, output_limit - retained)] if strict_retention else chunk)
                if retained + len(chunk) > output_limit:
                    failure = "outputOverflow"
                    break
            if failure:
                break
        if failure is None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                failure = "timeout"
            else:
                try:
                    process.wait(timeout=remaining)
                except subprocess.TimeoutExpired:
                    failure = "timeout"
    except KeyboardInterrupt:
        interrupted = True
    except (OSError, ValueError):
        failure = "processIoError"
    finally:
        cleanup = _CleanupState(interrupted=interrupted)
        original_sigint = None
        handler_installed = False

        def defer_sigint(_signum, _frame):
            cleanup.interrupted = True

        try:
            original_sigint = signal.signal(signal.SIGINT, defer_sigint)
            handler_installed = True
        except (OSError, ValueError):
            pass
        try:
            if selector is not None:
                try:
                    _retry_cleanup(selector.close, cleanup)
                except Exception:
                    cleanup.failed = True
            # A successful direct child may still have descendants in its process group.
            _terminate_group(process, cleanup)
            for stream in (process.stdin, process.stdout, process.stderr):
                if not _retry_cleanup(lambda stream=stream: _close_stream(stream), cleanup):
                    cleanup.failed = True
        finally:
            if handler_installed:
                try:
                    signal.signal(signal.SIGINT, original_sigint)
                except (OSError, ValueError):
                    cleanup.failed = True
    if cleanup.failed:
        failure = "cancelledCleanupError" if cleanup.interrupted else "processCleanupError"
    if cleanup.interrupted and not cleanup.failed:
        raise KeyboardInterrupt
    return bytes(streams[process.stdout]), bytes(streams[process.stderr]), failure


def _parse_response(raw: bytes, request: Dict[str, object], bundle: Bundle, process_code: int) -> Observation:
    try:
        response = parse_json_bytes(raw, "tool response")
    except SentinelError:
        return Observation("toolError", 1) if not raw and process_code != 0 else Observation("backendError", 6)
    if not isinstance(response, dict) or set(response) != RESPONSE_KEYS:
        return Observation("backendError", 6)
    string_fields = ("protocolVersion", "requestId", "command", "moduleId", "language", "toolVersion", "status")
    if any(not isinstance(response.get(key), str) for key in string_fields):
        return Observation("backendError", 6)
    if isinstance(response.get("exitCode"), bool) or not isinstance(response.get("exitCode"), int):
        return Observation("backendError", 6)
    if not isinstance(response.get("passed"), bool):
        return Observation("backendError", 6)
    for key in ("protocolVersion", "requestId", "command", "moduleId", "language"):
        if response[key] != request[key]:
            return Observation("backendError", 6)
    if response["toolVersion"] != bundle.version:
        return Observation("backendError", 6)
    status = response["status"]
    if status not in STATUS_CODES or response["exitCode"] != STATUS_CODES[status]:
        return Observation("backendError", 6)
    if response["passed"] is not (status == "passed"):
        return Observation("backendError", 6)
    if status == "noChanges" and "changedFiles" not in request:
        return Observation("backendError", 6)
    if process_code != response["exitCode"]:
        return Observation("backendError", 6)
    if status == "passed":
        return Observation("passed", 0)
    return Observation(status, response["exitCode"])


def _entrypoint_command(executable: Path) -> List[str]:
    """A Python adapter runs under this interpreter (isolated, no bytecode); anything else runs as is.

    The shebang route depends on /usr/bin/python3 existing, which is not given on macOS.
    """

    try:
        with open(executable, "rb") as stream:
            first_line = stream.readline(256)
    except OSError:
        return [str(executable)]
    if first_line.startswith(b"#!") and b"python" in first_line:
        return [sys.executable, "-I", "-B", str(executable)]
    return [str(executable)]


def run_check(
    module: Module,
    project: Path,
    bundle: Bundle,
    timeout: float,
    gate: Gate = DEFAULT_GATE,
    changed_files: Optional[Sequence[str]] = None,
) -> Observation:
    request: Dict[str, object] = {
        "protocolVersion": "sentinel-tool-protocol-v1",
        "requestId": str(uuid.uuid4()),
        "command": "check",
        "moduleId": module.module_id,
        "language": module.language,
        "projectRoot": str(module.root.absolute()),
        "config": str(module.config.absolute()) if module.config else None,
        "gate": gate.as_json(),
    }
    if changed_files is not None:
        request["changedFiles"] = list(changed_files)
    payload = json.dumps(request, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    executable = bundle.source / bundle.entrypoint
    try:
        process = subprocess.Popen(
            _entrypoint_command(executable),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            start_new_session=True,
            env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"},
            cwd=str(module.root),
        )
    except OSError:
        return Observation("backendError", 6)
    stdout, _stderr, failure = _collect(process, payload, timeout)
    if failure == "outputOverflow":
        return Observation("evidenceError", 7)
    if failure == "cancelledCleanupError":
        return Observation("backendError", 6, cancellation_requested=True)
    if failure is not None:
        return Observation("backendError", 6)
    return _parse_response(stdout, request, bundle, process.returncode)
