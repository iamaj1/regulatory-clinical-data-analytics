import pandas as pd
from src.validators import validate_regulatory, validate_clinical

def test_regulatory_normalizes_and_flags_duplicates_and_dates():
    df=pd.DataFrame({"module":[" CTD Module 1 ","m1"],"document_id":["A","A"],"document_name":["x","x"],"version":["1",None],"review_status":["Approved","Bad"],"review_date":["2026-01-01","no"]})
    r=validate_regulatory(df)
    assert r["data"].normalized_module.tolist()==["Module 1","Module 1"]
    assert {"REG-004","REG-006","REG-007","REG-008"}.issubset(set(r["findings"].rule_id))

def test_clinical_allows_repeated_site_but_not_full_record():
    df=pd.DataFrame({"study_id":["S","S","S"],"site_id":["X","X","X"],"subject_id":["1","2","2"]})
    f=validate_clinical(df)["findings"]
    assert (f.rule_id=="CLN-005").sum()==2

def test_missing_columns_and_empty_data_are_safe():
    assert (validate_regulatory(pd.DataFrame())["findings"].rule_id == "REG-001").sum() == 5
    assert (validate_clinical(pd.DataFrame())["findings"].rule_id == "CLN-001").sum() == 3
    empty = pd.DataFrame(columns=["study_id", "site_id", "subject_id"])
    assert validate_clinical(empty)["findings"].empty

def test_configured_clinical_consistency_check():
    df = pd.DataFrame({"study_id":["S"],"site_id":["X"],"subject_id":["1"],"status":["Invalid"]})
    assert "CLN-004" in set(validate_clinical(df, {"status":["Complete"]})["findings"].rule_id)
