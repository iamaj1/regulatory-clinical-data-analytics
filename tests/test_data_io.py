from io import BytesIO
import pandas as pd
import pytest
from src.data_io import read_upload, workbook_sheets

class Upload(BytesIO):
    def __init__(self, data, name):
        super().__init__(data)
        self.name = name
        self.size = len(data)

def test_csv_upload_and_empty_upload_rejection():
    upload = Upload(b"module,document_id\n1,A\n", "data.csv")
    assert read_upload(upload).document_id.tolist() == ["A"]
    with pytest.raises(ValueError, match="non-empty"):
        read_upload(Upload(b"", "empty.csv"))

def test_excel_upload_and_sheet_selection():
    content = BytesIO()
    with pd.ExcelWriter(content, engine="openpyxl") as writer:
        pd.DataFrame({"id":[1]}).to_excel(writer, sheet_name="Register", index=False)
        pd.DataFrame({"id":[2]}).to_excel(writer, sheet_name="Other", index=False)
    upload = Upload(content.getvalue(), "data.xlsx")
    assert workbook_sheets(upload) == ["Register", "Other"]
    upload.seek(0)
    assert read_upload(upload, "Other").id.tolist() == [2]
