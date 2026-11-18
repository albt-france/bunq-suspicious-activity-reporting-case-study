-- SIMULATED corrective action plan (CAP) items, status as of 31 Oct 2026.
-- A CAP item counts as done only when it is closed AND evidence is attached.

-- name: sim_cap_status
WITH s AS (
    SELECT *, DATE '2026-10-31' AS as_of,
           CASE
             WHEN closed_date IS NOT NULL AND NOT evidence_attached THEN 'closed without evidence'
             WHEN closed_date IS NOT NULL AND closed_date <= due_date THEN 'closed on time'
             WHEN closed_date IS NOT NULL THEN 'closed late'
             WHEN due_date < DATE '2026-10-31' THEN 'overdue'
             WHEN due_date <= DATE '2026-10-31' + 14 THEN 'due within 14 days'
             ELSE 'open, on track'
           END AS cap_state
    FROM cap_items
)
SELECT cap_id, item, owner_team, opened_date::DATE AS opened_date, due_date::DATE AS due_date,
       closed_date::DATE AS closed_date, evidence_attached, cap_state,
       CASE WHEN closed_date IS NULL THEN date_diff('day', DATE '2026-10-31', due_date::DATE) END AS days_to_due
FROM s ORDER BY cap_state, due_date;

-- name: sim_cap_by_team
WITH s AS (
    SELECT owner_team,
           (closed_date IS NULL AND due_date < DATE '2026-10-31')        AS overdue,
           (closed_date IS NOT NULL AND NOT evidence_attached)           AS no_evidence,
           (closed_date IS NOT NULL AND evidence_attached AND closed_date <= due_date) AS on_time
    FROM cap_items
)
SELECT owner_team, count(*) AS items, sum(overdue::INT) AS overdue, sum(no_evidence::INT) AS closed_without_evidence,
       sum(on_time::INT) AS closed_on_time_with_evidence
FROM s GROUP BY 1 ORDER BY overdue DESC, owner_team;
