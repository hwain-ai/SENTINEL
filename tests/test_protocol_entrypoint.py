import sys
import tempfile
import unittest
from pathlib import Path

from sentinel.protocol import _entrypoint_command


class EntrypointCommandTests(unittest.TestCase):
    """A Python adapter runs under this interpreter (macOS has no /usr/bin/python3 guarantee); others run as is."""

    def test_python_shebang_runs_under_this_isolated_interpreter(self):
        with tempfile.TemporaryDirectory() as directory:
            entrypoint = Path(directory) / "sentinel-tool"
            entrypoint.write_text("#!/usr/bin/python3 -I\nprint('x')\n", encoding="utf-8")
            self.assertEqual([sys.executable, "-I", "-B", str(entrypoint)], _entrypoint_command(entrypoint))

    def test_other_entrypoints_run_directly(self):
        with tempfile.TemporaryDirectory() as directory:
            shell = Path(directory) / "sentinel-tool"
            shell.write_text("#!/bin/sh\necho x\n", encoding="utf-8")
            self.assertEqual([str(shell)], _entrypoint_command(shell))
            self.assertEqual([str(shell.with_name("missing"))], _entrypoint_command(shell.with_name("missing")))


if __name__ == "__main__":
    unittest.main()
