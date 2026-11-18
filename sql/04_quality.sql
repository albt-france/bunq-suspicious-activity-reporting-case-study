-- SIMULATED reporting desk: data quality of reports before they reach the FIU.
-- Required fields: subject_id, account_id, amount_eur, transaction_dates, counterparty_country,
-- counterparty_iban, typology, narrative (>= 30 words). See docs/REPORTING_PROCEDURE.md.

-- name: sim_quality_monthly
WITH r AS (
    SELECT report_id, any_value(desk) AS desk, min(submitted_ts_utc) AS sub_utc, count(*) AS submission_rows,
           any_value(missing_fields_at_draft) AS missing_at_draft,
           any_value(subject_id IS NOT NULL AND account_id IS NOT NULL AND amount_eur IS NOT NULL
                     AND transaction_dates IS NOT NULL AND counterparty_country IS NOT NULL
                     AND counterparty_iban IS NOT NULL AND typology IS NOT NULL AND narrative_words >= 30) AS complete
    FROM reports GROUP BY report_id
),
ret AS (SELECT report_id, count(*) AS n_returns FROM quality_returns GROUP BY 1)
SELECT desk, date_trunc('month', (sub_utc AT TIME ZONE 'UTC') AT TIME ZONE 'Europe/Paris') AS month,
       count(*)                                              AS reports,
       avg(complete::INT)                                    AS complete_at_submission,
       avg((missing_at_draft = '')::INT)                     AS complete_at_draft,
       avg((ret.report_id IS NOT NULL)::INT)                 AS qa_return_rate,
       sum(submission_rows) - count(*)                       AS duplicate_submission_rows,
       (sum(submission_rows) - count(*)) / count(*)::DOUBLE  AS duplicate_rate
FROM r LEFT JOIN ret USING (report_id)
GROUP BY 1, 2 HAVING month < DATE '2026-11-01' ORDER BY 1, 2;

-- name: sim_field_gaps
-- Which required field is missing, at draft, by month (FR and BNL).
SELECT desk, date_trunc('month', draft_ts_utc) AS month, missing_fields_at_draft AS missing, count(DISTINCT report_id) AS reports
FROM reports
WHERE missing_fields_at_draft <> ''
GROUP BY 1, 2, 3 ORDER BY 1, 2, 3;

-- name: sim_return_reasons
SELECT desk, reason, count(*) AS returns, min(return_ts_utc)::DATE AS first_seen, max(return_ts_utc)::DATE AS last_seen
FROM quality_returns GROUP BY 1, 2 ORDER BY 1, returns DESC;

-- name: sim_duplicates
-- Submission rows sharing a report_id: the retry bug. Window function keeps the first one.
WITH s AS (
    SELECT *, row_number() OVER (PARTITION BY report_id ORDER BY submitted_ts_utc) AS rn,
           submitted_ts_utc - lag(submitted_ts_utc) OVER (PARTITION BY report_id ORDER BY submitted_ts_utc) AS gap
    FROM reports
)
SELECT desk, date_trunc('month', submitted_ts_utc) AS month, count(*) AS duplicate_rows,
       median(epoch(gap) / 60.0) AS median_minutes_after_first
FROM s WHERE rn > 1 GROUP BY 1, 2 ORDER BY 1, 2;
