import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from sentinel.cli import build_parser
from sentinel.errors import SentinelError
from sentinel.selection import resolve_selection
from sentinel.diagnostics import normalize_details, STATES


class SelectionTests(unittest.TestCase):
    def test_repeated_test_files_are_preserved_by_the_parser(self):
        args = build_parser().parse_args(["check", "--file", "src/a.py", "--function", "a", "--tests", "tests/a.py", "--tests", "tests/b.py"])
        self.assertEqual(args.tests, ["tests/a.py", "tests/b.py"])
        self.assertIsNone(args.timeout_seconds)

    def test_file_selection_resolves_the_module_and_rejects_missing_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "api").mkdir()
            (root / "web").mkdir()
            (root / "api/a.py").write_text("pass")
            modules = [SimpleNamespace(module_id=name, root=root / name) for name in ("api", "web")]
            selected, details = resolve_selection(root, modules, ["api/a.py"], ["a"], [])
            self.assertEqual([item.module_id for item in selected], ["api"])
            self.assertEqual(details["api"]["files"], ["a.py"])
            with self.assertRaises(SentinelError):
                resolve_selection(root, modules, ["api/missing.py"], [], [])
            with self.assertRaises(SentinelError):
                resolve_selection(root, modules, ["api/a.py"], ["a()"], [])

    def test_empty_mutation_is_unmeasured_and_inconsistent_details_are_rejected(self):
        raw = {"scope": {}, "crap": {"functions": [], "passed": False},
               "mutation": {**dict.fromkeys(STATES, 0), "inScope": 0, "pass": False, "mutants": []}}
        report = normalize_details("java", raw, {"crapMax": "8", "mutationMin": "90"})
        self.assertIsNone(report["mutation"]["score"])
        raw["mutation"].update(inScope=1, killed=1)
        with self.assertRaises(ValueError):
            normalize_details("java", raw, {"crapMax": "8", "mutationMin": "90"})
