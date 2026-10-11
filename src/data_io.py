from io import BytesIO
import pandas as pd

def workbook_sheets(uploaded):
    return pd.ExcelFile(uploaded).sheet_names if uploaded.name.lower().endswith((".xlsx", ".xls")) else ["CSV"]

def read_upload(uploaded, sheet=None):
    if uploaded is None or getattr(uploaded, "size", 1) == 0:
        raise ValueError("Please upload a non-empty CSV or Excel file.")
    name = uploaded.name.lower()
    if name.endswith(".csv"):
        return pd.read_csv(uploaded)
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(uploaded, sheet_name=sheet)
    raise ValueError("Unsupported format. Upload CSV, XLSX, or XLS.")
