import streamlit as st
from engine.rules_loader import load_rules
from engine.extract import extract_facts
from engine.evaluate import evaluate_requirements, compute_readiness_score
from llm.draft_letter import draft_letter_deterministic

st.set_page_config(page_title="PA Readiness Copilot", layout="wide")

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

    note_text = st.text_area("Clinical note (mock/synthetic)", height=220, placeholder="Paste a synthetic note here...")
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
score_info = compute_readiness_score(results)

# outputs
st.markdown("### Outputs")
o1, o2 = st.columns([1, 2])

with o1:
    st.metric("PA Readiness Score", f"{score_info['readiness_score']}/100")
    st.write(
        {
            "met": score_info["met_count"],
            "weak": score_info["weak_count"],
            "missing": score_info["missing_count"],
            "total": score_info["total"],
        }
    )

with o2:
    st.subheader("Missing / Weak Requirements")
    if not reasons:
        st.success("No missing/weak requirements detected by current rules.")
    else:
        for r in reasons:
            st.write(f"- {r}")

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

st.subheader("Draft Justification Letter (deterministic MVP)")
letter = draft_letter_deterministic(
    payer=payer,
    procedure_code=proc_code,
    procedure_name=proc_name,
    dx_codes=dx_codes,
    facts=facts,
    results=[x for x in rows],
)
st.text_area("Letter draft", value=letter, height=220)

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
}
st.json(audit)

st.markdown("### Test Suite (Synthetic Cases)")
if st.button("Run test suite"):
    from engine.test_suite import run_cases
    rows = run_cases("rules/payer_rules.yaml", "inputs/synthetic_cases.json")
    st.dataframe(rows, use_container_width=True)

