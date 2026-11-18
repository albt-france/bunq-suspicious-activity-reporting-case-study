-- IBM "AML" HI-Small (synthetic, AMLSim). Profile of the labelled transactions.
-- Tables: trans (one row per transaction, deduplicated), patterns (transactions listed in laundering attempts).
-- Output: aggregates only (no account-level rows leave the local database).

-- name: ibm_overview
SELECT count(*)                                   AS transactions,
       sum(is_laundering)                         AS laundering_transactions,
       avg(is_laundering)                         AS laundering_share,
       count(DISTINCT from_acct)                  AS sending_accounts,
       min(ts)::DATE                              AS first_day,
       max(ts)::DATE                              AS last_day,
       sum(amount_usd) FILTER (WHERE is_laundering = 1) / sum(amount_usd) AS laundering_value_share
FROM trans;

-- name: ibm_by_format
-- Laundering rate by payment format: where the labelled cases concentrate.
SELECT payment_format,
       count(*)                     AS transactions,
       sum(is_laundering)           AS laundering_transactions,
       avg(is_laundering)           AS laundering_rate,
       median(amount_usd)           AS median_usd
FROM trans
GROUP BY payment_format
ORDER BY laundering_transactions DESC;

-- name: ibm_typologies
-- Laundering attempts by typology (from the patterns file): count, size, value.
WITH a AS (
    SELECT attempt_id, typology,
           count(*)                                         AS tx,
           count(DISTINCT from_acct) + count(DISTINCT to_acct) AS account_slots,
           max(ts) - min(ts)                                AS duration
    FROM patterns
    GROUP BY attempt_id, typology
)
SELECT typology,
       count(*)                                 AS attempts,
       sum(tx)                                  AS transactions,
       median(tx)                               AS median_tx_per_attempt,
       median(epoch(duration) / 3600.0)         AS median_duration_hours
FROM a
GROUP BY typology
ORDER BY attempts DESC;

-- name: ibm_daily
SELECT ts::DATE AS day, count(*) AS transactions, sum(is_laundering) AS laundering_transactions
FROM trans
GROUP BY 1
ORDER BY 1;
