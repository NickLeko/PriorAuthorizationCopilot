import streamlit as st

from engine.rules_loader import load_rules
from engine.extract import extract_facts
from engine.evaluate import (
    evaluate_requirements,
    compute_readiness_score,
    compute_overall_status,
)
from llm.draft_letter import draft_letter_deterministic

st.set_page_config(page_title="PA Readiness Copilot", layout="wide")

st.markdown(
    """
    <style>
      /* Ensure the overall page can scroll on iOS/webviews */
      html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
        height: 100% !important;
        overflow: auto !important;
        -webkit-overflow-scrolling: touch !important;
      }

      /* Streamlit header can cause scroll-jank on mobile */
      header[data-testid="stHeader"] {
        position: relative !important;
      }

      /* Avoid nested overflow containers clipping content */
      section[data-testid="stSidebar"], div[data-testid="stVerticalBlock"] {
        overflow: visible !important;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("PA Readiness Copilot (Flagship)")
st.caption("Administrative decision support only — not medical or billing advice.")

RULES_PATH = "rules/payer_rules.yaml"

rules = load_rules(RULES_PATH)
payers = sorted(rules["payers"].keys())

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

    submitted = st.form_submit_button("Evaluate PA readiness")

if not submitted:
    st.info("Fill the form and click **Evaluate PA readiness**.")
    st.stop()

dx_codes = [x.strip() for x in (dx_raw or "").split(",") if x.strip()]
proc_obj = rules["payers"][payer]["procedures"][proc_code]
proc_name = proc_obj.get("display_name", proc_code)
requirements = proc_obj.get("required", [])

facts = extract_facts(note_text)
results, reasons = evaluate_requirements(requirements, facts)

# Bias-resistant gating (prevents false confidence when documentation is missing)
overall = compute_overall_status(results)
status = overall["overall_status"]
submission_readiness = bool(overall["submission_readiness"])

# Scoring (expects tri-state result statuses)
score_info = compute_readiness_score(results)
readiness_score = score_info["readiness_score"]
met_count = score_info["met_count"]
not_met_count = score_info["not_met_count"]
not_documented_count = score_info["not_documented_count"]
total = score_info["total"]

# -----------------------------------------
# Outputs
# -----------------------------------------
st.markdown("### Outputs")

# Top banner (automation-bias control)
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

o1, o2 = st.columns([1, 2])

with o1:
    st.metric("PA Readiness Score", f"{readiness_score}/100")
    st.write(
        {
            "met": met_count,
            "not_documented": not_documented_count,
            "not_met": not_met_count,
            "total": total,
        }
    )
    st.write(
        {
            "overall_status": status,
            "submission_readiness": submission_readiness,
        }
    )

with o2:
    st.subheader("Blocking Items (Most Important)")

    not_documented_items = [r for r in results if r.status == "NOT_DOCUMENTED"]
    not_met_items = [r for r in results if r.status == "NOT_MET"]

    if not not_documented_items and not not_met_items:
        st.success("No blocking items detected by current rules.")
    else:
        if not_documented_items:
            st.markdown("**Missing documentation (cannot determine readiness):**")
            for r in not_documented_items:
                st.write(f"- {r.label}: {r.reason}")

        if not_met_items:
            st.markdown("**Documented but not met (not ready):**")
            for r in not_met_items:
                st.write(f"- {r.label}: {r.reason}")

# Full table
st.subheader("Rule-based Requirement Results")
rows = []
for r in results:
    rows.append(
        {
            "key": r.key,
            "label": r.label,
            "status": r.status,
            "reason": r.reason,
            "evidence_hint": r.evidence or "",
        }
    )
st.dataframe(rows, use_container_width=True)

# Letter drafting (deterministic MVP)
st.subheader("Draft Justification Letter (deterministic MVP)")
letter = draft_letter_deterministic(
    payer=payer,
    procedure_code=proc_code,
    procedure_name=proc_name,
    dx_codes=dx_codes,
    facts=facts,
    results=rows,
)
st.text_area("Letter draft", value=letter, height=220)

# Audit trail
st.subheader("Audit Trail")
audit = {
    "payer": payer,
    "procedure_code": proc_code,
    "procedure_name": proc_name,
    "site_of_care": site,
    "specialty": specialty,
    "rules_version": rules.get("version"),
    "facts_extracted": facts,
    "requirements_checked": [r["key"] for r in rows],
    "overall_status": status,
    "submission_readiness": submission_readiness,
}
st.json(audit)

# Test suite
st.markdown("### Test Suite (Synthetic Cases)")
if st.button("Run test suite"):
    from engine.test_suites import run_cases

    test_rows = run_cases("rules/payer_rules.yaml", "inputs/synthetic_cases.json")
    st.dataframe(test_rows, use_container_width=True)
