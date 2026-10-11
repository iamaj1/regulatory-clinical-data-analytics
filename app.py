import streamlit as st
import pandas as pd
import plotly.express as px
import json
from src.data_io import workbook_sheets, read_upload
from src.validators import validate_regulatory, validate_clinical
from src.reporting import csv_report, excel_report, pdf_report

st.set_page_config(page_title="Regulatory & Clinical Analytics", layout="wide")
st.title("Regulatory & Clinical Data Analytics System")
st.caption("Portfolio decision-support tool — synthetic/demo data only")
st.warning("Disclaimer: This tool supports data-quality review only. It does not provide regulatory, scientific, or technical eCTD validation and does not guarantee submission acceptance. Never upload patient-identifiable information.")
page=st.sidebar.radio("Navigate",["Home", "Regulatory dossier", "Clinical data quality"])
if page=="Home":
    st.header("Review data quality with traceable findings")
    st.write("Upload a CSV/XLSX register or use the bundled synthetic samples. Select a worksheet, review findings, and download results.")
    st.info("Expected-document checklist is entered as comma-separated names and is evaluated against the document_name column.")
else:
    regulatory=page=="Regulatory dossier"
    st.header("Regulatory Dossier Quality & Submission Readiness" if regulatory else "Clinical Data Quality & Analytics")
    demo = st.checkbox("Use synthetic demo data")
    uploaded = None if demo else st.file_uploader("Upload CSV or Excel", type=["csv","xlsx","xls"])
    try:
        if demo:
            path="samples/regulatory_demo.csv" if regulatory else "samples/clinical_demo.csv"; df=pd.read_csv(path)
        elif uploaded:
            sheets=workbook_sheets(uploaded); sheet=st.selectbox("Worksheet",sheets) if len(sheets)>1 else sheets[0]; df=read_upload(uploaded,sheet)
        else:
            st.info("Upload a file or enable synthetic demo mode."); st.stop()
    except Exception as e: st.error(str(e)); st.stop()
    st.subheader("Data preview"); st.dataframe(df.head(100), use_container_width=True)
    if regulatory:
        expected=st.text_input("Expected document checklist (comma-separated)","Quality Overall Summary, Clinical Overview")
        result=validate_regulatory(df,[x.strip() for x in expected.split(",") if x.strip()])
    else:
        rules_text = st.text_input("Consistency rules (JSON, optional)", "", placeholder='{"status": ["Complete", "Open"]}')
        try:
            consistency = json.loads(rules_text) if rules_text.strip() else {}
            if not isinstance(consistency, dict) or not all(isinstance(v, list) for v in consistency.values()):
                raise ValueError
        except (json.JSONDecodeError, ValueError):
            st.error("Consistency rules must be a JSON object whose values are lists.")
            st.stop()
        result=validate_clinical(df, consistency)
    findings=result["findings"]
    a,b,c=st.columns(3); a.metric("Records",len(df)); b.metric("Findings",len(findings)); c.metric("Critical / High",int(findings.severity.isin(["Critical","High"]).sum()) if not findings.empty else 0)
    if regulatory and "normalized_module" in result["data"]:
        st.plotly_chart(px.bar(result["data"].groupby("normalized_module",dropna=False).size().reset_index(name="documents"),x="normalized_module",y="documents",title="Documents by CTD module"),use_container_width=True)
    elif not regulatory and {"study_id","site_id"}.issubset(df.columns):
        unique_subjects = df["subject_id"].nunique(dropna=True) if "subject_id" in df else 0
        open_queries = int(df["query_status"].astype(str).str.strip().str.lower().eq("open").sum()) if "query_status" in df else 0
        d, e = st.columns(2); d.metric("Unique subjects", unique_subjects); e.metric("Open queries", open_queries)
        st.plotly_chart(px.bar(df.groupby(["study_id","site_id"]).size().reset_index(name="records"),x="site_id",y="records",color="study_id",title="Records by study/site"),use_container_width=True)
    st.subheader("Actionable findings"); st.dataframe(findings,use_container_width=True)
    st.download_button("Download CSV findings",csv_report(findings),"findings.csv","text/csv")
    st.download_button("Download Excel report",excel_report(result["data"],findings),"validation_report.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.download_button("Download PDF report",pdf_report(page,findings),"validation_report.pdf","application/pdf")
