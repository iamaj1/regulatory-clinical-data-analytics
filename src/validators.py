from __future__ import annotations
import pandas as pd

REG_REQUIRED = ["module", "document_id", "document_name", "version", "review_status"]
CLIN_REQUIRED = ["study_id", "site_id", "subject_id"]
VALID_MODULES = {f"{n}": f"Module {n}" for n in range(1, 6)}
VALID_MODULES.update({f"module {n}": f"Module {n}" for n in range(1, 6)})
VALID_MODULES.update({f"m{n}": f"Module {n}" for n in range(1, 6)})
VALID_MODULES.update({f"ctd module {n}": f"Module {n}" for n in range(1, 6)})

def finding(row, rule, severity, explanation, action, ref):
    return {"record_reference": ref, "rule_id": rule, "severity": severity,
            "explanation": explanation, "corrective_action": action, "row": row + 1}

def _empty(): return pd.DataFrame(columns=["record_reference", "rule_id", "severity", "explanation", "corrective_action", "row"])

def validate_regulatory(df: pd.DataFrame, expected=None):
    findings = []
    missing = [c for c in REG_REQUIRED if c not in df.columns]
    for c in missing: findings.append(finding(0, "REG-001", "Critical", f"Required column '{c}' is absent.", "Add the required column.", "Dataset"))
    if missing: return _results(df, findings)
    out = df.copy()
    out["normalized_module"] = out.module.astype(str).str.strip().str.lower().map(VALID_MODULES)
    for i, r in out.iterrows():
        ref = str(r.document_id)
        if pd.isna(r.document_id) or not str(r.document_id).strip(): findings.append(finding(i,"REG-002","Critical","Document identifier is missing.","Assign a unique document identifier.",ref))
        if pd.isna(r.document_name) or not str(r.document_name).strip(): findings.append(finding(i,"REG-003","High","Document name is missing.","Enter the document name.",ref))
        if pd.isna(r.version) or not str(r.version).strip(): findings.append(finding(i,"REG-004","High","Version is missing.","Enter a controlled version.",ref))
        if pd.isna(r.normalized_module): findings.append(finding(i,"REG-005","High","CTD module must be 1–5.","Use Module 1 through Module 5.",ref))
        if str(r.review_status).strip().lower() not in {"approved", "reviewed", "draft", "pending"}: findings.append(finding(i,"REG-006","Medium","Review status is invalid.","Use Approved, Reviewed, Draft, or Pending.",ref))
        if "review_date" in out and pd.notna(r.review_date) and pd.isna(pd.to_datetime(r.review_date, errors="coerce")): findings.append(finding(i,"REG-007","Medium","Review date is malformed.","Use an ISO date (YYYY-MM-DD).",ref))
    for ident, group in out.groupby(out.document_id.astype(str).str.strip(), dropna=False):
        if ident and ident.lower() != "nan" and len(group) > 1:
            for i in group.index: findings.append(finding(i,"REG-008","High",f"Duplicate document identifier '{ident}'.","Retain one unique identifier or correct duplicates.",ident))
    if expected:
        present = set(out.document_name.astype(str).str.strip().str.lower())
        for name in expected:
            if name.strip().lower() not in present: findings.append(finding(0,"REG-009","High",f"Expected document '{name}' is not in the register.","Add it or update the expected checklist.",name))
    return _results(out, findings)

def validate_clinical(df: pd.DataFrame, consistency=None):
    findings=[]; missing=[c for c in CLIN_REQUIRED if c not in df.columns]
    for c in missing: findings.append(finding(0,"CLN-001","Critical",f"Required column '{c}' is absent.","Add the required column.","Dataset"))
    if missing: return _results(df, findings)
    for i,r in df.iterrows():
        ref=" | ".join(str(r.get(c,"")) for c in CLIN_REQUIRED)
        for c in CLIN_REQUIRED:
            if pd.isna(r[c]) or not str(r[c]).strip(): findings.append(finding(i,"CLN-002","High",f"{c} is missing.",f"Resolve missing {c}.",ref))
        for c in [x for x in df.columns if "date" in x.lower()]:
            if pd.notna(r[c]) and pd.isna(pd.to_datetime(r[c],errors="coerce")): findings.append(finding(i,"CLN-003","Medium",f"Malformed date in {c}.","Use YYYY-MM-DD.",ref))
        for c, allowed in (consistency or {}).items():
            if c in df and pd.notna(r[c]) and str(r[c]) not in allowed: findings.append(finding(i,"CLN-004","Medium",f"{c} is outside configured values.",f"Use one of: {', '.join(allowed)}.",ref))
    keys=["study_id","site_id","subject_id"]
    for _,g in df.groupby(keys,dropna=False):
        if len(g)>1:
            for i in g.index: findings.append(finding(i,"CLN-005","High","Duplicate subject record within study and site.","Review duplicate records."," | ".join(str(g.loc[i,k]) for k in keys)))
    return _results(df, findings)

def _results(data, findings):
    return {"data": data, "findings": pd.DataFrame(findings) if findings else _empty()}
