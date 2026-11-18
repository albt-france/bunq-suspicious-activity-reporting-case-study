-- SIMULATED reporting desk: alert -> case -> report funnel, timeliness and backlog.
-- Rules used everywhere (see docs/KPI_DEFINITIONS.md):
--   * a report is counted once per report_id (submission rows can be duplicated by a retry bug);
--   * time to file = first submission - ALERT timestamp (never the tool's own field, which changed in Sept 2026);
--   * months and deadlines use Europe/Paris local dates (timestamps are stored in UTC).

-- name: sim_monthly_funnel
WITH al AS (
    SELECT desk, date_trunc('month', (alert_ts_utc AT TIME ZONE 'UTC') AT TIME ZONE 'Europe/Paris') AS month,
           count(*) AS alerts,
           count(*) FILTER (WHERE source = 'monitoring_rule')   AS alerts_rule,
           count(*) FILTER (WHERE source = 'internal_referral') AS alerts_internal,
           count(*) FILTER (WHERE source = 'external_request')  AS alerts_external,
           count(case_id) AS escalated
    FROM alerts GROUP BY 1, 2
),
rp AS (
    SELECT desk, date_trunc('month', (first_sub AT TIME ZONE 'UTC') AT TIME ZONE 'Europe/Paris') AS month,
           count(*) AS reports, sum(rows_) AS submission_rows
    FROM (SELECT report_id, any_value(desk) AS desk, min(submitted_ts_utc) AS first_sub, count(*) AS rows_
          FROM reports GROUP BY report_id)
    GROUP BY 1, 2
)
SELECT al.*, rp.reports, rp.submission_rows,
       al.escalated / al.alerts::DOUBLE     AS alert_to_case_rate,
       rp.reports / al.escalated::DOUBLE    AS case_to_report_rate_same_month
FROM al LEFT JOIN rp USING (desk, month)
WHERE al.month < DATE '2026-11-01'          -- alerts after 23:00 UTC on 31 Oct fall in November, Paris time
ORDER BY desk, month;

-- name: sim_timeliness
-- One row per desk and month of first submission. true_* use the alert as clock start; tool_* is the
-- tool's own field (clock start moved to case opening on 1 Sep 2026); on-time = Paris date of submission
-- <= Paris date of alert + 14 days (internal target, SIMULATED); on_time_utc_check reproduces the UTC mistake.
WITH r AS (
    SELECT report_id, any_value(case_id) AS case_id, any_value(desk) AS desk,
           min(submitted_ts_utc) AS sub_utc, any_value(tool_time_to_file_days) AS tool_days,
           any_value(tool_clock_start) AS tool_clock_start
    FROM reports GROUP BY report_id
),
j AS (
    SELECT r.*, a.alert_ts_utc, c.opened_ts_utc,
           epoch(r.sub_utc - a.alert_ts_utc) / 86400.0  AS true_days,
           epoch(r.sub_utc - c.opened_ts_utc) / 86400.0 AS from_case_open_days,
           ((r.sub_utc AT TIME ZONE 'UTC') AT TIME ZONE 'Europe/Paris')::DATE
               <= ((a.alert_ts_utc AT TIME ZONE 'UTC') AT TIME ZONE 'Europe/Paris')::DATE + 14 AS on_time,
           r.sub_utc::DATE <= a.alert_ts_utc::DATE + 14                                    AS on_time_utc_check
    FROM r JOIN cases c USING (case_id) JOIN alerts a ON a.alert_id = c.alert_id
)
SELECT desk, date_trunc('month', (sub_utc AT TIME ZONE 'UTC') AT TIME ZONE 'Europe/Paris') AS month,
       count(*)                            AS reports,
       median(true_days)                   AS true_median_days,
       quantile_cont(true_days, 0.9)       AS true_p90_days,
       median(tool_days)                   AS tool_median_days,
       median(from_case_open_days)         AS case_open_to_submit_median_days,
       avg(on_time::INT)                   AS on_time_rate,
       avg(on_time_utc_check::INT)         AS on_time_rate_utc_check,
       sum((on_time <> on_time_utc_check)::INT) AS misclassified_by_utc,
       any_value(tool_clock_start)         AS tool_clock_start
FROM j
GROUP BY 1, 2
HAVING month < DATE '2026-11-01'
ORDER BY 1, 2;

-- name: sim_backlog_age
-- Escalated alerts still waiting for triage at each month end, by age (days since alert).
WITH me AS (SELECT unnest(generate_series(TIMESTAMP '2025-12-01', TIMESTAMP '2026-11-01', INTERVAL 1 MONTH)) - INTERVAL 1 MINUTE AS snap),
w AS (
    SELECT a.desk, me.snap, epoch(me.snap - a.alert_ts_utc) / 86400.0 AS age_days
    FROM alerts a JOIN cases c ON c.case_id = a.case_id
    CROSS JOIN me
    WHERE a.alert_ts_utc <= me.snap AND c.opened_ts_utc > me.snap
)
SELECT desk, snap::DATE AS month_end,
       count(*) FILTER (WHERE age_days < 7)                     AS age_0_6,
       count(*) FILTER (WHERE age_days >= 7 AND age_days < 14)  AS age_7_13,
       count(*) FILTER (WHERE age_days >= 14 AND age_days < 30) AS age_14_29,
       count(*) FILTER (WHERE age_days >= 30)                   AS age_30_plus,
       count(*)                                                 AS backlog
FROM w GROUP BY 1, 2 ORDER BY 1, 2;

-- name: sim_weekly_alerts
SELECT desk, date_trunc('week', alert_ts_utc)::DATE AS week, source, count(*) AS alerts,
       count(*) FILTER (WHERE typology_hint = 'APP scam (year-end)') AS app_scam_tagged
FROM alerts GROUP BY 1, 2, 3 ORDER BY 1, 2, 3;
