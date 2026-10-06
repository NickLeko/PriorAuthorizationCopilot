"""Declared representations for the four existing pathways; no evaluation changes.

These contracts describe CAPTURED values, not passing policy values or clinical
truth. MISSING and NEEDS_REVIEW are separate states, never scalar vocabulary.
Finite vocabularies distinguish extractor outputs from reviewer entries. Numeric
domains are specified by kind and unit instead of enumerating every number.
AMBIGUOUS means the code does not define that public boolean's false meaning;
such false values are excluded from reviewer entries, not interpreted as missing.
DatePresence.value is the boolean consumed by the existing operator. Its optional
ISO date is supporting detail only: it is never evaluated for recency or ordering.
Validation returns the original value without coercion, normalization or parsing
into a different representation. The correction engine validates reviewer entries
against these declarations; evaluation operators are unchanged.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import Any, Literal

from .policies import create_policy, facts_for_policy
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
    meaning: str
    unit: str | None = None
    extractor_emittable: tuple[str | bool, ...] = ()
    reviewer_enterable: tuple[str | bool, ...] = ()
    permits_missing: bool = True
    permits_needs_review: bool = True

    def __post_init__(self) -> None:
        if type(self.requirement_key) is not str or not self.requirement_key or self.requirement_key != self.requirement_key.strip():
            raise ValueError("requirement_key must be a nonblank, unpadded string")
        if self.fact_kind not in {"boolean", "duration_weeks", "numeric", "enum", "date_presence"}:
            raise ValueError("unknown fact kind")
        if type(self.meaning) is not str or not self.meaning.strip():
            raise ValueError("meaning must be a nonblank plain-language string")
        if self.fact_kind == "duration_weeks" and self.unit != "weeks":
            raise ValueError("duration_weeks requires unit weeks")
        if self.fact_kind == "numeric" and (type(self.unit) is not str or not self.unit.strip()):
            raise ValueError("numeric requires an explicit unit (use dimensionless when applicable)")
        if self.fact_kind in {"boolean", "enum", "date_presence"} and self.unit is not None:
            raise ValueError("boolean, enum and date_presence operator values have no unit")
        for vocabulary in (self.extractor_emittable, self.reviewer_enterable):
            if type(vocabulary) is not tuple:
                raise ValueError("vocabularies must be tuples")
            if self.fact_kind in {"enum", "boolean", "date_presence"}:
                value_type = str if self.fact_kind == "enum" else bool
                if not vocabulary or any(type(value) is not value_type or (value_type is str and not value) for value in vocabulary):
                    raise ValueError("finite vocabulary must contain values of the contract's exact type")
                if len(set(vocabulary)) != len(vocabulary):
                    raise ValueError("finite vocabulary must be unique")
            elif vocabulary:
                raise ValueError("numeric domains are declared by kind and unit, not finite vocabularies")
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
            FactContract(
                "back_pain_with_radiculopathy",
                "boolean",
                "True: patient back pain and radiculopathy are documented together affirmatively. "
                "False: at least one is explicitly negated in the paired documentation; not missing documentation.",
                extractor_emittable=(True, False),
                reviewer_enterable=(True, False),
            ),
            FactContract(
                "objective_motor_or_reflex_change_in_root_distribution",
                "boolean",
                "True: objective motor weakness or a reflex change is documented in a named nerve-root distribution. "
                "False: the documented finding is normal or explicitly denied in that distribution; not missing documentation.",
                extractor_emittable=(True, False),
                reviewer_enterable=(True, False),
            ),
            FactContract(
                "cpb_0236_conservative_therapy_weeks",
                "duration_weeks",
                "Nonnegative integer weeks of the documented CPB 0236 conservative-therapy course; not symptom duration.",
                unit="weeks",
            ),
            FactContract(
                "cpb_0236_conservative_therapy_no_improvement",
                "boolean",
                "True: no, minimal, little, or insufficient improvement is documented for the linked conservative-therapy course. "
                "False: substantial, significant, meaningful, or good improvement, or symptom resolution, is documented for that course.",
                extractor_emittable=(True, False),
                reviewer_enterable=(True, False),
            ),
            FactContract(
                "conservative_therapy_weeks",
                "duration_weeks",
                "Nonnegative integer weeks explicitly attached to conservative therapy, not symptom duration.",
                unit="weeks",
            ),
            FactContract(
                "symptom_duration_weeks",
                "duration_weeks",
                "Nonnegative integer weeks of documented symptoms, not treatment duration. "
                "The existing extractor represents a documented month as four weeks; corrections must already be in weeks.",
                unit="weeks",
            ),
            # extract.py:757-760, 803-813: explicit denial also becomes public True.
            FactContract(
                "neuro_red_flags_documented",
                "boolean",
                "True: neurological red flags are explicitly addressed, whether present or denied; it does not mean red flags are present. "
                "False: AMBIGUOUS; the public extractor emits True or a missing/review state, never False. "
                "Do not reinterpret False as absent red flags or missing documentation.",
                extractor_emittable=(True,),
                reviewer_enterable=(True,),
            ),
            FactContract(
                "prior_imaging_result",
                "enum",
                "none: no prior imaging is documented. normal: a normal, unremarkable, or no-acute-findings result is documented. "
                "negative: an abnormal finding is explicitly negated. inconclusive: the result is indeterminate, unclear, unknown, "
                "or not specified. abnormal: an abnormal finding is documented. unrecognized: imaging-result language is present "
                "but the extractor cannot map it to a supported category; this is an extractor diagnostic, not a reviewer category.",
                extractor_emittable=("none", "normal", "negative", "inconclusive", "abnormal", "unrecognized"),
                reviewer_enterable=("none", "normal", "negative", "inconclusive", "abnormal"),
            ),
            # extract.py:887-892, 921-930: False is explicit denial, not missingness.
            FactContract(
                "mechanical_symptoms_documented",
                "boolean",
                "True: positive mechanical symptoms such as locking, catching, buckling, or instability are documented. "
                "False: mechanical symptoms are explicitly denied or described as absent; not missing documentation.",
                extractor_emittable=(True, False),
                reviewer_enterable=(True, False),
            ),
            FactContract(
                "osa_diagnosis",
                "boolean",
                "True: an affirmative patient OSA diagnosis is documented. False: OSA is explicitly negated in the documentation. "
                "The extractor represents a negative-only mention as MISSING, not public False.",
                extractor_emittable=(True,),
                reviewer_enterable=(True, False),
            ),
            FactContract(
                "sleep_study_date",
                "date_presence",
                "True: a completed sleep study is documented; scheduled, ordered, or pending studies do not count as presence. "
                "An optional ISO date is supporting detail only and is never checked for recency or ordering. "
                "False: AMBIGUOUS; the extractor uses missing/review states rather than False and does not define its meaning.",
                extractor_emittable=(True,),
                reviewer_enterable=(True,),
            ),
            # extract.py:989-1015: missing numeric AHI/RDI becomes None, never False.
            FactContract(
                "ahi_documented",
                "boolean",
                "True: a numeric AHI or RDI value is documented; this boolean is not the measurement or its clinical interpretation. "
                "False: AMBIGUOUS; absent or explicitly missing measurements become MISSING, never public False.",
                extractor_emittable=(True,),
                reviewer_enterable=(True,),
            ),
        )
    }
)


def get_fact_contract(requirement_key: str) -> FactContract:
    try:
        return FACT_CONTRACTS[requirement_key]
    except KeyError:
        raise FactContractError(requirement_key, "missing_fact_contract") from None


def validate_fact_value(
    contract: FactContract,
    candidate: Any,
    *,
    vocabulary: Literal["extractor_emittable", "reviewer_enterable"] = "reviewer_enterable",
) -> Any:
    """Validate a CAPTURED value; return it unchanged or raise FactContractError.

    State markers (including None and the extractor's internal review sentinel) are
    not CAPTURED values. State permissions are declared separately on the contract.
    An integer-valued float is still not the integer representation of week duration.
    Reviewer entries are the default; conformance checks explicitly select extractor
    outputs. This selects a representation vocabulary, never a policy passing set.
    """
    key = contract.requirement_key
    if vocabulary not in {"extractor_emittable", "reviewer_enterable"}:
        raise FactContractError(key, "unknown_vocabulary")
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
        if candidate not in contract.extractor_emittable + contract.reviewer_enterable:
            raise FactContractError(key, "unknown_enum_member")
    elif contract.fact_kind == "date_presence":
        if type(candidate) is not bool and (type(candidate) is not DatePresence or type(candidate.value) is not bool):
            raise FactContractError(key, "expected_date_presence_boolean")
        if type(candidate) is DatePresence and candidate.supporting_date is not None:
            if candidate.value is not True:
                raise FactContractError(key, "date_detail_requires_positive_presence")
            if type(candidate.supporting_date) is not str or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", candidate.supporting_date) is None:
                raise FactContractError(key, "expected_iso_date")
            try:
                date.fromisoformat(candidate.supporting_date)
            except ValueError:
                raise FactContractError(key, "invalid_iso_date") from None
    if contract.fact_kind in {"enum", "boolean", "date_presence"}:
        scalar = candidate.value if type(candidate) is DatePresence else candidate
        if scalar not in getattr(contract, vocabulary):
            raise FactContractError(key, f"value_not_{vocabulary}")
    return candidate


def check_policy_compatibility(requirements: Iterable[dict[str, Any] | RequirementDefinition]) -> None:
    """Check declared contracts, not policy satisfaction or source semantics.

    Reuse policies.create_policy for operator/type validation and
    policies.facts_for_policy for captured representation compatibility.
    Policies do not declare units; the duration representation fixes them to weeks.
    """
    for requirement in requirements:
        raw = requirement.model_dump(exclude_none=True) if isinstance(requirement, RequirementDefinition) else requirement
        contract = get_fact_contract(raw["key"])
        # This single-requirement snapshot is only an in-memory compatibility
        # probe, never a runtime or archived policy.
        policy = create_policy(
            policy_id="fact-contract-compatibility",
            version_id="probe",
            effective_date="2000-01-01",
            payer="contract-check",
            procedure_code="MRI_LUMBAR",
            supported_sites=["outpatient"],
            requirements=[raw],
        )
        probe = (
            contract.extractor_emittable[0]
            if contract.fact_kind == "enum"
            else 0
            if contract.fact_kind in {"duration_weeks", "numeric"}
            else True
        )
        _, incompatible = facts_for_policy({contract.requirement_key: probe}, policy)
        if incompatible:
            raise FactContractError(contract.requirement_key, "incompatible_policy_type")
        if policy.requirements[0]["operator"] == "one_of" and any(value not in contract.extractor_emittable for value in raw["allowed"]):
            raise FactContractError(contract.requirement_key, "policy_value_outside_vocabulary")
