import warnings
from copy import deepcopy
from itertools import product

import pytest
from dual_extraction_helpers import synthetic_regex, synthetic_response

from engine.fact_contracts import FACT_CONTRACTS
from engine.schemas import PARequest
from engine.service import ReadinessService
from experiments.dual_extraction.baseline import normalize_evaluation
from experiments.dual_extraction.errors import ExperimentFailure
from experiments.dual_extraction.proposals import proposal_to_legacy
from experiments.dual_extraction.reconcile import reconcile
from experiments.dual_extraction.recorded import adapt_recorded_response

KEY = "cpb_0236_conservative_therapy_no_improvement"
THERAPY = ("cpb_0236_conservative_therapy_weeks", KEY)


def comparison(record, key=KEY):
    return next(item for item in record.comparisons if item.key == key)


def response_for_state(note, state, value=True):
    return synthetic_response(note, {KEY: value} if state == "CAPTURED" else {}, {KEY: state})


@pytest.mark.parametrize(
    "left,right,right_value,disposition,reason",
    [
        ("CAPTURED", "CAPTURED", True, "CAPTURED", "AGREED_CAPTURE"),
        ("CAPTURED", "CAPTURED", False, "NEEDS_REVIEW", "VALUE_DISAGREEMENT"),
        ("CAPTURED", "MISSING", None, "NEEDS_REVIEW", "STATE_DISAGREEMENT"),
        ("MISSING", "CAPTURED", True, "NEEDS_REVIEW", "STATE_DISAGREEMENT"),
        ("MISSING", "MISSING", None, "MISSING", "BOTH_MISSING"),
        ("NEEDS_REVIEW", "CAPTURED", True, "NEEDS_REVIEW", "REVIEW_REQUIRED"),
        ("CAPTURED", "NEEDS_REVIEW", None, "NEEDS_REVIEW", "REVIEW_REQUIRED"),
        ("NEEDS_REVIEW", "MISSING", None, "NEEDS_REVIEW", "REVIEW_REQUIRED"),
        ("MISSING", "NEEDS_REVIEW", None, "NEEDS_REVIEW", "REVIEW_REQUIRED"),
        ("NEEDS_REVIEW", "NEEDS_REVIEW", None, "NEEDS_REVIEW", "REVIEW_REQUIRED"),
    ],
)
def test_reconciliation_decision_table(left, right, right_value, disposition, reason):
    note = "Synthetic response documentation."
    regex = synthetic_regex(note, response_for_state(note, left))
    recorded = adapt_recorded_response(note, response_for_state(note, right, right_value))
    record = reconcile(regex, recorded)
    item = comparison(record)
    assert item.disposition == disposition
    assert item.reason == reason
    assert item.state_disagreement == (left != right)
    assert item.values_agree == ((right_value is True) if left == right == "CAPTURED" else None)
    assert record.dual.snapshot.content["states"][KEY] == disposition
    assert record.regex == regex
    assert record.recorded_llm == recorded
    assert len(record.comparisons) == len(record.dual.snapshot.content["facts"]) == 12
    assert record.clinical_verification is False
    assert record == reconcile(regex, recorded)


def test_scalar_agreement_does_not_erase_evidence_disagreement():
    note = "OSA. OSA."
    raw = synthetic_response(note, {"osa_diagnosis": True})
    raw["facts"]["osa_diagnosis"]["evidence"] = [{"start": 0, "end": 3, "text": "OSA"}]
    regex = synthetic_regex(note, raw)
    other = deepcopy(raw)
    other["facts"]["osa_diagnosis"]["evidence"] = [{"start": 5, "end": 8, "text": "OSA"}]
    recorded = adapt_recorded_response(note, other)
    before = (regex.model_dump_json(), recorded.model_dump_json())
    record = reconcile(regex, recorded)
    item = comparison(record, "osa_diagnosis")
    assert item.values_agree is True
    assert item.retained_citation_sets_equal is False
    assert item.disposition == "CAPTURED"
    assert item.evidence_source == "regex"
    assert record.dual.snapshot.content["evidence"]["osa_diagnosis"] == raw["facts"]["osa_diagnosis"]["evidence"]
    assert before == (regex.model_dump_json(), recorded.model_dump_json())


def test_citation_sets_and_order_are_compared_separately():
    note = "OSA. OSA."
    raw = synthetic_response(note, {"osa_diagnosis": True})
    raw["facts"]["osa_diagnosis"]["evidence"] = [{"start": 0, "end": 3, "text": "OSA"}, {"start": 5, "end": 8, "text": "OSA"}]
    regex = synthetic_regex(note, raw)
    raw["facts"]["osa_diagnosis"]["evidence"].reverse()
    item = comparison(reconcile(regex, adapt_recorded_response(note, raw)), "osa_diagnosis")
    assert item.retained_citation_sets_equal is True
    assert item.retained_citation_order_equal is False


def test_truncated_citation_sets_are_only_observed_prefixes():
    note = "OSA. " * 15
    response = synthetic_response(note, {"osa_diagnosis": True})
    response["facts"]["osa_diagnosis"]["evidence"] = [{"start": i * 5, "end": i * 5 + 3, "text": "OSA"} for i in range(10)]
    response["evidence_counts"] = {"osa_diagnosis": 15}
    first = adapt_recorded_response(note, response)
    second = adapt_recorded_response(note, response)
    record = reconcile(first.proposal, second)
    item = comparison(record, "osa_diagnosis")
    assert item.retained_citation_sets_equal is True
    assert item.citation_comparison_complete is False
    assert proposal_to_legacy(record.dual)[1].total_counts == {"osa_diagnosis": 15}
    assert len(proposal_to_legacy(record.dual)[1]["osa_diagnosis"]) == 10
    response["evidence_counts"]["osa_diagnosis"] = 16
    changed = comparison(reconcile(first.proposal, adapt_recorded_response(note, response)), "osa_diagnosis")
    assert changed.total_citation_counts_equal is False


@pytest.mark.parametrize("states", list(product(("CAPTURED", "MISSING", "NEEDS_REVIEW"), repeat=4)))
def test_linked_therapy_fields_cannot_form_a_new_cross_source_capture(states):
    note = "NSAIDs for 8 weeks with no improvement."
    responses = []
    for pair in (states[:2], states[2:]):
        values = {key: value for key, value, state in zip(THERAPY, (8, True), pair) if state == "CAPTURED"}
        responses.append(synthetic_response(note, values, dict(zip(THERAPY, pair))))
    regex = synthetic_regex(note, responses[0])
    record = reconcile(regex, adapt_recorded_response(note, responses[1]))
    snapshot = record.dual.snapshot.content
    jointly_captured = all(snapshot["states"][key] == "CAPTURED" for key in THERAPY)
    assert jointly_captured == all(state == "CAPTURED" for state in states)
    assert record.jointly_captured_therapy_citation_source == ("regex" if jointly_captured else None)
    if jointly_captured:
        for key in THERAPY:
            assert snapshot["evidence"][key] == regex.snapshot.content["evidence"][key]


def test_linked_agreed_values_retain_both_citations_from_one_original_course():
    note = "NSAIDs for 8 weeks with no improvement. Analgesics for 8 weeks with no improvement."
    raw = synthetic_response(note, dict(zip(THERAPY, (8, True))))
    first_end = note.index(".")
    for key in THERAPY:
        raw["facts"][key]["evidence"] = [{"start": 0, "end": first_end, "text": note[:first_end]}]
    regex = synthetic_regex(note, raw)
    start = note.index("Analgesics")
    for key in THERAPY:
        raw["facts"][key]["evidence"] = [{"start": start, "end": len(note) - 1, "text": note[start:-1]}]
    record = reconcile(regex, adapt_recorded_response(note, raw))
    assert record.jointly_captured_therapy_citation_source == "regex"
    for key in THERAPY:
        assert comparison(record, key).retained_citation_sets_equal is False
        assert record.dual.snapshot.content["evidence"][key] == regex.snapshot.content["evidence"][key]


def test_linked_value_conflict_does_not_create_a_jointly_captured_course():
    note = "NSAIDs for 8 weeks with no improvement."
    raw = synthetic_response(note, dict(zip(THERAPY, (8, True))))
    regex = synthetic_regex(note, raw)
    raw["facts"][THERAPY[0]]["value"] = 6
    record = reconcile(regex, adapt_recorded_response(note, raw))
    assert comparison(record, THERAPY[0]).reason == "VALUE_DISAGREEMENT"
    assert comparison(record, THERAPY[1]).reason == "AGREED_CAPTURE"
    assert record.jointly_captured_therapy_citation_source is None


def test_identical_false_captures_are_retained_and_not_treated_as_missing():
    note = "Explicitly denied treatment nonresponse."
    raw = synthetic_response(note, {KEY: False})
    record = reconcile(synthetic_regex(note, raw), adapt_recorded_response(note, raw))
    assert comparison(record).reason == "AGREED_CAPTURE"
    assert record.dual.snapshot.content["facts"][KEY] is False


@pytest.mark.parametrize("failure", [None, {}, ExperimentFailure("RECORDED_EXTRACTION_FAILURE")])
def test_extraction_failure_is_not_a_missing_proposal(failure):
    note = "OSA"
    raw = synthetic_response(note, {"osa_diagnosis": True})
    with pytest.raises(ExperimentFailure, match="INVALID_PROPOSAL"):
        reconcile(synthetic_regex(note, raw), failure)


def test_exact_note_binding_and_bypassed_models_are_revalidated():
    regex = synthetic_regex("OSA", synthetic_response("OSA", {"osa_diagnosis": True}))
    recorded = adapt_recorded_response("OSA ", synthetic_response("OSA ", {"osa_diagnosis": True}))
    with pytest.raises(ExperimentFailure, match="NOTE_MISMATCH"):
        reconcile(regex, recorded)
    valid = adapt_recorded_response("OSA", synthetic_response("OSA", {"osa_diagnosis": True}))
    invalid = valid.model_copy(update={"proposal": valid.proposal.model_copy(update={"note_text": "xxx"})})
    with pytest.raises(ExperimentFailure, match="INVALID_PROPOSAL"):
        reconcile(regex, invalid)


def test_malformed_proposal_diagnostics_do_not_emit_clinical_values(caplog, capsys):
    note = "PRIVATE_SYNTHETIC_NOTE_SENTINEL"
    raw = synthetic_response(note, {"osa_diagnosis": True})
    regex = synthetic_regex(note, raw)
    recorded = adapt_recorded_response(note, raw)
    invalid = recorded.model_copy(update={"recording": {"source": note}})
    with warnings.catch_warnings(record=True) as emitted:
        warnings.simplefilter("always")
        with pytest.raises(ExperimentFailure, match="INVALID_PROPOSAL") as caught:
            reconcile(regex, invalid)
    assert note not in str(caught.value)
    assert not any(note in str(item.message) for item in emitted)
    captured = capsys.readouterr()
    assert note not in caplog.text + captured.out + captured.err


def test_implausible_numeric_support_is_flagged_without_new_thresholds_or_value_changes():
    note = "PT for 8 weeks."
    raw = synthetic_response(note, {"conservative_therapy_weeks": 999999})
    record = reconcile(synthetic_regex(note, raw), adapt_recorded_response(note, raw))
    item = comparison(record, "conservative_therapy_weeks")
    assert set(item.analysis_flags) == {"REGEX_NUMERIC_NOT_LITERAL_IN_RETAINED_CITATIONS", "LLM_NUMERIC_NOT_LITERAL_IN_RETAINED_CITATIONS"}
    assert item.disposition == "CAPTURED"
    assert record.dual.snapshot.content["facts"]["conservative_therapy_weeks"] == 999999
    # Legitimate normalized units can also trigger this advisory; it is not adjudication.
    normalized = synthetic_response("Symptoms for 3 months.", {"symptom_duration_weeks": 12})
    normalized_record = reconcile(
        synthetic_regex("Symptoms for 3 months.", normalized), adapt_recorded_response("Symptoms for 3 months.", normalized)
    )
    assert comparison(normalized_record, "symptom_duration_weeks").analysis_flags


def test_structural_agreement_on_unsupported_fact_is_never_human_verification():
    note = "Mother has OSA. Sleep study completed 2024-05-18. AHI 22."
    raw = synthetic_response(note, {"osa_diagnosis": True, "sleep_study_date": True, "ahi_documented": True})
    record = reconcile(synthetic_regex(note, raw), adapt_recorded_response(note, raw))
    assert comparison(record, "osa_diagnosis").reason == "AGREED_CAPTURE"
    assert record.clinical_verification is False
    request = PARequest(payer="Aetna", procedure_code="CPAP_DEVICE", note_text=note)
    actual = ReadinessService(extractor=lambda text: proposal_to_legacy(record.dual)).evaluate(request)
    assert all(result.status == "MET" and result.verification.state == "UNVERIFIED" for result in actual.results)
    assert actual.overall_status == "PENDING_VERIFICATION"
    assert actual.submission_readiness is False


def test_experimental_provenance_does_not_change_production_fingerprints():
    note = "OSA"
    raw = synthetic_response(note, {"osa_diagnosis": True})
    first = adapt_recorded_response(note, raw)
    raw["recording"].update(source="recorded-llm:alternate", model_id="synthetic-alternate", response_id="synthetic-other")
    second = adapt_recorded_response(note, raw)
    request = PARequest(payer="Aetna", procedure_code="CPAP_DEVICE", note_text=note)
    results = [
        ReadinessService(extractor=lambda text, proposal=p: proposal_to_legacy(proposal)).evaluate(request)
        for p in (first.proposal, second.proposal)
    ]
    assert normalize_evaluation(results[0].model_dump(mode="json")) == normalize_evaluation(results[1].model_dump(mode="json"))
    assert set(results[0].facts) == set(FACT_CONTRACTS)
