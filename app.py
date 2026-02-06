# -*- coding: utf-8 -*-


import streamlit as st
import yaml
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

# NEW: schema + write-only letter drafting
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

st.title("PA Readiness Copilot (Flagship)")
st.caption("Administrative decision support only — not medical or billing advice.")


# ----------------------------
# Session state initialization
# ----------------------------
if "last_eval" not in st.session_state:
    st.session_state.last_eval = None
if "test_rows" not in st.session_state:
    st.session_state.test_rows = None

# NEW: letter UI state (write-only)
if "letter_text" not in st.session_state:
    st.session_state.letter_text = ""
if "letter_meta" not in st.session_state:
    st.session_state.letter_meta = {}
if "letter_error" not in st.session_state:
    st.session_state.letter_error = ""

# NEW: policy drift acknowledge gate state
if "ack_policy_drift" not in st.session_state:
    st.session_state.ack_policy_drift = False


# ----------------------------
# Load rules + provenance
# ----------------------------
RULES_PATH = "rules/payer_rules.yaml"
rules = load_rules(RULES_PATH)
payers = sorted(rules["payers"].keys())

PROV_PATH = "rules/provenance.yaml"
try:
    with open(PROV_PATH, "r", encoding="utf-8") as f:
        prov = yaml.safe_load(f) or {}
except FileNotFoundError:
    prov = {}


# ----------------------------
# Sidebar: System Health (auto tests, cached)
# ----------------------------
st.sidebar.markdown("### 🧪 System Health")

# Manual cache bust button (prevents stale failures after edits)
if st.sidebar.button("🔄 Refresh test health (clear cache)", use_container_width=True):
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


# ----------------------------
# Policy Drift Monitor (governance-only)
# ----------------------------
def _read_drift_log(log_path: Path) -> list[dict]:
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
                # Ignore malformed lines; monitor is governance-only
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
    snapshot_root_p = Path(snapshot_root)
    log_path = snapshot_root_p / "drift_log.jsonl"

    # Load sources (YAML)
    try:
        sources = load_policy_sources(Path(sources_path))
    except Exception:
        sources = []

    # Load drift events and compute latest event per source
    events = _read_drift_log(log_path)
    latest_event_by_id: dict[str, dict] = {}
    for e in events:
        sid = e.get("id")
        if not sid:
            continue
        # drift_log is append-only; last occurrence wins
        latest_event_by_id[str(sid)] = e

    rows: list[dict] = []
    any_review_required = False

    for src in sources:
        latest_snap = read_latest_snapshot(snapshot_root_p, src.id)
        last_checked = latest_snap.get("fetched_at_utc") if latest_snap else None

        # Default status
        status = "NO_BASELINE" if latest_snap is None else "OK"

        # If the last logged event for this source is drift detected, mark review-required
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
policy_rows, any_review_required = _policy_monitor_status()

st.subheader("Policy Monitor (Governance)")
st.caption("Detects policy drift via committed snapshots + drift log. Does not auto-update rules or change outcomes.")

if policy_rows:
    st.dataframe(policy_rows, use_container_width=True)
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
# Intake form
# ----------------------------
st.markdown("### Intake")

with st.form("pa_form", clear_on_submit=False):
    c1, c2, c3 = st.columns(3)

    with c1:
        payer = st.selectbox("Payer", payers)

    with c2:
        procedures = rules["payers"][payer]["procedures"]
        proc_code = st.selectbox("Procedure", list(procedures.keys()))

    with c3:
        dx_raw = st.text_input("Dx codes (comma-separated)", placeholder="e.g., M54.5, M51.26")

    specialty = st.text_input("Ordering specialty (optional)", placeholder="e.g., Orthopedics")
    site = st.selectbox("Site of care", ["outpatient", "inpatient", "ASC", "office"])

    note_text = st.text_area(
        "Clinical note (mock/synthetic)",
        height=220,
        placeholder="Paste a synthetic note here...",
    )

    tests_healthy = bool(st.session_state.get("tests_healthy", False))
    submitted = st.form_submit_button(
        "Evaluate PA readiness",
        disabled=(not tests_healthy) or policy_gate_block,
    )


# ----------------------------
# Evaluate action (persist results)
# ----------------------------
if submitted:
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
    prov_info = (prov.get("sources", {}) or {}).get(payer, {}).get(proc_code, {})
    source_type = (prov_info or {}).get("source_type", "unknown")
    policy_trust_level = "verified" if source_type == "policy_document" else "demo"

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

    # NEW: build schema objects for write-only letter drafting
    def _clean_dx(code: str) -> str:
        # Conservative normalization: no inference, no validation against ICD tables
        return code.strip().upper().replace(" ", "").replace("%", "")

    dx_codes_clean = [_clean_dx(c) for c in dx_codes if c.strip()]

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
st.markdown("### Outputs")

if st.session_state.last_eval is None:
    st.info("Run an evaluation to see case outputs. Test suite can be run anytime below.")
else:
    ev = st.session_state.last_eval
    overall = ev["overall"]
    score_info = ev["score_info"]
    metrics = ev["metrics"]

    status = overall["overall_status"]
    submission_readiness = bool(overall["submission_readiness"])

    # Policy provenance + banner
    st.markdown("### Policy Provenance")
    if ev["policy_trust_level"] != "verified":
        st.warning(
            "⚠️ **Demo rules in use** — Requirements are manually curated for demonstration. "
            "Verify criteria against the official payer policy before any real submission."
        )

    st.write(
        {
            "policy_trust_level": ev["policy_trust_level"],
            "source_type": ev["provenance"].get("source_type"),
            "source_name": ev["provenance"].get("source_name"),
            "last_reviewed": ev["provenance"].get("last_reviewed"),
            "notes": ev["provenance"].get("notes"),
        }
    )

    # Invariant errors
    inv = ev.get("invariant_errors", [])
    if inv:
        st.error("Internal consistency checks failed:")
        for msg in inv:
            st.write(f"- {msg}")

    # Status banner
    if status == "CANNOT_DETERMINE":
        st.warning(
            "Approval readiness **cannot be determined** — one or more required criteria are **not documented** in the note. "
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

    o1, o2, o3 = st.columns([1, 1, 1])

    with o1:
        st.metric("PA Readiness Score", f"{score_info['readiness_score']}/100")
        st.write(
            {
                "met": score_info["met_count"],
                "not_documented": score_info["not_documented_count"],
                "not_met": score_info["not_met_count"],
                "total": score_info["total"],
            }
        )
        st.write({"overall_status": status, "submission_readiness": submission_readiness})

    with o2:
        st.metric(
            "Extraction Success",
            f"{metrics['extraction_success_rate']}%",
            delta=f"-{metrics['extraction_failure_count']} missing",
        )

    with o3:
        cr = metrics["compliance_rate"]
        st.metric(
            "Requirement Compliance",
            f"{cr}%" if cr is not None else "N/A",
            delta=f"{metrics['non_compliant_count']} below threshold",
        )

    # Blocking items
    st.subheader("Blocking Items (Most Important)")
    not_documented_items = [r for r in ev["rows"] if r["status"] == "NOT_DOCUMENTED"]
    not_met_items = [r for r in ev["rows"] if r["status"] == "NOT_MET"]

    if not not_documented_items and not not_met_items:
        st.success("No blocking items detected by current rules.")
    else:
        if not_documented_items:
            st.markdown("**Missing documentation (cannot determine readiness):**")
            for r in not_documented_items:
                st.write(f"- {r['label']}: {r['reason']}")
        if not_met_items:
            st.markdown("**Documented but not met (not ready):**")
            for r in not_met_items:
                st.write(f"- {r['label']}: {r['reason']}")

    # Explainable results (with evidence snippets)
    st.subheader("Rule-based Requirement Results (Explainable)")
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

    # ----------------------------
    # Letter Drafting UI (Write-only)
    # ----------------------------
    st.subheader("Justification Letter (Write-only)")

    # NEW: Letter type selector (presentation only; does not change readiness logic)
    letter_type = st.selectbox(
        "Letter type",
        ["submission_cover_letter", "missing_info_request", "appeal_template"],
        index=0,
    )

    cA, cB = st.columns([1, 1])
    with cA:
        generate_letter = st.button("Generate letter draft", type="primary", use_container_width=True)
    with cB:
        clear_letter = st.button("Clear draft", use_container_width=True)

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

            # NEW: Audit linkage without storing full letter content
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
            use_container_width=True,
        )
        st.download_button(
            "📥 Download Letter Metadata (.json)",
            data=json.dumps(st.session_state.letter_meta, indent=2),
            file_name=f"pa_{letter_type}_metadata.json",
            mime="application/json",
            use_container_width=True,
        )
    else:
        st.caption("No letter generated yet. Select a letter type and click **Generate letter draft**.")

    # Audit export (no note_text)
    st.subheader("Audit Trail")
    st.json(ev["audit"])

    audit_json = json.dumps(ev["audit"], indent=2)
    ts_local = datetime.now().strftime("%Y%m%d_%H%M%S")
    st.download_button(
        label="📥 Download Audit Trail (JSON)",
        data=audit_json,
        file_name=f"pa_audit_{ev['audit']['payer']}_{ev['audit']['procedure_code']}_{ts_local}.json",
        mime="application/json",
        use_container_width=True,
    )


# ----------------------------
# Test suite (manual run + export + inspect)
# ----------------------------
st.markdown("### Test Suite (Synthetic Cases)")

run_tests = st.button("Run test suite", use_container_width=True)

if run_tests:
    from engine.test_suites import run_cases
    st.session_state.test_rows = run_cases("rules/payer_rules.yaml", "inputs/synthetic_cases.json")

if st.session_state.test_rows is None:
    st.caption("Click **Run test suite** to evaluate the rules engine on synthetic cases.")
else:
    st.dataframe(st.session_state.test_rows, use_container_width=True)

    test_json = json.dumps(st.session_state.test_rows, indent=2)
    ts_local = datetime.now().strftime("%Y%m%d_%H%M%S")
    st.download_button(
        label="📥 Download Test Results (JSON)",
        data=test_json,
        file_name=f"pa_test_results_{ts_local}.json",
        mime="application/json",
        use_container_width=True,
    )

    st.markdown("---")
    st.subheader("🔎 Inspect a Test Case (shows evidence snippets)")

    # Load the raw cases so we can re-run extraction/eval for one selected case
    with open("inputs/synthetic_cases.json", "r", encoding="utf-8") as f:
        _cases = json.load(f)

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

        st.markdown("**Extracted facts:**")
        st.json(facts_i)

        st.markdown("**Evidence map (raw spans):**")
        st.json(evidence_map_i)

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
