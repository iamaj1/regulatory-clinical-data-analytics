from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from src.data_io import read_upload, workbook_sheets
from src.reporting import csv_report, excel_report, pdf_report
from src.validators import validate_clinical, validate_regulatory

st.set_page_config(page_title="Regulatory & Clinical Data Analytics", page_icon="📊", layout="wide")

# Calm, readable, responsive presentation. Keep active and inactive navigation text legible.
st.markdown("""
<style>
:root { color-scheme: light; }
.block-container {padding-top: 1.35rem; padding-bottom: 2rem; max-width: 1440px;}
[data-testid="stSidebar"] {background: #edf1ef; border-right: 1px solid #d8e0dc;}
[data-testid="stSidebar"] * {color: #253b36 !important;}
[data-testid="stSidebar"] [data-testid="stRadio"] label {padding: .45rem .55rem; border-radius: .55rem; line-height: 1.35;}
[data-testid="stSidebar"] [data-testid="stRadio"] label:hover {background: #dfe8e3;}
[data-testid="stMetric"] {background: #f6f8f6; border: 1px solid #e2e8e3; padding: .8rem 1rem; border-radius: .8rem;}
div[data-testid="stButton"] > button {border-radius: .65rem; min-height: 2.6rem;}
[data-testid="stDataFrame"] {border: 1px solid #e1e7e3; border-radius: .6rem;}
.small-note {color:#63716b; font-size:.9rem;}
.hero {padding:1.15rem 1.35rem; background:linear-gradient(115deg,#f3f6f3,#e8f0ec); border:1px solid #dfe7e1; border-radius:1rem; margin-bottom:1rem;}
.hero h2 {margin:0 0 .35rem 0; color:#263c35;}
@media (max-width: 700px) {.block-container {padding: .8rem .8rem 1.5rem;} h1 {font-size:1.65rem !important;}}
</style>
""", unsafe_allow_html=True)

st.session_state.setdefault("workspace", "Regulatory")
st.session_state.setdefault("source_data", {})
st.session_state.setdefault("validation", {})
st.session_state.setdefault("review_actions", {})
st.session_state.setdefault("audit_events", [])
st.session_state.setdefault("active_record", None)

def log_event(message: str) -> None:
    st.session_state.audit_events.insert(0, {"Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Event": message})
    st.session_state.audit_events = st.session_state.audit_events[:500]

def current_key() -> str:
    return st.session_state.workspace.lower()

def current_data():
    return st.session_state.source_data.get(current_key())

def current_result():
    return st.session_state.validation.get(current_key())

def findings_with_actions(findings: pd.DataFrame) -> pd.DataFrame:
    if findings.empty:
        return findings.copy()
    out = findings.copy()
    statuses, actions = [], []
    for _, row in out.iterrows():
        key = f"{current_key()}::{row.get('rule_id','')}::{row.get('record_reference','')}::{row.get('row','')}"
        saved = st.session_state.review_actions.get(key, {})
        statuses.append(saved.get("status", "Pending"))
        actions.append(saved.get("action", "Not started"))
    out["review_status"] = statuses
    out["action_taken"] = actions
    return out

with st.sidebar:
    st.markdown("## 📊 Regulatory & Clinical")
    st.selectbox("Switch workspace", ["Regulatory", "Clinical"], key="workspace")
    st.caption(f"{st.session_state.workspace.upper()} WORKSPACE")
    if st.session_state.workspace == "Regulatory":
        pages = ["Dashboard", "Document Upload", "Regulatory Dossier", "Validation Results", "CTD Module View", "Analytics & Trends", "Reports & Export", "Audit Trail", "Settings"]
    else:
        pages = ["Dashboard", "Data Upload", "Clinical Data Quality", "Validation Results", "Study Listings", "Subject Data Review", "Analytics & Trends", "Reports & Export", "Audit Trail", "Settings"]
    if st.session_state.get("jump_page") in pages:
        st.session_state["page_nav"] = st.session_state.pop("jump_page")
    page = st.radio("Navigation", pages, key="page_nav", label_visibility="collapsed")

st.markdown('<div class="hero"><h2>Regulatory & Clinical Data Analytics</h2><div class="small-note">Upload → Validate → Review → Export · Clear, traceable data-quality workflow</div></div>', unsafe_allow_html=True)
st.caption("Portfolio decision-support prototype · Use synthetic/demo data only. Do not upload patient-identifiable information.")

def get_validated(data: pd.DataFrame, workspace: str, expected_text: str = "", consistency_text: str = ""):
    if workspace == "Regulatory":
        expected = [x.strip() for x in expected_text.split(",") if x.strip()]
        return validate_regulatory(data, expected)
    consistency = json.loads(consistency_text) if consistency_text.strip() else {}
    if not isinstance(consistency, dict) or not all(isinstance(v, list) for v in consistency.values()):
        raise ValueError("Consistency rules must be a JSON object whose values are lists.")
    return validate_clinical(data, consistency)

def do_validate():
    data = current_data()
    if data is None:
        st.warning("Upload a file or load the synthetic sample first.")
        return
    try:
        result = get_validated(data, st.session_state.workspace,
            st.session_state.get("expected_docs", "Quality Overall Summary, Clinical Overview"),
            st.session_state.get("consistency_rules", ""))
        st.session_state.validation[current_key()] = result
        log_event(f"{st.session_state.workspace}: validation run for {len(data)} records; {len(result['findings'])} findings.")
        st.success("Validation completed. Open Validation Results to review each finding.")
    except (ValueError, json.JSONDecodeError) as exc:
        st.error(str(exc))

def kpis(data, result):
    findings = result["findings"] if result else pd.DataFrame()
    total_findings = len(findings)
    if not findings.empty:
        statuses = []
        for _, row in findings.iterrows():
            key = f"{current_key()}::{row.get('rule_id','')}::{row.get('record_reference','')}::{row.get('row','')}"
            statuses.append(st.session_state.review_actions.get(key, {}).get("status", "Pending"))
        pending = sum(x == "Pending" for x in statuses)
        complete = sum(x == "Completed" for x in statuses)
    else:
        pending = complete = 0
    cols = st.columns(4)
    cols[0].metric("Records / Documents", len(data) if data is not None else "—")
    cols[1].metric("Findings", total_findings if result else "—")
    cols[2].metric("Pending review", pending if result else "—")
    cols[3].metric("Completed actions", complete if result else "—")

def chart_status(result):
    if not result or result["findings"].empty:
        st.info("Run validation to generate charts from your actual data.")
        return
    data = findings_with_actions(result["findings"])
    counts = data.groupby("review_status").size().reset_index(name="Count")
    fig = px.bar(counts, x="Count", y="review_status", orientation="h", text="Count",
                 title="Findings by review status", color="review_status",
                 color_discrete_map={"Pending":"#c7a36b","In Review":"#7a9eab","Completed":"#7b9b88","Not Applicable":"#a7ada9"})
    fig.update_layout(height=250, margin=dict(l=8,r=15,t=45,b=8), showlegend=False,
                      xaxis_title="Number of findings", yaxis_title="", font=dict(size=12))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

def action_editor(findings: pd.DataFrame, label: str = "Finding"):
    if findings.empty:
        st.success("No findings to review for this dataset.")
        return
    table = findings_with_actions(findings)
    st.dataframe(table, use_container_width=True, hide_index=True)
    st.markdown("#### Review one item")
    options = []
    for i, row in findings.iterrows():
        options.append(f"{i + 1}. {row.get('rule_id','Rule')} · {row.get('record_reference','Record')} · {row.get('severity','')} · row {row.get('row','')}")
    chosen = st.selectbox(f"Select {label.lower()}", options, key=f"{current_key()}_finding_select")
    idx = options.index(chosen)
    row = findings.iloc[idx]
    st.markdown(f"**{row.get('rule_id','Finding')} — {row.get('severity','')}**")
    st.write(row.get("explanation", "No explanation available."))
    st.info(f"Suggested corrective action: {row.get('corrective_action', 'Review the source record.')}")
    key = f"{current_key()}::{row.get('rule_id','')}::{row.get('record_reference','')}::{row.get('row','')}"
    saved = st.session_state.review_actions.get(key, {})
    with st.form(f"action_form_{current_key()}_{idx}"):
        status = st.selectbox("Review status", ["Pending", "In Review", "Completed", "Not Applicable"],
                              index=["Pending", "In Review", "Completed", "Not Applicable"].index(saved.get("status", "Pending")))
        action = st.selectbox("Action taken", ["Not started", "Corrected source data", "Requested clarification", "Escalated for review", "Accepted / no change", "Other"],
                              index=["Not started", "Corrected source data", "Requested clarification", "Escalated for review", "Accepted / no change", "Other"].index(saved.get("action", "Not started")))
        notes = st.text_area("Reviewer notes", value=saved.get("notes", ""), placeholder="Record what was checked and why this decision was made.")
        submitted = st.form_submit_button("Save review action", type="primary")
        if submitted:
            st.session_state.review_actions[key] = {"status": status, "action": action, "notes": notes, "updated_at": datetime.now().isoformat(timespec="seconds")}
            log_event(f"{st.session_state.workspace}: {row.get('rule_id')} / {row.get('record_reference')} marked {status}; action: {action}.")
            st.success("Review action saved for this session.")

def report_page(data, result):
    if data is None:
        st.info("Upload data and run validation before exporting a report.")
        return
    findings = findings_with_actions(result["findings"]) if result else pd.DataFrame()
    st.subheader("Final report")
    st.write("The report combines the uploaded dataset, validation findings, severity, recommended corrective actions and review status.")
    a, b, c = st.columns(3)
    a.metric("Source records", len(data))
    b.metric("Findings", len(findings) if result else "—")
    c.metric("Completed", int((findings["review_status"] == "Completed").sum()) if not findings.empty else 0)
    if result:
        st.dataframe(findings, use_container_width=True, hide_index=True)
        st.download_button("Download CSV findings", csv_report(findings), "review_findings.csv", "text/csv", use_container_width=True)
        st.download_button("Download Excel report", excel_report(data, findings), "final_review_report.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
        st.download_button("Download PDF summary", pdf_report(f"{st.session_state.workspace} Review Report", findings),
                           "final_review_summary.pdf", "application/pdf", use_container_width=True)
    else:
        st.warning("Validation has not been run yet.")

if page in ("Document Upload", "Data Upload"):
    st.header("Step 1 · Upload data")
    st.write("Upload a CSV/XLSX file, preview the contents, then explicitly run validation.")
    demo = st.checkbox("Use synthetic demo dataset", key=f"{current_key()}_demo")
    uploaded = st.file_uploader("Choose CSV or Excel file", type=["csv", "xlsx", "xls"], key=f"{current_key()}_upload")
    if st.session_state.workspace == "Regulatory":
        st.text_input("Expected document checklist (comma-separated)", "Quality Overall Summary, Clinical Overview", key="expected_docs")
    else:
        st.text_input("Consistency rules (optional JSON)", "", key="consistency_rules", placeholder='{"status":["Complete","Open"]}')
    if demo:
        sample = Path("samples/regulatory_demo.csv" if st.session_state.workspace == "Regulatory" else "samples/clinical_demo.csv")
        if sample.exists():
            st.session_state.source_data[current_key()] = pd.read_csv(sample)
            st.caption(f"Loaded synthetic sample: {sample.name}")
    elif uploaded is not None:
        try:
            sheets = workbook_sheets(uploaded)
            sheet = st.selectbox("Worksheet", sheets) if len(sheets) > 1 else sheets[0]
            uploaded.seek(0)
            data = read_upload(uploaded, sheet)
            st.session_state.source_data[current_key()] = data
            st.caption(f"Selected file: {uploaded.name} · {len(data):,} rows · {len(data.columns)} columns")
        except Exception as exc:
            st.error(f"Could not read this file: {exc}")
    data = current_data()
    if data is not None:
        st.subheader("File preview")
        st.dataframe(data.head(50), use_container_width=True, hide_index=True)
        if st.button("Submit data & run validation", type="primary", use_container_width=True):
            do_validate()
        st.markdown("#### Quick actions")
        a, b, c = st.columns(3)
        if a.button("View results", use_container_width=True):
            st.session_state["jump_page"] = "Validation Results"
            st.rerun()
        if b.button("Open case study", use_container_width=True):
            st.session_state["jump_page"] = "Subject Data Review" if st.session_state.workspace == "Clinical" else "Regulatory Dossier"
            st.rerun()
        if c.button("Final report", use_container_width=True):
            st.session_state["jump_page"] = "Reports & Export"
            st.rerun()
elif page == "Dashboard":
    st.header(f"{st.session_state.workspace} work management")
    st.write("A single place to see workload, validate files, review findings and export the final report.")
    data, result = current_data(), current_result()
    kpis(data, result)
    st.markdown("#### Workflow")
    steps = st.columns(4)
    for col, title, desc in zip(steps, ["1 · Upload", "2 · Validate", "3 · Review", "4 · Export"],
                                ["Select a file", "Run quality rules", "Record decisions", "Download report"]):
        col.markdown(f"**{title}**")
        col.caption(desc)
    if data is None:
        st.info("Start by opening Document Upload / Data Upload in the sidebar, or use a synthetic demo dataset.")
    else:
        st.caption(f"Current dataset: {len(data):,} rows × {len(data.columns)} columns")
        chart_status(result)
    st.markdown("#### Quick actions")
    a, b, c = st.columns(3)
    if a.button("View Results", use_container_width=True):
        st.session_state["page_nav"] = "Validation Results"; st.rerun()
    if b.button("Open Case Study", use_container_width=True):
        st.session_state["page_nav"] = "Subject Data Review" if st.session_state.workspace == "Clinical" else "Regulatory Dossier"; st.rerun()
    if c.button("Final Report", use_container_width=True):
        st.session_state["page_nav"] = "Reports & Export"; st.rerun()
elif page in ("Regulatory Dossier", "Clinical Data Quality"):
    st.header("Record explorer")
    data, result = current_data(), current_result()
    if data is None:
        st.info("Upload a dataset first.")
    else:
        st.write("Browse the source records. Select a row to inspect all fields and related findings.")
        st.dataframe(data, use_container_width=True, hide_index=True)
        if not data.empty:
            selected = st.number_input("Source row number", min_value=1, max_value=len(data), value=1, step=1)
            record = data.iloc[int(selected)-1]
            with st.expander("Selected record details", expanded=True):
                st.json(record.where(pd.notna(record), None).to_dict())
                if result and not result["findings"].empty:
                    related = result["findings"][result["findings"]["row"] == int(selected)]
                    st.markdown("**Findings for this row**")
                    st.dataframe(related, use_container_width=True, hide_index=True)
                    if not related.empty:
                        action_editor(related, "record finding")
elif page == "Validation Results":
    st.header("Validation results & review actions")
    result = current_result()
    if result is None:
        st.info("Upload data and click Submit data & run validation.")
    else:
        findings = result["findings"]
        kpis(current_data(), result)
        action_editor(findings)
elif page == "CTD Module View":
    st.header("CTD module view")
    data, result = current_data(), current_result()
    if data is None or "normalized_module" not in (result or {}).get("data", pd.DataFrame()).columns:
        st.info("Upload a regulatory register and run validation to view documents grouped by CTD module.")
    else:
        grouped = result["data"].groupby("normalized_module", dropna=False).size().reset_index(name="Documents")
        st.dataframe(grouped, use_container_width=True, hide_index=True)
        st.plotly_chart(px.bar(grouped, x="Documents", y="normalized_module", orientation="h", text="Documents", title="Documents per CTD module").update_layout(height=260, margin=dict(l=8,r=10,t=45,b=8)), use_container_width=True, config={"displayModeBar":False})
elif page == "Study Listings":
    st.header("Study listings")
    data = current_data()
    if data is None or not {"study_id", "site_id", "subject_id"}.issubset(data.columns):
        st.info("Upload clinical data with study_id, site_id and subject_id columns.")
    else:
        # One row per study: this view is deliberately different from subject-level review.
        agg = {"Sites": ("site_id", "nunique"), "Records": ("subject_id", "size"), "Unique subjects": ("subject_id", "nunique")}
        listing = data.groupby("study_id", dropna=False).agg(**agg).reset_index()
        if "status" in data:
            statuses = data.groupby("study_id")["status"].apply(lambda s: ", ".join(sorted(set(s.dropna().astype(str))))).rename("Observed statuses").reset_index()
            listing = listing.merge(statuses, on="study_id", how="left")
        st.caption("Study-level summary: one row per study, not one row per subject.")
        st.dataframe(listing, use_container_width=True, hide_index=True)
        st.download_button("Export study listing CSV", listing.to_csv(index=False).encode(), "study_listings.csv", "text/csv")
elif page == "Subject Data Review":
    st.header("Subject-level case review")
    data, result = current_data(), current_result()
    if data is None or not {"study_id", "site_id", "subject_id"}.issubset(data.columns):
        st.info("Upload clinical data with study_id, site_id and subject_id columns.")
    else:
        labels = [f"Row {i+1} · Study {r.get('study_id','')} · Site {r.get('site_id','')} · Subject {r.get('subject_id','')}" for i, r in data.iterrows()]
        chosen = st.selectbox("Choose an individual subject record", labels)
        idx = labels.index(chosen); record = data.iloc[idx]
        st.subheader("Case details")
        st.json(record.where(pd.notna(record), None).to_dict())
        if result and not result["findings"].empty:
            related = result["findings"][result["findings"]["row"] == idx + 1]
            st.markdown("#### Findings for this subject")
            if related.empty:
                st.success("No configured validation findings for this record.")
            else:
                action_editor(related, "subject finding")
        with st.form(f"subject_action_{idx}"):
            case_status = st.selectbox("Case review status", ["Pending", "In Review", "Completed", "Not Applicable"], key=f"case_status_{idx}")
            case_notes = st.text_area("Case review notes", key=f"case_notes_{idx}")
            if st.form_submit_button("Save case review"):
                key = f"{current_key()}::CASE::{idx+1}"
                st.session_state.review_actions[key] = {"status":case_status, "action":"Case review", "notes":case_notes, "updated_at":datetime.now().isoformat(timespec="seconds")}
                log_event(f"Clinical subject row {idx+1} case review saved as {case_status}.")
                st.success("Case review saved for this session.")
elif page == "Analytics & Trends":
    st.header("Analytics & trends")
    data, result = current_data(), current_result()
    if data is None:
        st.info("Upload a dataset first.")
    elif result is None:
        st.info("Run validation to calculate analytics from real data.")
    else:
        findings = result["findings"]
        if findings.empty:
            st.success("No findings were generated for this dataset.")
        else:
            chart_status(result)
            severity = findings.groupby("severity").size().reset_index(name="Findings")
            fig = px.bar(severity, x="Findings", y="severity", orientation="h", text="Findings", title="Findings by severity",
                         color="severity", color_discrete_map={"Critical":"#9b5555","High":"#c78d64","Medium":"#c6ad72","Low":"#7b9b88"})
            fig.update_layout(height=240, margin=dict(l=8,r=10,t=45,b=8), showlegend=False, xaxis_title="Number of findings", yaxis_title="")
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})
            rule_counts = findings.groupby("rule_id").size().reset_index(name="Findings").sort_values("Findings", ascending=True)
            fig2 = px.bar(rule_counts, x="Findings", y="rule_id", orientation="h", text="Findings", title="Findings by validation rule")
            fig2.update_layout(height=max(200, min(360, 30*len(rule_counts)+80)), margin=dict(l=8,r=10,t=45,b=8), xaxis_title="Number of findings", yaxis_title="")
            st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar":False})
elif page == "Reports & Export":
    report_page(current_data(), current_result())
elif page == "Audit Trail":
    st.header("Audit trail")
    events = st.session_state.audit_events
    if events:
        st.dataframe(pd.DataFrame(events), use_container_width=True, hide_index=True)
        st.download_button("Download audit trail CSV", pd.DataFrame(events).to_csv(index=False).encode(), "audit_trail.csv", "text/csv")
    else:
        st.info("No session events recorded yet. Validation runs and saved review actions will appear here.")
elif page == "Settings":
    st.header("Settings & limitations")
    st.markdown("- This prototype keeps uploaded data and review actions in the current Streamlit session only. Refreshes/restarts may clear them.")
    st.markdown("- Use synthetic/demo data only; do not upload patient-identifiable or confidential submission data.")
    st.markdown("- Findings are configurable data-quality flags, not official regulatory decisions or clinical medical advice.")
    st.markdown("- A database is required for persistent records, users, and durable audit trails.")
