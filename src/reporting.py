from io import BytesIO
from xml.sax.saxutils import escape

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def csv_report(findings):
    return findings.to_csv(index=False).encode("utf-8")


def excel_report(data, findings, case_reviews=None):
    """Create a workbook containing source data, findings, and optional clinical case reviews."""
    out = BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        data.to_excel(writer, index=False, sheet_name="Source data")
        findings.to_excel(writer, index=False, sheet_name="Findings")
        if case_reviews is not None and not case_reviews.empty:
            case_reviews.to_excel(writer, index=False, sheet_name="Case reviews")
    return out.getvalue()


def pdf_report(title, findings, case_reviews=None):
    """Create a readable summary PDF with finding status and optional subject review status."""
    out = BytesIO()
    styles = getSampleStyleSheet()
    story = [
        Paragraph(escape(str(title)), styles["Title"]),
        Spacer(1, 10),
        Paragraph(f"Total findings: {len(findings)}", styles["Heading2"]),
    ]

    if not findings.empty and "review_status" in findings.columns:
        status_counts = findings["review_status"].fillna("Pending").value_counts()
        story.append(Paragraph("Finding review status", styles["Heading3"]))
        story.append(Paragraph(escape(" | ".join(f"{status}: {count}" for status, count in status_counts.items())), styles["BodyText"]))
        story.append(Spacer(1, 8))

    columns = [
        ("rule_id", "Rule"),
        ("severity", "Severity"),
        ("record_reference", "Reference"),
        ("explanation", "Finding"),
        ("review_status", "Status"),
        ("action_taken", "Action taken"),
        ("reviewer_notes", "Reviewer notes"),
    ]
    available = [(key, label) for key, label in columns if key in findings.columns]
    rows = [[label for _, label in available]]
    for _, item in findings.head(100).iterrows():
        rows.append([Paragraph(escape(str(item.get(key, "") if pd.notna(item.get(key, "")) else "" )[:240]), styles["BodyText"]) for key, _ in available])

    if rows and len(rows[0]) > 0:
        table = Table(rows, repeatRows=1, colWidths=[(10.0 * inch) / len(available)] * len(available))
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DDECF5")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#203447")),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#C8D3DC")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("LEADING", (0, 0), (-1, -1), 9),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.extend([Spacer(1, 6), table])

    if case_reviews is not None and not case_reviews.empty:
        story.extend([Spacer(1, 14), Paragraph("Clinical subject case reviews", styles["Heading2"])])
        if "Review status" in case_reviews.columns:
            counts = case_reviews["Review status"].fillna("Pending").value_counts()
            story.append(Paragraph(escape(" | ".join(f"{status}: {count}" for status, count in counts.items())), styles["BodyText"]))
        case_columns = [key for key in ["Study ID", "Site ID", "Subject ID", "Review status", "Action taken", "Reviewer notes"] if key in case_reviews.columns]
        case_rows = [[key for key in case_columns]]
        for _, item in case_reviews.head(100).iterrows():
            case_rows.append([Paragraph(escape(str(item.get(key, "") if pd.notna(item.get(key, "")) else "")[:180]), styles["BodyText"]) for key in case_columns])
        if case_columns:
            case_table = Table(case_rows, repeatRows=1, colWidths=[(10.0 * inch) / len(case_columns)] * len(case_columns))
            case_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DDF3E7")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#C8D3DC")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
            ]))
            story.append(case_table)

    if len(findings) > 100:
        story.append(Spacer(1, 6))
        story.append(Paragraph("Note: the PDF shows the first 100 findings. Use the CSV or Excel export for the complete list.", styles["Italic"]))

    SimpleDocTemplate(out, pagesize=landscape(letter), rightMargin=0.5 * inch, leftMargin=0.5 * inch).build(story)
    return out.getvalue()
