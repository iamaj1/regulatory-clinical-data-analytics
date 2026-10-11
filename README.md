# Regulatory & Clinical Data Analytics System

A Streamlit portfolio application for transparent, configurable quality-review support for regulatory document registers and clinical datasets.

## Features

- CTD Module 1–5 register review, expected-document checklist, identifiers, versions, review status and dates.
- Clinical missing values, malformed dates, optional JSON consistency checks, duplicate subject records within study/site, and available query/subject metrics.
- Row-level rule IDs, severity, explanation and corrective action; charts based on uploaded data.
- CSV, Excel and PDF reports generated from the actual validation findings.
- Synthetic demo files and a data dictionary. Uploaded data is never changed.

## Run locally

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
streamlit run app.py
```

Run tests with `pytest -q`.

For clinical consistency checks, use an optional JSON object such as `{"status": ["Complete", "Open"]}`. The application only reports findings; it never modifies the uploaded source data.

## Deployment

This repository is ready for Streamlit Community Cloud: connect the repository and use `app.py` as the entry point. Deployment has not been performed or verified by this repository.

## Limitations

This is a decision-support portfolio app, not a regulatory compliance determination. It does not perform eCTD technical validation, scientific validation, or guarantee regulatory submission acceptance. Use synthetic data for the demo; do not upload patient-identifiable data.
