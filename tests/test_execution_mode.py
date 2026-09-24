import json
import unittest
from types import SimpleNamespace

from sentinel.cli import build_parser
from sentinel.protocol import _parse_response


class ExecutionModeTests(unittest.TestCase):
    def test_parallel_is_default_and_sequential_is_explicit(self):
        self.assertEqual(build_parser().parse_args(["check"]).execution_mode, "parallel")
        self.assertEqual(build_parser().parse_args(["check", "--execution-mode", "sequential"]).execution_mode, "sequential")

    def test_old_or_mismatched_adapter_cannot_silently_choose_a_mode(self):
        request = dict(protocolVersion="sentinel-tool-protocol-v1", requestId="request",
                       command="check", moduleId="python", language="python", executionMode="parallel")
        response = {key: request[key] for key in ("protocolVersion", "requestId", "command", "moduleId", "language")}
        response.update(toolVersion="1.2.3", status="passed", exitCode=0, passed=True)
        for value in (None, "sequential"):
            document = dict(response)
            if value is not None:
                document["executionMode"] = value
            observation = _parse_response(json.dumps(document).encode(), request, SimpleNamespace(version="1.2.3"), 0)
            self.assertEqual(observation.diagnostic, "executionModeNotAcknowledged")
            self.assertEqual(observation.exit_code, 6)
        response["executionMode"] = "parallel"
        observation = _parse_response(json.dumps(response).encode(), request, SimpleNamespace(version="1.2.3"), 0)
        self.assertEqual(observation.execution_mode, "parallel")
        self.assertEqual(observation.exit_code, 0)
