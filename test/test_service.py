import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from verification_helpers import attest

from engine.config import load_app_config
from engine.policy_monitor import SNAPSHOT_NORMALIZATION_VERSION, hash_text
from engine.schemas import PARequest
from engine.service import ReadinessService, UnsupportedScopeError


def _evaluate_complete_lumbar_treatment(treatment_note: str):
    return ReadinessService().evaluate(
        PARequest(
            payer="Aetna",
            procedure_code="MRI_LUMBAR",
            dx_codes=["M54.16"],
            site_of_care="outpatient",
            specialty="Orthopedics",
            note_text=(
                "Low back pain with right leg radiculopathy. "
                "Objective motor exam in the right L5 distribution: ankle dorsiflexion strength 4/5. "
                f"{treatment_note}"
            ),
        )
    )


def _write_policy_snapshot(snapshot_root: Path, fetched_at_utc: str) -> None:
    snapshot_dir = snapshot_root / "aetna_mri_lumbar"
    snapshot_dir.mkdir(parents=True)
    normalized_text = "synthetic policy snapshot fixture\n"
    snapshot_dir.joinpath("latest.json").write_text(
        json.dumps(
            {
                "id": "aetna_mri_lumbar",
                "payer": "Aetna",
                "procedure_code": "MRI_LUMBAR",
                "url": "https://www.aetna.com/cpb/medical/data/200_299/0236.html",
                "fetched_at_utc": fetched_at_utc,
                "last_checked_utc": fetched_at_utc,
                "content_hash_sha256": hash_text(normalized_text),
                "normalization": SNAPSHOT_NORMALIZATION_VERSION,
                "normalized_text": normalized_text,
            }
        ),
        encoding="utf-8",
    )


def _copy_current_policy_snapshot(snapshot_root: Path) -> None:
    config = load_app_config()
    snapshot_dir = snapshot_root / "aetna_mri_lumbar"
    snapshot_dir.mkdir(parents=True)
    snapshot_dir.joinpath("latest.json").write_text(
        config.snapshot_root.joinpath("aetna_mri_lumbar", "latest.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )


def test_service_evaluates_known_ready_demo_case():
    service = ReadinessService()
    request = service.get_demo_case_request("MRI-01-complete")

    evaluation = service.evaluate(request)

    assert evaluation.overall_status == "PENDING_VERIFICATION"
    assert evaluation.submission_readiness is False
    assert evaluation.audit_trail.note_hash
    assert evaluation.audit_trail.evidence_map["cpb_0236_conservative_therapy_weeks"]
    assert evaluation.results[0].evidence_spans


def test_service_returns_cannot_determine_for_missing_documentation_case():
    service = ReadinessService()
    request = service.get_demo_case_request("CPAP-02-borderline")

    evaluation = service.evaluate(request)

    assert evaluation.overall_status == "CANNOT_DETERMINE"
    assert evaluation.blockers.not_documented
    assert not evaluation.submission_readiness
    assert evaluation.metrics.documentation_coverage_pct == 33.3
    assert evaluation.metrics.criteria_met_count == 1
    assert evaluation.metrics.evaluable_requirement_count == 1
    assert evaluation.metrics.missing_requirement_count == 2
    assert "compliance_rate" not in evaluation.metrics.model_dump()
    assert "readiness_score" not in evaluation.model_dump()


@pytest.mark.parametrize(
    "procedure_code, note_text, expected_status, fact_key, expected_fact",
    [
        (
            "CPAP_DEVICE",
            "Patient does not have OSA. Sleep study completed 2025-01-02. AHI 22.",
            "CANNOT_DETERMINE",
            "osa_diagnosis",
            None,
        ),
        (
            "CPAP_DEVICE",
            "There is no diagnosis of OSA. Sleep study completed 2025-01-02. AHI 22.",
            "CANNOT_DETERMINE",
            "osa_diagnosis",
            None,
        ),
        (
            "MRI_LUMBAR",
            "Seen 3 months ago. Back pain for 2 weeks. PT for 8 weeks. Denies weakness. No prior imaging.",
            "CANNOT_DETERMINE",
            "symptom_duration_weeks",
            2,
        ),
        (
            "MRI_LUMBAR",
            "Follow-up occurred 4 months ago. Back pain x 3 weeks. PT for 8 weeks. Denies weakness. No prior imaging.",
            "CANNOT_DETERMINE",
            "symptom_duration_weeks",
            3,
        ),
    ],
)
def test_adversarial_notes_cannot_produce_false_ready(procedure_code, note_text, expected_status, fact_key, expected_fact):
    service = ReadinessService()
    request = PARequest(
        payer="Aetna",
        procedure_code=procedure_code,
        dx_codes=[],
        site_of_care="outpatient",
        specialty="Primary Care",
        note_text=note_text,
    )

    evaluation = service.evaluate(request)

    assert evaluation.overall_status == expected_status
    assert evaluation.submission_readiness is False
    assert evaluation.facts[fact_key] == expected_fact


@pytest.mark.parametrize(
    "note_text",
    [
        "Back pain for 8 weeks. PT for 8 weeks. Denies weakness. Prior x-ray showed no fracture.",
        "Back pain for 8 weeks. PT for 8 weeks. Denies weakness. CT demonstrated no acute fracture.",
    ],
)
def test_recognized_negative_imaging_remains_extraction_only_for_verified_lumbar_branch(note_text):
    service = ReadinessService()
    request = PARequest(
        payer="Aetna",
        procedure_code="MRI_LUMBAR",
        dx_codes=[],
        site_of_care="outpatient",
        specialty="Primary Care",
        note_text=(
            "Low back pain with right leg radiculopathy. "
            "NSAIDs for 8 weeks with no improvement. "
            "Objective motor exam in the right L5 distribution: ankle dorsiflexion strength 4/5. "
            f"{note_text}"
        ),
    )

    evaluation = service.evaluate(request)
    assert evaluation.facts["prior_imaging_result"] == "negative"
    assert all(result.key != "prior_imaging_result" for result in evaluation.results)
    assert evaluation.overall_status == "PENDING_VERIFICATION"
    assert evaluation.submission_readiness is False
    assert not evaluation.blockers.not_met
    assert not evaluation.blockers.needs_review


def test_unrecognized_imaging_result_is_documented_not_met_and_requires_review():
    service = ReadinessService()
    request = PARequest(
        payer="Aetna",
        procedure_code="MRI_CERVICAL",
        dx_codes=["M54.12"],
        site_of_care="outpatient",
        specialty="Primary Care",
        note_text="Neck pain x 8 weeks. PT x 8 weeks. Denies weakness. MRI showed edema.",
    )

    evaluation = service.evaluate(request)
    imaging_result = next(result for result in evaluation.results if result.key == "prior_imaging_result")

    assert evaluation.overall_status == "NEEDS_REVIEW"
    assert evaluation.submission_readiness is False
    assert imaging_result.status == "NEEDS_REVIEW"
    assert imaging_result.reason == "Imaging result is documented but its category is unrecognized; human review is required."
    assert all(blocker.key != "prior_imaging_result" for blocker in evaluation.blockers.not_documented)
    assert all(blocker.key != "prior_imaging_result" for blocker in evaluation.blockers.not_met)
    assert any(blocker.key == "prior_imaging_result" for blocker in evaluation.blockers.needs_review)
    assert evaluation.report.needs_review_count == 1
    assert evaluation.metrics.human_review_count == 1
    assert any("human review is required" in warning for warning in evaluation.warnings)


def test_service_lists_new_cervical_procedure_with_registry_metadata():
    service = ReadinessService()

    procedures = service.list_supported_procedures()
    cervical = next(item for item in procedures if item.procedure_code == "MRI_CERVICAL")

    assert cervical.metadata.category == "advanced_imaging"
    assert cervical.metadata.rule_family == "spine_mri_conservative_therapy"
    assert cervical.required_field_keys == [
        "conservative_therapy_weeks",
        "neuro_red_flags_documented",
        "prior_imaging_result",
        "symptom_duration_weeks",
    ]
    assert cervical.provenance.rule_source_label == "Human-curated summary of cervical spine MRI administrative criteria"
    assert cervical.monitored_for_drift is False


def test_only_verified_lumbar_pathway_receives_verified_trust():
    service = ReadinessService()

    trust_by_procedure = {item.procedure_code: item.policy_trust_level for item in service.list_supported_procedures()}

    assert trust_by_procedure == {
        "CPAP_DEVICE": "demo",
        "MRI_CERVICAL": "demo",
        "MRI_KNEE": "demo",
        "MRI_LUMBAR": "verified",
    }

    lumbar = service.get_supported_procedure("Aetna", "MRI_LUMBAR")
    assert lumbar.required_field_keys == [
        "back_pain_with_radiculopathy",
        "objective_motor_or_reflex_change_in_root_distribution",
        "cpb_0236_conservative_therapy_weeks",
        "cpb_0236_conservative_therapy_no_improvement",
    ]
    assert set(lumbar.provenance.requirement_clause_map) == set(lumbar.required_field_keys)
    assert lumbar.provenance.policy_identifier == "CPB 0236"


def test_service_lists_new_knee_procedure_with_required_metadata():
    service = ReadinessService()

    procedures = service.list_supported_procedures()
    knee = next(item for item in procedures if item.procedure_code == "MRI_KNEE")

    assert knee.metadata.category == "advanced_imaging"
    assert knee.metadata.rule_family == "extremity_mri_conservative_therapy"
    assert knee.required_field_keys == [
        "conservative_therapy_weeks",
        "symptom_duration_weeks",
        "prior_imaging_result",
        "mechanical_symptoms_documented",
    ]
    assert knee.provenance.rule_source_label == "Human-curated summary of knee MRI administrative documentation criteria"
    assert knee.monitored_for_drift is False


def test_service_evaluates_new_cervical_demo_case():
    service = ReadinessService()
    request = service.get_demo_case_request("MRI-CERV-01-ready")

    evaluation = service.evaluate(request)

    assert evaluation.overall_status == "PENDING_VERIFICATION"
    assert evaluation.supported_procedure.procedure_code == "MRI_CERVICAL"
    assert evaluation.supported_procedure.metadata.rule_family == "spine_mri_conservative_therapy"


def test_service_evaluates_new_knee_demo_case():
    service = ReadinessService()
    request = service.get_demo_case_request("MRI-KNEE-01-ready")

    evaluation = service.evaluate(request)

    assert evaluation.overall_status == "PENDING_VERIFICATION"
    assert evaluation.supported_procedure.procedure_code == "MRI_KNEE"
    assert evaluation.supported_procedure.metadata.rule_family == "extremity_mri_conservative_therapy"


def test_service_returns_cannot_determine_when_knee_mechanical_symptoms_are_missing():
    service = ReadinessService()
    request = service.get_demo_case_request("MRI-KNEE-03-cannot-determine")

    evaluation = service.evaluate(request)

    assert evaluation.overall_status == "CANNOT_DETERMINE"
    assert any(blocker.key == "mechanical_symptoms_documented" for blocker in evaluation.blockers.not_documented)


def test_service_rejects_unsupported_scope():
    service = ReadinessService()
    request = PARequest(
        payer="Aetna",
        procedure_code="NOT_A_REAL_PROC",
        dx_codes=["Z00.00"],
        site_of_care="outpatient",
        specialty="Primary Care",
        note_text="Synthetic note text.",
    )

    try:
        service.evaluate(request)
    except UnsupportedScopeError as exc:
        assert "Unsupported request scope" in str(exc)
    else:  # pragma: no cover - assertion guard
        raise AssertionError("Unsupported procedure should raise UnsupportedScopeError")


def test_service_warns_on_blank_note():
    service = ReadinessService()
    request = PARequest(
        payer="Aetna",
        procedure_code="MRI_LUMBAR",
        dx_codes=[],
        site_of_care="outpatient",
        specialty="unknown",
        note_text="",
    )

    warnings = service.validate_request(request)

    assert any("No note text provided" in warning for warning in warnings)
    assert any("No diagnosis codes supplied" in warning for warning in warnings)


def test_service_rejects_unsupported_site_of_care():
    service = ReadinessService()
    request = PARequest(
        payer="Aetna",
        procedure_code="MRI_LUMBAR",
        dx_codes=["M54.5"],
        site_of_care="telehealth",
        specialty="Primary Care",
        note_text="Low back pain x 8 weeks. PT x 8 weeks. No prior imaging. Denies weakness.",
    )

    try:
        service.validate_request(request)
    except UnsupportedScopeError as exc:
        assert "Unsupported site_of_care" in str(exc)
    else:  # pragma: no cover - assertion guard
        raise AssertionError("Unsupported site of care should raise UnsupportedScopeError")


def test_service_rejects_inpatient_site_for_outpatient_only_procedure():
    service = ReadinessService()
    request = PARequest(
        payer="Aetna",
        procedure_code="MRI_LUMBAR",
        dx_codes=["M54.5"],
        site_of_care="inpatient",
        specialty="Primary Care",
        note_text="Low back pain x 8 weeks. PT x 8 weeks. No prior imaging. Denies weakness.",
    )

    try:
        service.evaluate(request)
    except UnsupportedScopeError as exc:
        assert "Supported demo sites: outpatient" in str(exc)
    else:  # pragma: no cover - assertion guard
        raise AssertionError("Inpatient site should be rejected for an outpatient-only procedure")


def test_drift_status_exposes_source_metadata_and_hash():
    service = ReadinessService()

    report = service.get_drift_status()

    assert report.sources
    assert report.any_review_required is False
    assert report.stale_source_count == 0
    first = report.sources[0]
    assert first.source_name.startswith("Aetna CPB 0236")
    assert first.trust_level == "verified"
    assert first.status == "OK"
    assert first.latest_hash == "5688a01dea8d5e55d9bb074fb4184f4b0722c89a7a35aacd343bf3444577e622"
    assert first.rule_source_label
    assert first.freshness_status == "CURRENT"
    assert first.days_since_last_checked is not None
    assert first.days_since_last_checked <= 35
    assert first.latest_snapshot_path == "policy_snapshots/aetna_mri_lumbar/latest.json"
    assert first.review_reason is None


def test_drift_status_can_be_scoped_to_the_evaluated_payer_and_procedure():
    service = ReadinessService()

    affected = service.get_drift_status(payer="Aetna", procedure_code="MRI_LUMBAR")
    unrelated = service.get_drift_status(payer="Aetna", procedure_code="CPAP_DEVICE")

    assert affected.sources
    assert affected.any_review_required is False
    assert unrelated.sources == []
    assert unrelated.any_review_required is False


def test_service_status_includes_rulebook_metadata():
    service = ReadinessService()

    status = service.get_status()

    assert status.rules_version == "1.0"
    assert status.rulebook_active_release_id == "2026-08-22-active-v1.0"


def test_verified_provenance_downgrades_when_monitoring_baseline_is_missing(tmp_path):
    config = load_app_config().model_copy(update={"snapshot_root": tmp_path})
    service = ReadinessService(config)

    evaluation = service.evaluate(attest(service.evaluate(service.get_demo_case_request("MRI-01-complete"))))

    assert evaluation.overall_status == "READY"
    assert evaluation.policy_trust_level == "demo"
    assert evaluation.submission_readiness is False
    assert any("Policy trust remains DEMO" in warning for warning in evaluation.warnings)


def test_verified_provenance_downgrades_when_baseline_hash_does_not_match(tmp_path):
    snapshot_dir = tmp_path / "aetna_mri_lumbar"
    snapshot_dir.mkdir(parents=True)
    snapshot_dir.joinpath("latest.json").write_text(
        json.dumps(
            {
                "id": "aetna_mri_lumbar",
                "payer": "Aetna",
                "procedure_code": "MRI_LUMBAR",
                "url": "https://www.aetna.com/cpb/medical/data/200_299/0236.html",
                "fetched_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "content_hash_sha256": "b" * 64,
            }
        ),
        encoding="utf-8",
    )
    config = load_app_config().model_copy(update={"snapshot_root": tmp_path})
    service = ReadinessService(config)

    evaluation = service.evaluate(attest(service.evaluate(service.get_demo_case_request("MRI-01-complete"))))

    assert evaluation.overall_status == "READY"
    assert evaluation.policy_trust_level == "demo"
    assert evaluation.submission_readiness is False


@pytest.mark.parametrize(
    "note_text, expected_status, expected_blocker",
    [
        (
            "Low back pain with right leg radiculopathy. NSAIDs for 8 weeks with no improvement. "
            "Objective motor exam in the right L5 distribution: ankle dorsiflexion strength 4/5.",
            "PENDING_VERIFICATION",
            None,
        ),
        (
            "Low back pain with right leg radiculopathy. NSAIDs for 4 weeks with no improvement. "
            "Objective motor exam in the right L5 distribution: ankle dorsiflexion strength 4/5.",
            "NOT_READY",
            "cpb_0236_conservative_therapy_weeks",
        ),
        (
            "Low back pain with right leg radiculopathy. NSAIDs for 8 weeks with no improvement.",
            "CANNOT_DETERMINE",
            "objective_motor_or_reflex_change_in_root_distribution",
        ),
        (
            "Low back pain with right leg radiculopathy. NSAIDs for 8 weeks with no improvement. "
            "Patient reports weakness in the right L5 distribution.",
            "CANNOT_DETERMINE",
            "objective_motor_or_reflex_change_in_root_distribution",
        ),
    ],
)
def test_verified_lumbar_policy_branch_positive_negative_missing_and_ambiguous(note_text, expected_status, expected_blocker):
    service = ReadinessService()
    evaluation = service.evaluate(
        PARequest(
            payer="Aetna",
            procedure_code="MRI_LUMBAR",
            dx_codes=["M54.16"],
            site_of_care="outpatient",
            specialty="Orthopedics",
            note_text=note_text,
        )
    )

    assert evaluation.overall_status == expected_status
    assert evaluation.policy_trust_level == "verified"
    if expected_blocker is None:
        assert evaluation.submission_readiness is False
    else:
        blockers = evaluation.blockers.not_documented + evaluation.blockers.not_met + evaluation.blockers.needs_review
        assert any(blocker.key == expected_blocker for blocker in blockers)


@pytest.mark.parametrize(
    (
        "treatment_note",
        "expected_weeks",
        "expected_no_improvement",
        "expected_overall",
        "expected_duration_status",
        "expected_response_status",
    ),
    [
        ("NSAIDs for 6 weeks with no improvement.", 6, True, "PENDING_VERIFICATION", "MET", "MET"),
        (
            "Analgesics for 2 weeks were stopped. NSAIDs and muscle relaxants for 6 weeks with no improvement.",
            6,
            True,
            "PENDING_VERIFICATION",
            "MET",
            "MET",
        ),
        ("NSAIDs for 4 weeks with no improvement.", 4, True, "NOT_READY", "NOT_MET", "MET"),
        ("NSAIDs for 6 weeks with significant improvement.", 6, False, "NOT_READY", "MET", "NOT_MET"),
        ("NSAIDs for 6 weeks.", 6, None, "CANNOT_DETERMINE", "MET", "NOT_DOCUMENTED"),
        (
            "Physical therapy for 6 weeks with no improvement.",
            None,
            None,
            "CANNOT_DETERMINE",
            "NOT_DOCUMENTED",
            "NOT_DOCUMENTED",
        ),
    ],
)
def test_verified_lumbar_conservative_therapy_modalities_duration_and_response_are_independent(
    treatment_note,
    expected_weeks,
    expected_no_improvement,
    expected_overall,
    expected_duration_status,
    expected_response_status,
):
    service = ReadinessService()
    evaluation = service.evaluate(
        PARequest(
            payer="Aetna",
            procedure_code="MRI_LUMBAR",
            dx_codes=["M54.16"],
            site_of_care="outpatient",
            specialty="Orthopedics",
            note_text=(
                "Low back pain with right leg radiculopathy. "
                "Objective motor exam in the right L5 distribution: ankle dorsiflexion strength 4/5. "
                f"{treatment_note}"
            ),
        )
    )

    requirement_statuses = {result.key: result.status for result in evaluation.results}
    assert evaluation.audit_trail.rulebook_active_release_id == "2026-08-22-active-v1.0"
    assert evaluation.facts["cpb_0236_conservative_therapy_weeks"] == expected_weeks
    assert evaluation.facts["cpb_0236_conservative_therapy_no_improvement"] is expected_no_improvement
    assert evaluation.overall_status == expected_overall
    assert requirement_statuses["cpb_0236_conservative_therapy_weeks"] == expected_duration_status
    assert requirement_statuses["cpb_0236_conservative_therapy_no_improvement"] == expected_response_status


@pytest.mark.parametrize(
    "treatment_note",
    [
        ("Muscle relaxants for 2 weeks with no improvement. NSAIDs for 8 weeks with significant improvement."),
        ("NSAIDs for 8 weeks with significant improvement. Muscle relaxants for 2 weeks with no improvement."),
    ],
)
def test_conflicting_therapy_episodes_are_order_independent_and_never_ready(treatment_note):
    evaluation = _evaluate_complete_lumbar_treatment(treatment_note)

    assert evaluation.overall_status == "NEEDS_REVIEW"
    assert evaluation.submission_readiness is False
    assert evaluation.facts["cpb_0236_conservative_therapy_weeks"] is None
    assert evaluation.facts["cpb_0236_conservative_therapy_no_improvement"] is None


def test_duration_and_response_from_unlinked_therapy_sentences_are_not_combined():
    evaluation = _evaluate_complete_lumbar_treatment("NSAIDs for 8 weeks. Muscle relaxants provided no improvement.")

    assert evaluation.overall_status == "NEEDS_REVIEW"
    assert evaluation.submission_readiness is False
    assert {blocker.key for blocker in evaluation.blockers.needs_review} == {
        "cpb_0236_conservative_therapy_weeks",
        "cpb_0236_conservative_therapy_no_improvement",
    }


def test_conflicting_responses_in_one_therapy_sentence_require_review():
    evaluation = _evaluate_complete_lumbar_treatment(
        "Muscle relaxants for 2 weeks gave no improvement, while NSAIDs for 8 weeks gave significant improvement."
    )

    assert evaluation.overall_status == "NEEDS_REVIEW"
    assert evaluation.submission_readiness is False
    assert evaluation.facts["cpb_0236_conservative_therapy_no_improvement"] is None


def test_family_history_diagnosis_does_not_establish_patient_diagnosis():
    service = ReadinessService()
    evaluation = service.evaluate(
        PARequest(
            payer="Aetna",
            procedure_code="CPAP_DEVICE",
            dx_codes=["G47.33"],
            site_of_care="outpatient",
            specialty="Sleep Medicine",
            note_text="Family history: mother has OSA. Patient sleep study completed 2024-05-18. AHI 22.",
        )
    )

    assert evaluation.facts["osa_diagnosis"] is None
    assert evaluation.overall_status == "CANNOT_DETERMINE"
    assert evaluation.submission_readiness is False


def test_uncertain_diagnosis_requires_review_instead_of_becoming_established():
    evaluation = ReadinessService().evaluate(
        PARequest(
            payer="Aetna",
            procedure_code="MRI_LUMBAR",
            dx_codes=["M54.16"],
            site_of_care="outpatient",
            specialty="Orthopedics",
            note_text=(
                "Low back pain with possible lumbar radiculopathy. "
                "Objective motor exam in the right L5 distribution: ankle dorsiflexion strength 4/5. "
                "NSAIDs for 8 weeks with no improvement."
            ),
        )
    )

    assert evaluation.facts["back_pain_with_radiculopathy"] is None
    assert evaluation.overall_status == "NEEDS_REVIEW"
    assert evaluation.submission_readiness is False


def test_planned_therapy_is_not_treated_as_completed_therapy():
    evaluation = _evaluate_complete_lumbar_treatment("Plan: NSAIDs for 8 weeks with no improvement.")

    assert evaluation.facts["cpb_0236_conservative_therapy_weeks"] is None
    assert evaluation.facts["cpb_0236_conservative_therapy_no_improvement"] is None
    assert evaluation.overall_status == "CANNOT_DETERMINE"
    assert evaluation.submission_readiness is False


def test_contradictory_diagnosis_evidence_requires_review():
    evaluation = _evaluate_complete_lumbar_treatment("Low back pain without radiculopathy. NSAIDs for 8 weeks with no improvement.")

    assert evaluation.facts["back_pain_with_radiculopathy"] is None
    assert evaluation.overall_status == "NEEDS_REVIEW"
    assert evaluation.submission_readiness is False


@pytest.mark.parametrize(
    "treatment_note",
    [
        "Muscle relaxants for 2 weeks produced no improvement, whereas NSAIDs for 8 weeks were also documented.",
        "NSAIDs for 8 weeks were documented, while muscle relaxants for 2 weeks produced no improvement.",
        "NSAIDs for 8 weeks were documented and muscle relaxants for 2 weeks produced no improvement.",
    ],
)
def test_cross_therapy_duration_response_candidates_fail_closed(treatment_note):
    evaluation = _evaluate_complete_lumbar_treatment(treatment_note)

    statuses = {result.key: result.status for result in evaluation.results}
    assert evaluation.overall_status == "NEEDS_REVIEW"
    assert evaluation.submission_readiness is False
    assert statuses["cpb_0236_conservative_therapy_weeks"] == "NEEDS_REVIEW"
    assert statuses["cpb_0236_conservative_therapy_no_improvement"] == "NEEDS_REVIEW"
    assert evaluation.facts["cpb_0236_conservative_therapy_weeks"] is None
    assert evaluation.facts["cpb_0236_conservative_therapy_no_improvement"] is None
    assert "__REVIEW_REQUIRED__" not in evaluation.model_dump_json()


@pytest.mark.parametrize(
    "treatment_note",
    [
        "Mother reports she completed NSAIDs for 8 weeks with no improvement.",
        "The patient's mother reports she completed analgesics for 7 weeks without relief.",
        "Father states he finished NSAIDs for 6 weeks with little relief.",
        "The caregiver reports she completed NSAIDs for 8 weeks with no improvement.",
        "NSAIDs for 8 weeks with no improvement were completed by her mother.",
        "NSAIDs for 8 weeks with no improvement were undertaken by the guardian.",
        "NSAIDs for 8 weeks with no improvement were her mother's treatment.",
        "NSAIDs for 8 weeks with no improvement belonged to her father.",
    ],
)
def test_nonpatient_therapy_candidates_do_not_satisfy_patient_requirements(treatment_note):
    evaluation = _evaluate_complete_lumbar_treatment(treatment_note)

    assert evaluation.overall_status == "CANNOT_DETERMINE"
    assert evaluation.submission_readiness is False
    assert evaluation.facts["cpb_0236_conservative_therapy_weeks"] is None
    assert evaluation.facts["cpb_0236_conservative_therapy_no_improvement"] is None


@pytest.mark.parametrize(
    "treatment_note",
    [
        "The plan is NSAIDs for 8 weeks with no improvement expected.",
        "NSAIDs are proposed for 8 weeks with insufficient response expected.",
        "Patient intends to try analgesics for 6 weeks and expects no improvement.",
        "The plan includes NSAIDs for 8 weeks with no improvement expected.",
        "The patient is going to try NSAIDs for 8 weeks with no improvement expected.",
        "NSAIDs for 8 weeks with no improvement will be initiated tomorrow.",
        "NSAIDs for 8 weeks with no improvement should be tried next.",
        "If NSAIDs are tried for 8 weeks, no improvement is expected.",
    ],
)
def test_hypothetical_therapy_candidates_do_not_become_completed_courses(treatment_note):
    evaluation = _evaluate_complete_lumbar_treatment(treatment_note)

    assert evaluation.overall_status == "CANNOT_DETERMINE"
    assert evaluation.submission_readiness is False
    assert evaluation.facts["cpb_0236_conservative_therapy_weeks"] is None
    assert evaluation.facts["cpb_0236_conservative_therapy_no_improvement"] is None


@pytest.mark.parametrize(
    "diagnosis_sentence",
    [
        "Low back pain with radiculopathy that cannot be excluded.",
        "Low back pain with suspected lumbar radiculopathy.",
        "Low back pain with radiculopathy not yet ruled out.",
        "Low back pain with radiculopathy remains possible.",
        "Low back pain with radiculopathy that cannot be ruled out.",
        "Low back pain with questionable radiculopathy.",
        "Low back pain with radiculopathy under consideration.",
        "Low back pain with radiculopathy is being considered.",
        "Low back pain with radiculopathy remains a diagnostic possibility.",
        "Low back pain with radiculopathy remains in the differential.",
        "Low back pain with radiculopathy versus referred pain.",
        "Low back pain with radiculopathy could not be confirmed.",
        "Low back pain with radiculopathy?",
    ],
)
def test_uncertain_diagnosis_candidates_require_review(diagnosis_sentence):
    evaluation = _evaluate_complete_lumbar_treatment(f"{diagnosis_sentence} NSAIDs for 8 weeks with no improvement.")

    assert evaluation.overall_status == "NEEDS_REVIEW"
    assert evaluation.submission_readiness is False
    assert evaluation.facts["back_pain_with_radiculopathy"] is None
    assert "__REVIEW_REQUIRED__" not in evaluation.model_dump_json()


@pytest.mark.parametrize(
    "diagnosis_sentence",
    [
        "Low back pain with radiculopathy, but repeat assessment ruled out radiculopathy.",
        "Repeat assessment ruled out radiculopathy, although low back pain with radiculopathy was documented initially.",
        "Low back pain with radiculopathy was present initially but radiculopathy was later ruled out.",
    ],
)
def test_competing_diagnosis_candidates_require_review(diagnosis_sentence):
    evaluation = _evaluate_complete_lumbar_treatment(f"{diagnosis_sentence} NSAIDs for 8 weeks with no improvement.")

    assert evaluation.overall_status == "NEEDS_REVIEW"
    assert evaluation.submission_readiness is False
    assert evaluation.facts["back_pain_with_radiculopathy"] is None


@pytest.mark.parametrize(
    "objective_sentence",
    [
        "Objective motor exam in the right L5 distribution: strength 4/5 initially, but strength 5/5 on repeat.",
        "Objective motor exam in the right L5 distribution: strength 5/5 on repeat, but initial strength 4/5.",
        "Right L5 distribution strength was 4/5 at first and later strength was 5/5.",
        "Right L5 distribution repeat strength 5/5 after prior strength 4/5.",
        "Right L5 distribution strength improved from 4/5 to 5/5.",
        "Right L5 distribution strength declined from 5/5 to 4/5.",
        "Right L5 distribution reflexes were diminished initially but later reflexes were normal.",
        "Right L5 distribution reflexes were normal on repeat but diminished initially.",
    ],
)
def test_competing_objective_candidates_are_order_independent_and_require_review(objective_sentence):
    evaluation = ReadinessService().evaluate(
        PARequest(
            payer="Aetna",
            procedure_code="MRI_LUMBAR",
            dx_codes=["M54.16"],
            site_of_care="outpatient",
            specialty="Orthopedics",
            note_text=(f"Low back pain with radiculopathy. {objective_sentence} NSAIDs for 8 weeks with no improvement."),
        )
    )

    assert evaluation.overall_status == "NEEDS_REVIEW"
    assert evaluation.submission_readiness is False
    assert evaluation.facts["objective_motor_or_reflex_change_in_root_distribution"] is None
    assert "__REVIEW_REQUIRED__" not in evaluation.audit_trail.model_dump_json()


@pytest.mark.parametrize(
    "objective_sentence, expected_status",
    [
        (
            "Objective motor exam in the right L5 distribution: strength 4/5 cannot be confirmed.",
            "NEEDS_REVIEW",
        ),
        (
            "Objective motor exam in the right L5 distribution: strength 4/5 is under consideration.",
            "NEEDS_REVIEW",
        ),
        (
            "Objective motor exam in the right L5 distribution: strength may be 4/5.",
            "NEEDS_REVIEW",
        ),
        (
            "Objective motor exam in the right L5 distribution: strength might be 4/5.",
            "NEEDS_REVIEW",
        ),
        (
            "Objective motor exam in the right L5 distribution: strength 4/5?",
            "NEEDS_REVIEW",
        ),
        (
            "Objective motor exam in the right L5 distribution: strength 4/5 was documented in her mother.",
            "CANNOT_DETERMINE",
        ),
    ],
)
def test_uncertain_or_nonpatient_objective_candidates_never_produce_ready(objective_sentence, expected_status):
    evaluation = ReadinessService().evaluate(
        PARequest(
            payer="Aetna",
            procedure_code="MRI_LUMBAR",
            dx_codes=["M54.16"],
            site_of_care="outpatient",
            specialty="Orthopedics",
            note_text=(f"Low back pain with radiculopathy. {objective_sentence} NSAIDs for 8 weeks with no improvement."),
        )
    )

    assert evaluation.overall_status == expected_status
    assert evaluation.submission_readiness is False
    assert evaluation.facts["objective_motor_or_reflex_change_in_root_distribution"] is None


@pytest.mark.parametrize(
    "diagnosis_text, expected_status",
    [
        ("OSA?", "NEEDS_REVIEW"),
        ("OSA under consideration.", "NEEDS_REVIEW"),
        ("OSA remains in the differential.", "NEEDS_REVIEW"),
        ("OSA was diagnosed in her mother.", "CANNOT_DETERMINE"),
        ("OSA is her mother's diagnosis.", "CANNOT_DETERMINE"),
    ],
)
def test_uncertain_or_nonpatient_osa_candidates_never_produce_ready(diagnosis_text, expected_status):
    evaluation = ReadinessService().evaluate(
        PARequest(
            payer="Aetna",
            procedure_code="CPAP_DEVICE",
            dx_codes=["G47.33"],
            site_of_care="outpatient",
            specialty="Sleep Medicine",
            note_text=f"{diagnosis_text} Sleep study completed 2024-05-18. AHI 22.",
        )
    )

    assert evaluation.overall_status == expected_status
    assert evaluation.submission_readiness is False
    assert evaluation.facts["osa_diagnosis"] is None


@pytest.mark.parametrize(
    "note_text",
    [
        "OSA. Sleep study completed 2024-05-18? AHI 22.",
        "OSA. Sleep study completed 2024-05-18. AHI 22?",
    ],
)
def test_questioned_cpap_evidence_requires_review(note_text):
    evaluation = ReadinessService().evaluate(
        PARequest(
            payer="Aetna",
            procedure_code="CPAP_DEVICE",
            dx_codes=["G47.33"],
            site_of_care="outpatient",
            specialty="Sleep Medicine",
            note_text=note_text,
        )
    )

    assert evaluation.overall_status == "NEEDS_REVIEW"
    assert evaluation.submission_readiness is False
    assert "__REVIEW_REQUIRED__" not in evaluation.model_dump_json()


def test_demo_policy_can_preserve_ready_status_but_never_be_submission_ready():
    service = ReadinessService()
    evaluation = service.evaluate(attest(service.evaluate(service.get_demo_case_request("CPAP-01-complete"))))

    assert evaluation.overall_status == "READY"
    assert evaluation.policy_trust_level == "demo"
    assert evaluation.submission_readiness is False
    assert any("criteria evaluate to READY" in warning for warning in evaluation.warnings)


def test_stale_policy_snapshot_blocks_submission_readiness(tmp_path):
    _write_policy_snapshot(tmp_path, "2020-01-01T00:00:00Z")
    service = ReadinessService(load_app_config().model_copy(update={"snapshot_root": tmp_path}))

    evaluation = service.evaluate(attest(service.evaluate(service.get_demo_case_request("MRI-01-complete"))))

    assert evaluation.overall_status == "READY"
    assert evaluation.policy_trust_level == "demo"
    assert evaluation.submission_readiness is False


def test_unresolved_policy_drift_blocks_submission_readiness(tmp_path):
    _write_policy_snapshot(
        tmp_path,
        datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    )
    tmp_path.joinpath("drift_log.jsonl").write_text(
        json.dumps({"id": "aetna_mri_lumbar", "event": "POLICY_DRIFT_DETECTED"}) + "\n",
        encoding="utf-8",
    )
    service = ReadinessService(load_app_config().model_copy(update={"snapshot_root": tmp_path}))

    evaluation = service.evaluate(attest(service.evaluate(service.get_demo_case_request("MRI-01-complete"))))

    assert evaluation.overall_status == "READY"
    assert evaluation.policy_trust_level == "demo"
    assert evaluation.submission_readiness is False


def test_malformed_drift_log_fails_policy_trust_closed(tmp_path):
    _copy_current_policy_snapshot(tmp_path)
    tmp_path.joinpath("drift_log.jsonl").write_text("not-json\n", encoding="utf-8")
    service = ReadinessService(load_app_config().model_copy(update={"snapshot_root": tmp_path}))

    drift = service.get_drift_status(payer="Aetna", procedure_code="MRI_LUMBAR")
    evaluation = service.evaluate(attest(service.evaluate(service.get_demo_case_request("MRI-01-complete"))))

    assert drift.any_review_required is True
    assert drift.sources[0].status == "INVALID_DRIFT_LOG"
    assert "not valid JSON" in (drift.sources[0].review_reason or "")
    assert evaluation.overall_status == "READY"
    assert evaluation.policy_trust_level == "demo"
    assert evaluation.submission_readiness is False


def test_later_non_drift_event_does_not_clear_unresolved_drift(tmp_path):
    _copy_current_policy_snapshot(tmp_path)
    tmp_path.joinpath("drift_log.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"id": "aetna_mri_lumbar", "event": "POLICY_DRIFT_DETECTED"}),
                json.dumps({"id": "aetna_mri_lumbar", "event": "BOOTSTRAP_SNAPSHOT_CREATED"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    service = ReadinessService(load_app_config().model_copy(update={"snapshot_root": tmp_path}))

    drift = service.get_drift_status(payer="Aetna", procedure_code="MRI_LUMBAR")
    evaluation = service.evaluate(attest(service.evaluate(service.get_demo_case_request("MRI-01-complete"))))

    assert drift.any_review_required is True
    assert drift.sources[0].status == "REVIEW_REQUIRED"
    assert evaluation.policy_trust_level == "demo"
    assert evaluation.submission_readiness is False


def test_invalid_runtime_rulebook_blocks_submission_readiness(tmp_path):
    source_rules = load_app_config().rules_path.read_text(encoding="utf-8")
    changed_rules = tmp_path / "payer_rules.yaml"
    changed_rules.write_text(source_rules.replace("version: 1.0", "version: 1.0-unreleased", 1), encoding="utf-8")
    service = ReadinessService(load_app_config().model_copy(update={"rules_path": changed_rules}))

    evaluation = service.evaluate(attest(service.evaluate(service.get_demo_case_request("MRI-01-complete"))))

    assert evaluation.overall_status == "READY"
    assert evaluation.policy_trust_level == "demo"
    assert evaluation.submission_readiness is False
    assert evaluation.audit_trail.rulebook_active_release_id == "2026-08-22-active-v1.0"


@pytest.mark.parametrize("mutation", ["hash_mismatch", "missing_content", "future_timestamp"])
def test_invalid_policy_snapshot_integrity_blocks_submission_readiness(tmp_path, mutation):
    config = load_app_config()
    snapshot = json.loads(config.snapshot_root.joinpath("aetna_mri_lumbar", "latest.json").read_text(encoding="utf-8"))
    if mutation == "hash_mismatch":
        snapshot["normalized_text"] = "tampered content\n"
    elif mutation == "missing_content":
        snapshot.pop("normalized_text")
    else:
        snapshot["fetched_at_utc"] = "2099-01-01T00:00:00Z"
        snapshot["last_checked_utc"] = "2099-01-01T00:00:00Z"

    snapshot_dir = tmp_path / "aetna_mri_lumbar"
    snapshot_dir.mkdir(parents=True)
    snapshot_dir.joinpath("latest.json").write_text(json.dumps(snapshot), encoding="utf-8")
    service = ReadinessService(config.model_copy(update={"snapshot_root": tmp_path}))

    drift = service.get_drift_status(payer="Aetna", procedure_code="MRI_LUMBAR")
    evaluation = service.evaluate(attest(service.evaluate(service.get_demo_case_request("MRI-01-complete"))))

    assert drift.any_review_required is True
    assert drift.sources[0].status == "INVALID_SNAPSHOT"
    assert evaluation.overall_status == "READY"
    assert evaluation.policy_trust_level == "demo"
    assert evaluation.submission_readiness is False
