"""Generate the requirement-level baseline report and the human labeling packet.

    python -m evaluation.report            # rewrite docs/evaluation/*
    python -m evaluation.report --check    # fail if the committed files are out of date

Output is deterministic: no timestamps, run IDs or wall-clock values.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, List

from engine import __version__ as ENGINE_VERSION
from engine.fact_contracts import get_fact_contract
from engine.note_context import DRUG_TABLE_PATH
from engine.service import ReadinessService

from .harness import evaluate_dataset, service_predictor
from .metrics import CONTROLS
from .schema import DATASET_DIR, REPO_ROOT, SCORED_TIERS, Dataset, dataset_file_sha256, load_dataset

REPORT_VERSION = 1
OUTPUT_DIR = REPO_ROOT / "docs" / "evaluation"
EVALUATED_DATASETS = ("corpus52_labels.json", "challenge_v1.json")
SEALED_DATASETS = ("holdout_v1.json",)

SCOPE = (
    "Requirement-level agreement between the production regex extractor and written labels on synthetic notes. "
    "It measures extraction proposals. It does not measure authorization readiness, payer approval, medical necessity "
    "or clinical accuracy."
)
LIMITATIONS = [
    "No label has been reviewed by a human or a clinician. Every scored label is provisional and agent-authored.",
    "All notes are synthetic. No note is real clinical documentation.",
    "The datasets are small and were selected, not sampled. Counts are observed failures on these notes; "
    "no population-level error rate is estimated or implied.",
    "The label author had read the extractor source, and for part of the challenge set had seen extractor output before labeling.",
    "The challenge set is adversarial and partly chosen because the extractor was already seen to fail on it. Its counts are a "
    "list of known failures. Its proportions say nothing about real-world or clinical performance and are shown without percentages.",
    "The bundled corpus was written alongside the extractor. Agreement on it shows the extractor still does what its fixtures "
    "expect, not that it is accurate.",
    "READY is structurally unreachable in this harness because no human verifications are supplied. No false-READY rate exists here.",
    "Labels marked needs_review and requirements without a label are excluded from every rate and listed separately.",
    "Evidence coverage and overlap are weak checks. The extractor often cites a whole sentence, so a cited span can overlap the "
    "expected quote and still contain the words that should have disqualified it.",
]


def _dataset_summary(dataset: Dataset, path: Path) -> Dict[str, Any]:
    return {"file": path.relative_to(REPO_ROOT).as_posix(), "sha256": dataset_file_sha256(path)}


def build_report(service: ReadinessService | None = None) -> Dict[str, Any]:
    service = service or ReadinessService()
    predict = service_predictor(service)
    datasets: Dict[str, Any] = {}
    sources: Dict[str, Any] = {}
    for name in EVALUATED_DATASETS:
        path = DATASET_DIR / name
        dataset = load_dataset(path)
        datasets[dataset.dataset_id] = evaluate_dataset(dataset, predict)
        sources[dataset.dataset_id] = _dataset_summary(dataset, path)
    sealed = {}
    for name in SEALED_DATASETS:
        path = DATASET_DIR / name
        raw = json.loads(path.read_text(encoding="utf-8"))
        sealed[raw["dataset_id"]] = {
            "file": path.relative_to(REPO_ROOT).as_posix(),
            "sha256": dataset_file_sha256(path),
            "cases": len(raw["cases"]),
            "evaluated": False,
            "reason": "Sealed holdout. Not labeled and never run through the extractor.",
        }
    return {
        "report_version": REPORT_VERSION,
        "scope": SCOPE,
        "limitations": LIMITATIONS,
        "population_error_rate_estimate": None,
        "system_under_test": {
            "engine_version": ENGINE_VERSION,
            "path": "engine.service.ReadinessService.evaluate, no verifications, no corrections",
            "rules_version": str(service.rules.get("version")),
            "drug_table_sha256": sha256(DRUG_TABLE_PATH.read_bytes()).hexdigest(),
        },
        "dataset_files": sources,
        "datasets": datasets,
        "sealed_holdouts": sealed,
    }


def _fmt(entry: Dict[str, Any], percent: bool = True) -> str:
    if entry["value"] is None:
        return f"not measured (0/{entry['denominator']})" if entry["denominator"] else "not measured (no eligible labels)"
    if not percent:
        return f"{entry['numerator']} of {entry['denominator']}"
    return f"{entry['numerator']}/{entry['denominator']} ({entry['value'] * 100:.1f}%)"


def _metric_rows(summary: Dict[str, Any], percent: bool = True) -> List[str]:
    names = [
        ("false_met", "False MET"),
        ("met_precision", "MET precision"),
        ("missed_met", "Missed MET"),
        ("met_recall", "MET recall"),
        ("over_abstention", "Over-abstention"),
        ("abstention_rate", "Abstention rate"),
        ("review_rate", "Review rate"),
        ("decided_coverage", "Decided coverage"),
        ("exact_agreement", "Exact agreement"),
        ("acceptable_agreement", "Acceptable agreement"),
        ("evidence_coverage", "Evidence coverage"),
        ("evidence_overlap", "Evidence overlap"),
    ]
    rows = ["| Metric | Result | Denominator |", "| --- | --- | --- |"]
    for key, label in names:
        entry = summary[key]
        rows.append(f"| {label} | {_fmt(entry, percent)} | {entry.get('denominator_meaning', 'all scored labels')} |")
    return rows


def _confusion(summary: Dict[str, Any]) -> List[str]:
    matrix = summary["confusion_matrix"]
    states = list(matrix)
    rows = ["| Expected \\ Observed | " + " | ".join(states) + " |", "| --- | " + " | ".join("---:" for _ in states) + " |"]
    rows += [f"| {expected} | " + " | ".join(str(matrix[expected][observed]) for observed in states) + " |" for expected in states]
    return rows


def render_markdown(report: Dict[str, Any]) -> str:
    out: List[str] = [
        "# Requirement-level extraction baseline",
        "",
        "Generated by `python -m evaluation.report`. Do not edit by hand.",
        "",
        report["scope"],
        "",
        "## Read this first",
        "",
    ]
    out += [f"- {item}" for item in report["limitations"]]
    system = report["system_under_test"]
    out += [
        "",
        f"System under test: engine {system['engine_version']}, rules {system['rules_version']}, {system['path']}.",
        "",
    ]
    for dataset_id, data in report["datasets"].items():
        counts = data["label_counts"]
        percent = data["split"] != "challenge"
        out += [
            f"## Dataset `{dataset_id}` ({data['split']})",
            "",
            data["description"],
            "",
            f"- Notes: {data['note_authorship']}",
            f"- Selection: {data['selection']}",
            f"- Cases: {data['cases']}; requirement slots: {data['requirement_slots']}",
            f"- Labels: {counts['verified']} verified, {counts['provisional']} provisional, "
            f"{counts['needs_review']} needs review (unscored), {len(data['unlabeled_requirements'])} unlabeled (unscored)",
            f"- Source cases with no labels at all: {len(data['unlabeled_source_cases'])}",
            f"- Cases whose extractor output was seen before labeling: {data['cases_with_output_seen_before_labeling']}",
            "",
        ]
        for tier in SCORED_TIERS:
            block = data["tiers"][tier]
            aggregate = block["aggregate"]
            out += [f"### {tier.capitalize()} labels", ""]
            if aggregate["scored_labels"] == 0:
                out += [f"No {tier} labels exist. Nothing is reported for this tier.", ""]
                continue
            out += [f"Scored labels: {aggregate['scored_labels']}.", ""]
            if not percent:
                out += ["Adversarial set: counts only. These are known failures, not rates.", ""]
            out += _metric_rows(aggregate, percent)
            flags = ", ".join(aggregate["utility_flags"]) or "none"
            out += ["", f"Utility flags: {flags}.", "", "Confusion matrix (all requirements):", ""]
            out += _confusion(aggregate)
            out += ["", "Per requirement:", "", "| Requirement | Scored | False MET | Missed MET | MET precision | MET recall |"]
            out += ["| --- | ---: | --- | --- | --- | --- |"]
            for key, summary in block["by_requirement"].items():
                out.append(
                    f"| `{key}` | {summary['scored_labels']} | {_fmt(summary['false_met'], percent)} | "
                    f"{_fmt(summary['missed_met'], percent)} | {_fmt(summary['met_precision'], percent)} | "
                    f"{_fmt(summary['met_recall'], percent)} |"
                )
            out += [
                "",
                "Controls on the same labels. A constant predictor must not look good:",
                "",
                "| Predictor | False MET | MET recall | Decided coverage | Degenerate | Flags |",
                "| --- | --- | --- | --- | --- | --- |",
                f"| Production extractor | {_fmt(aggregate['false_met'], percent)} | {_fmt(aggregate['met_recall'], percent)} | "
                f"{_fmt(aggregate['decided_coverage'], percent)} | {'no' if aggregate['meets_minimum_utility'] else 'yes'} | {flags} |",
            ]
            for control in CONTROLS:
                summary = block["controls"][control]
                out.append(
                    f"| {control} | {_fmt(summary['false_met'], percent)} | {_fmt(summary['met_recall'], percent)} | "
                    f"{_fmt(summary['decided_coverage'], percent)} | {'no' if summary['meets_minimum_utility'] else 'yes'} | "
                    f"{', '.join(summary['utility_flags']) or 'none'} |"
                )
            out += [
                "",
                "'Degenerate: no' only means the predictor is not one of these constant baselines. It is not a quality bar.",
                "",
            ]
        case_level = data["case_level"]
        out += [
            "### Case level",
            "",
            f"{case_level['note']} Fully scored cases: {case_level['fully_scored_cases']} of {data['cases']}. "
            f"Label tiers used: {', '.join(case_level['label_tiers_used']) or 'none'}.",
            "",
            "| Measure | Result | Denominator |",
            "| --- | --- | --- |",
        ]
        for key, label in (
            ("false_all_met", "All requirements MET when at least one must not be"),
            ("missed_all_met", "Not all MET when every requirement is expected MET"),
            ("false_met_hidden_by_another_blocker", "False MET hidden by another blocker"),
        ):
            entry = case_level[key]
            out.append(f"| {label} | {entry['numerator']}/{entry['denominator']} | {entry['denominator_meaning']} |")
        depth = case_level["blocker_depth"]
        out += [
            "",
            f"Blocker depth: {depth['single_blocker_cases']} of {depth['denominator']} non-passing cases are blocked by exactly one "
            "requirement. Only in those can a single false MET change the overall status; in the rest it stays hidden "
            f"(cases by number of blocking requirements: {depth['cases_by_blocking_requirements']}).",
            "",
            f"READY: not reachable. {case_level['ready']['reason']}",
            "",
        ]
        failures = data["observed_failures"]
        out += [f"### Observed failures ({len(failures)})", ""]
        if failures:
            out += ["| Case | Requirement | Class | Expected | Observed | Phenomena |", "| --- | --- | --- | --- | --- | --- |"]
            for row in failures:
                out.append(
                    f"| {row['case_id']} | `{row['requirement_key']}` | {row['error_class']} | {row['expected_state']} | "
                    f"{row['observed_state']} | {', '.join(row['phenomena']) or '-'} |"
                )
        else:
            out.append("None against the scored labels.")
        out += ["", f"### Unscored requirements ({len(data['unscored_needs_review']) + len(data['unlabeled_requirements'])})", ""]
        if data["unscored_needs_review"]:
            out += ["| Case | Requirement | Observed | Question for a reviewer |", "| --- | --- | --- | --- |"]
            for row in data["unscored_needs_review"]:
                out.append(f"| {row['case_id']} | `{row['requirement_key']}` | {row['observed_state']} | {row['question_for_reviewer']} |")
        for row in data["unlabeled_requirements"]:
            out.append(f"- Unlabeled: {row['case_id']} `{row['requirement_key']}`")
        for case_id in data["unlabeled_source_cases"]:
            out.append(f"- Source case with no labels: {case_id}")
        out.append("")
    out += ["## Sealed holdouts", ""]
    for dataset_id, data in report["sealed_holdouts"].items():
        out.append(f"- `{dataset_id}`: {data['cases']} cases, not evaluated. {data['reason']}")
    return "\n".join(out) + "\n"


PACKET_COLUMNS = [
    "priority",
    "dataset",
    "case_id",
    "procedure",
    "requirement_key",
    "note_text",
    "proposed_state",
    "other_acceptable_states",
    "evidence_quote",
    "rationale",
    "uncertainty",
    "question",
    "reviewer_state",
    "reviewer_other_acceptable_states",
    "reviewer_evidence_quote",
    "reviewer_comment",
    "reviewer_name",
    "reviewed_on",
]


def build_packet_rows() -> List[Dict[str, str]]:
    """Rows for a human reviewer. Extractor output is deliberately absent so the reviewer stays blind to it."""
    rows: List[Dict[str, str]] = []
    for name in EVALUATED_DATASETS:
        dataset = load_dataset(DATASET_DIR / name)
        for case in dataset.cases:
            for label in case.labels:
                if label.review_status == "verified":
                    continue
                priority = (
                    "1-decide" if label.review_status == "needs_review" else {"high": "2", "medium": "2", "low": "3"}[label.uncertainty]
                )
                rows.append(
                    {
                        "priority": priority if priority == "1-decide" else f"{priority}-confirm",
                        "dataset": dataset.dataset_id,
                        "case_id": case.case_id,
                        "procedure": case.procedure_code,
                        "requirement_key": label.requirement_key,
                        "note_text": case.note_text or "",
                        "proposed_state": label.expected_state or "",
                        "other_acceptable_states": ", ".join(s for s in label.acceptable_states if s != label.expected_state),
                        "evidence_quote": label.evidence_quote or "",
                        "rationale": label.rationale,
                        "uncertainty": label.uncertainty,
                        "question": label.uncertainty_note or "",
                    }
                )
    holdout = load_dataset(DATASET_DIR / SEALED_DATASETS[0], allow_sealed_holdout=True)
    for case in holdout.cases:
        rows.append(
            {
                "priority": "4-label-from-scratch",
                "dataset": holdout.dataset_id,
                "case_id": case.case_id,
                "procedure": case.procedure_code,
                "requirement_key": "(all requirements of this procedure)",
                "note_text": case.note_text or "",
                "question": "Sealed holdout. Label every requirement without running the tool on this note.",
            }
        )
    rows.sort(key=lambda row: (row["priority"], row["dataset"], row["case_id"], row["requirement_key"]))
    return [{column: row.get(column, "") for column in PACKET_COLUMNS} for row in rows]


def render_packet_csv(rows: List[Dict[str, str]]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=PACKET_COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


CPB_0236_CRITERION = (
    "Persistent back or neck pain with radiculopathy as evidenced by pain plus objective findings of motor or reflex changes "
    "in the specific nerve root distribution, and no improvement after 6 weeks of conservative therapy"
)
CPB_0236_FOOTNOTE_1 = "Conservative therapy = moderate activity, analgesics, non-steroidal anti-inflammatory drugs, muscle relaxants."
DECISION_LABELS = {
    "textual": "Reading of the text. A careful non-clinician can decide.",
    "policy": "Policy or rule interpretation. Needs whoever owns the policy reading; a reader's view is provisional.",
    "clinical": "Clinical judgment. Needs a clinician; leave open otherwise.",
    None: "Not classified.",
}


def _rule_text(requirement: Any) -> str:
    if requirement.operator == "minimum":
        return f"value must be at least {requirement.min:g}"
    if requirement.operator == "one_of":
        return "value must be one of: " + ", ".join(requirement.allowed)
    if requirement.operator == "documented":
        return "must be explicitly addressed, present or denied"
    return "must be affirmatively documented"


def render_decision_packet(service: ReadinessService | None = None) -> str:
    """Compact first-pass review packet. Shows proposed labels only; extractor output is never included."""
    service = service or ReadinessService()
    spec = json.loads((DATASET_DIR / "decision_packet_v1.json").read_text(encoding="utf-8"))
    loaded = {}
    for name in EVALUATED_DATASETS:
        dataset = load_dataset(DATASET_DIR / name)
        loaded[dataset.dataset_id] = {case.case_id: case for case in dataset.cases}
    requirements = {
        (item.payer, item.procedure_code): {req.key: req for req in item.requirements} for item in service.list_supported_procedures()
    }
    grouped: Dict[tuple, List[str]] = {}
    for entry in spec["entries"]:
        grouped.setdefault((entry["dataset"], entry["case_id"]), []).append(entry["requirement_key"])
    counts = {"textual": 0, "policy": 0, "clinical": 0}
    glossary: Dict[str, str] = {}
    body: List[str] = []
    number = 0
    for (dataset_id, case_id), keys in sorted(grouped.items(), key=lambda pair: pair[0][1]):
        case = loaded[dataset_id][case_id]
        labels = {label.requirement_key: label for label in case.labels}
        body += [f"## {case_id} ({case.procedure_code})", "", f"> {case.note_text}", ""]
        for key in keys:
            label = labels[key]
            requirement = requirements[(case.payer, case.procedure_code)][key]
            glossary[f"{key} {case.procedure_code}"] = (
                f"- `{key}` ({case.procedure_code}): {_rule_text(requirement)}. {get_fact_contract(key).meaning}"
            )
            number += 1
            counts[label.decision_type] += 1
            others = [state for state in label.acceptable_states if state != label.expected_state]
            status = "open question" if label.review_status == "needs_review" else "provisional"
            quote = f'"{label.evidence_quote}"' if label.evidence_quote else "none in the note"
            body += [
                f"**{number}. `{key}`** ({label.decision_type})",
                "",
                f"- Proposed: **{label.expected_state}** ({status})" + (f"; also defensible: {', '.join(others)}" if others else ""),
                f"- Evidence: {quote}",
                f"- Why: {label.rationale}",
                f"- Ambiguity: {label.uncertainty_note or 'none identified by the label author'}",
                "- Decision: state `____` also defensible `____` quote `____` comment `____`",
                "",
            ]
    head = [
        "# Compact decision packet (first review pass)",
        "",
        "Generated by `python -m evaluation.report`. Do not edit by hand; record decisions in the dataset files.",
        "",
        f"{number} label decisions across {len(grouped)} synthetic notes. Review this before the full "
        "[labeling packet](labeling_packet.csv).",
        "",
        "## How to use this",
        "",
        "- Decide each label from the note and the wording below. Do not run the tool on these notes first.",
        "- The tool's output is deliberately absent. Some rows are ones where the tool agreed with the proposed label and some are "
        "ones where it did not. They are not marked, so a row's presence tells you nothing about what the tool did.",
        "- Proposed labels are agent-authored. Disagree freely.",
        "- Completing this packet is label review. It is not clinical validation of the tool or of the labels.",
        "- All notes are synthetic.",
        "",
        "## Decision types",
        "",
        f"- textual ({counts['textual']}): {DECISION_LABELS['textual']} These can be recorded as verified.",
        f"- policy ({counts['policy']}): {DECISION_LABELS['policy']} Record your view and leave the label unverified.",
        f"- clinical ({counts['clinical']}): {DECISION_LABELS['clinical']}",
        "",
        "## Policy wording",
        "",
        f'- `MRI_LUMBAR`, Aetna CPB 0236 as stored in the repository snapshot: "{CPB_0236_CRITERION}." Footnote 1: "{CPB_0236_FOOTNOTE_1}"',
        "- `MRI_CERVICAL`, `MRI_KNEE`, `CPAP_DEVICE`: no payer policy text. These are synthetic demonstration rules, "
        "so a policy decision here means deciding what the demo rule should mean.",
        "",
        "## Requirements",
        "",
        *[glossary[key] for key in sorted(glossary)],
        "",
    ]
    return "\n".join(head + body)


def outputs() -> Dict[Path, str]:
    report = build_report()
    return {
        OUTPUT_DIR / "requirement_level_baseline.json": json.dumps(report, indent=2, sort_keys=True) + "\n",
        OUTPUT_DIR / "requirement_level_baseline.md": render_markdown(report),
        OUTPUT_DIR / "labeling_packet.csv": render_packet_csv(build_packet_rows()),
        OUTPUT_DIR / "decision_packet.md": render_decision_packet(),
    }


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Requirement-level extraction baseline (evaluation only).")
    parser.add_argument("--check", action="store_true", help="Verify committed reports are current; write nothing.")
    args = parser.parse_args(argv)
    stale = []
    for path, content in outputs().items():
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                stale.append(path.relative_to(REPO_ROOT).as_posix())
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            print(path.relative_to(REPO_ROOT).as_posix())
    if stale:
        print("Out of date: " + ", ".join(stale), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
