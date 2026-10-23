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
st.session_state.setdefault("workspace", "Regulatory")
st.session_state.setdefault("source_data", {})
st.session_state.setdefault("validation", {})
st.session_state.setdefault("review_actions", {})
st.session_state.setdefault("audit_events", [])
st.session_state.setdefault("active_record", None)

workspace_theme = {
    "Regulatory": {"sidebar_bg":"#263B50","sidebar_text":"#F4F8FC","sidebar_muted":"#C7D8E7","accent":"#8BB9D8","selected_bg":"#DDECF5","selected_text":"#203447","hover_bg":"#36536C","hero_bg":"#EAF2F8","hero_border":"#CBDCE8","hero_text":"#263B50","metric_bg":"#F3F7FA","metric_border":"#D8E4ED","table_border":"#D8E4ED"},
    "Clinical": {"sidebar_bg":"#24443A","sidebar_text":"#F4FBF7","sidebar_muted":"#C7E4D7","accent":"#9AD9BD","selected_bg":"#DDF3E7","selected_text":"#234136","hover_bg":"#31594B","hero_bg":"#EAF5EF","hero_border":"#CDE4D6","hero_text":"#24443A","metric_bg":"#F3F9F5","metric_border":"#D6E8DC","table_border":"#D6E8DC"}
}[st.session_state.workspace]

css = """
<style>
:root { color-scheme: light; }
.block-container {padding-top: 2rem; padding-bottom: 2rem; max-width: 1440px;}
[data-testid="stSidebar"] {background: __SIDEBAR_BG__; border-right: 1px solid __HERO_BORDER__;}
[data-testid="stSidebar"] * {color: __SIDEBAR_TEXT__;}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {color: __SIDEBAR_MUTED__ !important;}
[data-testid="stSidebar"] [data-testid="stRadio"] label {padding: .45rem .55rem; border-radius: .55rem; line-height: 1.35; color: __SIDEBAR_TEXT__ !important;}
[data-testid="stSidebar"] [data-testid="stRadio"] label:hover {background: __HOVER_BG__;}
[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) {background: __SELECTED_BG__; color: __SELECTED_TEXT__ !important; font-weight: 650;}
[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) * {color: __SELECTED_TEXT__ !important;}
[data-testid="stSidebar"] [data-testid="stSelectbox"] label {color: __SIDEBAR_TEXT__ !important; font-weight: 700; font-size: .98rem; padding-bottom: .2rem;}\n[data-testid="stSidebar"] [data-testid="stSelectbox"] div[data-baseweb="select"] {background: #fff; border: 1px solid #B7C9D8; border-radius: .6rem; min-height: 2.8rem;}
[data-testid="stSidebar"] [data-testid="stSelectbox"] div[data-baseweb="select"] * {color: #243746 !important; font-weight: 600;}
[data-testid="stMetric"] {background: __METRIC_BG__; border: 1px solid __METRIC_BORDER__; padding: .8rem 1rem; border-radius: .8rem;}
div[data-testid="stButton"] > button {border-radius: .65rem; min-height: 2.6rem;}
[data-testid="stDataFrame"] {border: 1px solid __TABLE_BORDER__; border-radius: .6rem;}
.small-note {color:#63716b; font-size:.9rem;}
.hero {padding:1.15rem 1.35rem; background:__HERO_BG__; border:1px solid __HERO_BORDER__; border-radius:1rem; margin-bottom:1rem;}
.hero h2 {margin:0 0 .35rem 0; color:__HERO_TEXT__;}
@media (max-width: 700px) {.block-container {padding: .8rem .8rem 1.5rem;} h1 {font-size:1.65rem !important;}}
</style>
"""
for theme_key, css_key in [("sidebar_bg","SIDEBAR_BG"),("sidebar_text","SIDEBAR_TEXT"),("sidebar_muted","SIDEBAR_MUTED"),("hover_bg","HOVER_BG"),("selected_bg","SELECTED_BG"),("selected_text","SELECTED_TEXT"),("hero_bg","HERO_BG"),("hero_border","HERO_BORDER"),("hero_text","HERO_TEXT"),("metric_bg","METRIC_BG"),("metric_border","METRIC_BORDER"),("table_border","TABLE_BORDER")]:
    css = css.replace("__" + css_key + "__", workspace_theme[theme_key])
st.markdown(css, unsafe_allow_html=True)

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

def get_validated(data: pd.DataFrame, workspace: str, expected_text: str = "", consistency_text: str = ""):
    if workspace == "Regulatory":
        expected = [x.strip() for x in expected_text.split(",") if x.strip()]
        return validate_regulatory(data, expected)
    consistency = json.loads(consistency_text) if consistency_text.strip() else {}
    if not isinstance(consistency, dict) or not all(isinstance(v, list) for v in consistency.values()):
        raise ValueError("Consistency rules must be a JSON object whose values are lists.")
    return validate_clinical(data, consistency)

def run_validation_action():
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

with st.sidebar:
    st.markdown("## 📊 Regulatory & Clinical")
    st.selectbox("Switch workspace", ["Regulatory", "Clinical"], key="workspace")
    st.caption(f"{st.session_state.workspace.upper()} WORKSPACE")

    # Upload is an always-visible workflow action, not a separate navigation page.
    st.markdown("### ⬆️ Upload & validate")
    demo = st.checkbox("Use synthetic demo dataset", key=f"{current_key()}_demo")
    uploaded = st.file_uploader("Choose CSV or Excel file", type=["csv", "xlsx", "xls"], key=f"{current_key()}_upload")
    if demo:
        sample = Path("samples/regulatory_demo.csv" if st.session_state.workspace == "Regulatory" else "samples/clinical_demo.csv")
        if sample.exists():
            st.session_state.source_data[current_key()] = pd.read_csv(sample)
            st.caption(f"Demo loaded: {sample.name}")
    elif uploaded is not None:
        try:
            sheets = workbook_sheets(uploaded)
            sheet = st.selectbox("Worksheet", sheets, key=f"{current_key()}_sheet") if len(sheets) > 1 else sheets[0]
            uploaded.seek(0)
            data = read_upload(uploaded, sheet)
            st.session_state.source_data[current_key()] = data
            st.caption(f"Loaded: {uploaded.name} · {len(data):,} rows")
        except Exception as exc:
            st.error(f"Could not read this file: {exc}")
    if st.button("▶ Submit & Run Validation", type="primary", width="stretch", key=f"{current_key()}_run_validation"):
        run_validation_action()
    st.divider()

    if st.session_state.workspace == "Regulatory":
        pages = ["Dashboard", "Validation Results", "Regulatory Dossier", "CTD Module View", "Analytics & Trends", "Reports & Export", "Audit Trail", "Settings"]
    else:
        pages = ["Dashboard", "Validation Results", "Clinical Data Quality", "Study Listings", "Subject Data Review", "Analytics & Trends", "Reports & Export", "Audit Trail", "Settings"]
    if st.session_state.get("jump_page") in pages:
        st.session_state["page_nav"] = st.session_state.pop("jump_page")
    if st.session_state.get("page_nav") not in pages:
        st.session_state["page_nav"] = "Dashboard"
    page = st.radio("Navigation", pages, key="page_nav", label_visibility="collapsed")

st.markdown('<div class="hero"><h2>Regulatory & Clinical Data Analytics</h2><div class="small-note">A simple 4-step workspace: 1. Upload your file → 2. Check the data → 3. Review issues → 4. Download the final report.</div></div>', unsafe_allow_html=True)
st.info("New here? Start on Dashboard. Upload a CSV/Excel file, click **Run validation**, review each issue in plain language, then open **Reports & Export** for your final summary.")
st.caption("Portfolio decision-support prototype · Use synthetic/demo data only. Do not upload patient-identifiable information.")

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
    left, right = st.columns([1, 1.4])
    with left:
        donut = px.pie(counts, values="Count", names="review_status", hole=0.62, title="Review progress",
                       color="review_status", color_discrete_map={"Pending":"#C89B55","In Review":"#6D9CB5","Completed":"#5B9278","Not Applicable":"#9AA5AD"})
        donut.update_traces(textposition="inside", textinfo="percent")
        donut.update_layout(height=280, margin=dict(l=8,r=8,t=48,b=8), legend_title_text="Status", font=dict(size=11))
        st.plotly_chart(donut, use_container_width=True, config={"displayModeBar": False})
    with right:
        fig = px.bar(counts.sort_values("Count"), x="Count", y="review_status", orientation="h", text="Count",
                     title="Issues by review status", color="review_status",
                     color_discrete_map={"Pending":"#C89B55","In Review":"#6D9CB5","Completed":"#5B9278","Not Applicable":"#9AA5AD"})
        fig.update_layout(height=280, margin=dict(l=8,r=12,t=48,b=8), showlegend=False,
                          xaxis_title="Number of issues", yaxis_title="", font=dict(size=11))
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

if page == "Dashboard":
    st.header(f"{st.session_state.workspace} Dashboard")
    st.write("Follow the steps below in order. You do not need to know technical terms to use this app.")
    st.markdown("### Step 1 · Add your data")
    st.caption("Choose a CSV or Excel file. For a safe practice run, use the sample data in the sidebar.")
    main_upload = st.file_uploader("Upload your CSV / Excel file", type=["csv", "xlsx", "xls"], key=f"{current_key()}_dashboard_upload", help="Use a table with column headers in the first row. Do not upload patient-identifiable or confidential data.")
    if main_upload is not None:
        try:
            main_sheets = workbook_sheets(main_upload)
            main_sheet = st.selectbox("Choose worksheet", main_sheets, key=f"{current_key()}_dashboard_sheet") if len(main_sheets) > 1 else main_sheets[0]
            main_upload.seek(0)
            main_data = read_upload(main_upload, main_sheet)
            st.session_state.source_data[current_key()] = main_data
            st.success(f"File ready: {main_upload.name} · {len(main_data):,} rows · {len(main_data.columns)} columns")
        except Exception as exc:
            st.error(f"Could not read this file: {exc}")
    data, result = current_data(), current_result()
    st.markdown("### Step 2 · Check your data")
    if data is not None:
        st.caption(f"Current dataset: {len(data):,} rows and {len(data.columns)} columns.")
        if st.button("Run validation", type="primary", use_container_width=True, key=f"{current_key()}_dashboard_validate"):
            run_validation_action()
            st.rerun()
    else:
        st.info("No file loaded yet. Upload a file above, or tick **Use synthetic demo dataset** in the sidebar.")
    kpis(data, result)
    if data is not None:
        st.subheader("Uploaded data preview")
        st.caption(f"{len(data):,} records · {len(data.columns)} fields")
        st.dataframe(data.head(20), use_container_width=True, hide_index=True)
        left_action, mid_action, right_action = st.columns(3)
        with left_action:
            if st.button("Open validation results", type="primary", use_container_width=True):
                st.session_state["page_nav"] = "Validation Results"; st.rerun()
        with mid_action:
            case_page = "Subject Data Review" if st.session_state.workspace == "Clinical" else "Regulatory Dossier"
            if st.button("Open record / case review", use_container_width=True):
                st.session_state["page_nav"] = case_page; st.rerun()
        with right_action:
            if st.button("Open final report", use_container_width=True):
                st.session_state["page_nav"] = "Reports & Export"; st.rerun()
        chart_status(result)
    else:
        st.info("Start here: use the Upload & validate panel at the top of the sidebar.")
    st.markdown("#### Workflow")
    steps = st.columns(4)
    for col, title, desc in zip(steps, ["1 · Upload", "2 · Validate", "3 · Review", "4 · Export"],
                                ["Choose CSV/XLSX", "Run configured checks", "Record action and status", "Download final report"]):
        col.markdown(f"**{title}**")
        col.caption(desc)
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
                # Present every source field as a readable two-column table (never raw JSON).
                raw_record = record.to_dict()
                detail_rows = []
                for field_name, raw_value in raw_record.items():
                    if pd.isna(raw_value):
                        display_value = "—"
                    elif isinstance(raw_value, (pd.Timestamp, datetime)):
                        display_value = raw_value.strftime("%Y-%m-%d %H:%M") if not pd.isna(raw_value) else "—"
                    else:
                        display_value = str(raw_value).strip()
                        if not display_value:
                            display_value = "—"
                    detail_rows.append({"Field": str(field_name).replace("_", " ").strip().title(), "Value": display_value})
                details_table = pd.DataFrame(detail_rows, columns=["Field", "Value"])
                st.dataframe(
                    details_table,
                    use_container_width=True,
                    hide_index=True,
                    height=min(520, max(140, 38 * (len(details_table) + 1))),
                    column_config={
                        "Field": st.column_config.TextColumn("Field", width="medium"),
                        "Value": st.column_config.TextColumn("Value", width="large"),
                    },
                )
                if result is not None and not result["findings"].empty:
                    related = result["findings"][result["findings"]["row"] == int(selected)]
                    st.markdown("#### Findings for this record")
                    if related.empty:
                        st.success("No validation findings are linked to this record.")
                    else:
                        st.dataframe(related, use_container_width=True, hide_index=True)
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
        st.table(pd.DataFrame({"Field": list(record.where(pd.notna(record), None).to_dict().keys()), "Value": [str(v) if v is not None else "—" for v in record.where(pd.notna(record), None).to_dict().values()]}))
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
            chart_left, chart_right = st.columns([1, 1.4])
            with chart_left:
                sev_fig = px.pie(severity, values="Findings", names="severity", hole=0.55, title="Severity mix",
                                 color="severity", color_discrete_map={"Critical":"#A84E4E","High":"#D18A54","Medium":"#D2B45E","Low":"#63947C"})
                sev_fig.update_traces(textposition="inside", textinfo="percent")
                sev_fig.update_layout(height=290, margin=dict(l=8,r=8,t=45,b=8), font=dict(size=11))
                st.plotly_chart(sev_fig, use_container_width=True, config={"displayModeBar":False})
            with chart_right:
                fig = px.bar(severity.sort_values("Findings"), x="Findings", y="severity", orientation="h", text="Findings", title="Issues by severity",
                             color="severity", color_discrete_map={"Critical":"#A84E4E","High":"#D18A54","Medium":"#D2B45E","Low":"#63947C"})
                fig.update_layout(height=290, margin=dict(l=8,r=10,t=45,b=8), showlegend=False, xaxis_title="Number of issues", yaxis_title="", font=dict(size=11))
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
