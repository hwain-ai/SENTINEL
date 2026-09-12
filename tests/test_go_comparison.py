"""Installed closed-profile wiring tests; the fixture only records argv."""
import inspect
from pathlib import Path
import subprocess
import tempfile
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from sentinel import go_sandbox
from sentinel.errors import SentinelError


class ComparisonWiringTests(unittest.TestCase):
    def request(self, command='comparison', value=None):
        self.assertIn('mutant_timeout_ms', inspect.signature(go_sandbox.GoRunRequest).parameters,
                      'RED: explicit optional comparison replay budget is missing')
        sources = ('value.go',) if command in ('comparison', 'mutation', 'check') else ()
        return go_sandbox.GoRunRequest(command, sources, mutant_timeout_ms=value)

    def test_omitted_budget_preserves_legacy_request(self):
        request = self.request()
        self.assertEqual(go_sandbox._request_arguments(request), ('0', 'comparison', 'value.go'))

    def test_explicit_budget_is_a_validated_positional_value(self):
        for value in (1, 30000, 840000):
            with self.subTest(value=value):
                request = self.request(value=value)
                self.assertEqual(go_sandbox._request_arguments(request), (str(value), 'comparison', 'value.go'))

    def test_existing_three_positional_fields_keep_their_meaning(self):
        self.request()
        request = go_sandbox.GoRunRequest('original', (), 17.0)
        self.assertEqual(request.timeout_seconds, 17.0)
        self.assertIsNone(request.mutant_timeout_ms)
        self.assertEqual(go_sandbox._request_arguments(request), ('0', 'original'))

    def test_bad_budget_or_wrong_lane_is_rejected(self):
        for value in (True, False, 0, -1, 840001, 3.5, '30000', [], 10 ** 1000):
            request = self.request(value=value)
            with self.subTest(value=value):
                with self.assertRaises(SentinelError):
                    go_sandbox._request_arguments(request)
        for command in ('preflight', 'original', 'help', 'doctor', 'crap', 'history'):
            with self.subTest(command=command):
                with self.assertRaises(SentinelError):
                    go_sandbox._request_arguments(self.request(command, 30000))

    def test_bad_budget_is_rejected_before_input_or_docker_access(self):
        box = go_sandbox.GoSandbox.__new__(go_sandbox.GoSandbox)
        box.cancellation_requested = False
        with mock.patch.object(go_sandbox, 'recheck_go_inputs') as recheck:
            with mock.patch.object(go_sandbox.sandbox.subprocess, 'Popen') as child:
                for request in (self.request(value=True), self.request(value=840001),
                                self.request('original', 30000)):
                    with self.subTest(request=request):
                        with self.assertRaises(SentinelError):
                            box.run(request)
                recheck.assert_not_called()
                child.assert_not_called()

    def test_literal_comparison_function_passes_only_requested_budget(self):
        self.request()
        _before, found, body = go_sandbox._BOOTSTRAP.partition('run_lane() {\n')
        self.assertTrue(found)
        body, found, _after = body.partition('\n}\nstage=lane')
        self.assertTrue(found)
        prefix = ('set -euo pipefail\nmutant_timeout_ms=$1\nartifact=$2\n'
                  'runtime=/fixture/runtime\nproject=/fixture/project\ncommand=comparison\n'
                  'source_flags=(--source value.go)\n')
        script = prefix + 'run_lane() {\n' + body + '\n}\nrun_lane\n'
        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary)
            probe = artifact / 'support/bin/sentinel-go-mutesting-probe'
            probe.parent.mkdir(parents=True)
            probe.write_bytes(b'#!/bin/sh\nprintf "%s\\000" "$@"\n')
            probe.chmod(0o700)
            expected = ['--project', '/fixture/project', '--go-binary', '/fixture/runtime/bin/go',
                        '--timeout-ms', '840000']
            for value in ('0', '30000'):
                result = subprocess.run(['/usr/bin/bash', '--noprofile', '--norc', '-c', script,
                                         'sentinel-comparison-fixture', value, str(artifact)],
                                        env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'},
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=3)
                self.assertEqual(result.returncode, 0, result.stderr)
                argv = result.stdout.rstrip(b'\0').decode().split('\0')
                option = [] if value == '0' else ['--mutant-timeout-ms', value]
                self.assertEqual(argv, expected + option + ['--source', 'value.go'])


if __name__ == '__main__':
    unittest.main()
