import pandas as pd
from src.reporting import csv_report, excel_report, pdf_report

def test_exports_are_generated():
    f=pd.DataFrame([{"record_reference":"A","rule_id":"X","severity":"High","explanation":"Test","corrective_action":"Fix","row":1}])
    assert b"rule_id" in csv_report(f)
    assert len(excel_report(pd.DataFrame({"a":[1]}),f))>100
    assert pdf_report("Report",f).startswith(b"%PDF")
