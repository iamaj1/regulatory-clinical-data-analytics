from io import BytesIO
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
from reportlab.lib.styles import getSampleStyleSheet

def csv_report(findings): return findings.to_csv(index=False).encode()
def excel_report(data, findings):
    out=BytesIO()
    with pd.ExcelWriter(out,engine="openpyxl") as w:
        data.to_excel(w,index=False,sheet_name="Source data"); findings.to_excel(w,index=False,sheet_name="Findings")
    return out.getvalue()
def pdf_report(title, findings):
    out=BytesIO(); styles=getSampleStyleSheet(); story=[Paragraph(title,styles["Title"]),Spacer(1,12),Paragraph(f"Findings: {len(findings)}",styles["BodyText"])]
    rows=[["Rule","Severity","Reference","Explanation"]]+[[str(x.get(k,""))[:55] for k in ["rule_id","severity","record_reference","explanation"]] for _,x in findings.head(100).iterrows()]
    story += [Spacer(1,12),Table(rows,repeatRows=1)]
    SimpleDocTemplate(out,pagesize=letter).build(story); return out.getvalue()
