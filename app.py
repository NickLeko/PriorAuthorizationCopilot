from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from engine.config import load_app_config
from engine.demo_cases import expected_overall_status_for_demo_case, featured_demo_cases
from engine.rendering import export_evaluation_payload
from engine.schemas import EvaluationResult, PARequest
from engine.service import ReadinessService, ServiceError
from engine.test_suites import run_cases

BASE_DIR = Path(__file__).resolve().parent


st.set_page_config(page_title="PA Readiness Copilot", layout="wide")

st.markdown(
    """
    <style>
      :root {
        --ink: #1f2937;
        --muted: #5f6b7a;
        --line: #d8dee6;
        --panel: #f5f8fb;
        --ready: #166534;
        --warn: #9a3412;
        --stop: #991b1b;
        --info: #1d4ed8;
      }
      .hero {
        border: 1px solid var(--line);
        border-radius: 18px;
        padding: 1.2rem 1.25rem;
        background: linear-gradient(135deg, #f9fbfd 0%, #eef4f8 100%);
        margin-bottom: 1rem;
      }
      .hero h1 {
        margin: 0 0 0.35rem 0;
        color: var(--ink);
        font-size: 2rem;
      }
      .hero p {
        margin: 0.2rem 0;
        color: var(--muted);
      }
      .status-panel {
        border-radius: 16px;
        border: 1px solid var(--line);
        padding: 1rem 1.1rem;
        margin-bottom: 1rem;
        color: var(--ink);
      }
      .status-panel strong {
        display: block;
        font-size: clamp(1.45rem, 3vw, 2.2rem);
        line-height: 1.1;
        overflow-wrap: anywhere;
        white-space: normal;
        margin-bottom: 0.45rem;
      }
      .status-ready {
        background: #f1f8f2;
        border-left: 6px solid var(--ready);
      }
      .status-not-ready {
        background: #fff5ef;
        border-left: 6px solid var(--warn);
      }
      .status-cannot-determine {
        background: #fff4f4;
        border-left: 6px solid var(--stop);
      }
      .status-needs-review {
        background: #f4f8ff;
        border-left: 6px solid var(--info);
      }
      .status-unknown {
        background: #f4f8ff;
        border-left: 6px solid var(--info);
      }
      .scope-panel {
        border-radius: 16px;
        border: 1px solid var(--line);
        background: var(--panel);
        padding: 1rem 1.1rem;
      }
      .eyebrow {
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--muted);
        margin-bottom: 0.3rem;
      }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_service() -> ReadinessService:
    return ReadinessService(load_app_config(BASE_DIR))


service = get_service()
config = service.config


@st.cache_data(ttl=300)
def get_synthetic_eval_status() -> tuple[int, int, list[dict]]:
    rows = run_cases(str(config.rules_path), str(config.synthetic_cases_path))
    passed = sum(1 for row in rows if row.get("pass") == "✅")
    return passed, len(rows), rows


def load_case_into_session(case: dict) -> None:
    st.session_state["selected_demo_case_id"] = case["id"]
    st.session_state["payer"] = case["payer"]
    st.session_state["procedure_code"] = case["procedure_code"]
    st.session_state["dx_codes"] = ", ".join(case.get("dx_codes", []))
    st.session_state["site_of_care"] = case.get("site_of_care", "outpatient")
    st.session_state["specialty"] = case.get("specialty", "unknown")
    st.session_state["note_text"] = case.get("note_text", "")


def current_request() -> PARequest:
    dx_codes = [item.strip() for item in st.session_state.get("dx_codes", "").split(",") if item.strip()]
    return PARequest(
        payer=st.session_state["payer"],
        procedure_code=st.session_state["procedure_code"],
        dx_codes=dx_codes,
        site_of_care=st.session_state["site_of_care"],
        specialty=st.session_state["specialty"],
        note_text=st.session_state["note_text"],
    )


def status_panel(evaluation: EvaluationResult) -> None:
    status = evaluation.overall_status
    klass = {
        "READY": "status-ready",
        "NOT_READY": "status-not-ready",
        "CANNOT_DETERMINE": "status-cannot-determine",
        "NEEDS_REVIEW": "status-needs-review",
    }.get(status, "status-unknown")

    summaries = {
        "READY": (
            "Administratively ready under the current versioned rules.",
            "All required elements were explicitly documented and met threshold.",
        ),
        "NOT_READY": (
            "Not ready to submit under the current versioned rules.",
            "At least one required element was documented but failed threshold.",
        ),
        "CANNOT_DETERMINE": (
            "Readiness cannot be determined from the documentation provided.",
            "At least one required element was missing or not explicit enough for deterministic extraction.",
        ),
        "NEEDS_REVIEW": (
            "Human review is required before administrative readiness can be determined.",
            "At least one documented result could not be evaluated against the configured categories.",
        ),
    }
    headline, detail = summaries.get(
        status,
        ("Status unavailable.", "Unexpected status returned by the deterministic workflow."),
    )

    st.markdown(
        f"""
        <div class="status-panel {klass}">
          <div class="eyebrow">Decision</div>
          <strong>{status}</strong>
          <div>{headline}</div>
          <div>{detail}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def format_fact_value(value: object) -> str:
    if value is None:
        return "null (not extracted)"
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, str):
        return f'"{value}"'
    return str(value)


def format_rule_operator(requirement) -> str:
    operator = requirement.operator
    if operator == "minimum":
        return f"minimum ≥ {requirement.min:g}"
    if operator == "one_of":
        return f"one of: {', '.join(requirement.allowed)}"
    if operator == "documented":
        return "must be explicitly addressed"
    if operator == "equals_true":
        return "must equal true"
    return "operator not configured"


def render_decision_trace(evaluation: EvaluationResult) -> None:
    requirements_by_key = {requirement.key: requirement for requirement in evaluation.supported_procedure.requirements}
    display_status = {
        "MET": "MET",
        "NOT_MET": "NOT MET",
        "NOT_DOCUMENTED": "MISSING",
        "NEEDS_REVIEW": "NEEDS REVIEW",
    }
    status_icon = {"MET": "✅", "NOT_MET": "⚠️", "NOT_DOCUMENTED": "❌", "NEEDS_REVIEW": "🔎"}

    st.markdown("#### Deterministic decision trace")
    st.caption("Every decision follows the same inspectable path; no generative reasoning layer is added.")
    headers = st.columns([2.2, 1.5, 2.1, 1.7])
    for column, label in zip(
        headers,
        ["1 · NOTE EVIDENCE →", "2 · EXTRACTED FACT →", "3 · PAYER RULE →", "4 · REQUIREMENT RESULT"],
    ):
        with column:
            st.caption(label)

    for result in evaluation.results:
        requirement = requirements_by_key[result.key]
        with st.container(border=True):
            columns = st.columns([2.2, 1.5, 2.1, 1.7])
            with columns[0]:
                if result.evidence_snippets:
                    snippet = result.evidence_snippets[0]
                    st.write(f"“{snippet}”")
                    if len(result.evidence_snippets) > 1:
                        st.caption(f"+{len(result.evidence_snippets) - 1} additional evidence span(s)")
                else:
                    st.caption("No matching note evidence")
            with columns[1]:
                st.caption(result.key)
                st.write(f"**{format_fact_value(evaluation.facts.get(result.key))}**")
            with columns[2]:
                st.caption(result.label)
                st.write(f"`{requirement.operator}` · {format_rule_operator(requirement)}")
            with columns[3]:
                st.write(f"**{status_icon[result.status]} {display_status[result.status]}**")
                st.caption(result.reason)

    st.caption(f"Requirement results resolve deterministically to the overall decision shown above: {evaluation.overall_status}.")


def render_requirement_result(result) -> None:
    default_open = result.status != "MET"
    icon = {"MET": "✅", "NOT_MET": "⚠️", "NOT_DOCUMENTED": "❌", "NEEDS_REVIEW": "🔎"}.get(result.status, "❓")
    with st.expander(f"{icon} {result.label}", expanded=default_open):
        c1, c2 = st.columns([1.2, 2])
        with c1:
            st.metric("Status", result.status)
        with c2:
            st.write(result.reason)

        if result.evidence:
            st.info(f"What the rule expects: {result.evidence}")

        if result.evidence_snippets:
            st.markdown("**Evidence found in the note**")
            for snippet in result.evidence_snippets[:5]:
                st.code(snippet, language="text")
        else:
            st.caption("No supporting snippet was captured for this requirement.")

        if result.evidence_spans:
            refs = [f"{span.start}-{span.end}" for span in result.evidence_spans[:5]]
            st.caption(f"Normalized evidence references: {', '.join(refs)}")


def render_fact_card(label: str, value: object, status: str) -> None:
    if value is None:
        display = "Missing from note"
    elif isinstance(value, bool):
        display = "Documented" if value else "Explicitly denied or absent"
    elif label.endswith("(weeks)"):
        display = f"{value} weeks"
    else:
        display = str(value)

    st.markdown(f"**{label}**")
    st.write(display)
    if status == "NOT_DOCUMENTED":
        st.caption("Missing or not explicit enough for deterministic extraction.")
    elif status == "NOT_MET":
        st.caption("Documented, but below the current rule threshold.")
    elif status == "NEEDS_REVIEW":
        st.caption("Documented, but not evaluable under the configured categories; human review is required.")
    else:
        st.caption("Captured and used in deterministic evaluation.")


def render_scope_panel() -> None:
    st.markdown(
        """
        <div class="scope-panel">
          <div class="eyebrow">Scope</div>
          <strong>This product checks administrative readiness only.</strong>
          <p>It does not make clinical judgments, predict approval, review medical necessity, or take autonomous action.</p>
          <p>Bundled data is synthetic. Input is not screened; do not submit real patient information.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


supported_procedures = service.list_supported_procedures()
payers = sorted({item.payer for item in supported_procedures})
procedures_by_payer = {payer: [item for item in supported_procedures if item.payer == payer] for payer in payers}
registry_rows = [
    {
        "payer": procedure.payer,
        "procedure_code": procedure.procedure_code,
        "display_name": procedure.display_name,
        "category": procedure.metadata.category,
        "rule_family": procedure.metadata.rule_family,
        "trust": procedure.policy_trust_level.upper(),
        "drift_monitored": "Yes" if procedure.monitored_for_drift else "No",
        "rule_source": procedure.provenance.rule_source_label or procedure.provenance.source_name or "n/a",
        "last_rule_update": procedure.metadata.last_rule_update or "n/a",
        "last_reviewed": procedure.provenance.last_reviewed or "n/a",
    }
    for procedure in supported_procedures
]

if "last_eval_payload" not in st.session_state:
    st.session_state["last_eval_payload"] = None
if "letter_text" not in st.session_state:
    st.session_state["letter_text"] = ""
if "letter_meta" not in st.session_state:
    st.session_state["letter_meta"] = {}
if "ack_policy_drift" not in st.session_state:
    st.session_state["ack_policy_drift"] = False
if "selected_demo_case_id" not in st.session_state:
    st.session_state["selected_demo_case_id"] = None
if "payer" not in st.session_state:
    st.session_state["payer"] = payers[0]
if "procedure_code" not in st.session_state:
    st.session_state["procedure_code"] = procedures_by_payer[st.session_state["payer"]][0].procedure_code
if "dx_codes" not in st.session_state:
    st.session_state["dx_codes"] = ""
if "site_of_care" not in st.session_state:
    st.session_state["site_of_care"] = config.allowed_sites[0]
if "specialty" not in st.session_state:
    st.session_state["specialty"] = ""
if "note_text" not in st.session_state:
    st.session_state["note_text"] = ""


st.markdown(
    """
    <div class="hero">
      <h1>Prior Authorization Readiness Copilot</h1>
      <p>Deterministic administrative readiness review for versioned payer rules and synthetic demo cases.</p>
      <p>Narrow, explainable, auditable behavior. No clinical judgment. No approval prediction. No autonomous action.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

hero_cols = st.columns(3)
with hero_cols[0]:
    st.metric("Supported procedures", len(supported_procedures))
with hero_cols[1]:
    st.metric("Monitored policy sources", len(service.policy_sources))
with hero_cols[2]:
    st.metric("Synthetic demo cases", len(service.demo_cases))

render_scope_panel()

with st.sidebar:
    st.header("Quality Gates")
    try:
        passed, total, synthetic_rows = get_synthetic_eval_status()
        if passed == total:
            st.success(f"Synthetic eval suite: {passed}/{total}")
        else:
            st.error(f"Synthetic eval suite: {passed}/{total}")
        st.caption("Coarse fixture-label regression. Exact output shapes are protected separately by acceptance snapshots.")
        with st.expander("View synthetic evaluation details"):
            failures = [row for row in synthetic_rows if row.get("pass") != "✅"]
            if failures:
                for failure in failures:
                    st.write(
                        f"- {failure['id']}: expected `{failure['expected']}`, got `{failure['predicted']}` ({failure['overall_status']})"
                    )
            else:
                st.write("All bundled synthetic cases matched expected labels.")
    except Exception as exc:  # pragma: no cover - defensive UI path
        passed, total = 0, 0
        synthetic_rows = []
        st.error(f"Synthetic eval suite unavailable: {exc}")

    tests_healthy = bool(total and passed == total)

    st.header("Supported Scope")
    for procedure in supported_procedures:
        monitored = "Yes" if procedure.monitored_for_drift else "No"
        st.caption(
            f"{procedure.payer} | {procedure.procedure_code} | {procedure.metadata.category} | "
            f"trust={procedure.policy_trust_level} | drift monitored={monitored}"
        )


drift_report = service.get_drift_status()
rulebook_status = service.get_rulebook_status()
st.subheader("Governance Monitor")
st.caption("Configured monitored sources only. Drift detection is governance-only and never changes rules automatically.")
st.dataframe([source.model_dump(mode="json") for source in drift_report.sources], width="stretch")
if drift_report.any_review_required:
    st.warning(
        "One or more monitored sources require governance review because a policy diff was detected "
        "or the monitoring baseline is stale or missing."
    )
    st.session_state["ack_policy_drift"] = st.checkbox(
        "I acknowledge governance issues may make the affected monitored procedure's demo outputs stale.",
        value=st.session_state["ack_policy_drift"],
    )
else:
    st.success("No monitored-source drift or stale/missing baselines currently require review.")
    st.session_state["ack_policy_drift"] = True

if drift_report.stale_source_count:
    st.warning(
        f"{drift_report.stale_source_count} monitored source(s) are stale relative to the configured check frequency. "
        "This is a governance signal only; it does not auto-change rules."
    )


def policy_gate_blocked(payer: str, procedure_code: str) -> bool:
    scoped_report = service.get_drift_status(payer=payer, procedure_code=procedure_code)
    return scoped_report.any_review_required and not st.session_state["ack_policy_drift"]


if not tests_healthy:
    st.error("Evaluation is gated because the bundled synthetic regression suite is not fully green.")

st.subheader("Rulebook Governance")
st.caption("Versioned reviewed and active snapshots make rule promotion inspectable. Monitoring never promotes rules automatically.")
rulebook_rows = [
    {
        "release_id": release.release_id,
        "stage": release.stage or "unassigned",
        "rules_version": release.rules_version or "n/a",
        "procedures": len(release.procedures),
        "reviewed_at": release.reviewed_at or "n/a",
        "runtime_match": "Yes" if release.runtime_matches else ("No" if release.runtime_matches is False else "n/a"),
    }
    for release in rulebook_status.releases
]
st.dataframe(rulebook_rows, width="stretch")
if rulebook_status.validation_errors:
    st.error("Rulebook validation errors detected.")
    for item in rulebook_status.validation_errors:
        st.write(f"- {item}")
else:
    st.success(f"Active rulebook release: {rulebook_status.active_release_id or 'n/a'}")

with st.expander("Promotion workflow", expanded=False):
    st.write("- Draft: candidate snapshot awaiting human review.")
    st.write("- Reviewed: validated snapshot kept for comparison and audit.")
    st.write("- Active: runtime rulebook intentionally promoted by a human. Drift monitoring never auto-promotes.")

st.subheader("Supported Procedure Registry")
st.caption("Compact view of the current deterministic scope, rule family, provenance label, and drift coverage.")
st.dataframe(registry_rows, width="stretch")
featured_cases = featured_demo_cases(config)

st.subheader("Featured Demo Cases")
st.caption("Seeded examples for live demos. Each one remains fully editable after loading.")
showcase_submitted = False
showcase_message = None

for start in range(0, len(featured_cases), 2):
    cols = st.columns(2)
    for col, case in zip(cols, featured_cases[start : start + 2]):
        with col:
            st.markdown(f"#### {case.showcase.get('title', case.id)}")
            st.write(case.showcase.get("description", "Synthetic demo case."))
            expected_status = expected_overall_status_for_demo_case(case)
            if expected_status:
                st.caption(f"Expected overall status: {expected_status}")
            elif case.expected_label:
                st.caption(f"Fixture label: {case.expected_label}")
            if case.showcase.get("scenario_type"):
                st.caption(f"Scenario: {case.showcase.get('scenario_type')}")
            if case.showcase.get("tags"):
                st.caption(f"Tags: {', '.join(case.showcase.get('tags', []))}")
            st.caption(case.showcase.get("why_interesting", ""))
            if st.button("Load Demo Case", key=f"case_{case.id}", width="stretch"):
                load_case_into_session(case.model_dump(mode="json"))
                case_policy_gate_block = policy_gate_blocked(case.payer, case.procedure_code)
                showcase_submitted = tests_healthy and not case_policy_gate_block
                if showcase_submitted:
                    showcase_message = (
                        "success",
                        f'Loaded "{case.showcase.get("title", case.id)}" and ran the evaluation.',
                    )
                elif case_policy_gate_block:
                    showcase_message = (
                        "info",
                        f'Loaded "{case.showcase.get("title", case.id)}". Acknowledge the drift gate to run it.',
                    )
                else:
                    showcase_message = (
                        "info",
                        f'Loaded "{case.showcase.get("title", case.id)}". Resolve the synthetic eval gate to run it.',
                    )

if showcase_message:
    getattr(st, showcase_message[0])(showcase_message[1])


st.subheader("Evaluate Request")
left, right = st.columns([1.5, 1])

with left:
    with st.form("evaluation_form", clear_on_submit=False):
        payer = st.selectbox("Payer", options=payers, key="payer")
        procedure_options = procedures_by_payer[payer]
        default_index = next(
            (index for index, item in enumerate(procedure_options) if item.procedure_code == st.session_state.get("procedure_code")),
            0,
        )
        selected_procedure = st.selectbox(
            "Procedure",
            options=procedure_options,
            index=default_index,
            format_func=lambda item: f"{item.procedure_code} | {item.display_name}",
            key="procedure_selectbox",
        )
        st.session_state["procedure_code"] = selected_procedure.procedure_code

        st.text_input("Diagnosis codes (comma-separated)", key="dx_codes", placeholder="e.g., M54.16, G47.33")
        st.selectbox("Site of care", options=config.allowed_sites, key="site_of_care")
        st.text_input("Ordering specialty", key="specialty", placeholder="e.g., Orthopedics")
        st.text_area(
            "Synthetic note text",
            key="note_text",
            height=220,
            placeholder="Paste or edit a synthetic note here.",
        )

        submitted = st.form_submit_button(
            "Run deterministic readiness review",
            disabled=not tests_healthy,
        )

with right:
    current_supported = service.get_supported_procedure(
        st.session_state["payer"],
        st.session_state["procedure_code"],
    )
    st.markdown("#### Current Rule Summary")
    st.caption(f"Category: {current_supported.metadata.category}")
    st.caption(f"Rule family: {current_supported.metadata.rule_family}")
    st.caption(f"Trust level: {current_supported.policy_trust_level.upper()}")
    st.caption(f"Rule source: {current_supported.provenance.rule_source_label or current_supported.provenance.source_name or 'n/a'}")
    st.caption(
        f"Rule last updated: {current_supported.metadata.last_rule_update or 'n/a'} | "
        f"Last reviewed: {current_supported.provenance.last_reviewed or 'n/a'}"
    )
    st.caption(f"Drift monitoring: {'Configured' if current_supported.monitored_for_drift else 'Not configured for this procedure'}")
    if current_supported.monitored_for_drift:
        st.caption(
            f"Monitored source: {current_supported.provenance.monitored_source_name or current_supported.provenance.monitored_source_id}"
        )
    for requirement in current_supported.requirements:
        requirement_line = f"- {requirement.label} ({requirement.type})"
        if requirement.min is not None:
            requirement_line += f" | min={requirement.min:g}"
        if requirement.allowed:
            requirement_line += f" | allowed={', '.join(requirement.allowed)}"
        st.write(requirement_line)
    if current_supported.metadata.notes:
        with st.expander("Rule notes", expanded=False):
            for note in current_supported.metadata.notes:
                st.write(f"- {note}")
    with st.expander("Scope and limitations", expanded=False):
        st.write("- Bundled data is synthetic; input is not screened, so do not submit real patient information")
        st.write("- Deterministic rule evaluation only")
        st.write("- No approval prediction")
        st.write("- No medical-necessity or clinical recommendation logic")
        st.write("- Human review remains required before any real submission")


should_run = submitted or showcase_submitted
if should_run:
    st.session_state["letter_text"] = ""
    st.session_state["letter_meta"] = {}
    request = current_request()
    if policy_gate_blocked(request.payer, request.procedure_code):
        st.info("Acknowledge the governance issue for this monitored payer/procedure before running the evaluation.")
        st.session_state["last_eval_payload"] = None
    else:
        try:
            evaluation = service.evaluate(request)
            st.session_state["last_eval_payload"] = evaluation.model_dump(mode="json")
        except ServiceError as exc:
            st.error(str(exc))
            st.session_state["last_eval_payload"] = None


st.subheader("Results")
if not st.session_state["last_eval_payload"]:
    st.info("Run a demo case or submit synthetic input to inspect deterministic readiness results.")
else:
    evaluation = EvaluationResult.model_validate(st.session_state["last_eval_payload"])
    status_panel(evaluation)

    if evaluation.policy_trust_level != "verified":
        st.warning(
            "This procedure currently uses DEMO trust. "
            "The rule logic is still deterministic, but provenance remains curated for demonstration."
        )

    if evaluation.warnings:
        with st.expander("Evaluation warnings", expanded=False):
            for warning in evaluation.warnings:
                st.write(f"- {warning}")

    metric_cols = st.columns(3)
    with metric_cols[0]:
        st.metric(
            "Criteria met",
            f"{evaluation.metrics.criteria_met_count} of {evaluation.metrics.total_requirements}",
        )
    with metric_cols[1]:
        st.metric("Missing", f"{evaluation.metrics.missing_requirement_count} missing")
    with metric_cols[2]:
        st.metric("Needs review", f"{evaluation.metrics.human_review_count} needs review")

    render_decision_trace(evaluation)

    tabs = st.tabs(["Overview", "Requirement Reasoning", "Facts and Evidence", "Audit and Export"])

    with tabs[0]:
        st.markdown("#### Blockers")
        if not evaluation.blockers.not_documented and not evaluation.blockers.not_met and not evaluation.blockers.needs_review:
            st.success("No blockers detected under the current rules.")
        else:
            if evaluation.blockers.not_documented:
                st.markdown("**Missing documentation**")
                for blocker in evaluation.blockers.not_documented:
                    st.write(f"- {blocker.label}: {blocker.reason}")
            if evaluation.blockers.not_met:
                st.markdown("**Documented but below threshold**")
                for blocker in evaluation.blockers.not_met:
                    st.write(f"- {blocker.label}: {blocker.reason}")
            if evaluation.blockers.needs_review:
                st.markdown("**Documented but requiring human review**")
                for blocker in evaluation.blockers.needs_review:
                    st.write(f"- {blocker.label}: {blocker.reason}")

        st.markdown("#### Procedure metadata")
        rule_source_label = (
            evaluation.supported_procedure.provenance.rule_source_label or evaluation.supported_procedure.provenance.source_name or "n/a"
        )
        monitored_source_label = (
            evaluation.supported_procedure.provenance.monitored_source_name
            or evaluation.supported_procedure.provenance.monitored_source_id
            or "n/a"
        )
        st.write(f"- Payer: {evaluation.request.payer}")
        st.write(f"- Procedure: {evaluation.request.procedure_code} ({evaluation.supported_procedure.display_name})")
        st.write(f"- Category: {evaluation.supported_procedure.metadata.category}")
        st.write(f"- Rule family: {evaluation.supported_procedure.metadata.rule_family}")
        st.write(f"- Site of care: {evaluation.request.site_of_care}")
        st.write(f"- Specialty: {evaluation.request.specialty}")
        st.write(f"- Policy trust level: {evaluation.policy_trust_level.upper()}")
        st.write(f"- Required field keys: {', '.join(evaluation.supported_procedure.required_field_keys)}")
        st.write(f"- Rule source: {rule_source_label}")
        st.write(f"- Last rule update: {evaluation.supported_procedure.metadata.last_rule_update or 'n/a'}")
        st.write(f"- Last reviewed: {evaluation.supported_procedure.provenance.last_reviewed or 'n/a'}")
        if evaluation.supported_procedure.monitored_for_drift:
            st.write(f"- Monitored source: {monitored_source_label}")

    with tabs[1]:
        st.caption("Requirement-level reasoning stays deterministic and traceable.")
        for result in evaluation.results:
            render_requirement_result(result)

    with tabs[2]:
        st.markdown("#### Extracted facts")
        for start in range(0, len(evaluation.results), 2):
            cols = st.columns(2)
            for col, result in zip(cols, evaluation.results[start : start + 2]):
                with col:
                    render_fact_card(result.label, evaluation.facts.get(result.key), result.status)

        st.markdown("#### Evidence map")
        for result in evaluation.results:
            with st.expander(result.label, expanded=False):
                spans = evaluation.evidence_map.get(result.key, [])
                if spans:
                    for span in spans:
                        st.code(span.text, language="text")
                        st.caption(f"Character offsets: {span.start}-{span.end}")
                else:
                    st.caption("No explicit evidence span was captured for this requirement.")

    with tabs[3]:
        st.markdown("#### Audit summary")
        audit_cols = st.columns(4)
        with audit_cols[0]:
            st.metric("Run ID", evaluation.audit_trail.run_id[:8])
        with audit_cols[1]:
            st.metric("Note hash", evaluation.audit_trail.note_hash)
        with audit_cols[2]:
            st.metric("Rules version", evaluation.audit_trail.rules_version or "n/a")
        with audit_cols[3]:
            st.metric("Submission ready", "YES" if evaluation.submission_readiness else "NO")

        if evaluation.audit_trail.invariant_errors:
            st.error("Invariant checks require review before trusting this run.")
            for item in evaluation.audit_trail.invariant_errors:
                st.write(f"- {item}")

        with st.expander("Structured provenance", expanded=False):
            st.json(evaluation.provenance)

        letter_type = st.selectbox(
            "Letter type",
            options=["submission_cover_letter", "missing_info_request", "appeal_template"],
            key="letter_type",
        )
        letter_cols = st.columns([1, 1])
        with letter_cols[0]:
            if st.button("Generate deterministic letter", width="stretch"):
                letter_text, letter_meta = service.generate_letter(evaluation, letter_type=letter_type)
                st.session_state["letter_text"] = letter_text
                st.session_state["letter_meta"] = letter_meta
        with letter_cols[1]:
            if st.button("Clear letter", width="stretch"):
                st.session_state["letter_text"] = ""
                st.session_state["letter_meta"] = {}

        if st.session_state["letter_text"]:
            st.markdown("**Letter draft**")
            st.text_area("Deterministic administrative letter", value=st.session_state["letter_text"], height=300)
            st.json(st.session_state["letter_meta"])

        export_payload = export_evaluation_payload(
            evaluation,
            letter_text=st.session_state.get("letter_text") or None,
            letter_meta=st.session_state.get("letter_meta") or None,
        )
        st.download_button(
            "Download JSON artifact",
            data=json.dumps(export_payload, indent=2, sort_keys=True),
            file_name=f"{evaluation.request.payer.lower()}_{evaluation.request.procedure_code.lower()}_{evaluation.audit_trail.run_id[:8]}.json",
            mime="application/json",
        )

        with st.expander("Raw evaluation payload", expanded=False):
            st.json(export_payload)
