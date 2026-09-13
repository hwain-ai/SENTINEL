"""Gate thresholds shared by the workspace config, the CLI and the tool request."""

import re
from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Dict, Optional

from .errors import SentinelError


# Same text contract as SENTINEL_SPEC golden/gate/threshold-v1.json.
THRESHOLD = re.compile(r"^(0|[1-9][0-9]*)(\.[0-9]{1,2})?$")
DEFAULT_CRAP_MAX = "8"
DEFAULT_MUTATION_MIN = "100"
GATE_KEYS = ("crapMax", "mutationMin")


@dataclass(frozen=True)
class Gate:
    crap_max: str
    mutation_min: str

    def as_json(self) -> Dict[str, str]:
        return {"crapMax": self.crap_max, "mutationMin": self.mutation_min}


DEFAULT_GATE = Gate(DEFAULT_CRAP_MAX, DEFAULT_MUTATION_MIN)


def _threshold(value: Any, label: str) -> str:
    if not isinstance(value, str) or not THRESHOLD.fullmatch(value):
        raise SentinelError("invalidGate", f"{label} must be a decimal string with at most two places", 3)
    return value


def validate_crap_max(value: Any) -> str:
    text = _threshold(value, "crapMax")
    if Fraction(text) <= 0:
        raise SentinelError("invalidGate", "crapMax must be greater than zero", 3)
    return text


def validate_mutation_min(value: Any) -> str:
    text = _threshold(value, "mutationMin")
    if Fraction(text) > 100:
        raise SentinelError("invalidGate", "mutationMin must be no more than 100", 3)
    return text


def load_gate(value: Any) -> Gate:
    """Read the optional workspace gate object; missing fields keep the defaults."""

    if value is None:
        return DEFAULT_GATE
    if not isinstance(value, dict):
        raise SentinelError("invalidType", "workspace gate must be an object", 3)
    if set(value) - set(GATE_KEYS):
        raise SentinelError("invalidFields", "workspace gate has unknown fields", 3)
    return Gate(
        validate_crap_max(value["crapMax"]) if "crapMax" in value else DEFAULT_CRAP_MAX,
        validate_mutation_min(value["mutationMin"]) if "mutationMin" in value else DEFAULT_MUTATION_MIN,
    )


def override_gate(gate: Gate, crap_max: Optional[str], mutation_min: Optional[str]) -> Gate:
    """Apply command-line overrides after validating them like config values."""

    return Gate(
        validate_crap_max(crap_max) if crap_max is not None else gate.crap_max,
        validate_mutation_min(mutation_min) if mutation_min is not None else gate.mutation_min,
    )
