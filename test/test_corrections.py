import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError
from verification_helpers import attest

from engine.corrections import (
    CONTRACT_VERSION,
    capture_original,
    fact_set_fingerprint,
    input_fingerprint,
    materialize,
    note_hash,
    verification_fingerprint,
)
from engine.decision_store import DecisionStore
from engine.extract import extract_facts
from engine.policies import canonical_json, content_hash
from engine.replay import replay_decision
from engine.schemas import EvaluationResult, EvaluationResultV15, PARequest
from engine.service import InvalidRequestError, ReadinessService

EDITED_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)
NOTE = "Low back pain with radiculopathy. Right L5 distribution: strength 4/5. NSAIDs for 8 weeks with no improvement."
THERAPY_KEY = "cpb_0236_conservative_therapy_weeks"


def request(note=NOTE, procedure="MRI_LUMBAR", events=()):
    return PARequest(payer="Aetna", procedure_code=procedure, note_text=note, corrections=list(events))


def event(note=NOTE, key=THERAPY_KEY, value=8, **overrides):
    payload = dict(
        requirement_key=key, action="SET_VALUE", value=value, reason="incorrect_value",
        editor="Self-reported test editor", edited_at=EDITED_AT.isoformat(), note_hash=note_hash(note),
        evidence_spans=[{"start": 0, "end": len(note), "text": note}],
    )
    return payload | overrides


def nonvalue_event(key, action, **overrides):
    return dict(requirement_key=key, action=action, reason="restore" if action == "RESTORE_ORIGINAL" else "withdrawal",
                editor="Self-reported test editor", edited_at=EDITED_AT.isoformat()) | overrides


def insert_history(store, result, payload, decision_id="history"):
    store.add_policy(result.policy_version)
    store.connection.execute(
        "INSERT INTO decisions VALUES (?, ?, ?, ?, ?)",
        (decision_id, result.policy_version.policy_id, result.policy_version.version_id, canonical_json(payload),
         content_hash({"decision_id": decision_id, "evaluation": payload})),
    )
    store.connection.commit()


@pytest.mark.parametrize(
    "key,value",
    [
        ("osa_diagnosis", "false"), ("osa_diagnosis", "true"), ("osa_diagnosis", 1),
        (THERAPY_KEY, "8"), (THERAPY_KEY, True), (THERAPY_KEY, -1), (THERAPY_KEY, 8.0), (THERAPY_KEY, 8.5),
        (THERAPY_KEY, float("nan")), (THERAPY_KEY, float("inf")), (THERAPY_KEY, -float("inf")),
        ("prior_imaging_result", "edema"), ("prior_imaging_result", "unrecognized"),
        ("neuro_red_flags_documented", False), ("ahi_documented", False), ("sleep_study_date", False),
        ("sleep_study_date", {"value": True, "supporting_date": "2023-02-29"}),
        ("sleep_study_date", {"value": "true", "supporting_date": "2024-02-29"}),
        ("unknown_requirement", True),
    ],
)
def test_type_boundaries_through_request_and_service(key, value):
    with pytest.raises(ValidationError):
        ReadinessService().evaluate(request(events=[event(key=key, value=value)]))


@pytest.mark.parametrize(
    "override",
    [
        {"evidence_spans": []},
        {"evidence_spans": [{"start": 0, "end": 4, "text": "fake"}]},
        {"evidence_spans": [{"start": 1, "end": 5, "text": "Low "}]},
        {"evidence_spans": [{"start": -1, "end": 4, "text": "Low "}]},
        {"evidence_spans": [{"start": 0, "end": len(NOTE) + 1, "text": NOTE}]},
        {"evidence_spans": [{"start": True, "end": 4, "text": "Low "}]},
        {"evidence_spans": [{"start": "0", "end": 4, "text": "Low "}]},
        {"note_hash": note_hash("another note")},
        {"comment": "x" * 1001},
        {"edited_at": "2026-01-01T00:00:00"},
        {"editor": " "},
    ],
)
def test_invalid_evidence_and_metadata_rejected(override):
    with pytest.raises(ValidationError):
        request(events=[event(**override)])


def test_same_quote_from_another_note_still_requires_correct_note_hash():
    with pytest.raises(ValidationError, match="note hash"):
        request(NOTE + " Other text.", events=[event()])


def test_unicode_spans_use_original_code_points_not_lowercase_or_utf8_offsets():
    note = "😀 İ note. " + NOTE
    start = note.index("NSAIDs")
    quote = note[start:]
    corrected = ReadinessService().evaluate(request(note, events=[event(
        note, value=9, evidence_spans=[{"start": start, "end": len(note), "text": quote}],
    )]))
    assert corrected.facts[THERAPY_KEY] == 9
    assert corrected.evidence_map[THERAPY_KEY][0].start == start
    assert corrected.original_snapshot.content["facts"][THERAPY_KEY] == 8


def test_gate_sequence_and_whole_set_verification():
    service = ReadinessService()
    original = service.evaluate(request())
    corrected = service.evaluate(request(events=[event(value=9)]))
    assert original.original_snapshot == corrected.original_snapshot
    assert corrected.original_snapshot.content["facts"][THERAPY_KEY] == 8
    assert corrected.facts[THERAPY_KEY] == 9
    assert corrected.input_fingerprint == original.input_fingerprint
    assert corrected.fact_set_fingerprint != original.fact_set_fingerprint
    assert corrected.overall_status == "PENDING_VERIFICATION"
    assert all(item.verification.state == "UNVERIFIED" for item in corrected.results)
    for omitted in corrected.results:
        partial = service.evaluate(attest(corrected, [item.key for item in corrected.results if item.key != omitted.key]))
        assert partial.overall_status == "PENDING_VERIFICATION"
    ready = service.evaluate(attest(corrected))
    assert ready.overall_status == "READY"
    assert ready.uses_reviewer_corrections is True
    assert ready.corrected_requirement_keys == [THERAPY_KEY]


@pytest.mark.parametrize("action,expected", [("SET_MISSING", "CANNOT_DETERMINE"), ("SET_NEEDS_REVIEW", "NEEDS_REVIEW")])
def test_explicit_states_apply_without_reinterpreting_original(action, expected):
    service = ReadinessService()
    original = service.evaluate(request())
    patch = nonvalue_event(THERAPY_KEY, action)
    if action == "SET_MISSING":
        patch["document_review"] = {
            "note_hash": note_hash(NOTE), "proposal_spans": original.original_snapshot.content["evidence"][THERAPY_KEY],
        }
    result = service.evaluate(request(events=[patch]))
    assert result.overall_status == expected
    assert result.original_snapshot == original.original_snapshot
    assert result.facts[THERAPY_KEY] is None
    assert result.captured_fact_states[THERAPY_KEY] == action.removeprefix("SET_")


def test_missing_requires_offending_proposal_span_where_one_exists():
    patch = nonvalue_event(THERAPY_KEY, "SET_MISSING", document_review={"note_hash": note_hash(NOTE)})
    with pytest.raises(InvalidRequestError, match="offending proposal"):
        ReadinessService().evaluate(request(events=[patch]))


def test_missing_review_rejects_valid_quote_that_is_not_the_offending_proposal():
    patch = nonvalue_event(THERAPY_KEY, "SET_MISSING", document_review={
        "note_hash": note_hash(NOTE), "proposal_spans": [{"start": 0, "end": 3, "text": "Low"}],
    })
    with pytest.raises(InvalidRequestError, match="offending proposal"):
        ReadinessService().evaluate(request(events=[patch]))


def test_failing_correction_and_original_negation_error():
    note = ("Patient does not have low back pain with radiculopathy. Right L5 distribution: strength 4/5. "
            "NSAIDs for 8 weeks with no improvement.")
    service = ReadinessService()
    original = service.evaluate(request(note))
    assert original.facts["back_pain_with_radiculopathy"] is True  # Known drafting error is not rebuilt.
    corrected = service.evaluate(request(note, events=[event(note, "back_pain_with_radiculopathy", False)]))
    assert corrected.original_snapshot == original.original_snapshot
    assert corrected.facts["back_pain_with_radiculopathy"] is False
    assert corrected.overall_status == "NOT_READY"
    assert service.evaluate(request(events=[event(value=5)])).overall_status == "NOT_READY"


@pytest.mark.parametrize("phrase", ["Lumbosacral radicular syndrome documented.", "Patient has persistent lumbar root pain."])
def test_missed_positive_proposal_can_be_supplied_and_then_verified(phrase):
    note = phrase + " Right L5 distribution: strength 4/5. NSAIDs for 8 weeks with no improvement."
    service = ReadinessService()
    original = service.evaluate(request(note))
    assert original.facts["back_pain_with_radiculopathy"] is None
    corrected = service.evaluate(request(note, events=[event(note, "back_pain_with_radiculopathy", True, reason="missed_documented_fact")]))
    assert corrected.original_snapshot == original.original_snapshot
    assert corrected.overall_status == "PENDING_VERIFICATION"
    assert service.evaluate(attest(corrected)).overall_status == "READY"


def test_osa_false_has_documentary_denial_semantics_and_fails_equals_true():
    note = "Patient denies OSA. Sleep study completed 2024-02-29. AHI 22."
    service = ReadinessService()
    original = service.evaluate(request(note, "CPAP_DEVICE"))
    assert original.overall_status == "CANNOT_DETERMINE"
    corrected = service.evaluate(request(note, "CPAP_DEVICE", [event(note, "osa_diagnosis", False)]))
    assert corrected.facts["osa_diagnosis"] is False
    assert corrected.original_snapshot == original.original_snapshot
    assert corrected.overall_status == "NOT_READY"


def test_borrowed_date_can_be_withdrawn_without_fixing_extraction():
    note = "OSA. Visit date 2024-05-18. Sleep study date not recorded. AHI 22."
    service = ReadinessService()
    original = service.evaluate(request(note, "CPAP_DEVICE"))
    assert original.facts["sleep_study_date"] is True
    review = {"note_hash": note_hash(note), "proposal_spans": original.original_snapshot.content["evidence"]["sleep_study_date"]}
    patch = nonvalue_event("sleep_study_date", "SET_MISSING", reason="incorrect_citation", document_review=review)
    corrected = service.evaluate(request(note, "CPAP_DEVICE", [patch]))
    assert corrected.original_snapshot == original.original_snapshot
    assert corrected.overall_status == "CANNOT_DETERMINE"


def test_ordered_events_last_wins_and_restored_keys_remain_annotated():
    service = ReadinessService()
    patches = [event(value=7), event(value=9)]
    corrected = service.evaluate(request(events=patches))
    assert corrected.facts[THERAPY_KEY] == 9
    restored = service.evaluate(request(events=patches + [nonvalue_event(THERAPY_KEY, "RESTORE_ORIGINAL")]))
    assert len(restored.request.corrections) == 3
    assert restored.facts[THERAPY_KEY] == 8
    assert restored.original_snapshot == corrected.original_snapshot
    assert restored.fact_set_fingerprint != corrected.fact_set_fingerprint
    ready = service.evaluate(attest(restored))
    assert ready.uses_reviewer_corrections and ready.corrected_requirement_keys == [THERAPY_KEY]
    first_view = restored.original_snapshot.content
    first_view["facts"][THERAPY_KEY] = 999
    assert restored.original_snapshot.content["facts"][THERAPY_KEY] == 8
    with pytest.raises(ValidationError):
        restored.original_snapshot.content_hash = "0" * 64


@pytest.mark.parametrize("change", ["added", "removed", "reordered", "comment", "reason", "editor", "evidence"])
def test_any_correction_change_invalidates_all_attestations(change):
    service = ReadinessService()
    patches = [event(value=7), event(value=9)]
    ready = service.evaluate(attest(service.evaluate(request(events=patches))))
    payload = ready.request.model_dump(mode="json")
    if change == "added":
        payload["corrections"].append(nonvalue_event(THERAPY_KEY, "RESTORE_ORIGINAL"))
    elif change == "removed":
        payload["corrections"] = []
    elif change == "reordered":
        payload["corrections"].reverse()
    elif change == "evidence":
        payload["corrections"][0]["evidence_spans"] = [{"start": 0, "end": 3, "text": "Low"}]
    else:
        payload["corrections"][0][change] = {"comment": "audit-only", "reason": "wrong_attribution", "editor": "another editor"}[change]
    with pytest.raises(InvalidRequestError, match="Stale"):
        service.evaluate(PARequest.model_validate(payload))


def test_new_correction_invalidates_even_untouched_requirement_attestations():
    service = ReadinessService()
    verified = attest(service.evaluate(request()))
    payload = verified.model_dump(mode="json")
    payload["corrections"] = [event(value=9)]
    payload["fact_verifications"].pop(THERAPY_KEY)
    with pytest.raises(InvalidRequestError, match="Stale"):
        service.evaluate(PARequest.model_validate(payload))


@pytest.mark.parametrize("delta", [timedelta(0), -timedelta(seconds=1)])
def test_equal_or_earlier_attestation_time_is_not_self_verification(delta):
    service = ReadinessService()
    corrected = service.evaluate(request(events=[event()]))
    payload = attest(corrected).model_dump(mode="json")
    for verification in payload["fact_verifications"].values():
        verification["verified_at"] = (EDITED_AT + delta).isoformat()
    with pytest.raises(InvalidRequestError, match="strictly later"):
        service.evaluate(PARequest.model_validate(payload))


def test_self_reported_timestamps_cannot_prove_separate_actions_or_people():
    # Deliberate limitation: a caller can compute public hashes offline, backdate
    # an edit, and supply a later attestation in ONE call. No workflow/authentication
    # claim is made; the mechanism enforces ordering of the supplied timestamps only.
    service = ReadinessService()
    corrected_request = request(events=[event()])
    policy = service.evaluate(request()).policy_version
    original = capture_original(*extract_facts(NOTE))
    effective = materialize(original, corrected_request.corrections, NOTE, [item["key"] for item in policy.requirements])
    input_hash = input_fingerprint(corrected_request, policy, service._bundle_digest(), CONTRACT_VERSION)
    fact_hash = fact_set_fingerprint(input_hash, original, corrected_request.corrections, effective)
    payload = corrected_request.model_dump(mode="json")
    payload["fact_verifications"] = {
        item["key"]: {"state": "HUMAN_VERIFIED", "reviewer": "Same self-reported editor",
                      "verified_at": (EDITED_AT + timedelta(seconds=1)).isoformat(),
                      "fingerprint": verification_fingerprint(fact_hash, item["key"])}
        for item in policy.requirements
    }
    assert service.evaluate(PARequest.model_validate(payload)).overall_status == "READY"


@pytest.mark.parametrize("field", ["effective_facts", "facts", "original_snapshot", "overall_status", "rule_reasons",
                                   "uses_reviewer_corrections", "corrected_requirement_keys", "fact_set_fingerprint"])
def test_client_cannot_supply_derived_state(field):
    with pytest.raises(ValidationError, match="Extra inputs"):
        PARequest.model_validate(request().model_dump(mode="json") | {field: True})


def test_selected_policy_rejects_correction_to_unrelated_requirement():
    with pytest.raises(InvalidRequestError, match="Unknown correction requirement"):
        ReadinessService().evaluate(request(events=[event(key="osa_diagnosis", value=True)]))


@pytest.mark.parametrize("mode", ["ready", "effective", "typed_value", "annotation", "audit_annotation", "evidence", "fingerprint"])
def test_archive_rejects_forged_corrected_records(tmp_path, mode):
    result = ReadinessService().evaluate(request(events=[event(value=9)]))
    payload = result.model_dump(mode="json")
    if mode == "ready":
        for copy in (payload, payload["audit_trail"], payload["report"]["audit_trail"]):
            copy["overall_status"] = "READY"
    elif mode in {"effective", "typed_value"}:
        key = THERAPY_KEY if mode == "effective" else "back_pain_with_radiculopathy"
        payload["facts"][key] = 99 if mode == "effective" else 1
    elif mode == "annotation":
        payload["corrected_requirement_keys"] = []
    elif mode == "audit_annotation":
        payload["audit_trail"]["uses_reviewer_corrections"] = False
        payload["report"]["audit_trail"]["uses_reviewer_corrections"] = False
    elif mode == "evidence":
        payload["request"]["corrections"][0]["evidence_spans"][0]["text"] = "fabricated"
    else:
        payload["fact_set_fingerprint"] = "0" * 64
    with DecisionStore(tmp_path / "archive.sqlite") as store:
        insert_history(store, result, payload)
        with pytest.raises(ValidationError):
            store.get_decision("history")
        # model_construct/copy cannot evade strict writer revalidation.
        forged = result.model_copy(update={"facts": {**result.facts, THERAPY_KEY: 99}})
        with pytest.raises(ValidationError):
            store.record(forged, "forged")


def test_corrected_archive_is_viewable_but_not_replayable_and_letters_refuse(tmp_path):
    service = ReadinessService()
    corrected = service.evaluate(attest(service.evaluate(request(events=[event(value=9)]))))
    with DecisionStore(tmp_path / "archive.sqlite") as store:
        store.record(corrected, "corrected")
        loaded = store.get_decision("corrected")
        assert loaded == corrected
        assert loaded.schema_version == "2.0.0"
        assert loaded.original_snapshot.content["facts"][THERAPY_KEY] == 8
        assert loaded.facts[THERAPY_KEY] == 9
        with pytest.raises(ValueError, match="viewable but not replayable"):
            replay_decision(loaded, loaded.policy_version)
        for kind in ("submission_cover_letter", "missing_info_request", "appeal_template"):
            with pytest.raises(InvalidRequestError, match="not yet supported"):
                service.generate_letter(loaded, kind)


def test_v15_reads_are_unchanged_and_uncorrected_v2_replay_has_parity(tmp_path):
    old_payload = json.loads(Path("docs/artifacts/MRI-01-complete.json").read_text())
    old_payload.pop("letter")  # Export-only attachment was never part of the v1.5 archive schema.
    old = EvaluationResultV15.model_validate(old_payload)
    assert old.model_dump(mode="json") == old_payload
    service = ReadinessService()
    # The display artifact redacts note text. Use its original synthetic case for
    # current evaluation; historical replay still uses only captured evidence.
    new = service.evaluate(service.get_demo_case_request("MRI-01-complete"))
    assert new.facts == old.facts
    assert new.overall_status == old.overall_status
    assert replay_decision(new, old.policy_version) == replay_decision(old, old.policy_version)
    with DecisionStore(tmp_path / "archive.sqlite") as store:
        insert_history(store, new, old_payload)
        assert store.get_decision("history").model_dump(mode="json") == old_payload
        with pytest.raises(ValueError):
            store.record(old, "downgrade")


@pytest.mark.parametrize("version", ["3.0.0", "9.5.0", "200.0.0"])
def test_unknown_schema_major_fails_closed(tmp_path, version):
    result = ReadinessService().evaluate(request())
    payload = result.model_dump(mode="json") | {"schema_version": version}
    with DecisionStore(tmp_path / "archive.sqlite") as store:
        insert_history(store, result, payload)
        with pytest.raises(ValueError, match="Unknown.*major"):
            store.get_decision("history")


def test_writes_cannot_downgrade_schema(tmp_path):
    result = ReadinessService().evaluate(request(events=[event()]))
    with DecisionStore(tmp_path / "archive.sqlite") as store:
        with pytest.raises(ValidationError, match="schema_version"):
            store.record(result.model_copy(update={"schema_version": "1.5.0"}))
        assert store.decision_ids() == []


def test_mutable_request_copy_cannot_evade_value_validation():
    valid = request(events=[event()])
    invalid = valid.model_copy(update={"corrections": [valid.corrections[0].model_copy(update={"value": "9"})]})
    with pytest.raises(ValidationError):
        ReadinessService().evaluate(invalid)


def test_original_hash_corruption_is_rejected():
    result = ReadinessService().evaluate(request())
    payload = deepcopy(result.model_dump(mode="json"))
    payload["original_snapshot"]["content_hash"] = "0" * 64
    with pytest.raises(ValidationError, match="snapshot content hash"):
        EvaluationResult.model_validate(payload)


def test_set_missing_on_uncaptured_fact_needs_document_review_but_no_quote():
    note = "Right L5 distribution: strength 4/5. NSAIDs for 8 weeks with no improvement."
    patch = nonvalue_event("back_pain_with_radiculopathy", "SET_MISSING", document_review={"note_hash": note_hash(note)})
    result = ReadinessService().evaluate(request(note, events=[patch]))
    assert result.overall_status == "CANNOT_DETERMINE"
    assert result.request.corrections[0].document_review.proposal_spans == ()


@pytest.mark.parametrize("action", ["SET_MISSING", "SET_NEEDS_REVIEW", "RESTORE_ORIGINAL"])
def test_nonvalue_actions_reject_even_explicit_null_value(action):
    patch = nonvalue_event(THERAPY_KEY, action, value=None)
    if action == "SET_MISSING":
        patch["document_review"] = {"note_hash": note_hash(NOTE)}
    with pytest.raises(ValidationError, match="Only SET_VALUE"):
        request(events=[patch])


def test_restored_decision_still_refuses_letters():
    service = ReadinessService()
    restored = service.evaluate(request(events=[event(), nonvalue_event(THERAPY_KEY, "RESTORE_ORIGINAL")]))
    with pytest.raises(InvalidRequestError, match="not yet supported"):
        service.generate_letter(restored)


def test_acceptance_projection_keeps_original_snapshot_fingerprint_without_hiding_corrected_decisions():
    from engine.acceptance import normalize_evaluation_payload

    service = ReadinessService()
    original = service.evaluate(request())
    projection = normalize_evaluation_payload(original.model_dump(mode="json"))
    assert projection["original_snapshot_fingerprint"] == original.original_snapshot.content_hash
    assert original.original_snapshot.content["facts"] == projection["facts"]
    assert original.original_snapshot.content["states"] == projection["captured_fact_states"]
    assert original.original_snapshot.content["evidence"] == projection["evidence_map"]
    corrected = service.evaluate(request(events=[event(value=9)]))
    assert "original_snapshot" in normalize_evaluation_payload(corrected.model_dump(mode="json"))


def test_verified_failing_effective_fact_cannot_be_forged_into_ready(tmp_path):
    note = "Patient denies OSA. Sleep study completed 2024-02-29. AHI 22."
    service = ReadinessService()
    result = service.evaluate(attest(service.evaluate(request(note, "CPAP_DEVICE", [event(note, "osa_diagnosis", False)]))))
    assert all(item.verification.state == "HUMAN_VERIFIED" for item in result.results)
    payload = result.model_dump(mode="json")
    for copy in (payload, payload["audit_trail"], payload["report"]["audit_trail"]):
        copy["overall_status"] = "READY"
    for results in (payload["results"], payload["report"]["results"]):
        for item in results:
            item["status"] = "MET"  # Passes the old structural gate; v2 must recompute the actual False operator result.
    with DecisionStore(tmp_path / "archive.sqlite") as store:
        insert_history(store, result, payload)
        with pytest.raises(ValidationError, match="evaluation of effective facts"):
            store.get_decision("history")


def test_uncorrected_ready_explicitly_carries_false_annotation():
    service = ReadinessService()
    ready = service.evaluate(attest(service.evaluate(request())))
    payload = ready.model_dump(mode="json")
    for copy in (payload, payload["audit_trail"], payload["report"]["audit_trail"]):
        assert copy["uses_reviewer_corrections"] is False
        assert copy["corrected_requirement_keys"] == []
