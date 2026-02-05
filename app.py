import streamlit as st
import yaml
import json
import uuid
import hashlib
from datetime import datetime, timezone

from engine.rules_loader import load_rules
from engine.extract import extract_facts
from engine.evaluate import (
    evaluate_requirements,
    compute_readiness_score,
    compute_overall_status,
)
from llm.draft_letter import draft_letter_deterministic


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

    # Gate: only allow evaluations if tests are fully passing
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
# Global health banner (explicit gate)
# ----------------------------
tests_healthy = bool(st.session_state.get("tests_healthy", False))
if not tests_healthy:
    st.error(
        "🚫 **Build Unhealthy** — Synthetic test suite is not passing. "
        "Outputs may be unreliable. Fix failing tests before running evaluations."
    )


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
    submitted = st.form_submit_button("Evaluate PA readiness", disabled=(not tests_healthy))


# ----------------------------
# Evaluate action (persist results)
# ----------------------------
if submitted:
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

    # Letter draft
    letter = draft_letter_deterministic(
        payer=payer,
        procedure_code=proc_code,
        procedure_name=proc_name,
        dx_codes=dx_codes,
        facts=facts,
        results=rows,
        overall_status=overall["overall_status"],
    )

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
        "evidence_snippets": evidence_map,
        "requirements_checked": [r["key"] for r in rows],
        "overall_status": overall["overall_status"],
        "submission_readiness": bool(overall["submission_readiness"]),
        "blocking_issues": {"not_documented": blocking_not_documented, "not_met": blocking_not_met},
        "metrics": metrics,
        "invariant_errors": invariant_errors,
    }

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
        "letter": letter,
        "audit": audit,
        "invariant_errors": invariant_errors,
        "policy_trust_level": policy_trust_level,
        "provenance": prov_info or {},
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
                
    st.write("DEBUG evidence_snippets sample:", rows[0].get("evidence_snippets") if rows else None)

    # Letter
    st.subheader("Draft Letter (Deterministic MVP)")
    st.text_area("Letter draft", value=ev["letter"], height=220)

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
# Test suite (manual run + export)
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
