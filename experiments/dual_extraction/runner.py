"""Explicit offline comparison of frozen regex and verified synthetic recordings."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from hashlib import sha256
from pathlib import Path

from engine.acceptance import ACCEPTANCE_GOVERNANCE_NOW
from engine.config import load_app_config
from engine.corrections import note_hash
from engine.note_context import EvidenceMap
from engine.policies import content_hash
from engine.schemas import PARequest, PolicyVersion
from engine.service import ReadinessService, ServiceError

from . import recorded as recorded_adapter
from .baseline import DEFAULT_OUTPUT as BASELINE_PATH
from .baseline import normalize_evaluation
from .errors import ExperimentFailure
from .proposals import ExtractionProposal, proposal_from_legacy, proposal_to_legacy
from .reconcile import reconcile
from .recordings import NOTICE, RawAttemptManifest, load_manifest, load_raw_attempt, load_recording

DIRECTORY = Path(__file__).parent
DEFAULT_MANIFEST = DIRECTORY / "fixtures/phase3/manifest.json"
BASELINE_SHA256 = "af9a1805c42df33e2985542a7b85307262dfa0fe8ab33cfcbf7f69d2ece46728"
MODES = ("regex_only", "llm_only", "dual")


def load_frozen_baseline() -> list[dict]:
    try:
        data = BASELINE_PATH.read_bytes()
        if sha256(data).hexdigest() != BASELINE_SHA256:
            raise ValueError("Frozen baseline checksum mismatch.")
        rows = [json.loads(line) for line in data.splitlines()]
        if len(rows) != 178 or len({row["case_id"] for row in rows[1:]}) != 177:
            raise ValueError("Frozen case inventory mismatch.")
        return rows
    except (OSError, ValueError, TypeError, KeyError):
        raise ExperimentFailure("INVALID_FROZEN_BASELINE") from None


def baseline_proposal(row: dict) -> ExtractionProposal:
    evidence = EvidenceMap(row["evidence"])
    evidence.total_counts = row["evidence_counts"].copy()
    proposal = proposal_from_legacy(row["note_text"], (row["facts"], evidence), source="regex:2.7.0")
    if proposal.snapshot.content["states"] != row["states"] or note_hash(row["note_text"]) != row["note_sha256"]:
        raise ExperimentFailure("INVALID_FROZEN_BASELINE")
    return proposal


def bound_extraction(proposal: ExtractionProposal):
    def extract(note):
        if note != proposal.note_text:
            raise ExperimentFailure("NOTE_MISMATCH")
        return proposal_to_legacy(proposal)

    return extract


def policy_scope(row: dict, catalog=None) -> str:
    metadata = row.get("request_metadata")
    required = {"payer", "procedure_code", "dx_codes", "site_of_care", "specialty"}
    if not isinstance(metadata, dict) or not required <= set(metadata):
        return "INCOMPLETE"
    if catalog is None:
        catalog = {(p.payer, p.procedure_code): p for p in ReadinessService().list_supported_procedures()}
    supported = catalog.get((metadata["payer"], metadata["procedure_code"]))
    if supported is None or metadata["site_of_care"] not in supported.metadata.supported_sites:
        return "UNSUPPORTED"
    return "SUPPORTED" if row.get("evaluation") is not None else "INCOMPLETE"


def proposal_view(proposal: ExtractionProposal) -> dict:
    facts, evidence = proposal_to_legacy(proposal)
    return dict(
        source=proposal.source,
        facts=facts,
        fact_types={key: type(value).__name__ for key, value in facts.items()},
        states=proposal.snapshot.content["states"],
        evidence=dict(evidence),
        evidence_counts=evidence.total_counts,
        original_snapshot_hash=proposal.snapshot.content_hash,
        diagnostics=list(proposal.diagnostics),
    )


def comparison_view(record) -> dict:
    return dict(
        reconciliation_version=record.reconciliation_version,
        clinical_verification=record.clinical_verification,
        regex=proposal_view(record.regex),
        recorded_llm=dict(
            recording=record.recorded_llm.recording.model_dump(mode="json"),
            recording_sha256=record.recorded_llm.recording_sha256,
            proposal=proposal_view(record.recorded_llm.proposal),
        ),
        dual=proposal_view(record.dual),
        comparisons=[
            item.model_dump(mode="json")
            | dict(
                value_disagreement=item.values_agree is False,
                citation_set_disagreement=not item.retained_citation_sets_equal,
                citation_order_disagreement=not item.retained_citation_order_equal,
                truncated_or_incomplete_citation_comparison=not item.citation_comparison_complete,
            )
            for item in record.comparisons
        ],
        jointly_captured_therapy_citation_source=record.jointly_captured_therapy_citation_source,
    )


def evaluate_modes(row, record, config, bundle):
    request = PARequest.model_validate(row["request_metadata"] | {"note_text": row["note_text"]})
    if request.fact_verifications or request.corrections:
        raise ExperimentFailure("EVALUATION_FAILURE")
    policy = PolicyVersion.model_validate(row["evaluation"]["policy_version"])
    if row["evaluation"]["bundle_fingerprint"] != bundle:
        raise ExperimentFailure("EXPERIMENT_CONTEXT_CHANGED")
    results = {}
    for mode, proposal in zip(MODES, (record.regex, record.recorded_llm.proposal, record.dual), strict=True):
        service = ReadinessService(config, extractor=bound_extraction(proposal), utc_now_provider=lambda: ACCEPTANCE_GOVERNANCE_NOW)
        result = service.evaluate(request, policy_version=policy)
        if result.bundle_fingerprint != bundle or result.policy_version != policy:
            raise ExperimentFailure("EXPERIMENT_CONTEXT_CHANGED")
        if any(item.verification.state != "UNVERIFIED" for item in result.results):
            raise ExperimentFailure("EVALUATION_FAILURE")
        results[mode] = normalize_evaluation(result.model_dump(mode="json"))
    if results["regex_only"] != row["evaluation"]:
        raise ExperimentFailure("EXPERIMENT_CONTEXT_CHANGED")
    if any(results[mode]["policy_trust_level"] != results["regex_only"]["policy_trust_level"] for mode in MODES):
        raise ExperimentFailure("EXPERIMENT_CONTEXT_CHANGED")
    return results


def downstream_comparison(evaluations):
    requirements = [
        dict(
            key=item["key"],
            statuses={mode: next(r["status"] for r in evaluations[mode]["results"] if r["key"] == item["key"]) for mode in MODES},
        )
        for item in evaluations["regex_only"]["results"]
    ]
    for requirement in requirements:
        requirement["different"] = len(set(requirement["statuses"].values())) > 1
    statuses = {mode: evaluations[mode]["overall_status"] for mode in MODES}
    readiness = {mode: evaluations[mode]["submission_readiness"] for mode in MODES}
    return dict(
        requirements=requirements,
        overall_statuses=statuses,
        submission_readiness=readiness,
        governance={
            mode: dict(
                policy_trust_level=evaluations[mode]["policy_trust_level"],
                bundle_fingerprint=evaluations[mode]["bundle_fingerprint"],
                active_release=evaluations[mode]["audit_trail"]["rulebook_active_release_id"],
            )
            for mode in MODES
        },
        any_requirement_status_difference=any(item["different"] for item in requirements),
        overall_status_difference=len(set(statuses.values())) > 1,
        submission_readiness_difference=len(set(readiness.values())) > 1,
        any_decision_difference=(
            any(item["different"] for item in requirements) or len(set(statuses.values())) > 1 or len(set(readiness.values())) > 1
        ),
    )


def _rate(numerator, denominator, population):
    return dict(
        numerator=numerator,
        denominator=denominator,
        percent=round(100 * numerator / denominator, 4) if denominator else None,
        population=population,
    )


def metrics(cases):
    facts = [item for case in cases if case["comparison"] for item in case["comparison"]["comparisons"]]
    captured = [item for item in facts if item["values_agree"] is not None]
    requirements = [item for case in cases if case["downstream"] for item in case["downstream"]["requirements"]]
    return dict(
        value_agreement_rate=_rate(sum(item["values_agree"] is True for item in captured), len(captured), "both-CAPTURED fact pairs"),
        state_disagreement_rate=_rate(sum(item["state_disagreement"] for item in facts), len(facts), "valid compared fact pairs"),
        citation_disagreement_rate=_rate(
            sum(not item["retained_citation_sets_equal"] for item in facts),
            len(facts),
            "valid fact pairs; retained citation sets, including empty sets",
        ),
        citation_order_disagreement_rate=_rate(
            sum(not item["retained_citation_order_equal"] for item in facts), len(facts), "valid fact pairs; retained citation lists"
        ),
        dual_needs_review_rate=_rate(sum(item["disposition"] == "NEEDS_REVIEW" for item in facts), len(facts), "valid compared facts"),
        downstream_requirement_status_difference_rate=_rate(
            sum(item["different"] for item in requirements),
            len(requirements),
            "requirements in successful three-mode cases; any mode differs",
        ),
    )


def response_accounting(cases):
    groups = {}
    for population in ("actual_model", "synthetic_raw_demonstration"):
        attempts = [case for case in cases if case["attempt_population"] == population]
        statuses = Counter(case["attempt_status"] for case in attempts)
        valid = statuses["VALID_RESPONSE"]
        invalid = statuses["INVALID_RESPONSE"]
        groups[population] = dict(
            attempted_cases=len(attempts),
            declared_responses_received=sum(case["attempt"]["outcome"] == "response" for case in attempts),
            responses_received=sum(case["adaptation_attempted"] for case in attempts),
            valid_adapted_responses=valid,
            invalid_responses=invalid,
            extraction_failures=statuses["EXTRACTION_FAILURE"],
            missing_stored_responses=statuses["MISSING_RECORDING"],
            file_integrity_failures=statuses["STORED_FILE_INTEGRITY_FAILURE"],
            malformed_storage_failures=statuses["MALFORMED_STORAGE"],
            not_attempted_cases=len(cases) - len(attempts),
            successful_three_mode_evaluations=sum(case["evaluations"] is not None for case in attempts),
            invalid_recorded_response_rate=_rate(
                invalid,
                valid + invalid,
                "adapter-rejected / adaptation-attempted raw responses; excludes provider, missing-file, integrity and storage failures",
            ),
            end_to_end_usable_response_rate=_rate(
                valid, len(attempts), "valid adapted responses / all selected model attempts, including all failures"
            ),
        )
    legacy = [case for case in cases if case["recording_kind"] == "hand_authored_adapted"]
    groups["hand_authored_adapted"] = dict(
        selected_recordings=len(legacy),
        valid_recordings=sum(case["recording_status"] == "VALID" for case in legacy),
        missing_recordings=sum(case["recording_status"] == "MISSING" for case in legacy),
        malformed_recordings=sum(case["recording_status"] == "MALFORMED" for case in legacy),
        integrity_failures=sum(case["recording_status"] == "INTEGRITY_FAILURE" for case in legacy),
        measured_llm_performance=False,
    )
    return groups


def adapt_attempt(entry, ref, directory):
    """Storage check precedes adaptation; rejected raw bytes remain untouched."""
    try:
        raw = load_raw_attempt(entry["note_text"], ref, directory)
        if ref.outcome == "extraction_failure":
            entry["attempt_status"] = "EXTRACTION_FAILURE"
            entry["error_code"] = "RECORDED_EXTRACTION_FAILURE"
            return None
        entry["adaptation_attempted"] = True
        try:
            recorded = recorded_adapter.adapt_recorded_response(entry["note_text"], raw.decode("utf-8"))
            if recorded.recording.model_dump(mode="json") != ref.recording.model_dump(mode="json"):
                raise ExperimentFailure("INVALID_RECORDED_RESPONSE")
        except (ExperimentFailure, UnicodeError):
            # An error-shaped reply declared as a response is still rejected;
            # explicit provider failures are separately declared in the manifest.
            entry["attempt_status"] = "INVALID_RESPONSE"
            entry["error_code"] = "INVALID_RECORDED_RESPONSE"
            return None
        entry["attempt_status"] = "VALID_RESPONSE"
        return recorded
    except ExperimentFailure as exc:
        entry["error_code"] = exc.code
        entry["attempt_status"] = exc.code if exc.code in {"MISSING_RECORDING", "STORED_FILE_INTEGRITY_FAILURE"} else "MALFORMED_STORAGE"
        return None


def build_report(*, repo_root: Path | None = None, manifest_path: Path = DEFAULT_MANIFEST) -> dict:
    frozen = load_frozen_baseline()
    manifest = load_manifest(manifest_path)
    raw_manifest = isinstance(manifest, RawAttemptManifest)
    references = {ref.case_id: ref for ref in (manifest.attempts if raw_manifest else manifest.recordings)}
    if set(references) - {row["case_id"] for row in frozen[1:]}:
        raise ExperimentFailure("INVALID_RECORDING_MANIFEST")
    config = load_app_config(repo_root or Path.cwd())
    probe = ReadinessService(config, utc_now_provider=lambda: ACCEPTANCE_GOVERNANCE_NOW)
    bundle = probe._bundle_digest()
    governance = dict(rulebook=probe.get_rulebook_status().model_dump(mode="json"), drift=probe.get_drift_status().model_dump(mode="json"))
    catalog = {(p.payer, p.procedure_code): p for p in probe.list_supported_procedures()}
    cases = []
    for row in frozen[1:]:
        entry = dict(
            case_id=row["case_id"],
            note_text=row["note_text"],
            note_sha256=row["note_sha256"],
            scope=policy_scope(row, catalog),
            known_failure=row["known_failure"],
            demonstration=None,
            recording_status="ABSENT",
            error_code=None,
            comparison=None,
            evaluations=None,
            downstream=None,
            recording_kind=None,
            attempt=None,
            attempt_population=None,
            attempt_status="NOT_ATTEMPTED",
            adaptation_attempted=False,
        )
        ref = references.get(row["case_id"])
        if ref is not None:
            entry["recording_kind"] = "raw_attempt" if raw_manifest else "hand_authored_adapted"
            if raw_manifest:
                entry["attempt"] = ref.model_dump(mode="json")
                entry["attempt_population"] = "actual_model" if manifest.population == "actual_model_study" else manifest.population
            else:
                entry["demonstration"] = ref.demonstration
            try:
                if raw_manifest:
                    recorded = adapt_attempt(entry, ref, manifest_path.parent)
                    if recorded is None:
                        entry["recording_status"] = entry["attempt_status"]
                        cases.append(entry)
                        continue
                else:
                    recorded = load_recording(row["note_text"], ref, manifest_path.parent)
                entry["recording_status"] = "VALID"
                record = reconcile(baseline_proposal(row), recorded)
                entry["comparison"] = comparison_view(record)
                if entry["scope"] == "SUPPORTED":
                    entry["evaluations"] = evaluate_modes(row, record, config, bundle)
                    entry["downstream"] = downstream_comparison(entry["evaluations"])
            except ExperimentFailure as exc:
                if exc.code == "EXPERIMENT_CONTEXT_CHANGED":
                    raise
                entry["error_code"] = exc.code
                if entry["recording_status"] != "VALID":
                    entry["recording_status"] = (
                        "MISSING"
                        if exc.code == "MISSING_RECORDING"
                        else "MALFORMED"
                        if exc.code == "MALFORMED_RECORDING"
                        else "INTEGRITY_FAILURE"
                    )
            except (ServiceError, ValueError, TypeError, KeyError):
                entry["error_code"] = "EVALUATION_FAILURE"
        cases.append(entry)
    if (
        probe._bundle_digest() != bundle
        or probe.get_rulebook_status().model_dump(mode="json") != governance["rulebook"]
        or probe.get_drift_status().model_dump(mode="json") != governance["drift"]
    ):
        raise ExperimentFailure("EXPERIMENT_CONTEXT_CHANGED")
    statuses = Counter(case["recording_status"] for case in cases)
    coverage = dict(
        eligible_synthetic_cases=len(cases),
        policy_supported_cases=sum(case["scope"] == "SUPPORTED" for case in cases),
        incomplete_policy_scope_cases=sum(case["scope"] == "INCOMPLETE" for case in cases),
        unsupported_policy_scope_cases=sum(case["scope"] == "UNSUPPORTED" for case in cases),
        valid_recordings=statuses["VALID"],
        without_recordings=statuses["ABSENT"] + statuses["MISSING"] + statuses["MISSING_RECORDING"],
        absent_manifest_entries=statuses["ABSENT"],
        missing_recording_files=statuses["MISSING"] + statuses["MISSING_RECORDING"],
        malformed_recordings=statuses["MALFORMED"] + statuses["MALFORMED_STORAGE"],
        integrity_failures=statuses["INTEGRITY_FAILURE"] + statuses["STORED_FILE_INTEGRITY_FAILURE"],
        rejected_recordings=(
            statuses["MALFORMED"]
            + statuses["INTEGRITY_FAILURE"]
            + statuses["INVALID_RESPONSE"]
            + statuses["STORED_FILE_INTEGRITY_FAILURE"]
            + statuses["MALFORMED_STORAGE"]
        ),
        invalid_raw_responses=statuses["INVALID_RESPONSE"],
        extraction_failures=statuses["EXTRACTION_FAILURE"],
        successful_three_mode_cases=sum(case["evaluations"] is not None for case in cases),
        extraction_only_compared_cases=sum(case["comparison"] is not None and case["scope"] != "SUPPORTED" for case in cases),
        comparison_failures=sum(case["recording_status"] == "VALID" and case["error_code"] is not None for case in cases),
        known_shared_error_demonstrations=sum(
            case["demonstration"] == "known_shared_error" and case["comparison"] is not None for case in cases
        ),
    )
    return dict(
        report_schema_version=2,
        notice=manifest.notice if raw_manifest else NOTICE,
        clinical_accuracy_claim=False,
        baseline_sha256=BASELINE_SHA256,
        manifest_content_sha256=content_hash(manifest.model_dump(mode="json")),
        governance_clock=ACCEPTANCE_GOVERNANCE_NOW.isoformat(),
        bundle_fingerprint=bundle,
        rulebook=governance["rulebook"],
        drift=governance["drift"],
        coverage=coverage,
        metrics=metrics(cases),
        response_accounting=response_accounting(cases),
        cases=cases,
    )


def summary_markdown(report):
    lines = [
        "# Offline three-mode synthetic experiment",
        "",
        report["notice"],
        "",
        "Structural comparisons only; no clinical accuracy claim. "
        f"Labeled shared-error demonstrations compared: {report['coverage']['known_shared_error_demonstrations']}.",
        "",
        "## Coverage",
        "",
        "| Count | Cases |",
        "| --- | ---: |",
    ]
    lines += [f"| {name} | {value} |" for name, value in report["coverage"].items()]
    lines += ["", "## Structural rates", "", "| Metric | Numerator / denominator | Percent | Population |", "| --- | ---: | ---: | --- |"]
    for name, metric in report["metrics"].items():
        percent = f"{metric['percent']}%" if metric["percent"] is not None else "not available"
        lines.append(f"| {name} | {metric['numerator']} / {metric['denominator']} | {percent} | {metric['population']} |")
    lines += ["", "## Response accounting", "", "Hand-authored and simulated responses are never measured LLM performance."]
    for population, accounting in report["response_accounting"].items():
        lines += ["", f"### {population}", "", "| Count or rate | Value |", "| --- | --- |"]
        for name, value in accounting.items():
            if isinstance(value, dict):
                percent = f"{value['percent']}%" if value["percent"] is not None else "not available"
                value = f"{value['numerator']} / {value['denominator']}; {percent}; {value['population']}"
            lines.append(f"| {name} | {value} |")
    lines += ["", "## Compared cases", "", "| Case | Scope | Three-mode overall statuses |", "| --- | --- | --- |"]
    for case in report["cases"]:
        if case["comparison"]:
            outcome = (
                "; ".join(f"{mode}: {value['overall_status']}" for mode, value in case["evaluations"].items())
                if case["evaluations"]
                else "extraction only; no scope invented"
            )
            lines.append(f"| {case['case_id']} | {case['scope']} | {outcome} |")
    lines += ["", "## Shared-error demonstration", ""]
    for case in report["cases"]:
        if case["demonstration"] == "known_shared_error" and case["comparison"]:
            lines.append(
                f"`{case['case_id']}`: known neither/nor extraction limitation. "
                "Both proposals retain the unsupported affirmative diagnosis as AGREED_CAPTURE; "
                "clinical_verification=false and no automatic READY."
            )
    if report["coverage"]["known_shared_error_demonstrations"] == 0:
        lines.append("No shared-error demonstration was successfully compared in this run.")
    lines += [
        "",
        "## Limits",
        "",
        "The default recordings and bundled raw-response examples are hand-authored synthetic data, not produced by a real LLM. "
        "This run's declared population, provenance and coverage are shown above. "
        "The three Phase 2 fixture notes do not exactly match this corpus and were not silently substituted.",
        "Absent recordings and extraction failures are coverage outcomes, never MISSING clinical facts. "
        "Missing policy scope produces extraction-only comparisons.",
        "Rates include the shared-error demonstration, describe only these compared proposals, "
        "and do not estimate correctness, precision, recall, sensitivity, or population performance.",
        "Citation comparisons cover retained spans only; combined totals can be unknown. "
        "Numeric literal flags are advisory and can flag valid unit normalization.",
        "The historical governance clock does not refresh policy monitoring. "
        "All initial comparisons are unverified; results are stored outside production archives.",
        "",
    ]
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DIRECTORY / "artifacts/phase3")
    args = parser.parse_args(argv)
    try:
        report = build_report(manifest_path=args.manifest)
        successful = [case for case in report["cases"] if case["evaluations"]]
        examples = {"comparisons.json": report}
        examples["three-mode-example.json"] = (
            next((case for case in successful if case["downstream"]["any_requirement_status_difference"]), successful[0])
            if successful
            else None
        )
        shared = next((case for case in successful if case["demonstration"] == "known_shared_error"), None)
        examples["correlated-error-example.json"] = shared
        outputs = {name: json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n" for name, value in examples.items()}
        outputs["summary.md"] = summary_markdown(report)
        for name, text in outputs.items():
            path = args.output_dir / name
            if args.write:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)
            elif not path.exists() or path.read_text() != text:
                print("Offline experiment artifacts differ.")
                return 1
        print("Offline experiment artifacts written." if args.write else "Offline experiment artifacts match.")
        return 0
    except ExperimentFailure as exc:
        print(exc.code)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
