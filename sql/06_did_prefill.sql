-- SIMULATED: effect of the August 2026 pre-fill on analyst effort per case, by difference-in-differences.
-- Treated: FR desk. Control: BNL desk (no pre-fill). Outcome: log(effort_hours), so effects read as % changes.
-- Pre: cases picked up 4 May - 2 Aug 2026. Post: 3 Aug - 31 Oct 2026.
-- The interval is computed in src/findings.py (bootstrap over weeks), the point estimate here.

-- name: sim_did_cells
WITH c AS (
    SELECT desk, ln(effort_hours) AS y,
           CASE WHEN picked_ts_utc >= TIMESTAMP '2026-08-03' THEN 'post' ELSE 'pre' END AS period
    FROM cases
    WHERE picked_ts_utc >= TIMESTAMP '2026-05-04' AND picked_ts_utc < TIMESTAMP '2026-11-01'
)
SELECT desk, period, count(*) AS cases, avg(y) AS mean_log_effort, exp(avg(y)) AS geo_mean_hours
FROM c GROUP BY 1, 2 ORDER BY 1, 2;

-- name: sim_did_estimate
WITH cells AS (
    SELECT desk, CASE WHEN picked_ts_utc >= TIMESTAMP '2026-08-03' THEN 'post' ELSE 'pre' END AS period,
           avg(ln(effort_hours)) AS m
    FROM cases
    WHERE picked_ts_utc >= TIMESTAMP '2026-05-04' AND picked_ts_utc < TIMESTAMP '2026-11-01'
    GROUP BY 1, 2
),
p AS (
    SELECT max(m) FILTER (WHERE desk = 'FR'  AND period = 'pre')  AS FR_pre,
           max(m) FILTER (WHERE desk = 'FR'  AND period = 'post') AS FR_post,
           max(m) FILTER (WHERE desk = 'BNL' AND period = 'pre')  AS BNL_pre,
           max(m) FILTER (WHERE desk = 'BNL' AND period = 'post') AS BNL_post
    FROM cells
)
SELECT (FR_post - FR_pre)                         AS fr_change_log,
       (BNL_post - BNL_pre)                       AS bnl_change_log,
       (FR_post - FR_pre) - (BNL_post - BNL_pre)  AS did_log,
       exp((FR_post - FR_pre) - (BNL_post - BNL_pre)) - 1 AS did_pct,
       exp(FR_post - FR_pre) - 1                  AS naive_fr_before_after_pct
FROM p;

-- name: sim_weekly_effort
-- Weekly geometric mean effort per desk: parallel trends before August, gap after.
SELECT desk, date_trunc('week', picked_ts_utc)::DATE AS week, count(*) AS cases,
       exp(avg(ln(effort_hours))) AS geo_mean_hours
FROM cases
WHERE picked_ts_utc >= TIMESTAMP '2026-01-05' AND picked_ts_utc < TIMESTAMP '2026-11-01'
GROUP BY 1, 2 ORDER BY 1, 2;
