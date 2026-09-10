from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Sequence

from pydantic import ValidationError

from engine.decision_store import DecisionStore
from engine.demo_cases import expected_overall_status_for_demo_case
from engine.policies import create_policy
from engine.rendering import (
    export_evaluation_payload,
    render_cli_evaluation,
    render_drift_status,
    render_rulebook_diff,
    render_rulebook_status,
    write_json_artifact,
)
from engine.replay import replay
from engine.schemas import PARequest, PolicyVersion
from engine.service import ReadinessService, ServiceError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pa-copilot",
        description=(
            "Deterministic prior authorization readiness review for synthetic demo cases. "
            "Administrative readiness only; no clinical judgment or approval prediction."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status", help="Show repo status and supported scope.")

    list_procedures = subparsers.add_parser("list-procedures", help="List supported payer/procedure combinations.")
    list_procedures.add_argument("--json", action="store_true", help="Emit JSON instead of a text table.")

    list_demo_cases = subparsers.add_parser("list-demo-cases", help="List bundled synthetic demo cases.")
    list_demo_cases.add_argument("--json", action="store_true", help="Emit JSON instead of a text table.")

    evaluate = subparsers.add_parser("evaluate", help="Evaluate one bundled synthetic demo case.")
    evaluation_input = evaluate.add_mutually_exclusive_group(required=True)
    evaluation_input.add_argument("--demo-case", help="Case ID from list-demo-cases.")
    evaluation_input.add_argument("--request-file", help="JSON PARequest, including any fact_verifications.")
    evaluate.add_argument("--verifications-file", help="JSON mapping of requirement keys to human attestations.")
    evaluate.add_argument("--json", action="store_true", help="Emit JSON instead of a text summary.")
    evaluate.add_argument("--store", help="Append this decision and its policy snapshot to a SQLite archive.")
    evaluate.add_argument("--decision-id", help="Unique archive identity; defaults to the evaluation run ID.")
    evaluate.add_argument("--policy-id", help="Policy family from policy-list (requires --store and --policy-version).")
    evaluate.add_argument("--policy-version", help="Explicit archived policy version; does not promote runtime rules.")

    export = subparsers.add_parser("export-report", help="Export a stable JSON artifact for one demo case.")
    export.add_argument("--demo-case", required=True, help="Case ID from list-demo-cases.")
    export.add_argument("--output", required=True, help="Output path for the JSON artifact.")
    export.add_argument("--with-letter", action="store_true", help="Include a letter draft in the exported artifact.")
    export.add_argument(
        "--letter-type",
        default="submission_cover_letter",
        choices=["submission_cover_letter", "missing_info_request", "appeal_template"],
        help="Letter type used when --with-letter is set.",
    )

    drift = subparsers.add_parser("drift-status", help="Show current governance-only drift status.")
    drift.add_argument("--json", action="store_true", help="Emit JSON instead of a text summary.")

    rulebook_status = subparsers.add_parser("rulebook-status", help="Show current rulebook registry and validation status.")
    rulebook_status.add_argument("--json", action="store_true", help="Emit JSON instead of a text summary.")

    rulebook_diff = subparsers.add_parser("rulebook-diff", help="Diff two rulebook releases.")
    rulebook_diff.add_argument("--from-release", required=True, help="Source release ID from rulebook/manifest.yaml.")
    rulebook_diff.add_argument("--to-release", required=True, help="Target release ID from rulebook/manifest.yaml.")
    rulebook_diff.add_argument("--json", action="store_true", help="Emit JSON instead of a text summary.")

    validate = subparsers.add_parser("validate-demo-case", help="Validate a bundled synthetic input before evaluation.")
    validate.add_argument("--demo-case", required=True, help="Case ID from list-demo-cases.")

    policy_add = subparsers.add_parser("policy-add", help="Register an immutable JSON policy version.")
    policy_add.add_argument("--store", required=True)
    policy_add.add_argument("--file", required=True, help="Policy descriptor or hash-validated snapshot JSON.")
    policy_list = subparsers.add_parser("policy-list", help="List archived policy snapshots.")
    policy_list.add_argument("--store", required=True)
    decision_show = subparsers.add_parser("decision-show", help="Read an immutable historical decision.")
    decision_show.add_argument("--store", required=True)
    decision_show.add_argument("--decision-id", required=True)
    replay_command = subparsers.add_parser("replay", help="Replay captured evidence; never changes original decisions.")
    replay_command.add_argument("--store", required=True)
    replay_command.add_argument("--policy-id", required=True)
    replay_command.add_argument("--target-version", required=True)
    selection = replay_command.add_mutually_exclusive_group()
    selection.add_argument("--from-version", help="Select all historical decisions under this version.")
    selection.add_argument("--decision-id", action="append", help="Select a historical decision; repeat for multiple cases.")
    replay_command.add_argument("--output", help="Create a new JSON report file (existing paths are rejected).")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "policy-add":
            payload = json.loads(Path(args.file).read_text(encoding="utf-8"))
            policy = PolicyVersion.model_validate(payload) if "content_hash" in payload else create_policy(**payload)
            with DecisionStore(args.store) as store:
                store.add_policy(policy)
            print(json.dumps(policy.model_dump(mode="json"), indent=2, sort_keys=True))
            return 0

        if args.command in {"policy-list", "decision-show", "replay"}:
            with DecisionStore(args.store, readonly=True) as store:
                if args.command == "policy-list":
                    payload = store.list_policies()
                elif args.command == "decision-show":
                    payload = store.get_decision(args.decision_id).model_dump(mode="json")
                else:
                    target = store.get_policy(args.policy_id, args.target_version)
                    ids = args.decision_id if args.decision_id is not None else store.decision_ids(args.policy_id, args.from_version)
                    payload = replay(store, ids, target)
            serialized = json.dumps(payload, indent=2, sort_keys=True) + "\n"
            if args.command == "replay" and args.output:
                with Path(args.output).open("x", encoding="utf-8") as output:
                    output.write(serialized)
                print(args.output)
            else:
                print(serialized, end="")
            return 0

        service = ReadinessService()
        if args.command == "status":
            print(json.dumps(service.get_status().model_dump(mode="json"), indent=2, sort_keys=True))
            return 0

        if args.command == "list-procedures":
            procedures = service.list_supported_procedures()
            if args.json:
                print(json.dumps([item.model_dump(mode="json") for item in procedures], indent=2, sort_keys=True))
            else:
                for item in procedures:
                    monitored = "yes" if item.monitored_for_drift else "no"
                    source_label = item.provenance.rule_source_label or item.provenance.source_name or "n/a"
                    print(
                        f"{item.payer}\t{item.procedure_code}\t{item.display_name}\t"
                        f"category={item.metadata.category}\tfamily={item.metadata.rule_family}\t"
                        f"trust={item.policy_trust_level}\tdrift_monitored={monitored}\t"
                        f"last_update={item.metadata.last_rule_update or 'n/a'}\tsource={source_label}"
                    )
            return 0

        if args.command == "list-demo-cases":
            demo_cases = service.list_demo_case_summaries()
            if args.json:
                print(json.dumps([item.model_dump(mode="json") for item in demo_cases], indent=2, sort_keys=True))
            else:
                for case in demo_cases:
                    title = case.showcase.get("title") or case.id
                    scenario_type = case.showcase.get("scenario_type") or "standard"
                    expectation_parts = []
                    expected_status = expected_overall_status_for_demo_case(case)
                    if expected_status:
                        expectation_parts.append(f"expected_status={expected_status}")
                    expectation = "\t".join(expectation_parts) if expectation_parts else "expectation=n/a"
                    print(f"{case.id}\t{case.payer}\t{case.procedure_code}\t{expectation}\t{scenario_type}\t{title}")
            return 0

        if args.command == "evaluate":
            if bool(args.policy_id) != bool(args.policy_version) or ((args.policy_id or args.decision_id) and not args.store):
                raise ValueError("Policy selection needs --policy-id, --policy-version and --store; --decision-id needs --store.")
            request = (
                PARequest.model_validate_json(Path(args.request_file).read_text(encoding="utf-8"))
                if args.request_file
                else service.get_demo_case_request(args.demo_case)
            )
            if args.verifications_file:
                request = PARequest.model_validate(
                    {
                        **request.model_dump(),
                        "fact_verifications": json.loads(Path(args.verifications_file).read_text(encoding="utf-8")),
                    }
                )
            selected_policy = None
            if args.policy_id:
                with DecisionStore(args.store, readonly=True) as store:
                    selected_policy = store.get_policy(args.policy_id, args.policy_version)
            evaluation = service.evaluate(request, policy_version=selected_policy)
            if args.store:
                with DecisionStore(args.store) as store:
                    store.record(evaluation, args.decision_id)
            if args.json:
                print(json.dumps(export_evaluation_payload(evaluation), indent=2, sort_keys=True))
            else:
                print(render_cli_evaluation(evaluation))
            return 0

        if args.command == "export-report":
            request = service.get_demo_case_request(args.demo_case)
            evaluation = service.evaluate(request)
            letter_text = None
            letter_meta = None
            if args.with_letter:
                letter_text, letter_meta = service.generate_letter(evaluation, letter_type=args.letter_type)
            artifact = export_evaluation_payload(evaluation, letter_text=letter_text, letter_meta=letter_meta)
            output_path = write_json_artifact(artifact, Path(args.output))
            print(output_path)
            return 0

        if args.command == "drift-status":
            report = service.get_drift_status()
            if args.json:
                print(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))
            else:
                print(render_drift_status(report))
            return 0

        if args.command == "rulebook-status":
            report = service.get_rulebook_status()
            if args.json:
                print(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))
            else:
                print(render_rulebook_status(report))
            return 0

        if args.command == "rulebook-diff":
            report = service.get_rulebook_diff(args.from_release, args.to_release)
            if args.json:
                print(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))
            else:
                print(render_rulebook_diff(report))
            return 0

        if args.command == "validate-demo-case":
            request = service.get_demo_case_request(args.demo_case)
            warnings = service.validate_request(request)
            print(f"demo_case={args.demo_case}")
            print(f"payer={request.payer}")
            print(f"procedure_code={request.procedure_code}")
            print(f"site_of_care={request.site_of_care}")
            if warnings:
                print("warnings:")
                for warning in warnings:
                    print(f"- {warning}")
            else:
                print("warnings: none")
            return 0

    except (ValidationError, ValueError, OSError, sqlite3.DatabaseError, TypeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except KeyError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except ServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
