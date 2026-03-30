# -*- coding: utf-8 -*-


import streamlit as st
import json
import uuid
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from engine.rules_loader import load_rules
from engine.extract import extract_facts
from engine.evaluate import (
    evaluate_requirements,
    compute_readiness_score,
    compute_overall_status,
)
from engine.provenance import (
    get_provenance_entry,
    load_provenance,
    normalized_dx_codes,
    policy_trust_from_provenance,
)

BASE_DIR = Path(__file__).resolve().parent

# Schema + write-only letter drafting
from engine.schemas import PARequest, ReadinessReport, RequirementResult
from engine.letter_draft import draft_letter as draft_letter_writeonly

# Governance: policy drift monitor (offline UI reads artifacts; does not fetch internet)
from engine.policy_monitor import load_policy_sources, read_latest_snapshot


# ----------------------------
# Page config + CSS
# ----------------------------
st.set_page_config(page_title="PA Readiness Copilot", layout="wide")

st.markdown(
    """
    <style>
      html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
        height: 100% !important;
        overflow: auto !important;
        -webkit-overflow-scrolling: touch !important;
      }
      header[data-testid="stHeader"] { position: relative !important; }
      section[data-testid="stSidebar"], div[data-testid="stVerticalBlock"] { overflow: visible !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("PA Readiness Copilot")
st.caption("Administrative decision support only. Not clinical decision support, approval prediction, or billing advice.")


# ----------------------------
# Session state initialization
# ----------------------------
if "last_eval" not in st.session_state:
    st.session_state.last_eval = None
if "test_rows" not in st.session_state:
    st.session_state.test_rows = None

# Letter UI state (write-only)
if "letter_text" not in st.session_state:
    st.session_state.letter_text = ""
if "letter_meta" not in st.session_state:
    st.session_state.letter_meta = {}
if "letter_error" not in st.session_state:
    st.session_state.letter_error = ""

# Policy drift acknowledge gate state
if "ack_policy_drift" not in st.session_state:
    st.session_state.ack_policy_drift = False


# ----------------------------
# Load rules + provenance
# ----------------------------
RULES_PATH = "rules/payer_rules.yaml"
rules = load_rules(RULES_PATH)
payers = sorted(rules["payers"].keys())

PROV_PATH = "rules/provenance.yaml"
prov = load_provenance(PROV_PATH)

SITE_OPTIONS = ["outpatient", "inpatient", "ASC", "office"]


# ----------------------------
# Sidebar: System Health (auto tests, cached)
# ----------------------------
st.sidebar.markdown("### 🧪 System Health")

# Manual cache bust button (prevents stale failures after edits)
if st.sidebar.button("🔄 Refresh test health (clear cache)", width="stretch"):
    st.cache_data.clear()
    st.rerun()


@st.cache_data(ttl=300)
def _get_test_health():
    from engine.test_suites import run_cases

    results = run_cases("rules/payer_rules.yaml", "inputs/synthetic_cases.json")
    passed = sum(1 for r in results if r.get("pass") == "✅")
    total = len(results)
    return passed, total, results


try:
    passed, total, test_results_cached = _get_test_health()
    pass_rate = (passed / total * 100) if total > 0 else 0.0

    tests_healthy = (total > 0 and passed == total)
    st.session_state["tests_healthy"] = tests_healthy

    if pass_rate >= 90:
        st.sidebar.success(f"✅ Tests: {passed}/{total} ({pass_rate:.0f}%)")
    elif pass_rate >= 70:
        st.sidebar.warning(f"⚠️ Tests: {passed}/{total} ({pass_rate:.0f}%)")
    else:
        st.sidebar.error(f"❌ Tests: {passed}/{total} ({pass_rate:.0f}%)")

    with st.sidebar.expander("View Test Failures"):
        failures = [r for r in test_results_cached if r.get("pass") == "❌"]
        if failures:
            for f in failures[:10]:
                st.write(f"- {f.get('id')}: expected `{f.get('expected')}`, got `{f.get('predicted')}`")
        else:
            st.success("All tests passing!")

except Exception as e:
    st.session_state["tests_healthy"] = False
    st.sidebar.warning(f"Test health unavailable: {e}")


# ----------------------------
# Helpers
# ----------------------------
def _hash_note(note: str) -> str:
    h = hashlib.sha256((note or "").encode("utf-8")).hexdigest()
    return h[:16]  # short hash for readability


def _compute_metrics(score_info: dict) -> dict:
    total = int(score_info.get("total", 0) or 0)
    met = int(score_info.get("met_count", 0) or 0)
    not_met = int(score_info.get("not_met_count", 0) or 0)
    not_doc = int(score_info.get("not_documented_count", 0) or 0)

    extraction_success_rate = round(((met + not_met) / total * 100), 1) if total else 0.0
    compliance_rate = round((met / (met + not_met) * 100), 1) if (met + not_met) > 0 else None

    return {
        "extraction_success_rate": extraction_success_rate,
        "extraction_failure_count": not_doc,
        "compliance_rate": compliance_rate,
        "compliant_count": met,
        "non_compliant_count": not_met,
    }


def _render_key_value_block(title: str, payload: dict) -> None:
    st.markdown(f"**{title}**")
    lines = []
    for key, value in payload.items():
        rendered = "null" if value is None else str(value)
        lines.append(f"{key}: {rendered}")
    st.code("\n".join(lines) if lines else "(none)", language="text")


def _render_evidence_map_block(title: str, evidence_map: dict) -> None:
    st.markdown(f"**{title}**")
    if not evidence_map:
        st.caption("No evidence spans captured.")
        return

    blocks = []
    for key, spans in evidence_map.items():
        blocks.append(f"{key}:")
        if not spans:
            blocks.append("  (none)")
            continue
        for idx, span in enumerate(spans, start=1):
            text = str(span.get("text", "")).strip()
            start = span.get("start")
            end = span.get("end")
            blocks.append(f"  [{idx}] {start}-{end}: {text}")
    st.code("\n".join(blocks), language="text")


def _summary_text(value: object, fallback: str = "Not available") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text else fallback


def _render_audit_summary_card(audit: dict, provenance: dict, invariant_errors: list[str]) -> None:
    blocking = audit.get("blocking_issues") or {}
    not_documented = blocking.get("not_documented") or []
    not_met = blocking.get("not_met") or []
    total_blockers = len(not_documented) + len(not_met)
    letter_artifacts = audit.get("letter_artifacts") or {}

    st.subheader("Audit Summary")
    st.caption("Compact trust and traceability view. Full audit details remain available at the bottom.")

    top_row = st.columns(4)
    with top_row[0]:
        st.caption("Run ID")
        st.code(_summary_text(audit.get("run_id")), language="text")
    with top_row[1]:
        st.caption("Note Hash")
        st.code(_summary_text(audit.get("note_hash")), language="text")
    with top_row[2]:
        st.caption("Rules Version")
        st.code(_summary_text(audit.get("rules_version")), language="text")
    with top_row[3]:
        st.caption("Trust Level")
        st.code(_summary_text(str(audit.get("policy_trust_level", "")).upper()), language="text")

    bottom_row = st.columns(4)
    with bottom_row[0]:
        st.metric("Invariant Checks", "PASS" if not invariant_errors else "CHECK")
    with bottom_row[1]:
        st.metric("Total Blockers", total_blockers)
    with bottom_row[2]:
        st.metric("Missing Requirements", len(not_documented))
    with bottom_row[3]:
        st.caption("Letter Hash")
        st.code(_summary_text(letter_artifacts.get("letter_hash_sha256_16"), fallback="No letter draft yet"), language="text")

    source_name = provenance.get("source_name") or "Not documented"
    source_type = provenance.get("source_type") or "Not documented"
    last_reviewed = provenance.get("last_reviewed") or "Not documented"
    st.caption(f"Policy source: {source_name} | Source type: {source_type} | Last reviewed: {last_reviewed}")


def _format_extracted_fact_value(key: str, value: object) -> str:
    if value is None:
        return "Missing from note"

    if key in {"conservative_therapy_weeks", "symptom_duration_weeks"}:
        return f"{value} weeks"

    if key == "prior_imaging_result":
        mapping = {
            "none": "No prior imaging documented",
            "inconclusive": "Prior imaging documented as inconclusive",
            "abnormal": "Prior imaging documented as abnormal",
        }
        return mapping.get(str(value), str(value))

    if isinstance(value, bool):
        return "Documented" if value else "Documented as absent"

    return str(value)


@st.cache_data
def _load_synthetic_cases(cases_path: str = "inputs/synthetic_cases.json") -> list[dict]:
    cases_file = (BASE_DIR / cases_path).resolve()
    with cases_file.open("r", encoding="utf-8") as f:
        return json.load(f)


def _featured_showcase_cases(cases: list[dict]) -> list[dict]:
    featured = [case for case in cases if (case.get("showcase") or {}).get("featured")]
    return sorted(featured, key=lambda case: (case.get("showcase") or {}).get("sort_order", 999))


def _showcase_status_chip(status: str) -> str:
    chips = {
        "READY": "READY",
        "NOT_READY": "NOT_READY",
        "CANNOT_DETERMINE": "CANNOT_DETERMINE",
    }
    rendered = chips.get(status, status or "UNKNOWN")
    return f"`{rendered}`"


def _load_case_into_intake(case: dict) -> None:
    payer = case.get("payer") or payers[0]
    if payer not in rules["payers"]:
        payer = payers[0]

    procedures = rules["payers"][payer]["procedures"]
    proc_code = case.get("procedure_code")
    if proc_code not in procedures:
        proc_code = next(iter(procedures))

    st.session_state["intake_payer"] = payer
    st.session_state["intake_proc_code"] = proc_code
    st.session_state["intake_dx_raw"] = ", ".join(case.get("dx_codes", []))
    st.session_state["intake_specialty"] = case.get("specialty", "")
    st.session_state["intake_site"] = case.get("site_of_care", "outpatient")
    st.session_state["intake_note_text"] = case.get("note_text", "")
    st.session_state["selected_showcase_case_id"] = case.get("id")


synthetic_cases = _load_synthetic_cases()
featured_showcase_cases = _featured_showcase_cases(synthetic_cases)

if "selected_showcase_case_id" not in st.session_state:
    st.session_state.selected_showcase_case_id = None

if "intake_payer" not in st.session_state or st.session_state["intake_payer"] not in rules["payers"]:
    st.session_state["intake_payer"] = payers[0]

current_intake_payer = st.session_state["intake_payer"]
current_procedure_options = list(rules["payers"][current_intake_payer]["procedures"].keys())
if "intake_proc_code" not in st.session_state or st.session_state["intake_proc_code"] not in current_procedure_options:
    st.session_state["intake_proc_code"] = current_procedure_options[0]

if "intake_dx_raw" not in st.session_state:
    st.session_state["intake_dx_raw"] = ""
if "intake_specialty" not in st.session_state:
    st.session_state["intake_specialty"] = ""
if "intake_site" not in st.session_state or st.session_state["intake_site"] not in SITE_OPTIONS:
    st.session_state["intake_site"] = "outpatient"
if "intake_note_text" not in st.session_state:
    st.session_state["intake_note_text"] = ""


# ----------------------------
# Policy Drift Monitor (governance-only)
# ----------------------------

# Base directory for absolute path resolution (prevents Streamlit CWD issues)
BASE_DIR = Path(__file__).resolve().parent

# Ensure drift ack state exists
if "ack_policy_drift" not in st.session_state:
    st.session_state.ack_policy_drift = False


def _read_drift_log(log_path: Path) -> list[dict]:
    """
    Read append-only drift log. Ignores malformed lines.
    """
    if not log_path.exists():
        return []

    events: list[dict] = []
    with log_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    return events


def _policy_monitor_status(
    snapshot_root: str = "policy_snapshots",
    sources_path: str = "rules/policy_sources.yaml",
) -> tuple[list[dict], bool]:
    """
    Offline UI status:
      - Reads latest snapshots (baseline exists?)
      - Reads drift_log.jsonl to determine REVIEW_REQUIRED
    Does NOT fetch internet.
    """
    snapshot_root_p = (BASE_DIR / snapshot_root).resolve()
    log_path = snapshot_root_p / "drift_log.jsonl"

    # Load policy sources (absolute path)
    try:
        sources = load_policy_sources((BASE_DIR / sources_path).resolve())
    except Exception:
        sources = []

    # Load drift events
    events = _read_drift_log(log_path)

    # Latest event per source (append-only; last occurrence wins)
    latest_event_by_id: dict[str, dict] = {}
    for e in events:
        sid = e.get("id")
        if sid:
            latest_event_by_id[str(sid)] = e

    rows: list[dict] = []
    any_review_required = False

    for src in sources:
        latest_snap = read_latest_snapshot(snapshot_root_p, src.id)
        last_checked = latest_snap.get("fetched_at_utc") if latest_snap else None

        status = "NO_BASELINE" if latest_snap is None else "OK"

        last_evt = latest_event_by_id.get(src.id, {})
        if last_evt.get("event") == "POLICY_DRIFT_DETECTED":
            status = "REVIEW_REQUIRED"
            any_review_required = True

        rows.append(
            {
                "id": src.id,
                "payer": src.payer,
                "procedure_code": src.procedure_code,
                "trust_level": src.trust_level,
                "status": status,
                "last_checked_utc": last_checked,
            }
        )

    return rows, any_review_required


# ----------------------------
# Global health banner (explicit gate)
# ----------------------------
tests_healthy = bool(st.session_state.get("tests_healthy", False))
if not tests_healthy:
    st.error(
        "🚫 **Build Unhealthy** — Synthetic test suite is not passing. "
        "Outputs may be unreliable. Fix failing tests before running evaluations."
    )


# ----------------------------
# Policy Monitor panel + drift gate (shown before intake)
# ----------------------------
try:
    policy_rows, any_review_required = _policy_monitor_status()
except Exception as e:
    policy_rows, any_review_required = [], False
    st.warning(f"Policy monitor unavailable: {type(e).__name__}: {e}")

st.subheader("Policy Monitor")
st.caption("Detects policy drift via committed snapshots + drift log. Does not auto-update rules or change outcomes.")

if policy_rows:
    st.dataframe(policy_rows, width="stretch")
else:
    st.info("No policy sources configured (or policy_sources.yaml missing).")

if any_review_required:
    st.warning("⚠️ Policy drift detected — rules may be stale. Verify policy and update rules/tests before trusting outputs.")
    st.session_state.ack_policy_drift = st.checkbox(
        "I acknowledge policy drift; demo outputs may be stale.",
        value=st.session_state.ack_policy_drift,
    )
else:
    st.success("Policy drift status: OK (based on latest snapshots/log).")
    st.session_state.ack_policy_drift = True

policy_gate_block = any_review_required and (not st.session_state.get("ack_policy_drift", False))


# ----------------------------
# Featured showcase cases
# ----------------------------
showcase_submitted = False
showcase_feedback = None

st.subheader("Featured Showcase Cases")
st.caption(
    "Fastest way to experience the demo. Choose a curated synthetic case to load it into the main intake below. "
    "Loaded inputs stay editable for custom exploration."
)

if featured_showcase_cases:
    for start in range(0, len(featured_showcase_cases), 2):
        cols = st.columns(2)
        for col, case in zip(cols, featured_showcase_cases[start : start + 2]):
            showcase = case.get("showcase") or {}
            title = showcase.get("title", case.get("id", "Showcase case"))
            description = showcase.get("description", "")
            expected_status = showcase.get("expected_overall_status", "UNKNOWN")
            why_interesting = showcase.get("why_interesting", "")

            with col:
                st.markdown(f"#### {title}")
                st.write(description)
                st.markdown(f"**Expected outcome:** {_showcase_status_chip(expected_status)}")
                if why_interesting:
                    st.caption(f"Why this case is useful: {why_interesting}")
                if st.session_state.get("selected_showcase_case_id") == case.get("id"):
                    st.caption("Currently loaded in the intake below.")

                if st.button("Open This Demo Case", key=f"showcase_{case.get('id')}", width="stretch"):
                    _load_case_into_intake(case)
                    if tests_healthy and not policy_gate_block:
                        showcase_submitted = True
                        showcase_feedback = (
                            "success",
                            f'Loaded "{title}" and ran the evaluation below. The intake remains fully editable.',
                        )
                    elif policy_gate_block:
                        showcase_feedback = (
                            "info",
                            f'Loaded "{title}" into the intake below. Acknowledge the policy drift gate to run the evaluation.',
                        )
                    else:
                        showcase_feedback = (
                            "info",
                            f'Loaded "{title}" into the intake below. Resolve the build health gate before running the evaluation.',
                        )
else:
    st.info("No featured showcase cases configured.")

if showcase_feedback:
    getattr(st, showcase_feedback[0])(showcase_feedback[1])


# ----------------------------
# Intake form
# ----------------------------
st.markdown("### Intake")
current_showcase_case = next(
    (case for case in featured_showcase_cases if case.get("id") == st.session_state.get("selected_showcase_case_id")),
    None,
)
if current_showcase_case is not None:
    st.caption(
        f'Loaded showcase case: {(current_showcase_case.get("showcase") or {}).get("title", current_showcase_case.get("id"))}. '
        "You can edit any field below or replace the note for custom exploration."
    )
else:
    st.caption("Paste your own synthetic note here, or start with one of the featured showcase cases above.")

with st.form("pa_form", clear_on_submit=False):
    c1, c2, c3 = st.columns(3)

    with c1:
        payer = st.selectbox("Payer", payers, key="intake_payer")

    with c2:
        procedures = rules["payers"][payer]["procedures"]
        proc_code = st.selectbox("Procedure", list(procedures.keys()), key="intake_proc_code")

    with c3:
        dx_raw = st.text_input("Dx codes (comma-separated)", placeholder="e.g., M54.5, M51.26", key="intake_dx_raw")

    specialty = st.text_input("Ordering specialty (optional)", placeholder="e.g., Orthopedics", key="intake_specialty")
    site = st.selectbox("Site of care", SITE_OPTIONS, key="intake_site")

    note_text = st.text_area(
        "Clinical note (mock/synthetic)",
        height=220,
        placeholder="Paste a synthetic clinical note here...",
        key="intake_note_text",
    )

    tests_healthy = bool(st.session_state.get("tests_healthy", False))
    submitted = st.form_submit_button(
        "Evaluate PA readiness",
        disabled=(not tests_healthy) or policy_gate_block,
    )


# ----------------------------
# Evaluate action (persist results)
# ----------------------------
if submitted or showcase_submitted:
    # Clear prior letter UI output on new eval to avoid stale drafts
    st.session_state.letter_text = ""
    st.session_state.letter_meta = {}
    st.session_state.letter_error = ""

    dx_codes = [x.strip() for x in (dx_raw or "").split(",") if x.strip()]
    proc_obj = rules["payers"][payer]["procedures"][proc_code]
    proc_name = proc_obj.get("display_name", proc_code)
    requirements = proc_obj.get("required", [])

    facts, evidence_map = extract_facts(note_text)
    results, reasons = evaluate_requirements(requirements, facts, evidence_map=evidence_map)

    overall = compute_overall_status(results)
    score_info = compute_readiness_score(results)

    rows = []
    for rr in results:
        rows.append(
            {
                "key": rr.key,
                "label": rr.label,
                "status": rr.status,
                "reason": rr.reason,
                "evidence_hint": rr.evidence or "",
                "evidence_snippets": getattr(rr, "evidence_snippets", []) or [],
            }
        )

    # Blocking issues
    blocking_not_documented = [{"key": r["key"], "label": r["label"]} for r in rows if r["status"] == "NOT_DOCUMENTED"]
    blocking_not_met = [{"key": r["key"], "label": r["label"]} for r in rows if r["status"] == "NOT_MET"]

    # Invariants
    invariant_errors = []
    if blocking_not_documented and overall["overall_status"] != "CANNOT_DETERMINE":
        invariant_errors.append("Invariant violation: NOT_DOCUMENTED blockers exist but overall_status is not CANNOT_DETERMINE.")
    if (not blocking_not_documented) and blocking_not_met and overall["overall_status"] == "READY":
        invariant_errors.append("Invariant violation: NOT_MET blockers exist but overall_status is READY.")
    if (not blocking_not_documented) and (not blocking_not_met) and overall["overall_status"] != "READY":
        invariant_errors.append("Invariant violation: no blockers exist but overall_status is not READY.")

    # Provenance snapshot + trust level
    prov_info = get_provenance_entry(prov, payer, proc_code)
    policy_trust_level = policy_trust_from_provenance(prov_info)

    # Metrics
    metrics = _compute_metrics(score_info)

    run_id = str(uuid.uuid4())
    ts = datetime.now(timezone.utc).isoformat()

    audit = {
        "run_id": run_id,
        "timestamp_utc": ts,
        "note_hash": _hash_note(note_text),
        "note_length": len(note_text or ""),
        "payer": payer,
        "procedure_code": proc_code,
        "procedure_name": proc_name,
        "site_of_care": site,
        "specialty": specialty,
        "rules_version": rules.get("version"),
        "policy_trust_level": policy_trust_level,
        "provenance_snapshot": prov_info or {},
        "facts_extracted": facts,
        "evidence_map": evidence_map,
        "requirements_checked": [r["key"] for r in rows],
        "overall_status": overall["overall_status"],
        "submission_readiness": bool(overall["submission_readiness"]),
        "blocking_issues": {"not_documented": blocking_not_documented, "not_met": blocking_not_met},
        "metrics": metrics,
        "invariant_errors": invariant_errors,
    }

    # Build schema objects for write-only letter drafting
    dx_codes_clean = normalized_dx_codes(dx_codes)

    pa_model = PARequest(
        payer=payer,
        procedure_code=proc_code,
        dx_codes=dx_codes_clean,
        site_of_care=site,
        specialty=(specialty or "unknown"),
        note_text="",  # intentionally NOT used by drafting
    )

    req_models = [
        RequirementResult(
            key=r["key"],
            label=r["label"],
            status=r["status"],
            reason=r["reason"],
            evidence=(r.get("evidence_hint") or None),
            evidence_snippets=(r.get("evidence_snippets") or []),
        )
        for r in rows
    ]

    report_model = ReadinessReport(
        readiness_score=int(score_info.get("readiness_score", 0) or 0),
        not_documented_count=int(score_info.get("not_documented_count", 0) or 0),
        not_met_count=int(score_info.get("not_met_count", 0) or 0),
        met_count=int(score_info.get("met_count", 0) or 0),
        results=req_models,
        rule_reasons=list(reasons or []),
        audit_trail=dict(audit),
        letter_draft="",  # write-only; UI will populate separately
    )

    st.session_state.last_eval = {
        "payer": payer,
        "proc_code": proc_code,
        "proc_name": proc_name,
        "dx_codes": dx_codes,
        "facts": facts,
        "evidence_map": evidence_map,
        "rows": rows,
        "reasons": reasons,
        "overall": overall,
        "score_info": score_info,
        "metrics": metrics,
        "audit": audit,
        "invariant_errors": invariant_errors,
        "policy_trust_level": policy_trust_level,
        "provenance": prov_info or {},
        # NEW
        "pa_model": pa_model,
        "report_model": report_model,
    }


# ----------------------------
# Outputs
# ----------------------------
st.markdown("### Results")

if st.session_state.last_eval is None:
    st.info("Run an evaluation to see the result. The synthetic test suite remains available below.")
else:
    ev = st.session_state.last_eval
    overall = ev["overall"]
    score_info = ev["score_info"]
    metrics = ev["metrics"]

    status = overall["overall_status"]
    submission_readiness = bool(overall["submission_readiness"])
    inv = ev.get("invariant_errors", [])
    not_documented_items = [r for r in ev["rows"] if r["status"] == "NOT_DOCUMENTED"]
    not_met_items = [r for r in ev["rows"] if r["status"] == "NOT_MET"]
    total_blockers = len(not_documented_items) + len(not_met_items)
    source_name = ev["provenance"].get("source_name") or "Not documented"
    last_reviewed = ev["provenance"].get("last_reviewed") or "Not documented"

    # Decision first
    if status == "CANNOT_DETERMINE":
        st.warning(
            "Administrative readiness **cannot be determined** — one or more required criteria are **not documented** in the note. "
            "Add explicit documentation for the blocking items below."
        )
    elif status == "NOT_READY":
        st.error(
            "Not ready to submit — one or more required criteria are **documented but not met**. "
            "Review the failing items below."
        )
    elif status == "READY":
        st.success(
            "Administratively ready **per current rules** — all required criteria appear documented and met. "
            "Human review still required."
        )
    else:
        st.info("Status unavailable (unexpected overall_status).")

    if ev["policy_trust_level"] != "verified":
        st.warning(
            "Demo rules in use — requirements are manually curated for demonstration. "
            "Verify against the official payer policy before any real submission."
        )
    st.caption(
        f"Policy source: {source_name} | Last reviewed: {last_reviewed} | Trust level: {str(ev['policy_trust_level']).upper()}"
    )

    if inv:
        st.error("Internal consistency checks require review before trusting this run.")
        for msg in inv:
            st.write(f"- {msg}")

    # Blocking items and reasons
    st.subheader("What Needs Attention")
    blocker_cols = st.columns(3)
    with blocker_cols[0]:
        st.metric("Total Blockers", total_blockers)
    with blocker_cols[1]:
        st.metric("Missing Requirements", len(not_documented_items))
    with blocker_cols[2]:
        st.metric("Documented Failures", len(not_met_items))

    if not not_documented_items and not not_met_items:
        st.success("No blocking items detected under the current rules.")
    else:
        if not_documented_items:
            st.markdown("**Missing documentation (drives `CANNOT_DETERMINE`):**")
            for r in not_documented_items:
                st.write(f"- {r['label']}: {r['reason']}")
        if not_met_items:
            st.markdown("**Documented but below threshold (drives `NOT_READY`):**")
            for r in not_met_items:
                st.write(f"- {r['label']}: {r['reason']}")

    # Requirement-by-requirement explanation
    st.subheader("Why This Result")
    st.caption("Each requirement shows its status, the reason it landed there, and supporting note text when available.")
    status_emoji = {"MET": "✅", "NOT_MET": "⚠️", "NOT_DOCUMENTED": "❌"}

    for r in ev["rows"]:
        emoji = status_emoji.get(r.get("status"), "❓")
        expand_default = r.get("status") != "MET"

        with st.expander(f"{emoji} {r.get('label', '')}", expanded=expand_default):
            st.write(f"**Status:** {r.get('status')}")
            st.write(f"**Reason:** {r.get('reason')}")

            if r.get("evidence_hint"):
                st.info(f"💡 **What to look for in the note:** {r['evidence_hint']}")

            snips = r.get("evidence_snippets") or []
            if snips:
                st.markdown("**Evidence found in note:**")
                for s in snips[:5]:
                    st.code(str(s), language="text")
            else:
                st.caption("No evidence snippet captured for this requirement.")

    st.subheader("Extracted Facts")
    st.caption("Decision-relevant facts pulled from the note for this request.")
    for start in range(0, len(ev["rows"]), 2):
        cols = st.columns(2)
        for col, r in zip(cols, ev["rows"][start : start + 2]):
            key = r["key"]
            fact_value = _format_extracted_fact_value(key, ev["facts"].get(key))
            span_count = len(ev["evidence_map"].get(key) or [])

            with col:
                st.markdown(f"**{status_emoji.get(r.get('status'), '❓')} {r.get('label', '')}**")
                st.write(fact_value)
                if r["status"] == "NOT_DOCUMENTED":
                    st.caption("Missing from the note or not explicit enough for deterministic extraction.")
                elif r["status"] == "NOT_MET":
                    st.caption("Captured from the note, but below the current rule threshold.")
                elif span_count > 1:
                    st.caption("Captured from multiple note excerpts.")
                else:
                    st.caption("Captured from the note.")

    st.subheader("Evidence Mapping")
    st.caption("Compact note excerpts associated with the extracted facts above.")
    for start in range(0, len(ev["rows"]), 2):
        cols = st.columns(2)
        for col, r in zip(cols, ev["rows"][start : start + 2]):
            key = r["key"]
            spans = ev["evidence_map"].get(key) or []

            with col:
                st.markdown(f"**{r.get('label', '')}**")
                if spans:
                    st.caption(f"{len(spans)} supporting note excerpt(s) shown.")
                    for span in spans[:2]:
                        st.code(str(span.get("text", "")).strip(), language="text")
                        st.caption(f"Excerpt location: {span.get('start')}-{span.get('end')}")
                    if len(spans) > 2:
                        st.caption(f"+ {len(spans) - 2} more note excerpt(s) available in the raw details below.")
                elif r["status"] == "NOT_DOCUMENTED":
                    st.caption("No supporting note excerpt was captured because the fact was missing or not explicit enough.")
                else:
                    st.caption("No supporting note excerpt was captured for this fact.")

    _render_audit_summary_card(ev["audit"], ev["provenance"], inv)

    st.subheader("Secondary Diagnostics (Informational)")
    st.caption("These convenience metrics support review but do not change the frozen status or blockers above.")

    o1, o2, o3 = st.columns([1, 1, 1])

    with o1:
        st.metric("Score (informational only)", f"{score_info['readiness_score']}/100")
        st.caption(
            f"{score_info['met_count']} met | {score_info['not_documented_count']} missing | "
            f"{score_info['not_met_count']} below threshold out of {score_info['total']} requirements."
        )
        st.caption(f"Administratively ready under current demo rules: {'Yes' if submission_readiness else 'No'}")

    with o2:
        extraction_delta = (
            "0 missing"
            if metrics["extraction_failure_count"] == 0
            else f"-{metrics['extraction_failure_count']} missing"
        )
        st.metric(
            "Extraction Success",
            f"{metrics['extraction_success_rate']}%",
            delta=extraction_delta,
        )
        st.caption("Higher missing counts usually reflect documentation gaps, not hidden inference.")

    with o3:
        cr = metrics["compliance_rate"]
        st.metric(
            "Requirement Compliance",
            f"{cr}%" if cr is not None else "N/A",
            delta=f"{metrics['non_compliant_count']} below threshold",
        )
        st.caption("Compliance is calculated only from documented requirements and remains secondary to the frozen status contract.")

    # ----------------------------
    # Letter Drafting UI (Write-only)
    # ----------------------------
    st.subheader("Justification Letter (Write-only)")

    # Letter type selector (presentation only; does not change readiness logic)
    letter_type = st.selectbox(
        "Letter type",
        ["submission_cover_letter", "missing_info_request", "appeal_template"],
        index=0,
    )

    cA, cB = st.columns([1, 1])
    with cA:
        generate_letter = st.button("Generate letter draft", type="primary", width="stretch")
    with cB:
        clear_letter = st.button("Clear draft", width="stretch")

    if clear_letter:
        st.session_state.letter_text = ""
        st.session_state.letter_meta = {}
        st.session_state.letter_error = ""

    if generate_letter:
        try:
            pa_model: PARequest = ev["pa_model"]
            report_model: ReadinessReport = ev["report_model"]

            letter_text, letter_meta = draft_letter_writeonly(
                pa_model,
                report_model,
                letter_type=letter_type,
                policy_trust_level=ev.get("policy_trust_level", "demo"),
            )

            st.session_state.letter_text = letter_text
            st.session_state.letter_meta = letter_meta
            st.session_state.letter_error = ""

            # Audit linkage without storing full letter content
            ev["audit"]["letter_artifacts"] = {
                "letter_type": letter_meta.get("letter_type"),
                "letter_version": letter_meta.get("letter_version"),
                "generated_timestamp_utc": letter_meta.get("generated_timestamp_utc"),
                "letter_hash_sha256_16": letter_meta.get("letter_hash_sha256_16"),
                "cited_snippets_count": letter_meta.get("cited_snippets_count"),
                "overall_status": letter_meta.get("overall_status"),
                "policy_trust_level": letter_meta.get("policy_trust_level"),
                "draft_blocked": letter_meta.get("draft_blocked"),
            }

        except Exception as e:
            st.session_state.letter_error = f"{type(e).__name__}: {e}"

    if st.session_state.letter_error:
        st.error(st.session_state.letter_error)

    if st.session_state.letter_text:
        st.text_area("Letter draft (read-only)", value=st.session_state.letter_text, height=300)

        with st.expander("Letter metadata"):
            st.code(json.dumps(st.session_state.letter_meta, indent=2), language="json")

        st.download_button(
            "📥 Download Letter (.txt)",
            data=st.session_state.letter_text,
            file_name=f"pa_{letter_type}.txt",
            mime="text/plain",
            width="stretch",
        )
        st.download_button(
            "📥 Download Letter Metadata (.json)",
            data=json.dumps(st.session_state.letter_meta, indent=2),
            file_name=f"pa_{letter_type}_metadata.json",
            mime="application/json",
            width="stretch",
        )
    else:
        st.caption("No letter generated yet. Select a letter type and click **Generate letter draft**.")

    # Full audit/debug details
    st.subheader("Full Audit & Debug Details")
    with st.expander("Open raw audit JSON, extracted facts, and evidence spans"):
        st.json(ev["audit"])
        if ev["reasons"]:
            st.markdown("**Rule reasons**")
            st.code("\n".join(ev["reasons"]), language="text")
        _render_key_value_block("Extracted facts (raw)", ev["facts"])
        _render_evidence_map_block("Evidence map (raw spans)", ev["evidence_map"])

    audit_json = json.dumps(ev["audit"], indent=2)
    ts_local = datetime.now().strftime("%Y%m%d_%H%M%S")
    st.download_button(
        label="📥 Download Audit Trail (JSON)",
        data=audit_json,
        file_name=f"pa_audit_{ev['audit']['payer']}_{ev['audit']['procedure_code']}_{ts_local}.json",
        mime="application/json",
        width="stretch",
    )


# ----------------------------
# Test suite (manual run + export + inspect)
# ----------------------------
st.markdown("### Advanced: Synthetic Test Suite")

run_tests = st.button("Run test suite", width="stretch")

if run_tests:
    from engine.test_suites import run_cases
    st.session_state.test_rows = run_cases("rules/payer_rules.yaml", "inputs/synthetic_cases.json")

if st.session_state.test_rows is None:
    st.caption("Click **Run test suite** to evaluate the rules engine on synthetic cases.")
else:
    st.dataframe(st.session_state.test_rows, width="stretch")

    test_json = json.dumps(st.session_state.test_rows, indent=2)
    ts_local = datetime.now().strftime("%Y%m%d_%H%M%S")
    st.download_button(
        label="📥 Download Test Results (JSON)",
        data=test_json,
        file_name=f"pa_test_results_{ts_local}.json",
        mime="application/json",
        width="stretch",
    )

    st.markdown("---")
    st.subheader("🔎 Inspect a Test Case (shows evidence snippets)")

    # Load the raw cases so we can re-run extraction/eval for one selected case
    _cases = synthetic_cases

    case_ids = [c.get("id") for c in _cases]
    selected_id = st.selectbox("Select case", case_ids)

    case = next((c for c in _cases if c.get("id") == selected_id), None)
    if case:
        payer_i = case["payer"]
        proc_i = case["procedure_code"]
        note_i = case.get("note_text", "")

        proc_obj_i = rules["payers"][payer_i]["procedures"][proc_i]
        reqs_i = proc_obj_i.get("required", [])

        facts_i, evidence_map_i = extract_facts(note_i)
        results_i, _ = evaluate_requirements(reqs_i, facts_i, evidence_map=evidence_map_i)

        # Build rows including evidence_snippets
        rows_i = []
        for rr in results_i:
            rows_i.append(
                {
                    "key": rr.key,
                    "label": rr.label,
                    "status": rr.status,
                    "reason": rr.reason,
                    "evidence_hint": rr.evidence or "",
                    "evidence_snippets": getattr(rr, "evidence_snippets", []) or [],
                }
            )

        st.markdown("**Test case note (synthetic):**")
        st.text_area("note_text", value=note_i, height=160)

        _render_key_value_block("Extracted facts", facts_i)
        _render_evidence_map_block("Evidence map (raw spans)", evidence_map_i)

        st.markdown("**Explainable requirement results:**")
        status_emoji = {"MET": "✅", "NOT_MET": "⚠️", "NOT_DOCUMENTED": "❌"}
        for r in rows_i:
            emoji = status_emoji.get(r.get("status"), "❓")
            expand_default = r.get("status") != "MET"
            with st.expander(f"{emoji} {r.get('label','')}", expanded=expand_default):
                st.write(f"**Status:** {r.get('status')}")
                st.write(f"**Reason:** {r.get('reason')}")
                if r.get("evidence_hint"):
                    st.info(f"💡 **What to look for in the note:** {r['evidence_hint']}")

                snips = r.get("evidence_snippets") or []
                if snips:
                    st.markdown("**Evidence found in note:**")
                    for s in snips[:5]:
                        st.code(str(s), language="text")
                else:
                    st.caption("No evidence snippet captured for this requirement.")
