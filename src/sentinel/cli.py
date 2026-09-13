import argparse
import json
import math
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from . import __version__
from .bundle import Bundle, install_bundle, validate_installed_bundle
from .changes import changed_files, module_changes
from .errors import SentinelError
from .gate import override_gate
from .native_go import is_native_go, prepare_native_go, run_native_go
from .protocol import Observation, run_check
from .setup import SETUP_LANGUAGES, run_setup
from .workspace import Module, load_workspace, select_modules


FAILURE_PRIORITY = (7, 1, 5, 6, 8, 4, 3, 2)


class OutputFailure(Exception):
    def __init__(self, stream):
        super().__init__("CLI output failed")
        self.stream = stream


def _write(stream, value: str) -> None:
    try:
        stream.write(value)
    except KeyboardInterrupt:
        _silence_failed_stream(stream)
        raise
    except (OSError, ValueError) as error:
        raise OutputFailure(stream) from error


class CliParser(argparse.ArgumentParser):
    def _print_message(self, message, file=None) -> None:
        if message:
            _write(file or sys.stderr, message)

    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(3, "sentinel: usageError: invalid arguments\n")


# A full mutation run of a real project takes minutes to hours; the timeout is a safety net, not a budget.
DEFAULT_TOOL_TIMEOUT_SECONDS = 3600.0
# The native Go sandbox keeps its own hard limit.
NATIVE_GO_MAX_TIMEOUT_SECONDS = 900.0


def _timeout(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("timeout must be a number") from error
    if not math.isfinite(parsed) or not 0 < parsed <= 86400:
        raise argparse.ArgumentTypeError("timeout must be greater than 0 and no more than 86400")
    return parsed


def _workspace_options(parser: argparse.ArgumentParser, include_timeout: bool = False) -> None:
    parser.add_argument("--project")
    parser.add_argument("--config", default="sentinel.workspace.json")
    parser.add_argument("--tools")
    parser.add_argument("--language", action="append", default=[])
    parser.add_argument("--module", action="append", default=[])
    parser.add_argument("--format", choices=("text", "json"), default="text")
    if include_timeout:
        # Omitted: tool bundles get DEFAULT_TOOL_TIMEOUT_SECONDS, native Go its NATIVE_GO_MAX_TIMEOUT_SECONDS.
        parser.add_argument("--timeout-seconds", type=_timeout, default=None)


def _gate_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--crap-max")
    parser.add_argument("--mutation-min")


def build_parser() -> argparse.ArgumentParser:
    parser = CliParser(prog="sentinel")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command")
    for name in ("plan", "doctor"):
        _workspace_options(commands.add_parser(name))
    check = commands.add_parser("check")
    _workspace_options(check, include_timeout=True)
    check.add_argument("--experimental", action="store_true")
    check.add_argument("--changed", action="store_true")
    check.add_argument("--changed-base", default="HEAD")
    _gate_options(check)
    setup = commands.add_parser("setup")
    setup.add_argument("--project")
    setup.add_argument("--config", default="sentinel.workspace.json")
    setup.add_argument("--tools")
    setup.add_argument("--sources")
    setup.add_argument("--language", action="append", default=[], choices=sorted(SETUP_LANGUAGES), required=True)
    setup.add_argument("--format", choices=("text", "json"), default="text")
    setup.add_argument("--python-requirements")
    setup.add_argument("--java-dependencies", action="store_true")
    _gate_options(setup)
    install = commands.add_parser("install")
    install.add_argument("--bundle", required=True)
    install.add_argument("--sha256", required=True)
    install.add_argument("--tools", required=True)
    return parser


def _result(module: Module, status: str, exit_code: int) -> Dict[str, object]:
    return {"moduleId": module.module_id, "language": module.language, "status": status, "exitCode": exit_code}


def _envelope(command: str, selection: str, results: List[Dict[str, object]], passed: bool, exit_code: int) -> Dict[str, object]:
    return {
        "schemaVersion": "sentinel-workspace-result-v1",
        "command": command,
        "selection": selection,
        "moduleCount": len(results),
        "results": results,
        "pass": passed,
        "certified": False,
        "exitCode": exit_code,
    }


def _emit(payload: Dict[str, object], output_format: str) -> None:
    if output_format == "json":
        _write(sys.stdout, json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n")
        return
    lines = [f"SENTINEL {payload['command']}: exit {payload['exitCode']}, certified=false"]
    for result in payload["results"]:
        lines.append(f"{result['moduleId']} [{result['language']}]: {result['status']} (exit {result['exitCode']})")
    _write(sys.stdout, "\n".join(lines) + "\n")


def _emit_setup(payload: Dict[str, object], output_format: str) -> None:
    if output_format == "json":
        _write(sys.stdout, json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n")
        return
    gate = payload["gate"]
    lines = [f"SENTINEL setup: exit {payload['exitCode']}, crapMax={gate['crapMax']} mutationMin={gate['mutationMin']}"]
    for result in payload["results"]:
        detail = f" {result['toolVersion']} {result['toolDigest']}" if result["status"] == "installed" else ""
        lines.append(f"{result['language']}: {result['status']}{detail}")
    if payload["workspaceConfig"]:
        lines.append(f"workspace config: {payload['workspaceConfig']} written")
    if payload["projectConfig"]:
        lines.append(f"project config: sentinel.config.json {payload['projectConfig']}")
    _write(sys.stdout, "\n".join(lines) + "\n")


def _selected(args: argparse.Namespace) -> tuple:
    project, modules, gate = load_workspace(args.project or os.getcwd(), args.config)
    selection, selected = select_modules(modules, args.language, args.module)
    tools = Path(args.tools).absolute() if args.tools else project / ".sentinel-tools"
    if args.command == "check":
        gate = override_gate(gate, args.crap_max, args.mutation_min)
    return project, selection, selected, tools, gate


def _preflight(modules: Sequence[Module], tools: Path) -> tuple:
    bundles: Dict[str, Bundle] = {}
    results: List[Dict[str, object]] = []
    failed = False
    for module in modules:
        try:
            bundle = validate_installed_bundle(tools, module.language, module.tool_version, module.tool_digest)
            bundles[module.module_id] = bundle
            results.append(_result(module, "ready", 0))
        except SentinelError:
            failed = True
            results.append(_result(module, "dependencyError", 5))
    return bundles, results, failed


def _aggregate_exit(observations: Sequence[Observation]) -> int:
    codes = {item.exit_code for item in observations}
    for code in FAILURE_PRIORITY:
        if code in codes:
            return code
    return 6


def _run_workspace(args: argparse.Namespace) -> int:
    project, selection, modules, tools, gate = _selected(args)
    if args.command == "plan":
        payload = _envelope("plan", selection, [_result(item, "planned", 0) for item in modules], True, 0)
        _emit(payload, args.format)
        return 0
    bundles, preflight_results, failed = _preflight(modules, tools)
    if args.command == "doctor":
        exit_code = 5 if failed else 0
        payload = _envelope("doctor", selection, preflight_results, not failed, exit_code)
        _emit(payload, args.format)
        return exit_code
    if failed:
        payload = _envelope("check", selection, preflight_results, False, 5)
        _emit(payload, args.format)
        return 5
    if not args.experimental:
        results = [_result(item, "backendNotAdmitted", 6) for item in modules]
        payload = _envelope("check", selection, results, False, 6)
        _emit(payload, args.format)
        return 6
    native_modules = [
        module
        for module in modules
        if is_native_go(bundles[module.module_id])
    ]
    changes: Dict[str, List[str]] = {}
    changed_mode = getattr(args, "changed", False)
    if changed_mode:
        if native_modules:
            raise SentinelError("usageError", "changed mode is not supported for native Go modules", 3)
        changed = changed_files(project, getattr(args, "changed_base", "HEAD"))
        changes = {module.module_id: module_changes(module, changed) for module in modules}
    if native_modules and args.timeout_seconds is not None and args.timeout_seconds > NATIVE_GO_MAX_TIMEOUT_SECONDS:
        raise SentinelError(
            "usageError",
            "native Go timeout must be no more than 900 seconds",
            3,
        )
    native_timeout = NATIVE_GO_MAX_TIMEOUT_SECONDS if args.timeout_seconds is None else args.timeout_seconds
    tool_timeout = DEFAULT_TOOL_TIMEOUT_SECONDS if args.timeout_seconds is None else args.timeout_seconds
    native_prepared = {}
    native_failed = False
    for module in native_modules:
        try:
            native_prepared[module.module_id] = prepare_native_go(
                module,
                bundles[module.module_id],
                tools,
            )
        except SentinelError:
            native_failed = True
    if native_failed:
        results = [
            _result(
                module,
                "dependencyError" if module in native_modules and module.module_id not in native_prepared else "ready",
                5 if module in native_modules and module.module_id not in native_prepared else 0,
            )
            for module in modules
        ]
        payload = _envelope("check", selection, results, False, 5)
        _emit(payload, args.format)
        return 5
    observations: List[Observation] = []
    try:
        for module in modules:
            if module.module_id in native_prepared:
                observation = run_native_go(native_prepared[module.module_id], native_timeout)
            elif changed_mode and not changes[module.module_id]:
                # Nothing under this module changed, so no tool is started and nothing is judged.
                observation = Observation("noChanges", 0)
            else:
                observation = run_check(
                    module,
                    project,
                    bundles[module.module_id],
                    tool_timeout,
                    gate,
                    changes.get(module.module_id) if changed_mode else None,
                )
            observations.append(observation)
            if observation.cancellation_requested:
                while len(observations) < len(modules):
                    observations.append(Observation("cancelled", 8))
                break
    except KeyboardInterrupt:
        observations.append(Observation("cancelled", 8))
        while len(observations) < len(modules):
            observations.append(Observation("cancelled", 8))
    results = [_result(module, observation.status, observation.exit_code) for module, observation in zip(modules, observations)]
    exit_code = _aggregate_exit(observations)
    payload = _envelope("check", selection, results, False, exit_code)
    _emit(payload, args.format)
    return exit_code


def _main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    try:
        if args.command == "install":
            bundle = install_bundle(Path(args.bundle), args.sha256, Path(args.tools))
            _write(sys.stdout, f"installed {bundle.language} {bundle.version} {bundle.digest}\n")
            return 0
        if args.command == "setup":
            payload, exit_code = run_setup(args)
            _emit_setup(payload, args.format)
            return exit_code
        return _run_workspace(args)
    except SentinelError as error:
        _write(sys.stderr, f"sentinel: {error.code}: {error.message}\n")
        return error.exit_code
    except OSError:
        _write(sys.stderr, "sentinel: operationFailed: local operation failed\n")
        return 3
    except (UnicodeError, ValueError):
        _write(sys.stderr, "sentinel: usageError: invalid input\n")
        return 3
    except KeyboardInterrupt:
        _write(sys.stderr, "sentinel: cancelled\n")
        return 8


def _silence_failed_stream(stream, descriptor: Optional[int] = None) -> None:
    try:
        if descriptor is None:
            descriptor = stream.fileno()
        null_descriptor = os.open(os.devnull, os.O_WRONLY)
        # RISK(data-loss): os.open may reuse the missing target FD; closing that FD would revive final-flush failure.
        if null_descriptor != descriptor:
            try:
                os.dup2(null_descriptor, descriptor)
            finally:
                os.close(null_descriptor)
        if stream is not None:
            stream.flush()
    except (AttributeError, OSError, RuntimeError, ValueError):
        pass


def _flush(stream) -> None:
    try:
        stream.flush()
    except KeyboardInterrupt:
        _silence_failed_stream(stream)
        raise
    except (OSError, ValueError) as error:
        raise OutputFailure(stream) from error


def _diagnose(value: str) -> None:
    _write(sys.stderr, value)
    _flush(sys.stderr)


def _repair_missing_standard_streams() -> bool:
    missing = []
    for descriptor, stream in ((1, sys.stdout), (2, sys.stderr)):
        try:
            os.fstat(descriptor)
        except OSError:
            missing.append((descriptor, stream))
        else:
            if stream is None:
                missing.append((descriptor, stream))
    if not missing:
        return False
    for descriptor, stream in missing:
        _silence_failed_stream(stream, descriptor)
    if sys.stderr is not None:
        _diagnose("sentinel: operationFailed: local output failed\n")
    return True


def _output_failure(failed_stream) -> int:
    _silence_failed_stream(failed_stream)
    if failed_stream is not sys.stderr:
        try:
            _diagnose("sentinel: operationFailed: local output failed\n")
        except KeyboardInterrupt:
            return 8
        except OutputFailure as error:
            _silence_failed_stream(error.stream)
    return 3


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        if _repair_missing_standard_streams():
            return 3
        try:
            exit_code = _main(argv)
        except SystemExit as error:
            exit_code = error.code if isinstance(error.code, int) else 3
        _flush(sys.stdout)
        _flush(sys.stderr)
        return exit_code
    except OutputFailure as error:
        return _output_failure(error.stream)
    except KeyboardInterrupt:
        try:
            _diagnose("sentinel: cancelled\n")
        except KeyboardInterrupt:
            return 8
        except OutputFailure as error:
            return _output_failure(error.stream)
        return 8
    except (OSError, UnicodeError, ValueError):
        return _output_failure(sys.stderr)
