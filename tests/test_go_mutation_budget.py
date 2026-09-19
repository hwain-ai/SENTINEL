"""Optional native-budget wiring; trusted argv fixtures are not OCI evidence."""
from pathlib import Path
import subprocess
import tempfile
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from sentinel import go_sandbox
from sentinel.errors import SentinelError


class MutationBudgetWiringTests(unittest.TestCase):
    def request(self, command, value=None):
        sources = ('value.go',) if command in ('comparison', 'mutation', 'check') else ()
        return go_sandbox.GoRunRequest(command, sources, mutant_timeout_ms=value)

    def test_explicit_mutation_and_check_budget_is_positional(self):
        for command in ('mutation', 'check'):
            for value in (1, 30000, 600000):
                with self.subTest(command=command, value=value):
                    self.assertEqual(go_sandbox._request_arguments(self.request(command, value)),
                                     (str(value), command, 'value.go'))

    def test_omission_preserves_all_existing_lanes(self):
        for command in ('preflight', 'original', 'help', 'version', 'crap',
                        'mutation', 'check', 'history', 'comparison'):
            request = self.request(command)
            with self.subTest(command=command):
                self.assertEqual(go_sandbox._request_arguments(request), ('0', command, *request.sources))
                self.assertEqual(request.timeout_seconds, 900.0)

    def test_mutation_bounds_do_not_change_comparison_bounds(self):
        for command in ('mutation', 'check'):
            for value in (True, False, 0, -1, 600001, 840000, 1.5, '30000', [], 10 ** 1000):
                with self.subTest(command=command, value=value), self.assertRaises(SentinelError):
                    go_sandbox._request_arguments(self.request(command, value))
        self.assertEqual(go_sandbox._request_arguments(self.request('comparison', 840000)),
                         ('840000', 'comparison', 'value.go'))

    def test_other_lanes_still_reject_explicit_budget(self):
        for command in ('preflight', 'original', 'help', 'version', 'crap', 'history'):
            with self.subTest(command=command), self.assertRaises(SentinelError):
                go_sandbox._request_arguments(self.request(command, 30000))

    def test_bad_native_budget_is_rejected_before_inputs_and_docker(self):
        box = go_sandbox.GoSandbox.__new__(go_sandbox.GoSandbox)
        box.cancellation_requested = False
        with mock.patch.object(go_sandbox, 'recheck_go_inputs') as recheck:
            with mock.patch.object(go_sandbox.sandbox.subprocess, 'Popen') as child:
                for command in ('mutation', 'check'):
                    for value in (True, 0, 600001):
                        with self.subTest(command=command, value=value), self.assertRaises(SentinelError):
                            box.run(self.request(command, value))
                recheck.assert_not_called()
                child.assert_not_called()

    def test_literal_native_lane_passes_exact_selected_argv(self):
        _before, found, body = go_sandbox._BOOTSTRAP.partition('run_lane() {\n')
        self.assertTrue(found)
        body, found, _after = body.partition('\n}\nstage=lane')
        self.assertTrue(found)
        script = ('set -euo pipefail\nmutant_timeout_ms=$1\nartifact=$2\ncommand=$3\n'
                  'project=/fixture/project\nruntime=/fixture/runtime\n'
                  'source_flags=(--source value.go --source later.go)\n'
                  'run_lane() {\n' + body + '\n}\nrun_lane\n')
        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary)
            probe = artifact / 'bin/sentinel-go'
            probe.parent.mkdir(parents=True)
            probe.write_bytes(b'#!/bin/sh\nprintf "%s\\000" "$@"\n')
            probe.chmod(0o700)
            for command in ('mutation', 'check'):
                for value in ('0', '30000'):
                    with self.subTest(command=command, value=value):
                        result = subprocess.run(
                            ['/usr/bin/bash', '--noprofile', '--norc', '-c', script,
                             'sentinel-mutation-fixture', value, str(artifact), command],
                            env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'},
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=3)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        argv = result.stdout.rstrip(b'\0').decode().split('\0')
                        selected = [] if value == '0' else ['--mutant-timeout-ms', value]
                        self.assertEqual(argv, [command, '--project', '/fixture/project', '--format', 'json']
                                         + selected + ['--source', 'value.go', '--source', 'later.go'])


if __name__ == '__main__':
    unittest.main()
