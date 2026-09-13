"""Closed Go validation lanes over the shared, ownership-checked OCI lifecycle."""

from dataclasses import dataclass
import hashlib
import math
from typing import Optional, Tuple

from . import content_root, sandbox
from .go_inputs import (ARTIFACT_PATH, CORPUS_PATH, DESTINATIONS, PROJECT_PATH,
                        RUNTIME_PATH, STATE_PATH, GoPreparedInputs, _require_support_profile,
                        recheck_go_inputs, roots)


_COMPARISON_TIMEOUT_MS = 840000
_MUTATION_TIMEOUT_MS = 600000


@dataclass(frozen=True)
class GoRunRequest:
    command: str
    sources: Tuple[str, ...] = ()
    timeout_seconds: float = 900.0
    mutant_timeout_ms: Optional[int] = None


@dataclass(frozen=True)
class GoRunObservation:
    sandbox: sandbox.SandboxResult
    command_exit_code: Optional[int]
    input_integrity_verified: bool
    tool_stdout_bytes: int
    tool_stderr_bytes: int
    tool_stdout_sha256: str
    tool_stderr_sha256: str
    release_hashes: Tuple[str, ...]


def _request_arguments(request):
    if type(request) is not GoRunRequest or type(request.command) is not str or request.command not in {
        "preflight", "original", "help", "doctor", "crap", "mutation", "check", "history", "comparison"
    }:
        raise sandbox._sandbox_failure()
    timeout = request.timeout_seconds
    if type(timeout) not in (int, float) or not 0 < timeout <= 900 or not math.isfinite(timeout):
        raise sandbox._sandbox_failure()
    mutant_timeout = request.mutant_timeout_ms
    # RISK(breaking): omission preserves old artifact argv. Explicit budgets
    # cannot exceed the selected native lane's unchanged overall limit.
    mutant_maximum = {"comparison": _COMPARISON_TIMEOUT_MS,
                      "mutation": _MUTATION_TIMEOUT_MS, "check": _MUTATION_TIMEOUT_MS}.get(request.command, 0)
    if mutant_timeout is not None and (type(mutant_timeout) is not int
            or not 1 <= mutant_timeout <= mutant_maximum):
        raise sandbox._sandbox_failure()
    if (type(request.sources) is not tuple or len(request.sources) > 64
            or any(type(path) is not str for path in request.sources)
            or len(set(request.sources)) != len(request.sources)):
        raise sandbox._sandbox_failure()
    if request.sources and request.command not in {"mutation", "check", "comparison"}:
        raise sandbox._sandbox_failure()
    if request.command in {"mutation", "check", "comparison"} and not request.sources:
        raise sandbox._sandbox_failure()
    try:
        for path in request.sources:
            content_root._safe_relative(path)
            if not path.endswith(".go") or path.endswith("_test.go"):
                raise sandbox._sandbox_failure()
    except Exception:
        raise sandbox._sandbox_failure() from None
    return (str(mutant_timeout or 0), request.command, *request.sources)


def _go_profile(uid, gid, host_roots):
    if type(uid) is not int or type(gid) is not int or uid in (0, 65534) or gid in (0, 65534) or len(host_roots) != 4:
        raise sandbox._sandbox_failure()
    for path in host_roots:
        if type(path) is not str or not path.startswith("/") or any(c in path for c in ',"\\\n\r\0'):
            raise sandbox._sandbox_failure()
    owned = ",mode=0700,uid=" + str(uid) + ",gid=" + str(gid)
    # RISK(resources): these are fixed Go limits, never overrides of the
    # no-mount Sandbox API. Swap remains equal to memory, so extra swap is zero.
    return sandbox._ExecutionProfile(
        user=str(uid) + ":" + str(gid), nano_cpus=2000000000, memory=2147483648,
        pids=128, nofile=1024,
        tmpfs=(("/tmp", "rw,noexec,nosuid,nodev,size=134217728" + owned),
               (PROJECT_PATH, "rw,noexec,nosuid,nodev,size=134217728" + owned),
               (STATE_PATH, "rw,exec,nosuid,nodev,size=1073741824" + owned)),
        mounts=tuple(zip(host_roots, DESTINATIONS)),
    )


# The shell program expands only a product-owned numeric constant. All request
# values are positional arguments, never inserted into executable shell text.
_BOOTSTRAP_PREFIX = r'''set -euo pipefail
umask 077
stage=identity
trap 'bootstrap_exit=$?; if test "$bootstrap_exit" != 0; then printf "goBootstrapFailed:%s\n" "$stage" >&2; fi' EXIT
runtime=/opt/sentinel/go/toolchain/go-1.27.1
artifact=/opt/sentinel/go/artifact
state=/opt/sentinel/go/toolchain/state
dependencies=$state/module-cache
corpus=/input/project
project=/work/project
runtime_sha=$1
artifact_sha=$2
dependency_sha=$3
corpus_sha=$4
expected_uid=$5
expected_gid=$6
'''
_BOOTSTRAP_ARGUMENTS = r'''mutant_timeout_ms=$7
command=$8
shift 8
'''
_BOOTSTRAP_SETUP = r'''test "$(id -u)" = "$expected_uid"
test "$(id -g)" = "$expected_gid"
test ! -e /run/docker.sock
test ! -e /var/run/docker.sock
test -z "$(ls -A /home 2>/dev/null)"
test "$(ls /sys/class/net)" = lo
grep -Eq '^CapEff:[[:space:]]+0+$' /proc/self/status
grep -Eq '^NoNewPrivs:[[:space:]]+1$' /proc/self/status
tree_sha() {
  /usr/bin/tar --create --format=gnu --sort=name --mtime='UTC 1970-01-01' \
    --owner=0 --group=0 --numeric-owner --mode='u+rwX,go+rX' \
    --exclude='./.sentinel' --file=- --directory="$1" . | /usr/bin/sha256sum | /usr/bin/cut -d' ' -f1
}
verify_roots() {
  test "$(tree_sha "$runtime")" = "$runtime_sha"
  test "$(tree_sha "$artifact")" = "$artifact_sha"
  test "$(tree_sha "$dependencies")" = "$dependency_sha"
  test "$(tree_sha "$corpus")" = "$corpus_sha"
}
stage=roots
verify_roots
for protected in "$runtime" "$artifact" "$dependencies" "$corpus"; do
  test "$(stat -c %u "$protected")" = "$expected_uid"
  test "$(stat -c %a "$protected")" = 500
  if (printf forbidden > "$protected/.sentinel-write-probe") 2>/dev/null; then exit 70; fi
done
stage=state
for directory in home config tmp gopath build-cache; do mkdir -m 700 "$state/$directory"; done
export LC_ALL=C TZ=UTC HOME=$state/home XDG_CONFIG_HOME=$state/config
export PATH=$runtime/bin:$artifact/support/bin:/usr/bin:/bin
export TMPDIR=$state/tmp GOROOT=$runtime GOPATH=$state/gopath GOCACHE=$state/build-cache
export GOMODCACHE=$dependencies GOENV=off GOWORK=off GOFLAGS= GOPRIVATE= GONOPROXY= GONOSUMDB=
export GOPROXY=off GOSUMDB=off GOTOOLCHAIN=local GOVCS='*:off' GOTELEMETRY=off CGO_ENABLED=0
stage=runtime-version
test "$(go version)" = 'go version go1.27.1 linux/amd64'
test "$(go env GOVERSION GOOS GOARCH)" = $'go1.27.1\nlinux\namd64'
stage=native-version
test "$("$artifact/bin/sentinel-go" --version)" = 'sentinel-go/0.1.0'
test "$("$artifact/libexec/sentinel-go-test-runner" --version)" = 'sentinel-go-test-runner/1'
test "$("$artifact/libexec/sentinel-mutate4go-bridge" --version)" = 'sentinel-mutate4go-bridge/1 upstream/9016c7adafc1c7e282b5e27768e732e477713af8'
stage=make-version
test "$(make --version | head -n 1)" = 'GNU Make 4.3'
stage=project-copy
cp -R --no-preserve=ownership "$corpus/." "$project/"
find "$project" -type d -exec chmod 700 {} +
find "$project" -type f -exec chmod u+rw {} +
test "$(tree_sha "$project")" = "$corpus_sha"
cd "$project"
'''
_BOOTSTRAP_SOURCES = r'''source_flags=()
for source in "$@"; do source_flags+=(--source "$source"); done
'''
_BOOTSTRAP_LANE = r'''run_lane() {
  case "$command" in
    preflight) go mod verify && go list -mod=readonly -deps -test ./... ;;
    original) make ;;
    help) "$artifact/bin/sentinel-go" --help ;;
    doctor|crap|history) "$artifact/bin/sentinel-go" "$command" --project "$project" --format json ;;
    mutation|check)
      mutant_flags=()
      if test "$mutant_timeout_ms" -gt 0; then
        mutant_flags=(--mutant-timeout-ms "$mutant_timeout_ms")
      fi
      "$artifact/bin/sentinel-go" "$command" --project "$project" --format json "${mutant_flags[@]}" "${source_flags[@]}"
      ;;
    comparison)
      mutant_flags=()
      if test "$mutant_timeout_ms" -gt 0; then
        mutant_flags=(--mutant-timeout-ms "$mutant_timeout_ms")
      fi
      "$artifact/support/bin/sentinel-go-mutesting-probe" --project "$project" --go-binary "$runtime/bin/go" --timeout-ms __COMPARISON_TIMEOUT_MS__ "${mutant_flags[@]}" "${source_flags[@]}"
      ;;
    *) return 71 ;;
  esac
}
'''.replace('__COMPARISON_TIMEOUT_MS__', str(_COMPARISON_TIMEOUT_MS))
_BOOTSTRAP_AFTER = r'''stage=lane
set +e
run_lane > /tmp/tool.stdout 2> /tmp/tool.stderr
result=$?
set -e
stage=project-after
test "$(tree_sha "$project")" = "$corpus_sha"
stage=roots-after
verify_roots
out_bytes=$(wc -c < /tmp/tool.stdout)
err_bytes=$(wc -c < /tmp/tool.stderr)
out_sha=$(sha256sum /tmp/tool.stdout | cut -d' ' -f1)
err_sha=$(sha256sum /tmp/tool.stderr | cut -d' ' -f1)
'''
_BOOTSTRAP_FRAME = r'''printf '{"schemaVersion":"sentinel-go-observation-v1","commandExitCode":%s,"stdoutBytes":%s,"stderrBytes":%s,"stdoutSha256":"%s","stderrSha256":"%s","corpusSha256":"%s"}\n' "$result" "$out_bytes" "$err_bytes" "$out_sha" "$err_sha" "$corpus_sha"
head -c 65536 /tmp/tool.stdout
printf '\nSENTINEL_PRIVATE_STDERR\n'
head -c 65536 /tmp/tool.stderr
'''
_BOOTSTRAP = (_BOOTSTRAP_PREFIX + _BOOTSTRAP_ARGUMENTS + _BOOTSTRAP_SETUP
              + _BOOTSTRAP_SOURCES + _BOOTSTRAP_LANE + _BOOTSTRAP_AFTER + _BOOTSTRAP_FRAME)


class GoSandbox(sandbox.Sandbox):
    def __init__(self, lock_path, lock_sha256, session_root, session_sha256, manifest, config, inputs: GoPreparedInputs):
        self._check_inputs(inputs)
        super().__init__(lock_path, lock_sha256, session_root, session_sha256, manifest, config)
        self._inputs = inputs
        self._tool_diagnostic = b""

    def _support_profile(self):
        return "sentinel-go-support-v1"

    def _check_inputs(self, inputs):
        _require_support_profile(inputs, self._support_profile())
        recheck_go_inputs(inputs)

    def _execution_profile(self):
        return _go_profile(self._inputs.uid, self._inputs.gid, tuple(str(root.root) for root in roots(self._inputs)))

    def _before_start(self):
        self._check_inputs(self._inputs)

    # RISK(breaking): deadline을 키워드 전용으로 두어 기존 위치 인자 호출의
    # Go 요청 계약을 유지한다.
    def run(self, request: GoRunRequest, *, deadline=None) -> GoRunObservation:
        return self._run_go(
            request,
            _request_arguments,
            _BOOTSTRAP,
            "sentinel-go-closed",
            deadline=deadline,
        )

    def _run_go(self, request, request_arguments, bootstrap, entrypoint, *, deadline=None, _start_policy=None,
                _observe=None):
        if deadline is not None and (
            type(deadline) not in (int, float)
            or (type(deadline) is float and not math.isfinite(deadline))
        ):
            raise sandbox._sandbox_failure()
        if self.cancellation_requested:
            raise sandbox._cancelled()
        try:
            with self._signal_guard():
                operation = request_arguments(request)
                self._check_inputs(self._inputs)
                corpus_files = {entry.path for entry in self._inputs.corpus._entries}
                if any(path not in corpus_files for path in request.sources):
                    raise sandbox._sandbox_failure()
                argv = ("/usr/bin/bash", "--noprofile", "--norc", "-c", bootstrap, entrypoint,
                        *self._inputs.release_hashes, str(self._inputs.uid), str(self._inputs.gid), *operation)
                sandbox._validate_argv(argv, 60.0)
                self._tool_diagnostic = b""
                primary_error = None
                try:
                    options = {}
                    if _start_policy is not None:
                        options["_start_policy"] = _start_policy
                    if _observe is not None:
                        options["_observe"] = _observe
                    if deadline is not None:
                        options["_deadline"] = deadline
                    return self._run_validated(argv, request.timeout_seconds, **options)
                except sandbox.SentinelError as error:
                    primary_error = error
                    raise
                finally:
                    self._recheck_after_run(primary_error)
        except (sandbox._Interrupted, KeyboardInterrupt):
            self.cancellation_requested = True
            raise sandbox._cancelled() from None

    def _recheck_after_run(self, primary_error):
        # RISK(cancellation): a late interrupt or input failure must not hide an
        # existing execution/cleanup failure. The cancellation flag still sticks.
        try:
            self._check_inputs(self._inputs)
        except (sandbox._Interrupted, KeyboardInterrupt):
            self.cancellation_requested = True
            if primary_error is None or primary_error.code == "sandboxCancelled":
                raise sandbox._cancelled() from None
        except sandbox.SentinelError:
            if primary_error is None or primary_error.code == "sandboxCancelled":
                raise

    def _observation(self, start_result, state, timed_out):
        result = super()._observation(start_result, state, timed_out)
        if timed_out or state["OOMKilled"]:
            return GoRunObservation(result, None, False, 0, 0, "", "", self._inputs.release_hashes)
        if state["ExitCode"] != 0 or start_result.stderr:
            self._tool_diagnostic = start_result.stderr[:65536]
            raise sandbox._sandbox_failure()
        record, separator, diagnostic = start_result.stdout.partition(b"\n")
        self._tool_diagnostic = diagnostic
        value = sandbox._json(record)
        if (not separator or type(value) is not dict
                or set(value) != {"schemaVersion","commandExitCode","stdoutBytes","stderrBytes","stdoutSha256","stderrSha256","corpusSha256"}
                or value["schemaVersion"] != "sentinel-go-observation-v1"
                or type(value["commandExitCode"]) is not int or not 0 <= value["commandExitCode"] <= 255
                or value["corpusSha256"] != self._inputs.release_hashes[3]):
            raise sandbox._sandbox_failure()
        for key in ("stdoutBytes", "stderrBytes"):
            if type(value[key]) is not int or not 0 <= value[key] <= 134217728:
                raise sandbox._sandbox_failure()
        for key in ("stdoutSha256", "stderrSha256"):
            if type(value[key]) is not str or content_root.DIGEST.fullmatch(value[key]) is None:
                raise sandbox._sandbox_failure()
        return GoRunObservation(result, value["commandExitCode"], True, value["stdoutBytes"], value["stderrBytes"],
                                value["stdoutSha256"], value["stderrSha256"], self._inputs.release_hashes)
