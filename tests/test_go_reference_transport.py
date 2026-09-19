"""Real bounded pipe evidence and private byte frame contracts."""

import hashlib
import os
import signal
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from sentinel import go_sandbox, protocol, sandbox
from tests.test_go_reference_sandbox import reference_module, frame, RUN_ID, HASHES


class ReferenceCollectorTests(unittest.TestCase):
    def collect_bytes(self, collector, count):
        child = subprocess.Popen([sys.executable, '-B', '-c',
                                  'import os; data=b"x"*65536; n=int(__import__("sys").argv[1]); '
                                  '\nwhile n: written=os.write(1,data[:min(n,65536)]); n-=written', str(count)],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 start_new_session=True)
        def cleanup():
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=2)
            for stream in (child.stdin, child.stdout, child.stderr):
                stream.close()
        self.addCleanup(cleanup)
        result = collector(child, b'', 10)
        self.assertIsNotNone(child.poll())
        self.assertTrue(all(s.closed for s in (child.stdin, child.stdout, child.stderr)))
        return result

    def test_bootstrap_golden_with_version_command(self):
        raw = go_sandbox._BOOTSTRAP.encode()
        self.assertEqual(len(raw), 4583)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), '25507ca23ea5d99b5fd224122d7409824976b101773e50b2998eba77389f37a5')

    def test_default_collector_keeps_existing_extra_read_policy(self):
        self.assertEqual(protocol.MAX_OUTPUT_BYTES, 16 * 1024 * 1024)
        for count,expected in ((protocol.MAX_OUTPUT_BYTES,None),(protocol.MAX_OUTPUT_BYTES + 1,'outputOverflow')):
            stdout, stderr, failure = self.collect_bytes(protocol._collect, count)
            self.assertEqual((len(stdout), stderr, failure), (count, b'', expected))

    def test_reference_exact_bound_and_one_byte_overflow(self):
        collector = getattr(protocol, '_collect_reference', None)
        self.assertIsNotNone(collector, 'fixed bounded reference collector is missing')
        for count, failure in ((16846848, None), (16846849, 'outputOverflow')):
            with self.subTest(count=count):
                stdout, stderr, actual = self.collect_bytes(collector, count)
                self.assertEqual((len(stdout), stderr, actual), (16846848, b'', failure))

    def test_reference_policy_is_rejected_on_every_non_attached_command(self):
        import inspect
        self.assertIn('_output_policy', inspect.signature(sandbox.Sandbox._command).parameters)
        box = sandbox.Sandbox.__new__(sandbox.Sandbox)
        commands = [(['image','inspect','x'], False), (['container','create'],False),
                    (['container','start','--attach','c'*64],True),
                    (['container','start','--attach','bad'],False),
                    (['container','start','--attach','c'*64,'extra'],False),
                    (['container','rm','--force','c'*64],True)]
        with mock.patch.object(sandbox.subprocess,'Popen') as popen:
            for args, cleanup in commands:
                with self.subTest(args=args,cleanup=cleanup), self.assertRaises(sandbox._CommandFailure):
                    box._command(args, 1, cleanup=cleanup, _output_policy='reference')
            for policy in (True,16846848,'unknown'):
                with self.subTest(policy=policy), self.assertRaises(sandbox._CommandFailure):
                    box._command(['container','start','--attach','c'*64],1,_output_policy=policy)
            popen.assert_not_called()

    def test_interrupted_recollection_uses_selected_collector_and_reaps_real_child(self):
        box = sandbox.Sandbox.__new__(sandbox.Sandbox)
        box._session_root = Path('/tmp')
        box.cancellation_requested = False
        child = subprocess.Popen([sys.executable,'-B','-c','import sys; sys.stdin.buffer.read()'],
                                 stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                 start_new_session=True)
        def cleanup():
            if child.poll() is None:
                os.killpg(child.pid,signal.SIGKILL)
                child.wait(timeout=2)
            for stream in (child.stdin,child.stdout,child.stderr):
                stream.close()
        self.addCleanup(cleanup)
        timeouts = []
        def selected(process,request,timeout):
            timeouts.append(timeout)
            if len(timeouts) == 1:
                raise KeyboardInterrupt
            return protocol._collect_reference(process,request,timeout)
        with mock.patch.object(box,'_preflight'), mock.patch.object(sandbox.subprocess,'Popen',return_value=child), \
                mock.patch.object(sandbox,'_collect_reference',side_effect=selected), \
                mock.patch.object(sandbox,'_collect',side_effect=AssertionError('wrong collector')):
            with self.assertRaises(sandbox._Interrupted):
                box._command(['container','start','--attach','c'*64],2,_output_policy='reference')
        self.assertEqual(timeouts,[2,0.0])
        self.assertTrue(box.cancellation_requested)
        self.assertIsNotNone(child.poll())
        self.assertTrue(all(s.closed for s in (child.stdin,child.stdout,child.stderr)))

    def test_recollection_cleanup_error_has_precedence_over_interrupt(self):
        box = sandbox.Sandbox.__new__(sandbox.Sandbox)
        box._session_root = Path('/tmp')
        box.cancellation_requested = False
        process = SimpleNamespace(returncode=-9,stdin=SimpleNamespace(closed=False))
        results = [KeyboardInterrupt(),(b'',b'','processCleanupError')]
        with mock.patch.object(box,'_preflight'), mock.patch.object(sandbox.subprocess,'Popen',return_value=process), \
                mock.patch.object(sandbox,'_collect_reference',side_effect=results) as collector:
            with self.assertRaises(sandbox._CommandFailure) as caught:
                box._command(['container','start','--attach','c'*64],2,_output_policy='reference')
        self.assertEqual(caught.exception.result.collection_failure,'processCleanupError')
        self.assertEqual([call.args[2] for call in collector.call_args_list],[2,0.0])

    def test_attached_start_keeps_default_without_explicit_policy(self):
        box = sandbox.Sandbox.__new__(sandbox.Sandbox)
        box._session_root = Path('/tmp')
        box.cancellation_requested = False
        process = SimpleNamespace(returncode=0)
        with mock.patch.object(box,'_preflight'), mock.patch.object(sandbox.subprocess,'Popen',return_value=process), \
                mock.patch.object(sandbox,'_collect',return_value=(b'',b'',None)) as default, \
                mock.patch.object(sandbox,'_collect_reference',side_effect=AssertionError('implicit reference policy')):
            box._command(['container','start','--attach','c'*64],2)
        default.assert_called_once_with(process,b'',2)


class ReferenceFrameTests(unittest.TestCase):
    def setUp(self):
        self.module = reference_module(self)

    def decode(self, raw):
        return self.module._decode_frame(raw, RUN_ID, HASHES[3])

    def test_complete_bytes_and_all_boundaries(self):
        for stdout,stderr in [(b'',b''),(b'\nSENTINEL_PRIVATE_STDERR\n',b''),
                              (b'x'*16777216,b'e'*65536)]:
            value,out,err = self.decode(frame(stdout,stderr))
            self.assertEqual((out,err),(stdout,stderr))
            self.assertEqual(value['stdoutBytes'],len(stdout))
        raw = frame()
        header, body = raw.split(b'\n',1)
        self.decode(header + b' '*(4095-len(header)) + b'\n' + body)
        with self.assertRaises(Exception):
            self.decode(header + b' '*(4096-len(header)) + b'\n' + body)

    def test_malformed_frames_never_pass(self):
        invalid = [frame()[:-1],frame()+b'\n',b'x'*4096+b'\n',
                   frame(b'x'*16777217),frame(stderr=b'e'*65537)]
        for key,value in [('runId','b'*32),('runId','A'*32),('corpusSha256','0'*64),
                          ('stdoutBytes',True),('stdoutBytes',1.0),('stdoutBytes',-1),
                          ('stderrBytes',1),('commandExitCode',256),('commandExitCode',False),
                          ('stdoutSha256','A'*64),('stderrSha256','0'*64),('extra',0)]:
            invalid.append(frame(mutate=lambda record,key=key,value=value: record.update({key:value})))
        invalid.extend([frame().replace(b'"commandExitCode":0', b'"commandExitCode":'+token)
                        for token in (b'-0',b'0.0',b'0e0',b'true',b'null')])
        invalid.append(frame().replace(b'"commandExitCode":0',b'"commandExitCode":0,"commandExitCode":0'))
        invalid.append(frame(mutate=lambda record: record.pop('runId')))
        for index,raw in enumerate(invalid):
            with self.subTest(index=index), self.assertRaises((ValueError,sandbox.SentinelError)):
                self.decode(raw)


if __name__ == '__main__':
    unittest.main()
