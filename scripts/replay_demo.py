"""Generate synthetic historical decisions and all nine source/target replay reports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from engine.decision_store import DecisionStore
from engine.policies import content_hash
from engine.replay import replay
from engine.schemas import PARequest, PolicyVersion
from engine.service import ReadinessService

INPUT_ROOT = Path(__file__).resolve().parents[1] / "inputs/replay"


def run_demo(output: Path) -> dict:
    # A fresh directory makes reruns explicit and protects previous run artifacts.
    output.mkdir(parents=True, exist_ok=False)
    cases = json.loads((INPUT_ROOT / "cases.json").read_text())
    policies = [PolicyVersion.model_validate_json(path.read_text()) for path in sorted((INPUT_ROOT / "policies").glob("*.json"))]
    service = ReadinessService()
    with DecisionStore(output / "history.sqlite") as store:
        for policy in policies:
            store.add_policy(policy)
            for case in cases:
                request = PARequest.model_validate(case["request"])
                result = service.evaluate(request, policy)
                if case["synthetic_human_verification_fixture"] and result.overall_status == "PENDING_VERIFICATION":
                    # Fabricated historical attestations in a labeled fixture, never a real reviewer.
                    request = PARequest.model_validate(
                        request.model_dump(mode="json")
                        | {
                            "fact_verifications": {
                                item.key: {
                                    "state": "HUMAN_VERIFIED",
                                    "reviewer": "Synthetic replay fixture (not a real human review)",
                                    "verified_at": "2026-01-01T00:00:00Z",
                                    "fingerprint": item.verification_fingerprint,
                                }
                                for item in result.results
                            },
                        }
                    )
                    result = service.evaluate(request, policy)
                store.record(result, f"{policy.version_id}:{case['id']}")
    archive_hash_before = content_hash((output / "history.sqlite").read_bytes().hex())
    count_context = (
        f"{len(cases)} hand-authored synthetic cases across {len(policies)} synthetic policy versions, "
        "constructed to exercise each differential category. Counts demonstrate that the mechanism correctly distinguishes "
        "outcome flips, newly-undeterminable cases, unchanged outcomes with changed reasoning, and resolved refusals. "
        "They are not an estimate of how often real policy changes produce each outcome."
    )
    summary = {
        "count_context": count_context,
        "fixture": "14 hand-authored synthetic cervical MRI cases; three synthetic policy versions, not actual Aetna revisions.",
        "policy_changes": {
            "v1_to_v2": "Conservative therapy minimum 6 to 8 weeks; neurologic red-flag documentation added.",
            "v2_to_v3": "Prior-imaging criterion removed.",
        },
        "case_count": len(cases),
        "historical_decision_count": len(cases) * len(policies),
        "comparisons": [],
    }
    with DecisionStore(output / "history.sqlite", readonly=True) as store:
        for source in policies:
            ids = store.decision_ids(source.policy_id, source.version_id)
            for target in policies:
                report = replay(store, ids, target)
                report["count_context"] = count_context
                filename = f"{source.version_id}-to-{target.version_id}.json"
                (output / filename).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
                summary["comparisons"].append(
                    {
                        "count_context": count_context,
                        "source_version": source.version_id,
                        "target_version": target.version_id,
                        **{
                            key: report[key]
                            for key in (
                                "total_decisions",
                                "categories",
                                "target_outcomes",
                                "newly_required_evidence_missing",
                                "refusals_preserved",
                            )
                        },
                    }
                )
    summary["archive_unchanged_after_replay"] = archive_hash_before == content_hash((output / "history.sqlite").read_bytes().hex())
    if not summary["archive_unchanged_after_replay"]:
        raise AssertionError("Replay changed the historical archive.")
    (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True, help="A new directory for the archive and nine reports.")
    args = parser.parse_args()
    summary = run_demo(args.output_dir)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
