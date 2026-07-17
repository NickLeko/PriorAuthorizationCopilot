from engine.schemas import PARequest
from engine.service import ReadinessService, UnsupportedScopeError


def test_service_evaluates_known_ready_demo_case():
    service = ReadinessService()
    request = service.get_demo_case_request("MRI-01-complete")

    evaluation = service.evaluate(request)

    assert evaluation.overall_status == "READY"
    assert evaluation.submission_readiness is True
    assert evaluation.audit_trail.note_hash
    assert evaluation.audit_trail.evidence_map["conservative_therapy_weeks"]
    assert evaluation.results[0].evidence_spans


def test_service_returns_cannot_determine_for_missing_documentation_case():
    service = ReadinessService()
    request = service.get_demo_case_request("CPAP-02-borderline")

    evaluation = service.evaluate(request)

    assert evaluation.overall_status == "CANNOT_DETERMINE"
    assert evaluation.blockers.not_documented
    assert not evaluation.submission_readiness


def test_unrecognized_imaging_result_is_documented_not_met_and_requires_review():
    service = ReadinessService()
    request = PARequest(
        payer="Aetna",
        procedure_code="MRI_LUMBAR",
        dx_codes=["M54.5"],
        site_of_care="outpatient",
        specialty="Primary Care",
        note_text="Low back pain x 8 weeks. PT x 8 weeks. Denies weakness. MRI showed edema.",
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
    assert evaluation.metrics.needs_review_count == 1
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

    assert evaluation.overall_status == "READY"
    assert evaluation.supported_procedure.procedure_code == "MRI_CERVICAL"
    assert evaluation.supported_procedure.metadata.rule_family == "spine_mri_conservative_therapy"


def test_service_evaluates_new_knee_demo_case():
    service = ReadinessService()
    request = service.get_demo_case_request("MRI-KNEE-01-ready")

    evaluation = service.evaluate(request)

    assert evaluation.overall_status == "READY"
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
    assert report.any_review_required is True
    assert report.stale_source_count == 0
    first = report.sources[0]
    assert first.source_name == "Aetna CPB 0157"
    assert first.trust_level == "unverified"
    assert first.status == "NO_BASELINE"
    assert first.latest_hash is None
    assert first.rule_source_label
    assert first.freshness_status == "UNKNOWN"
    assert first.days_since_last_checked is None
    assert first.latest_snapshot_path == "policy_snapshots/aetna_mri_lumbar/latest.json"
    assert first.review_reason


def test_service_status_includes_rulebook_metadata():
    service = ReadinessService()

    status = service.get_status()

    assert status.rules_version == "0.6"
    assert status.rulebook_active_release_id == "2026-07-17-active-v0.6"
