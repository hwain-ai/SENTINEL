"""Closed experimental Go reference transport; no report admission or quality status."""

from dataclasses import dataclass
import hashlib
import json
import math
import re
from typing import Optional, Tuple

from . import content_root, go_sandbox, sandbox


_RUN_ID = re.compile(r"[0-9a-f]{32}\Z")
_UNSIGNED = re.compile(r"(?:0|[1-9][0-9]*)\Z")
_STDOUT_LIMIT = 16777216
_STDERR_LIMIT = 65536
_HEADER_LIMIT = 4096


@dataclass(frozen=True)
class GoReferenceRequest:
    run_id: str
    sources: Tuple[str, ...]
    timeout_seconds: float = 900.0
    mutant_timeout_ms: int = 30000


@dataclass(frozen=True)
class GoReferenceObservation:
    run_id: str
    sandbox: sandbox.SandboxResult
    command_exit_code: Optional[int]
    protected_input_integrity_verified: bool
    output_integrity_verified: bool
    tool_stdout_bytes: int
    tool_stderr_bytes: int
    tool_stdout_sha256: str
    tool_stderr_sha256: str
    release_hashes: Tuple[str, ...]


def _request_arguments(request):
    if (type(request) is not GoReferenceRequest or type(request.run_id) is not str
            or _RUN_ID.fullmatch(request.run_id) is None):
        raise sandbox._sandbox_failure()
    timeout = request.timeout_seconds
    if type(timeout) not in (int, float) or not 0 < timeout <= 900 or not math.isfinite(timeout):
        raise sandbox._sandbox_failure()
    if type(request.mutant_timeout_ms) is not int or not 1 <= request.mutant_timeout_ms <= 600000:
        raise sandbox._sandbox_failure()
    if (type(request.sources) is not tuple or not 1 <= len(request.sources) <= 64
            or any(type(path) is not str for path in request.sources)
            or len(set(request.sources)) != len(request.sources)):
        raise sandbox._sandbox_failure()
    try:
        for path in request.sources:
            content_root._safe_relative(path)
            if not path.endswith(".go") or path.endswith("_test.go"):
                raise sandbox._sandbox_failure()
    except Exception:
        raise sandbox._sandbox_failure() from None
    return (request.run_id, str(request.mutant_timeout_ms), *request.sources)


# This fragment is independently exercised only with trusted, authored files.
# RISK(security): generated coverage is confined to a disposable copy; checks
# after execution certify the protected project and mounts, not this copy.
_REFERENCE_COPY = r'''stage=reference-copy
reference_project=$state/reference-project
mkdir -m 700 "$reference_project"
cp -R --no-preserve=ownership "$project/." "$reference_project/"
test "$(tree_sha "$reference_project")" = "$corpus_sha"
cd "$reference_project"
'''
_BOOTSTRAP = (go_sandbox._BOOTSTRAP_PREFIX + r'''run_id=$7
mutant_timeout_ms=$8
shift 8
''' + go_sandbox._BOOTSTRAP_SETUP + _REFERENCE_COPY + r'''stage=reference-version
test "$("$artifact/support/bin/sentinel-go-reference-runner" --version)" = 'sentinel-go-reference-runner/1'
''' + go_sandbox._BOOTSTRAP_SOURCES + r'''run_lane() {
  "$artifact/libexec/sentinel-mutate4go-bridge" --project-root "$reference_project" \
    --go-binary "$runtime/bin/go" --runner-binary "$artifact/libexec/sentinel-go-test-runner" \
    --reference-runner-binary "$artifact/support/bin/sentinel-go-reference-runner" \
    --reference-run-id "$run_id" --timeout-ms 600000 --mutant-timeout-ms "$mutant_timeout_ms" "${source_flags[@]}"
}
''' + go_sandbox._BOOTSTRAP_AFTER + r'''stage=reference-frame
test "$out_bytes" -le 16777216
test "$err_bytes" -le 65536
printf '{"schemaVersion":"sentinel-go-reference-observation-v1","runId":"%s","commandExitCode":%s,"stdoutBytes":%s,"stderrBytes":%s,"stdoutSha256":"%s","stderrSha256":"%s","corpusSha256":"%s"}\n' "$run_id" "$result" "$out_bytes" "$err_bytes" "$out_sha" "$err_sha" "$corpus_sha" > /tmp/frame.header
test "$(wc -c < /tmp/frame.header)" -le 4096
cat /tmp/frame.header /tmp/tool.stdout /tmp/tool.stderr
''')


def _decode_frame(raw, expected_run_id, expected_corpus_sha):
    if type(raw) is not bytes:
        raise ValueError
    newline = raw.find(b"\n", 0, _HEADER_LIMIT)
    if newline < 0:
        raise ValueError

    def unsigned(token):
        if _UNSIGNED.fullmatch(token) is None:
            raise ValueError
        return int(token)

    def reject(_token):
        raise ValueError

    # RISK(security): these hashes correlate complete streams and input identity.
    # Same-UID producers can forge them; inner E2 reports need separate admission.
    value = json.loads(raw[:newline].decode("utf-8"), object_pairs_hook=sandbox._pairs,
                       parse_int=unsigned, parse_float=reject, parse_constant=reject)
    fields = {"schemaVersion", "runId", "commandExitCode", "stdoutBytes", "stderrBytes",
              "stdoutSha256", "stderrSha256", "corpusSha256"}
    if (type(value) is not dict or set(value) != fields
            or value["schemaVersion"] != "sentinel-go-reference-observation-v1"
            or type(value["runId"]) is not str or _RUN_ID.fullmatch(value["runId"]) is None
            or value["runId"] != expected_run_id or value["corpusSha256"] != expected_corpus_sha):
        raise ValueError
    for key, limit in (("commandExitCode", 255), ("stdoutBytes", _STDOUT_LIMIT), ("stderrBytes", _STDERR_LIMIT)):
        if type(value[key]) is not int or not 0 <= value[key] <= limit:
            raise ValueError
    for key in ("stdoutSha256", "stderrSha256", "corpusSha256"):
        if type(value[key]) is not str or content_root.DIGEST.fullmatch(value[key]) is None:
            raise ValueError
    start = newline + 1
    middle = start + value["stdoutBytes"]
    if len(raw) != middle + value["stderrBytes"]:
        raise ValueError
    stdout, stderr = raw[start:middle], raw[middle:]
    if (hashlib.sha256(stdout).hexdigest() != value["stdoutSha256"]
            or hashlib.sha256(stderr).hexdigest() != value["stderrSha256"]):
        raise ValueError
    return value, stdout, stderr


class GoReferenceSandbox(go_sandbox.GoSandbox):
    def _support_profile(self):
        return "sentinel-go-support-v2"

    def _verified_output(self):
        return getattr(self, "_private_output", (b"", b""))

    def run(self, request: GoReferenceRequest) -> GoReferenceObservation:
        self._private_output = (b"", b"")
        pending_output = (b"", b"")
        # Correlation lives in this invocation, independently of retained output.
        # Validation happens again in the shared guard before accessing inputs.
        expected_run_id = request.run_id if type(request) is GoReferenceRequest else None
        release_hashes = self._inputs.release_hashes

        def observe(start_result, state, timed_out):
            nonlocal pending_output
            result = sandbox.Sandbox._observation(self, start_result, state, timed_out)
            if timed_out or state["OOMKilled"]:
                return GoReferenceObservation(expected_run_id, result, None, False, False, 0, 0, "", "", release_hashes)
            if state["ExitCode"] != 0 or start_result.stderr:
                raise sandbox._sandbox_failure()
            value, stdout, stderr = _decode_frame(start_result.stdout, expected_run_id, release_hashes[3])
            pending_output = (stdout, stderr)
            return GoReferenceObservation(expected_run_id, result, value["commandExitCode"], True, True,
                                          value["stdoutBytes"], value["stderrBytes"], value["stdoutSha256"],
                                          value["stderrSha256"], release_hashes)

        try:
            result = self._run_go(request, _request_arguments, _BOOTSTRAP, "sentinel-go-reference-closed",
                                  _start_policy="reference", _observe=observe)
            # Publish only after cleanup, final input checks and signal restoration.
            self._private_output = pending_output
            return result
        except (sandbox._Interrupted, KeyboardInterrupt):
            self._private_output = (b"", b"")
            self.cancellation_requested = True
            raise sandbox._cancelled() from None
        except BaseException:
            self._private_output = (b"", b"")
            raise
