"""Exercise the closed Go profile through the real shared lifecycle.

Docker is the replaced external boundary; input-byte validation is covered by
its own tests and real SDK integration runs, not by these lightweight records.
"""

import hashlib
import json
import signal
import sys
import unittest
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

SENTINEL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SENTINEL_ROOT))
sys.path.insert(0, str(SENTINEL_ROOT / 'src'))

from sentinel import go_sandbox, sandbox
from sentinel.errors import SentinelError
from sentinel.oci_image import verify_image
from tests.test_oci_image import image_fixture
from tests.test_sandbox import DockerScript


HASHES = tuple(character * 64 for character in 'abcd')
HOST_ROOTS = tuple('/tmp/approved/root-' + str(index) for index in range(4))
RECORD = {
    'schemaVersion': 'sentinel-go-observation-v1', 'commandExitCode': 0,
    'stdoutBytes': 0, 'stderrBytes': 0,
    'stdoutSha256': hashlib.sha256(b'').hexdigest(),
    'stderrSha256': hashlib.sha256(b'').hexdigest(), 'corpusSha256': HASHES[3],
}


class GoDockerScript(DockerScript):
    def assert_create_contract(self, command):
        required = {
            ('--user', '1000:1000'), ('--memory', '2147483648'),
            ('--memory-swap', '2147483648'), ('--pids-limit', '128'),
            ('--cpus', '2.0'), ('--network', 'none'),
        }
        self.case.assertTrue(required <= set(zip(command, command[1:])))
        mounts = [command[index + 1] for index, word in enumerate(command) if word == '--mount']
        self.case.assertEqual(len(mounts), 4)
        for entry in mounts:
            self.case.assertTrue(entry.endswith(',readonly,bind-propagation=rprivate,bind-recursive=disabled'))

    def container_inspect(self, status):
        value = json.loads(super().container_inspect(status))
        profile = go_sandbox._go_profile(1000, 1000, HOST_ROOTS)
        value['Config']['User'] = profile.user
        value['HostConfig'].update({
            'NanoCpus': profile.nano_cpus, 'Memory': profile.memory,
            'MemorySwap': profile.memory, 'PidsLimit': profile.pids,
            'Tmpfs': dict(profile.tmpfs), 'Mounts': sandbox._host_mounts(profile),
            'Ulimits': [{'Name': 'nofile', 'Hard': 1024, 'Soft': 1024},
                        {'Name': 'core', 'Hard': 0, 'Soft': 0}],
        })
        value['Mounts'] = sandbox._inspected_mounts(profile)
        value['State']['ExitCode'] = 0
        return json.dumps(value).encode()

    def collect(self, process, request, timeout):
        if process.args[5:7] == ['container', 'start'] and self.start_failure is None:
            self.case.assertEqual(timeout, 900.0)
            return json.dumps(RECORD).encode() + b'\nSENTINEL_PRIVATE_STDERR\n', b'', None
        return super().collect(process, request, timeout)


class GoSandboxLifecycleTests(unittest.TestCase):
    def setUp(self):
        reference, manifest, config = image_fixture()
        self.identity = verify_image(reference, manifest, config)
        self.roots = tuple(SimpleNamespace(root=Path(path)) for path in HOST_ROOTS)
        self.inputs = SimpleNamespace(uid=1000, gid=1000, release_hashes=HASHES,
                                      support_schema='sentinel-go-support-v1',
                                      corpus=SimpleNamespace(_entries=()))
        lock = {'image': {'reference': reference, 'os': 'linux', 'architecture': 'amd64'}}
        with mock.patch.object(sandbox.oci, '_load_lock', return_value=lock):
            with mock.patch.object(go_sandbox, 'recheck_go_inputs'):
                self.box = go_sandbox.GoSandbox(Path('/tmp/mock-lock'), 'a' * 64,
                                               Path('/tmp/mock-session'), 'b' * 64,
                                               manifest, config, self.inputs)
        self.argv = ('/usr/bin/bash', '--noprofile', '--norc', '-c', go_sandbox._BOOTSTRAP,
                     'sentinel-go-closed', *HASHES, '1000', '1000', '0', 'original')

    def run_mocked(self, script, recheck, request=None):
        with mock.patch.object(go_sandbox, 'roots', return_value=self.roots):
            with mock.patch.object(go_sandbox, 'recheck_go_inputs', side_effect=recheck):
                with mock.patch.object(sandbox.oci, 'recheck_session'):
                    with mock.patch.object(sandbox.subprocess, 'Popen', side_effect=script.popen):
                        with mock.patch.object(sandbox, '_collect', side_effect=script.collect):
                            return self.box.run(request if request is not None else go_sandbox.GoRunRequest('original'))

    def test_comparison_budget_reaches_checked_container_argv(self):
        self.inputs.corpus = SimpleNamespace(_entries=(SimpleNamespace(path='value.go'),))
        argv = (*self.argv[:-2], '30000', 'comparison', 'value.go')
        script = GoDockerScript(self, self.identity, argv)
        request = go_sandbox.GoRunRequest('comparison', ('value.go',), mutant_timeout_ms=30000)
        result = self.run_mocked(script, lambda _value: None, request)
        self.assertTrue(result.input_integrity_verified)
        self.assertTrue(result.sandbox.removed)

    def test_success_visits_three_input_checks_and_exact_cleanup(self):
        script = GoDockerScript(self, self.identity, self.argv)
        checks = []
        result = self.run_mocked(script, lambda value: checks.append(value))
        self.assertEqual(len(checks), 3)
        self.assertTrue(result.input_integrity_verified)
        self.assertTrue(result.sandbox.removed)
        removals = [call[5:] for call in script.calls if call[5:7] == ['container', 'rm']]
        self.assertEqual(removals, [['container', 'rm', '--force', '--volumes', script.container_id]])

    def test_native_mutation_budget_reaches_checked_container_argv(self):
        self.inputs.corpus = SimpleNamespace(_entries=(SimpleNamespace(path='value.go'),))
        for command in ('mutation', 'check'):
            with self.subTest(command=command):
                argv = (*self.argv[:-2], '30000', command, 'value.go')
                script = GoDockerScript(self, self.identity, argv)
                request = go_sandbox.GoRunRequest(command, ('value.go',), mutant_timeout_ms=30000)
                result = self.run_mocked(script, lambda _value: None, request)
                self.assertTrue(result.input_integrity_verified)
                self.assertTrue(result.sandbox.removed)

    def test_changed_inputs_after_create_block_start_and_cleanup(self):
        script = GoDockerScript(self, self.identity, self.argv)
        checks = 0

        def recheck(_value):
            nonlocal checks
            checks += 1
            if checks == 2:
                raise SentinelError('goInputsFailed', 'Go input verification failed', 5)

        with self.assertRaises(SentinelError) as caught:
            self.run_mocked(script, recheck)
        self.assertEqual(caught.exception.code, 'sandboxFailed')
        self.assertEqual(checks, 3)
        self.assertFalse(any(call[5:7] == ['container', 'start'] for call in script.calls))
        self.assertTrue(any(call[5:7] == ['container', 'rm'] for call in script.calls))

    def test_timeout_is_unverified_observation_after_cleanup(self):
        script = GoDockerScript(self, self.identity, self.argv, start_failure='timeout', terminal_status='running')
        result = self.run_mocked(script, lambda _value: None)
        self.assertTrue(result.sandbox.timed_out)
        self.assertTrue(result.sandbox.removed)
        self.assertIsNone(result.command_exit_code)
        self.assertFalse(result.input_integrity_verified)

    def test_overflow_is_failure_with_exact_cleanup_and_final_recheck(self):
        script = GoDockerScript(self, self.identity, self.argv, start_failure='outputTooLarge')
        checks = []
        with self.assertRaises(SentinelError) as caught:
            self.run_mocked(script, lambda value: checks.append(value))
        self.assertEqual(caught.exception.code, 'sandboxFailed')
        self.assertEqual(len(checks), 3)
        removals = [call[5:] for call in script.calls if call[5:7] == ['container', 'rm']]
        self.assertEqual(removals, [['container', 'rm', '--force', '--volumes', script.container_id]])

    def test_cancellation_recorded_before_start_blocks_start_and_cleans(self):
        script = GoDockerScript(self, self.identity, self.argv)
        checks = 0

        def recheck(_value):
            nonlocal checks
            checks += 1
            if checks == 2:
                self.box.cancellation_requested = True

        with self.assertRaises(SentinelError) as caught:
            self.run_mocked(script, recheck)
        self.assertEqual(caught.exception.code, 'sandboxCancelled')
        self.assertEqual(checks, 3)
        self.assertFalse(any(call[5:7] == ['container', 'start'] for call in script.calls))
        self.assertTrue(any(call[5:7] == ['container', 'rm'] for call in script.calls))

    def test_initial_go_recheck_interrupt_is_safe_and_sticky(self):
        script = GoDockerScript(self, self.identity, self.argv)
        try:
            self.run_mocked(script, lambda _value: (_ for _ in ()).throw(KeyboardInterrupt()))
        except BaseException as error:
            self.assertIsInstance(error, SentinelError)
            self.assertEqual((error.code, error.exit_code), ('sandboxCancelled', 8))
        else:
            self.fail('initial interrupt was ignored')
        self.assertTrue(self.box.cancellation_requested)
        self.assertEqual(script.calls, [])
        with self.assertRaises(SentinelError) as caught:
            self.run_mocked(script, lambda _value: None)
        self.assertEqual(caught.exception.code, 'sandboxCancelled')
        self.assertEqual(script.calls, [])

    def test_final_go_recheck_interrupt_is_safe_and_sticky(self):
        script = GoDockerScript(self, self.identity, self.argv)
        checks = 0

        def recheck(_value):
            nonlocal checks
            checks += 1
            if checks == 3:
                raise KeyboardInterrupt

        try:
            self.run_mocked(script, recheck)
        except BaseException as error:
            self.assertIsInstance(error, SentinelError)
            self.assertEqual((error.code, error.exit_code), ('sandboxCancelled', 8))
        else:
            self.fail('final interrupt was ignored')
        self.assertEqual(checks, 3)
        self.assertTrue(self.box.cancellation_requested)
        self.assertTrue(any(call[5:7] == ['container', 'rm'] for call in script.calls))

    def test_final_interrupt_preserves_existing_container_cleanup_failure(self):
        script = GoDockerScript(self, self.identity, self.argv, rm_failure='timeout')
        checks = 0

        def recheck(_value):
            nonlocal checks
            checks += 1
            if checks == 3:
                raise KeyboardInterrupt

        try:
            self.run_mocked(script, recheck)
        except BaseException as error:
            self.assertIsInstance(error, SentinelError)
            self.assertEqual((error.code, error.exit_code), ('sandboxFailed', 6))
        else:
            self.fail('cleanup failure was ignored')
        self.assertEqual(checks, 3)
        self.assertTrue(self.box.cancellation_requested)
        self.assertTrue(any(call[5:7] == ['container', 'rm'] for call in script.calls))

    def test_final_input_failure_preserves_existing_container_cleanup_failure(self):
        script = GoDockerScript(self, self.identity, self.argv, rm_failure='timeout')
        checks = 0

        def recheck(_value):
            nonlocal checks
            checks += 1
            if checks == 3:
                raise SentinelError('goInputsFailed', 'Go input verification failed', 5)

        with self.assertRaises(SentinelError) as caught:
            self.run_mocked(script, recheck)
        self.assertEqual((caught.exception.code, caught.exception.exit_code), ('sandboxFailed', 6))
        self.assertEqual(checks, 3)

    def test_actual_sigint_during_initial_recheck_restores_handler(self):
        script = GoDockerScript(self, self.identity, self.argv)
        previous = signal.getsignal(signal.SIGINT)
        try:
            self.run_mocked(script, lambda _value: signal.raise_signal(signal.SIGINT))
        except BaseException as error:
            self.assertIsInstance(error, SentinelError)
            self.assertEqual((error.code, error.exit_code), ('sandboxCancelled', 8))
        else:
            self.fail('SIGINT was ignored')
        finally:
            self.assertIs(signal.getsignal(signal.SIGINT), previous)
        self.assertTrue(self.box.cancellation_requested)
        self.assertEqual(script.calls, [])

    def test_cancel_flag_does_not_disguise_an_independent_input_failure(self):
        script = GoDockerScript(self, self.identity, self.argv)

        def recheck(_value):
            self.box.cancellation_requested = True
            raise SentinelError('goInputsFailed', 'Go input verification failed', 5)

        with self.assertRaises(SentinelError) as caught:
            self.run_mocked(script, recheck)
        self.assertEqual((caught.exception.code, caught.exception.exit_code), ('goInputsFailed', 5))
        self.assertEqual(script.calls, [])

    def test_sigint_during_outer_handler_restore_preserves_cleanup_failure(self):
        script = GoDockerScript(self, self.identity, self.argv, rm_failure='timeout')
        self.assert_outer_restore_interrupt(script, 'sandboxFailed', 6)

    def test_sigint_during_outer_handler_restore_cancels_success(self):
        script = GoDockerScript(self, self.identity, self.argv)
        self.assert_outer_restore_interrupt(script, 'sandboxCancelled', 8)

    def assert_outer_restore_interrupt(self, script, code, exit_code):
        previous = signal.getsignal(signal.SIGINT)
        original_signal = signal.signal
        injected = False

        def restore_with_interrupt(number, handler):
            nonlocal injected
            if handler is previous and not injected:
                injected = True
                signal.raise_signal(signal.SIGINT)
            return original_signal(number, handler)

        try:
            with mock.patch.object(signal, 'signal', side_effect=restore_with_interrupt):
                with self.assertRaises(SentinelError) as caught:
                    self.run_mocked(script, lambda _value: None)
            self.assertTrue(injected)
            self.assertEqual((caught.exception.code, caught.exception.exit_code), (code, exit_code))
            self.assertTrue(self.box.cancellation_requested)
            self.assertIs(signal.getsignal(signal.SIGINT), previous)
        finally:
            original_signal(signal.SIGINT, previous)

    def test_shell_metacharacters_stay_in_separate_source_arguments(self):
        sources = ('a$(id).go', 'semi;colon.go', '--config.go')
        self.inputs.corpus._entries = tuple(SimpleNamespace(path=path) for path in sources)
        with mock.patch.object(go_sandbox, 'recheck_go_inputs'):
            with mock.patch.object(self.box, '_run_validated', return_value='mock-result') as run:
                result = self.box.run(go_sandbox.GoRunRequest('mutation', sources))
        self.assertEqual(result, 'mock-result')
        argv, timeout = run.call_args.args
        self.assertEqual(argv[4], go_sandbox._BOOTSTRAP)
        self.assertEqual(argv[-4:], ('mutation', *sources))
        self.assertEqual(timeout, 900.0)

    def test_enormous_integer_timeout_has_safe_error(self):
        try:
            go_sandbox._request_arguments(go_sandbox.GoRunRequest('original', timeout_seconds=10 ** 1000))
        except Exception as error:
            self.assertIsInstance(error, SentinelError)
            self.assertEqual((error.code, error.exit_code), ('sandboxFailed', 6))
        else:
            self.fail('enormous timeout was accepted')



if __name__ == '__main__':
    unittest.main(verbosity=2)
