import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))

from sentinel.errors import SentinelError  # noqa: E402
from sentinel.gate import DEFAULT_GATE, Gate, load_gate, override_gate, validate_crap_max, validate_mutation_min  # noqa: E402
from sentinel.workspace import load_workspace  # noqa: E402
from test_cli import module, write_json  # noqa: E402


class GateValueTests(unittest.TestCase):
    def test_defaults_are_crap_eight_and_ninety_percent_kill_rate(self):
        self.assertEqual({"crapMax": "8", "mutationMin": "90"}, DEFAULT_GATE.as_json())

    def test_accepts_decimal_text_with_at_most_two_places(self):
        self.assertEqual("8.5", validate_crap_max("8.5"))
        self.assertEqual("0.01", validate_crap_max("0.01"))
        self.assertEqual("0", validate_mutation_min("0"))
        self.assertEqual("99.99", validate_mutation_min("99.99"))

    def test_rejects_malformed_and_out_of_range_thresholds_as_usage_errors(self):
        for value in ("", "8.", ".5", "08", "8.000", "-1", "1e1", " 8", 8, None, True):
            with self.subTest(value=value):
                with self.assertRaises(SentinelError) as raised:
                    validate_crap_max(value)
                self.assertEqual((raised.exception.code, raised.exception.exit_code), ("invalidGate", 3))
        for validator, value in ((validate_crap_max, "0"), (validate_mutation_min, "100.01")):
            with self.subTest(value=value):
                with self.assertRaises(SentinelError) as raised:
                    validator(value)
                self.assertEqual(raised.exception.code, "invalidGate")

    def test_override_keeps_unspecified_values(self):
        gate = override_gate(Gate("7", "90"), None, "80")
        self.assertEqual({"crapMax": "7", "mutationMin": "80"}, gate.as_json())
        self.assertEqual(Gate("7", "90"), override_gate(Gate("7", "90"), None, None))

    def test_explicit_existing_full_kill_rate_is_preserved(self):
        gate = load_gate({"mutationMin": "100"})
        self.assertEqual(Gate("8", "100"), override_gate(gate, None, None))
        self.assertEqual(Gate("8", "100"), override_gate(DEFAULT_GATE, None, "100"))

    def test_load_gate_reads_partial_objects_and_rejects_unknown_fields(self):
        self.assertEqual(DEFAULT_GATE, load_gate(None))
        self.assertEqual(Gate("10", "90"), load_gate({"crapMax": "10"}))
        with self.assertRaises(SentinelError):
            load_gate({"crapMax": "10", "extra": True})
        with self.assertRaises(SentinelError):
            load_gate(["8"])


class WorkspaceGateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.project = Path(self.temporary.name) / "project"
        (self.project / "api").mkdir(parents=True)

    def tearDown(self):
        self.temporary.cleanup()

    def workspace(self, extra):
        document = {"schemaVersion": "sentinel-workspace-v1", "modules": [module("api", "python", "api")]}
        document.update(extra)
        write_json(self.project / "sentinel.workspace.json", document)

    def test_workspace_without_gate_uses_defaults(self):
        self.workspace({})
        _, _, gate = load_workspace(str(self.project), "sentinel.workspace.json")
        self.assertEqual(DEFAULT_GATE, gate)

    def test_workspace_gate_is_loaded_and_validated(self):
        self.workspace({"gate": {"crapMax": "12.5", "mutationMin": "95"}})
        _, _, gate = load_workspace(str(self.project), "sentinel.workspace.json")
        self.assertEqual({"crapMax": "12.5", "mutationMin": "95"}, gate.as_json())
        self.workspace({"gate": {"crapMax": 12}})
        with self.assertRaises(SentinelError) as raised:
            load_workspace(str(self.project), "sentinel.workspace.json")
        self.assertEqual("invalidGate", raised.exception.code)


if __name__ == "__main__":
    unittest.main()
