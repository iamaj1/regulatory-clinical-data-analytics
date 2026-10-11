# Data dictionary

## Regulatory register

Required: `module` (1–5 or Module 1–5), `document_id`, `document_name`, `version`, `review_status` (Approved, Reviewed, Draft, Pending). Optional: `review_date` in ISO format.

## Clinical data

Required: `study_id`, `site_id`, `subject_id`. Any column containing `date` is parsed as a date. Optional fields such as `status`, `query_status`, recruitment fields, and visit data are retained for exploration. A duplicate is only flagged when the complete study/site/subject combination repeats; repeating study or site values alone are valid.
