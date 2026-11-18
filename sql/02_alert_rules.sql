-- Four simple transaction-monitoring rules on IBM "AML" HI-Small, evaluated against the labels.
-- Unit of evaluation: the ACCOUNT (an analyst reviews an account, not a single payment).
--   positive account = sender or receiver of at least one transaction labelled Is Laundering = 1
--   precision = flagged positives / flagged accounts ; recall = flagged positives / all positives
-- Self-transfers (same account on both sides, e.g. 'Reinvestment') are excluded from every rule.
-- Thresholds are round numbers chosen before looking at the results; the fan-out threshold is then varied
-- (ibm_fanout_curve) to show the precision / recall trade-off instead of tuning on the labels.

-- name: ibm_rule_results
WITH t AS (
    SELECT *, date_trunc('week', ts) AS wk FROM trans WHERE from_acct <> to_acct
),
accounts AS (
    SELECT from_acct AS acct FROM trans UNION SELECT to_acct FROM trans
),
positives AS (
    SELECT from_acct AS acct FROM trans WHERE is_laundering = 1
    UNION SELECT to_acct FROM trans WHERE is_laundering = 1
),
-- R1 fan-out: one account pays 8+ distinct counterparties in the same week
r1 AS (SELECT DISTINCT from_acct AS acct FROM t GROUP BY from_acct, wk HAVING count(DISTINCT to_acct) >= 8),
-- R2 fan-in: one account is paid by 8+ distinct counterparties in the same week
r2 AS (SELECT DISTINCT to_acct AS acct FROM t GROUP BY to_acct, wk HAVING count(DISTINCT from_acct) >= 8),
-- R3 structuring: 3+ outgoing payments in a week, each between USD 8,500 and 9,999 (just under 10,000)
r3 AS (SELECT DISTINCT from_acct AS acct FROM t WHERE amount_usd >= 8500 AND amount_usd < 10000
       GROUP BY from_acct, wk HAVING count(*) >= 3),
-- R4 rapid pass-through: on the same day an account receives >= USD 1,000 and sends 80-100% of it onwards
day_in  AS (SELECT to_acct AS acct, ts::DATE AS d, sum(amount_usd) AS v_in  FROM t GROUP BY 1, 2),
day_out AS (SELECT from_acct AS acct, ts::DATE AS d, sum(amount_usd) AS v_out FROM t GROUP BY 1, 2),
r4 AS (SELECT DISTINCT i.acct FROM day_in i JOIN day_out o USING (acct, d)
       WHERE i.v_in >= 1000 AND o.v_out BETWEEN 0.8 * i.v_in AND i.v_in),
flags AS (
    SELECT 'R1 fan-out (8+ payees / week)' AS rule, acct FROM r1
    UNION ALL SELECT 'R2 fan-in (8+ payers / week)', acct FROM r2
    UNION ALL SELECT 'R3 structuring (3+ payments USD 8.5-10k / week)', acct FROM r3
    UNION ALL SELECT 'R4 rapid pass-through (80-100% out same day)', acct FROM r4
    UNION ALL SELECT 'Any rule (R1-R4)', acct FROM (SELECT acct FROM r1 UNION SELECT acct FROM r2
                                                     UNION SELECT acct FROM r3 UNION SELECT acct FROM r4)
),
n AS (SELECT (SELECT count(*) FROM accounts) AS n_acc, (SELECT count(*) FROM positives) AS n_pos)
SELECT f.rule,
       count(*)                                           AS flagged_accounts,
       count(p.acct)                                      AS flagged_positives,
       count(p.acct) / count(*)::DOUBLE                   AS precision,
       count(p.acct) / any_value(n.n_pos)::DOUBLE         AS recall,
       1000.0 * count(*) / any_value(n.n_acc)             AS alerts_per_1000_accounts,
       any_value(n.n_pos)                                 AS positive_accounts,
       any_value(n.n_acc)                                 AS accounts,
       any_value(n.n_pos) / any_value(n.n_acc)::DOUBLE    AS base_rate
FROM flags f
LEFT JOIN positives p USING (acct)
CROSS JOIN n
GROUP BY f.rule
ORDER BY f.rule;

-- name: ibm_fanout_curve
-- Same fan-out rule with thresholds 3 to 20 distinct payees per week.
WITH t AS (SELECT *, date_trunc('week', ts) AS wk FROM trans WHERE from_acct <> to_acct),
positives AS (SELECT from_acct AS acct FROM trans WHERE is_laundering = 1
              UNION SELECT to_acct FROM trans WHERE is_laundering = 1),
peak AS (SELECT from_acct AS acct, max(c) AS max_payees
         FROM (SELECT from_acct, wk, count(DISTINCT to_acct) AS c FROM t GROUP BY 1, 2) GROUP BY 1),
thr AS (SELECT unnest(range(3, 21)) AS threshold)
SELECT thr.threshold,
       count(peak.acct)                                         AS flagged_accounts,
       count(p.acct)                                            AS flagged_positives,
       count(p.acct) / nullif(count(peak.acct), 0)::DOUBLE      AS precision,
       count(p.acct) / (SELECT count(*) FROM positives)::DOUBLE AS recall
FROM thr
JOIN peak ON peak.max_payees >= thr.threshold
LEFT JOIN positives p ON p.acct = peak.acct
GROUP BY thr.threshold
ORDER BY thr.threshold;

-- name: ibm_typology_coverage
-- Share of laundering attempts in which at least one involved account is flagged by any rule.
WITH t AS (SELECT *, date_trunc('week', ts) AS wk FROM trans WHERE from_acct <> to_acct),
r1 AS (SELECT DISTINCT from_acct AS acct FROM t GROUP BY from_acct, wk HAVING count(DISTINCT to_acct) >= 8),
r2 AS (SELECT DISTINCT to_acct AS acct FROM t GROUP BY to_acct, wk HAVING count(DISTINCT from_acct) >= 8),
r3 AS (SELECT DISTINCT from_acct AS acct FROM t WHERE amount_usd >= 8500 AND amount_usd < 10000
       GROUP BY from_acct, wk HAVING count(*) >= 3),
day_in  AS (SELECT to_acct AS acct, ts::DATE AS d, sum(amount_usd) AS v_in  FROM t GROUP BY 1, 2),
day_out AS (SELECT from_acct AS acct, ts::DATE AS d, sum(amount_usd) AS v_out FROM t GROUP BY 1, 2),
r4 AS (SELECT DISTINCT i.acct FROM day_in i JOIN day_out o USING (acct, d)
       WHERE i.v_in >= 1000 AND o.v_out BETWEEN 0.8 * i.v_in AND i.v_in),
flagged AS (SELECT acct FROM r1 UNION SELECT acct FROM r2 UNION SELECT acct FROM r3 UNION SELECT acct FROM r4),
members AS (SELECT attempt_id, typology, from_acct AS acct FROM patterns
            UNION SELECT attempt_id, typology, to_acct FROM patterns),
att AS (SELECT attempt_id, typology, max(CASE WHEN f.acct IS NOT NULL THEN 1 ELSE 0 END) AS detected
        FROM members m LEFT JOIN flagged f USING (acct) GROUP BY 1, 2)
SELECT typology, count(*) AS attempts, sum(detected) AS detected_attempts, avg(detected) AS detection_rate
FROM att
GROUP BY typology
ORDER BY detection_rate;
