"""Content-addressed criteria snapshots; no active-policy promotion side effects."""

from __future__ import annotations

import json
from hashlib import sha256
from typing import Any

from .schemas import REVIEW_REQUIRED_FACT, PolicyVersion, RequirementDefinition


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def content_hash(value: Any) -> str:
    return sha256(canonical_json(value).encode()).hexdigest()


def facts_for_policy(facts: dict, policy: PolicyVersion) -> tuple[dict, list[str]]:
    """Do not let a new operator reinterpret a captured boolean as a number, etc."""
    compatible = dict(facts)
    incompatible = []
    expected_types = {"number": (int, float), "boolean": (bool,), "enum": (str,)}
    for requirement in policy.requirements:
        key = requirement["key"]
        value = facts.get(key)
        if value is not None and value != REVIEW_REQUIRED_FACT and type(value) not in expected_types[requirement["type"]]:
            compatible[key] = REVIEW_REQUIRED_FACT
            incompatible.append(key)
    return compatible, incompatible


def create_policy(
    *,
    policy_id: str,
    version_id: str,
    effective_date: str,
    payer: str,
    procedure_code: str,
    supported_sites: list[str],
    requirements: list[dict],
) -> PolicyVersion:
    criteria = [RequirementDefinition.model_validate(item).model_dump(exclude_none=True) for item in requirements]
    content = dict(
        policy_id=policy_id,
        version_id=version_id,
        effective_date=effective_date,
        payer=payer,
        procedure_code=procedure_code,
        supported_sites=supported_sites,
        criteria_json=canonical_json(criteria),
    )
    return PolicyVersion.model_validate(content | {"content_hash": content_hash(content)})


def runtime_policy(supported, rules_version: str) -> PolicyVersion:
    """Legacy rules use their declared rule-update date, not a claimed payer effective date."""
    requirements = [item.model_dump(exclude_none=True) for item in supported.requirements]
    effective_date = supported.metadata.last_rule_update or supported.provenance.rule_last_updated
    if not effective_date:
        raise ValueError("Versioned evaluation requires a declared rule effective/update date.")
    scope_hash = content_hash({"requirements": requirements, "supported_sites": supported.metadata.supported_sites})
    return create_policy(
        policy_id=f"{supported.payer}:{supported.procedure_code}",
        version_id=f"runtime-{rules_version}-{effective_date}-{scope_hash[:16]}",
        effective_date=effective_date,
        payer=supported.payer,
        procedure_code=supported.procedure_code,
        supported_sites=supported.metadata.supported_sites,
        requirements=requirements,
    )
