"""Deterministic corrections over captured proposals, never clinical truth.

Edits and attestation timestamps are self-reported. Strict temporal ordering
blocks equal-time verification, not a dishonest caller who backdates an edit.
There is no authentication, persisted workflow, or cross-decision lineage.
"""

from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256

from .fact_contracts import FACT_CONTRACTS, DatePresence, get_fact_contract, validate_fact_value
from .policies import canonical_json, content_hash, facts_for_policy
from .schemas import REVIEW_REQUIRED_FACT, OriginalProposal, ReviewerCorrection

CONTRACT_VERSION = content_hash({key: asdict(contract) for key, contract in FACT_CONTRACTS.items()})


def note_hash(note: str) -> str:
    return sha256(note.encode("utf-8")).hexdigest()


def validate_correction_value(key: str, value):
    contract = get_fact_contract(key)
    if contract.fact_kind == "date_presence" and type(value) is dict:
        if "value" not in value or set(value) - {"value", "supporting_date"}:
            raise ValueError("Date presence accepts only value and optional supporting_date.")
        value = DatePresence(value["value"], value.get("supporting_date"))
    accepted = validate_fact_value(contract, value, vocabulary="reviewer_enterable")
    return accepted.value if type(accepted) is DatePresence else accepted


def validate_spans(spans, note: str) -> None:
    for span in spans:
        item = span.model_dump() if hasattr(span, "model_dump") else span
        if (
            set(item) != {"start", "end", "text"}
            or type(item["start"]) is not int or type(item["end"]) is not int or type(item["text"]) is not str
            or not 0 <= item["start"] < item["end"] <= len(note)
            or note[item["start"]:item["end"]] != item["text"]
        ):
            raise ValueError("Evidence offsets/text must match the exact submitted note slice.")


def validate_note_evidence(correction: ReviewerCorrection, note: str) -> None:
    if correction.action == "SET_VALUE":
        if correction.note_hash != note_hash(note):
            raise ValueError("Correction note hash does not match submitted note.")
        validate_spans(correction.evidence_spans, note)
    if correction.document_review is not None:
        if correction.document_review.note_hash != note_hash(note):
            raise ValueError("Document-review note hash does not match submitted note.")
        validate_spans(correction.document_review.proposal_spans, note)


def capture_original(facts: dict, evidence: dict) -> OriginalProposal:
    snapshot = {
        "facts": {key: None if value == REVIEW_REQUIRED_FACT else value for key, value in facts.items()},
        "states": {key: "NEEDS_REVIEW" if value == REVIEW_REQUIRED_FACT else "MISSING" if value is None else "CAPTURED"
                   for key, value in facts.items()},
        "evidence": evidence,
    }
    return OriginalProposal(snapshot_json=canonical_json(snapshot), content_hash=content_hash(snapshot))


def materialize(original: OriginalProposal, corrections, note: str, requirement_keys) -> dict:
    """Fresh effective facts; original canonical JSON is never modified."""
    snapshot = original.content
    if set(snapshot) != {"facts", "states", "evidence"} or set(snapshot["facts"]) != set(snapshot["states"]):
        raise ValueError("Invalid original snapshot structure.")
    if set(snapshot["evidence"]) - set(snapshot["facts"]):
        raise ValueError("Original evidence contains unknown facts.")
    for key, value in snapshot["facts"].items():
        contract = get_fact_contract(key)
        state = snapshot["states"][key]
        if state == "CAPTURED":
            validate_fact_value(contract, value, vocabulary="extractor_emittable")
        elif state not in contract.permitted_states or value is not None:
            raise ValueError("Original state and captured value disagree.")
        validate_spans(snapshot["evidence"].get(key, []), note)
    effective = original.content
    for event in corrections:
        # Revalidate even frozen objects; nested SET_VALUE detail can be mutable.
        event = ReviewerCorrection.model_validate_json(event.model_dump_json())
        key = event.requirement_key
        if key not in requirement_keys:
            raise ValueError(f"Unknown correction requirement: {key}")
        contract = get_fact_contract(key)
        validate_note_evidence(event, note)
        if event.action == "SET_VALUE":
            effective["facts"][key] = validate_correction_value(key, event.value)
            effective["states"][key] = "CAPTURED"
            effective["evidence"][key] = [span.model_dump() for span in event.evidence_spans]
        elif event.action == "SET_MISSING":
            if not contract.permits_missing:
                raise ValueError("Contract does not permit MISSING.")
            proposed = effective["evidence"].get(key, []) or snapshot["evidence"].get(key, [])
            reviewed = [span.model_dump() for span in event.document_review.proposal_spans]
            if proposed and not reviewed:
                raise ValueError("Document review must retain an offending proposal span where one exists.")
            if any(span not in proposed for span in reviewed):
                raise ValueError("Document review does not cite the offending proposal.")
            effective["facts"][key] = None
            effective["states"][key] = "MISSING"
            effective["evidence"][key] = []
        elif event.action == "SET_NEEDS_REVIEW":
            if not contract.permits_needs_review:
                raise ValueError("Contract does not permit NEEDS_REVIEW.")
            effective["facts"][key] = None
            effective["states"][key] = "NEEDS_REVIEW"
        else:
            effective["facts"][key] = snapshot["facts"].get(key)
            effective["states"][key] = snapshot["states"].get(key, "MISSING")
            effective["evidence"].pop(key, None)
            if key in snapshot["evidence"]:
                effective["evidence"][key] = snapshot["evidence"][key]
    return effective


def input_fingerprint(request, policy, bundle_fingerprint: str, contract_version: str) -> str:
    return content_hash({
        "request": request.model_dump(mode="json", exclude={"fact_verifications", "corrections"}),
        "policy": policy.content_hash, "bundle": bundle_fingerprint, "contract_version": contract_version,
    })


def fact_set_fingerprint(input_hash: str, original: OriginalProposal, corrections, effective: dict) -> str:
    return content_hash({
        "input_fingerprint": input_hash, "original_snapshot_hash": original.content_hash,
        "corrections": [event.model_dump(mode="json") for event in corrections], "effective": effective,
    })


def verification_fingerprint(fact_set_hash: str, key: str) -> str:
    return content_hash({"fact_set_fingerprint": fact_set_hash, "requirement_key": key})


def validate_attestation(attestation, expected_fingerprint: str, corrections) -> None:
    if attestation.state == "HUMAN_VERIFIED":
        if attestation.fingerprint != expected_fingerprint:
            raise ValueError("Stale or mismatched verification; review the current fact set.")
        if corrections and attestation.verified_at <= max(event.edited_at for event in corrections):
            raise ValueError("Verification must be strictly later than the latest correction; corrections are not self-verifying.")


def evaluator_facts(effective: dict) -> dict:
    return {key: REVIEW_REQUIRED_FACT if effective["states"][key] == "NEEDS_REVIEW" else value
            for key, value in effective["facts"].items()}


def validate_v2_result(result) -> None:
    """Validate captured structure, not historical extraction or clinical truth."""
    from .evaluate import compute_overall_status, evaluate_requirements, summarize_results

    if not result.schema_version.startswith("2."):
        raise ValueError("v2 evaluations cannot downgrade their schema version.")
    if result.contract_version != CONTRACT_VERSION:
        raise ValueError("Unknown fact contract version.")
    if len(result.bundle_fingerprint) != 64:
        raise ValueError("Invalid bundle fingerprint.")
    keys = [item["key"] for item in result.policy_version.requirements]
    effective = materialize(result.original_snapshot, result.request.corrections, result.request.note_text, keys)
    if canonical_json(result.facts) != canonical_json(effective["facts"]) or result.captured_fact_states != effective["states"]:
        raise ValueError("Effective facts/states do not match correction materialization.")
    evidence = {key: [span.model_dump() for span in spans] for key, spans in result.evidence_map.items()}
    if evidence != effective["evidence"]:
        raise ValueError("Effective evidence does not match correction materialization.")
    input_hash = input_fingerprint(result.request, result.policy_version, result.bundle_fingerprint, result.contract_version)
    fact_hash = fact_set_fingerprint(input_hash, result.original_snapshot, result.request.corrections, effective)
    if (result.input_fingerprint, result.fact_set_fingerprint) != (input_hash, fact_hash):
        raise ValueError("Input/fact-set fingerprint mismatch.")
    corrected_keys = sorted({event.requirement_key for event in result.request.corrections})
    for copy in (result, result.audit_trail):
        if copy.uses_reviewer_corrections != bool(corrected_keys) or copy.corrected_requirement_keys != corrected_keys:
            raise ValueError("Reviewer-correction annotation mismatch.")
        if (copy.input_fingerprint, copy.fact_set_fingerprint) != (input_hash, fact_hash):
            raise ValueError("Audit fingerprints disagree.")
    audit = result.audit_trail
    # Retain the pre-v2 audit display hash; correction evidence uses full SHA-256.
    if (audit.note_hash, audit.note_length) != (note_hash(result.request.note_text)[:16], len(result.request.note_text)):
        raise ValueError("Audit note identity disagrees.")
    if canonical_json(audit.facts_extracted) != canonical_json(result.original_snapshot.content["facts"]):
        raise ValueError("Audit original proposal disagrees with immutable snapshot.")
    if canonical_json(audit.effective_facts) != canonical_json(effective["facts"] if corrected_keys else None):
        raise ValueError("Audit effective facts/evidence disagree.")
    if audit.evidence_map != result.evidence_map:
        raise ValueError("Audit effective facts/evidence disagree.")
    if result.report.audit_trail != audit.model_dump(mode="json"):
        raise ValueError("Report audit copy disagrees.")
    if result.policy_version != audit.policy_version:
        raise ValueError("Decision and audit policy versions disagree.")
    if (result.request.payer, result.request.procedure_code) != (result.policy_version.payer, result.policy_version.procedure_code):
        raise ValueError("Decision and policy scope disagree.")
    if result.request.site_of_care not in result.policy_version.supported_sites:
        raise ValueError("Decision site of care outside policy scope.")
    # Exactly the unchanged evaluator's operators over effective facts.
    facts = facts_for_policy(evaluator_facts(effective), result.policy_version)[0]
    expected_results, reasons = evaluate_requirements(result.policy_version.requirements, facts, evidence_map=effective["evidence"])
    for expected, actual in zip(expected_results, result.results):
        expected.fact_value = effective["facts"].get(expected.key)
        expected.verification_fingerprint = verification_fingerprint(fact_hash, expected.key)
        validate_attestation(actual.verification, expected.verification_fingerprint, result.request.corrections)
        expected.verification = actual.verification
        if expected.model_dump_json() != actual.model_dump_json():
            raise ValueError("Requirement result does not match evaluation of effective facts.")
    if result.rule_reasons != reasons or result.report.rule_reasons != reasons:
        raise ValueError("Rule reasons do not match effective evaluation.")
    if result.report.results != result.results or any(
        a.model_dump_json() != b.model_dump_json() for a, b in zip(result.report.results, result.results)
    ):
        raise ValueError("Report requirement copies disagree.")
    if audit.metrics != result.metrics or audit.blocking_issues != result.blockers or audit.evaluation_warnings != result.warnings:
        raise ValueError("Audit metrics/blockers/warnings disagree.")
    overall = compute_overall_status(expected_results)
    if overall["overall_status"] != result.overall_status:
        raise ValueError("Overall status does not match effective evaluation.")
    summary = summarize_results(expected_results)
    for field in ("met_count", "not_met_count", "not_documented_count", "needs_review_count"):
        if getattr(result.report, field) != summary[field]:
            raise ValueError("Report counts disagree with effective evaluation.")
    if corrected_keys and result.report.letter_draft:
        raise ValueError("Letters for corrected evaluations are not yet supported (pass 2b required).")
