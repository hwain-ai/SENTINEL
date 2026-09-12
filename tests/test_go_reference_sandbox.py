"""Closed request and scripted lifecycle evidence, not actual OCI isolation."""

from dataclasses import asdict, fields, replace
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from sentinel import go_inputs, go_sandbox, sandbox
from sentinel.errors import SentinelError
from sentinel.oci_image import verify_image
from tests.test_go_sandbox_lifecycle import GoDockerScript, HASHES, HOST_ROOTS
from tests.test_oci_image import image_fixture


RUN_ID = '0123456789abcdef' * 2


def reference_module(case):
    case.assertIsNotNone(importlib.util.find_spec('sentinel.go_reference_sandbox'),
                         'closed reference sandbox is missing')
    return importlib.import_module('sentinel.go_reference_sandbox')


def frame(stdout=b'report\n', stderr=b'', run_id=RUN_ID, exit_code=0, mutate=None):
    value = {'schemaVersion': 'sentinel-go-reference-observation-v1', 'runId': run_id,
             'commandExitCode': exit_code, 'stdoutBytes': len(stdout), 'stderrBytes': len(stderr),
             'stdoutSha256': hashlib.sha256(stdout).hexdigest(),
             'stderrSha256': hashlib.sha256(stderr).hexdigest(), 'corpusSha256': HASHES[3]}
    if mutate:
        mutate(value)
    return json.dumps(value, separators=(',', ':')).encode() + b'\n' + stdout + stderr


class ReferenceDockerScript(GoDockerScript):
    payload = None

    def collect_reference(self, process, request, timeout):
        self.case.assertEqual(process.args[5:], ['container', 'start', '--attach', self.container_id])
        if self.start_failure:
            return super().collect(process, request, timeout)
        return self.payload if self.payload is not None else frame(), b'', None


class ReferenceSandboxTests(unittest.TestCase):
    def setUp(self):
        self.module = reference_module(self)
        reference, manifest, config = image_fixture()
        self.identity = verify_image(reference, manifest, config)
        self.inputs = SimpleNamespace(uid=1000, gid=1000, release_hashes=HASHES,
                                      support_schema='sentinel-go-support-v2',
                                      corpus=SimpleNamespace(_entries=(SimpleNamespace(path='value.go'),)))
        self.roots = tuple(SimpleNamespace(root=Path(path)) for path in HOST_ROOTS)
        lock = {'image': {'reference': reference, 'os': 'linux', 'architecture': 'amd64'}}
        with mock.patch.object(sandbox.oci, '_load_lock', return_value=lock), mock.patch.object(go_sandbox, 'recheck_go_inputs'):
            self.box = self.module.GoReferenceSandbox(Path('/tmp/mock-lock'), 'a'*64,
                                                      Path('/tmp/mock-session'), 'b'*64,
                                                      manifest, config, self.inputs)
        self.request = self.module.GoReferenceRequest(RUN_ID, ('value.go',))
        self.argv = ('/usr/bin/bash', '--noprofile', '--norc', '-c', self.module._BOOTSTRAP,
                     'sentinel-go-reference-closed', *HASHES, '1000', '1000', RUN_ID, '30000', 'value.go')

    def run_script(self, script, recheck=lambda _: None, request=None):
        with mock.patch.object(go_sandbox, 'roots', return_value=self.roots), \
                mock.patch.object(go_sandbox, 'recheck_go_inputs', side_effect=recheck), \
                mock.patch.object(sandbox.oci, 'recheck_session'), \
                mock.patch.object(sandbox.subprocess, 'Popen', side_effect=script.popen), \
                mock.patch.object(sandbox, '_collect', side_effect=script.collect), \
                mock.patch.object(sandbox, '_collect_reference', side_effect=script.collect_reference):
            return self.box.run(self.request if request is None else request)

    def test_request_is_closed_and_frozen(self):
        self.assertEqual([f.name for f in fields(self.request)], ['run_id','sources','timeout_seconds','mutant_timeout_ms'])
        with self.assertRaises(AttributeError):
            self.request.run_id = 'a'*32
        for key, values in {
            'run_id': [None, True, 'A'*32, 'a'*31, 'g'*32],
            'sources': [(), [], ('value.go','value.go'), ('../value.go',), ('value_test.go',), ('absent.go',), ('/value.go',), ('x.py',), (None,), tuple('x'+str(i)+'.go' for i in range(65))],
            'timeout_seconds': [None, True, 0, -1, 901, float('nan'), float('inf'), 10**1000],
            'mutant_timeout_ms': [None, True, 0, -1, 600001, 1.0],
        }.items():
            for value in values:
                with self.subTest(key=key,value=value), mock.patch.object(sandbox.subprocess, 'Popen') as popen, \
                        mock.patch.object(go_sandbox, 'recheck_go_inputs'):
                    with self.assertRaises(SentinelError) as caught:
                        self.box.run(replace(self.request, **{key:value}))
                    self.assertEqual((caught.exception.code,caught.exception.exit_code), ('sandboxFailed',6))
                    popen.assert_not_called()
        with self.assertRaises(SentinelError):
            self.box.run(go_sandbox.GoRunRequest('original'))

    def test_consumer_mismatch_rejected_before_docker(self):
        with mock.patch.object(sandbox.subprocess, 'Popen') as popen, mock.patch.object(go_sandbox, 'recheck_go_inputs'):
            self.inputs.support_schema = 'sentinel-go-support-v1'
            with self.assertRaises(SentinelError) as caught:
                self.box.run(self.request)
            self.assertEqual(caught.exception.code, 'goInputsFailed')
            with self.assertRaises(SentinelError):
                self.box._before_start()
            self.inputs.support_schema = 'sentinel-go-support-v2'
            with self.assertRaises(SentinelError):
                go_sandbox.GoSandbox(None,None,None,None,None,None,self.inputs)
            self.inputs.support_schema = 'sentinel-go-support-v1'
            with self.assertRaises(SentinelError):
                self.module.GoReferenceSandbox(None,None,None,None,None,None,self.inputs)
            popen.assert_not_called()

    def test_complete_nonzero_frame_is_private_and_decoded_after_removal(self):
        script = ReferenceDockerScript(self, self.identity, self.argv)
        stdout, stderr = b'private source\nSENTINEL_PRIVATE_STDERR\n' + b'x'*1048576, b'native stderr'
        script.payload = frame(stdout, stderr, exit_code=7)
        decode = self.module._decode_frame
        def after_cleanup(*args):
            self.assertTrue(any(call[5:7] == ['container','rm'] for call in script.calls))
            self.assertEqual(script.calls[-1][5:7], ['container','ls'])
            return decode(*args)
        checks = []
        def recheck(inputs):
            checks.append(inputs)
            self.assertEqual(self.box._verified_output(),(b'',b''))
        with mock.patch.object(self.module, '_decode_frame', side_effect=after_cleanup):
            result = self.run_script(script, recheck)
        self.assertEqual(len(checks), 3)
        self.assertEqual(result.command_exit_code, 7)
        self.assertTrue(result.output_integrity_verified)
        self.assertTrue(result.protected_input_integrity_verified)
        self.assertEqual(self.box._verified_output(), (stdout,stderr))
        public = repr(result) + json.dumps(asdict(result))
        self.assertNotIn('private source', public)
        self.assertFalse({'passed','report_verified','certified','status'} & set(asdict(result)))

    def test_sequential_runs_and_invalid_attempt_clear_private_output(self):
        for run_id in (RUN_ID, 'b'*32):
            request = replace(self.request, run_id=run_id)
            argv = (*self.argv[:-3], run_id, '30000', 'value.go')
            script = ReferenceDockerScript(self, self.identity, argv)
            script.payload = frame(run_id.encode(), run_id=run_id)
            result = self.run_script(script, request=request)
            self.assertEqual(result.run_id,run_id)
            self.assertEqual(self.box._verified_output(), (run_id.encode(),b''))
        with self.assertRaises(SentinelError):
            self.box.run(replace(self.request, run_id='invalid'))
        self.assertEqual(self.box._verified_output(), (b'',b''))

    def test_interrupt_after_output_assignment_clears_unreturned_bytes(self):
        original = self.module.GoReferenceSandbox.__setattr__
        injected = False
        def interrupted_assignment(instance, name, value):
            nonlocal injected
            original(instance,name,value)
            if name == '_private_output' and value != (b'',b'') and not injected:
                injected = True
                raise KeyboardInterrupt
        script = ReferenceDockerScript(self,self.identity,self.argv)
        with mock.patch.object(self.module.GoReferenceSandbox,'__setattr__',interrupted_assignment):
            with self.assertRaises((KeyboardInterrupt,SentinelError)):
                self.run_script(script)
        self.assertTrue(injected)
        self.assertEqual(self.box._verified_output(),(b'',b''))

    def test_copy_fragment_preserves_original_target_and_checks_initial_identity(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        base = Path(temporary.name)
        project, state = base/'project', base/'state'
        (project/'target').mkdir(parents=True)
        state.mkdir()
        (project/'target'/'original').write_bytes(b'keep original target')
        (project/'value.go').write_bytes(b'package fixture\n')
        # Match the shared bootstrap's protected project permissions, including
        # on hosts whose default umask otherwise creates group-writable files.
        project.chmod(0o700)
        (project/'target').chmod(0o700)
        (project/'target'/'original').chmod(0o600)
        (project/'value.go').chmod(0o600)
        tree_function = 'tree_sha() {' + go_sandbox._BOOTSTRAP_SETUP.split('tree_sha() {',1)[1].split('verify_roots()',1)[0]
        script = ('set -euo pipefail\numask 077\nproject=$1\nstate=$2\n' + tree_function
                  + 'corpus_sha=$(tree_sha "$project")\n' + self.module._REFERENCE_COPY
                  + 'mkdir -p "$reference_project/target/sentinel-coverage"\n'
                  + 'printf coverage > "$reference_project/target/sentinel-coverage/output"\n'
                  + 'test "$(tree_sha "$project")" = "$corpus_sha"\n')
        child = subprocess.Popen(['/usr/bin/bash','--noprofile','--norc','-c',script,
                                  'sentinel-trusted-copy-fragment',str(project),str(state)],
                                 stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
        def cleanup():
            if child.poll() is None:
                os.killpg(child.pid,signal.SIGKILL)
                child.wait(timeout=2)
            child.stdout.close()
            child.stderr.close()
        self.addCleanup(cleanup)
        out,err = child.communicate(timeout=10)
        self.assertEqual((child.returncode,out,err),(0,b'',b''),err.decode())
        self.assertTrue(child.stdout.closed and child.stderr.closed)
        self.assertEqual((project/'target'/'original').read_bytes(),b'keep original target')
        self.assertFalse((project/'target'/'sentinel-coverage').exists())
        self.assertEqual((state/'reference-project'/'target'/'original').read_bytes(),b'keep original target')
        self.assertEqual((state/'reference-project'/'target'/'sentinel-coverage'/'output').read_bytes(),b'coverage')

    def test_request_bounds_and_metacharacters_reach_only_positional_arguments(self):
        sources = ('a$(id).go','semi;colon.go','--config.go')
        self.inputs.corpus._entries = tuple(SimpleNamespace(path=path) for path in sources)
        request = replace(self.request,sources=sources,timeout_seconds=0.001,mutant_timeout_ms=600000)
        with mock.patch.object(go_sandbox,'recheck_go_inputs'), mock.patch.object(self.box,'_run_validated',return_value='result') as run:
            self.assertEqual(self.box.run(request),'result')
        argv,timeout = run.call_args.args
        self.assertEqual(timeout,0.001)
        self.assertEqual(argv[-5:],(RUN_ID,'600000',*sources))
        self.assertEqual(argv[4],self.module._BOOTSTRAP)
        self.assertLess(len(argv[4].encode()),8192)
        for timeout_ms in (1,30000,600000):
            self.assertEqual(self.module._request_arguments(replace(self.request,mutant_timeout_ms=timeout_ms))[1],str(timeout_ms))
        sources64 = tuple('file'+str(i)+'.go' for i in range(64))
        self.assertEqual(self.module._request_arguments(replace(self.request,sources=sources64))[2:],sources64)

    def test_docker_stderr_and_stale_frame_fail_after_removal(self):
        for variant in ('stderr','stale'):
            script = ReferenceDockerScript(self,self.identity,self.argv)
            if variant == 'stale':
                script.payload = frame(run_id='b'*32)
            else:
                script.collect_reference = lambda p,r,t: (frame(),b'docker CLI stderr',None)
            with self.subTest(variant=variant), self.assertRaises(SentinelError) as caught:
                self.run_script(script)
            self.assertEqual(caught.exception.code,'sandboxFailed')
            self.assertEqual(self.box._verified_output(),(b'',b''))
            self.assertTrue(any(call[5:7] == ['container','rm'] for call in script.calls))

    def test_prior_success_is_cleared_before_sticky_cancellation(self):
        self.run_script(ReferenceDockerScript(self,self.identity,self.argv))
        self.assertNotEqual(self.box._verified_output(),(b'',b''))
        self.box.cancellation_requested = True
        with self.assertRaises(SentinelError) as caught:
            self.box.run(self.request)
        self.assertEqual(caught.exception.code,'sandboxCancelled')
        self.assertEqual(self.box._verified_output(),(b'',b''))

    def test_terminal_failure_paths_never_publish_bytes(self):
        cases = [({'start_failure':'timeout','terminal_status':'running'}, 'timeout'),
                 ({'mutation':('terminal-state','OOMKilled',True)}, 'oom'),
                 ({'start_failure':'outputOverflow'}, 'failure'),
                 ({'start_failure':'interrupt'}, 'cancel'),
                 ({'rm_failure':'timeout'}, 'failure'), ({}, 'decode')]
        for kwargs, expected in cases:
            with self.subTest(expected=expected):
                self.box.cancellation_requested = False
                self.run_script(ReferenceDockerScript(self,self.identity,self.argv))
                self.assertNotEqual(self.box._verified_output(),(b'',b''))
                script = ReferenceDockerScript(self,self.identity,self.argv,**kwargs)
                if expected == 'decode':
                    script.payload = b'bad frame'
                if expected in ('timeout','oom'):
                    result = self.run_script(script)
                    self.assertIsNone(result.command_exit_code)
                    self.assertFalse(result.output_integrity_verified)
                    self.assertFalse(result.protected_input_integrity_verified)
                    self.assertEqual((result.tool_stdout_bytes,result.tool_stderr_bytes,result.tool_stdout_sha256,result.tool_stderr_sha256),(0,0,'',''))
                else:
                    with self.assertRaises(SentinelError) as caught:
                        self.run_script(script)
                    self.assertEqual(caught.exception.code, 'sandboxCancelled' if expected == 'cancel' else 'sandboxFailed')
                self.assertEqual(self.box._verified_output(), (b'',b''))
                self.assertTrue(any(call[5:7] == ['container','rm'] for call in script.calls))

    def test_final_recheck_failure_and_interrupt_preserve_cleanup_precedence(self):
        for cleanup_failure in (None,'timeout'):
            for late_error in (KeyboardInterrupt(), SentinelError('goInputsFailed','Go input verification failed',5)):
                with self.subTest(cleanup=cleanup_failure,error=type(late_error).__name__):
                    self.box.cancellation_requested = False
                    checks = []
                    def recheck(inputs):
                        checks.append(inputs)
                        if len(checks) == 3:
                            raise late_error
                    script = ReferenceDockerScript(self,self.identity,self.argv,rm_failure=cleanup_failure)
                    with self.assertRaises(SentinelError) as caught:
                        self.run_script(script,recheck)
                    expected = 'sandboxFailed' if cleanup_failure else ('sandboxCancelled' if isinstance(late_error,KeyboardInterrupt) else 'goInputsFailed')
                    self.assertEqual(caught.exception.code,expected)
                    self.assertEqual(self.box._verified_output(),(b'',b''))


if __name__ == '__main__':
    unittest.main()
