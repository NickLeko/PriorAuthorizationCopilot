"""Declared representations for the four existing pathways; no evaluation changes.

These contracts describe CAPTURED values, not passing policy values or clinical
truth. MISSING and NEEDS_REVIEW are separate states, never scalar vocabulary.
DatePresence.value is the boolean consumed by the existing operator. Its optional
ISO date is supporting detail only: it is never evaluated for recency or ordering.
Validation returns the original value without coercion, normalization or parsing
into a different representation. This module is not wired into the runtime.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import Any, Literal

from .schemas import RequirementDefinition

FactKind = Literal["boolean", "duration_weeks", "numeric", "enum", "date_presence"]
FactState = Literal["CAPTURED", "MISSING", "NEEDS_REVIEW"]


class FactContractError(ValueError):
    """A stable rejection reason, suitable for reporting without coercing input."""

    def __init__(self, requirement_key: str, reason: str):
        self.requirement_key = requirement_key
        self.reason = reason
        super().__init__(f"{requirement_key}: {reason}")


@dataclass(frozen=True)
class FactContract:
    requirement_key: str
    fact_kind: FactKind
    unit: str | None = None
    captured_values: tuple[str, ...] = ()
    permits_missing: bool = True
    permits_needs_review: bool = True

    def __post_init__(self) -> None:
        if type(self.requirement_key) is not str or not self.requirement_key or self.requirement_key != self.requirement_key.strip():
            raise ValueError("requirement_key must be a nonblank, unpadded string")
        if self.fact_kind not in {"boolean", "duration_weeks", "numeric", "enum", "date_presence"}:
            raise ValueError("unknown fact kind")
        if self.fact_kind == "duration_weeks" and self.unit != "weeks":
            raise ValueError("duration_weeks requires unit weeks")
        if self.fact_kind == "numeric" and (type(self.unit) is not str or not self.unit.strip()):
            raise ValueError("numeric requires an explicit unit (use dimensionless when applicable)")
        if self.fact_kind in {"boolean", "enum", "date_presence"} and self.unit is not None:
            raise ValueError("boolean, enum and date_presence operator values have no unit")
        if type(self.captured_values) is not tuple or any(type(value) is not str or not value for value in self.captured_values):
            raise ValueError("captured_values must be a tuple of nonempty strings")
        if self.fact_kind == "enum":
            if not self.captured_values or len(set(self.captured_values)) != len(self.captured_values):
                raise ValueError("enum requires a nonempty, unique vocabulary")
        elif self.captured_values:
            raise ValueError("only enums have a captured-value vocabulary")
        if type(self.permits_missing) is not bool or type(self.permits_needs_review) is not bool:
            raise ValueError("state permissions must be booleans")

    @property
    def permitted_states(self) -> tuple[FactState, ...]:
        return ("CAPTURED",) + (("MISSING",) if self.permits_missing else ()) + (("NEEDS_REVIEW",) if self.permits_needs_review else ())


@dataclass(frozen=True)
class DatePresence:
    value: bool
    supporting_date: str | None = None


FACT_CONTRACTS: Mapping[str, FactContract] = MappingProxyType(
    {
        contract.requirement_key: contract
        for contract in (
            FactContract("back_pain_with_radiculopathy", "boolean"),
            FactContract("objective_motor_or_reflex_change_in_root_distribution", "boolean"),
            FactContract("cpb_0236_conservative_therapy_weeks", "duration_weeks", unit="weeks"),
            FactContract("cpb_0236_conservative_therapy_no_improvement", "boolean"),
            FactContract("conservative_therapy_weeks", "duration_weeks", unit="weeks"),
            FactContract("symptom_duration_weeks", "duration_weeks", unit="weeks"),
            FactContract("neuro_red_flags_documented", "boolean"),
            FactContract(
                "prior_imaging_result", "enum", captured_values=("none", "normal", "negative", "inconclusive", "abnormal", "unrecognized")
            ),
            FactContract("mechanical_symptoms_documented", "boolean"),
            FactContract("osa_diagnosis", "boolean"),
            FactContract("sleep_study_date", "date_presence"),
            FactContract("ahi_documented", "boolean"),
        )
    }
)


def get_fact_contract(requirement_key: str) -> FactContract:
    try:
        return FACT_CONTRACTS[requirement_key]
    except KeyError:
        raise FactContractError(requirement_key, "missing_fact_contract") from None


def validate_fact_value(contract: FactContract, candidate: Any) -> Any:
    """Validate a CAPTURED value; return it unchanged or raise FactContractError.

State markers (including None and the extractor's internal review sentinel) are
not CAPTURED values. State permissions are declared separately on the contract.
An integer-valued float is still not the integer representation of week duration.
"""
    key = contract.requirement_key
    if contract.fact_kind == "boolean":
        if type(candidate) is not bool:
            raise FactContractError(key, "expected_boolean")
    elif contract.fact_kind == "duration_weeks":
        if type(candidate) is not int:
            raise FactContractError(key, "expected_integer_weeks")
        if candidate < 0:
            raise FactContractError(key, "negative_weeks")
    elif contract.fact_kind == "numeric":
        if type(candidate) not in (int, float):
            raise FactContractError(key, "expected_number")
        if type(candidate) is float and not math.isfinite(candidate):
            raise FactContractError(key, "nonfinite_number")
    elif contract.fact_kind == "enum":
        if type(candidate) is not str:
            raise FactContractError(key, "expected_enum_string")
        if candidate not in contract.captured_values:
            raise FactContractError(key, "unknown_enum_member")
    elif contract.fact_kind == "date_presence":
        if type(candidate) is bool:
            return candidate
        if type(candidate) is not DatePresence or type(candidate.value) is not bool:
            raise FactContractError(key, "expected_date_presence_boolean")
        if candidate.supporting_date is not None:
            if candidate.value is not True:
                raise FactContractError(key, "date_detail_requires_positive_presence")
            if type(candidate.supporting_date) is not str or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", candidate.supporting_date) is None:
                raise FactContractError(key, "expected_iso_date")
            try:
                date.fromisoformat(candidate.supporting_date)
            except ValueError:
                raise FactContractError(key, "invalid_iso_date") from None
    return candidate


def check_policy_compatibility(requirements: Iterable[dict[str, Any] | RequirementDefinition]) -> None:
    """Check declared contracts, not policy satisfaction or source semantics.

The v1.5.0 tag predates engine/policies.py. Reuse its existing schema-level
operator/type validator instead of duplicating that compatibility logic.
Policies do not declare units; the duration representation fixes them to weeks.
"""
    contract_types = {"boolean": "boolean", "date_presence": "boolean", "duration_weeks": "number", "numeric": "number", "enum": "enum"}
    for requirement in requirements:
        raw = requirement.model_dump(exclude_none=True) if isinstance(requirement, RequirementDefinition) else requirement
        contract = get_fact_contract(raw["key"])
        validated = RequirementDefinition.model_validate(raw)
        if validated.type != contract_types[contract.fact_kind]:
            raise FactContractError(contract.requirement_key, "incompatible_policy_type")
        if validated.operator == "one_of" and any(value not in contract.captured_values for value in raw["allowed"]):
            raise FactContractError(contract.requirement_key, "policy_value_outside_vocabulary")
