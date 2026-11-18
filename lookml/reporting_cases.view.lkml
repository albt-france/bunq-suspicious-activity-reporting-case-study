# ILLUSTRATIVE, NOT VALIDATED IN A LOOKER INSTANCE.
# Semantic layer for the SIMULATED reporting desk of this case study (tables from src/simulate.py).
# Key choices encoded here so every dashboard uses the same definitions (docs/KPI_DEFINITIONS.md):
#   - one row per report_id (first submission): duplicates from retries are removed in the derived table;
#   - time to file starts at the ALERT, never at case opening;
#   - deadline logic on Europe/Paris dates (timestamps stored in UTC).

view: reporting_cases {
  derived_table: {
    sql:
      WITH first_sub AS (
        SELECT report_id, MIN(submitted_ts_utc) AS submitted_ts_utc, COUNT(*) AS submission_rows
        FROM reports GROUP BY report_id
      )
      SELECT r.report_id, r.case_id, r.desk, r.typology, r.amount_eur,
             r.counterparty_country, r.counterparty_iban, r.narrative_words, r.missing_fields_at_draft,
             f.submitted_ts_utc, f.submission_rows,
             c.opened_ts_utc, c.effort_hours, a.alert_ts_utc, a.source AS alert_source
      FROM first_sub f
      JOIN reports r ON r.report_id = f.report_id AND r.submitted_ts_utc = f.submitted_ts_utc
      JOIN cases   c ON c.case_id = r.case_id
      JOIN alerts  a ON a.alert_id = c.alert_id ;;
  }

  dimension: report_id { primary_key: yes  type: string  sql: ${TABLE}.report_id ;; }
  dimension: case_id { type: string  sql: ${TABLE}.case_id ;; }
  dimension: desk { type: string  sql: ${TABLE}.desk ;; }
  dimension: alert_source { type: string  sql: ${TABLE}.alert_source ;; }
  dimension: typology { type: string  sql: ${TABLE}.typology ;; }

  dimension_group: alert {
    type: time
    timeframes: [raw, date, week, month]
    sql: ${TABLE}.alert_ts_utc ;;
    convert_tz: yes            # stored in UTC, displayed in the connection's query time zone (set to Europe/Paris)
  }
  dimension_group: submitted {
    type: time
    timeframes: [raw, date, week, month]
    sql: ${TABLE}.submitted_ts_utc ;;
    convert_tz: yes
  }

  dimension: days_alert_to_submission {
    description: "Clock starts at the alert (first signal), stops at the first submission."
    type: number
    value_format_name: decimal_1
    sql: (EXTRACT(EPOCH FROM ${TABLE}.submitted_ts_utc) - EXTRACT(EPOCH FROM ${TABLE}.alert_ts_utc)) / 86400.0 ;;
  }

  dimension: is_on_time {
    description: "Paris date of submission <= Paris date of alert + 14 days (internal target of the simulated desk)."
    type: yesno
    sql: ${submitted_date} <= DATEADD(day, 14, ${alert_date}) ;;
  }

  dimension: is_complete {
    type: yesno
    sql: ${TABLE}.counterparty_country IS NOT NULL AND ${TABLE}.counterparty_iban IS NOT NULL
         AND ${TABLE}.narrative_words >= 30 ;;
  }

  dimension: duplicate_rows { type: number  sql: ${TABLE}.submission_rows - 1 ;; }

  measure: reports { type: count_distinct  sql: ${report_id} ;; }
  measure: median_days_to_file { type: median  sql: ${days_alert_to_submission} ;;  value_format_name: decimal_1 }
  measure: p90_days_to_file { type: percentile  percentile: 90  sql: ${days_alert_to_submission} ;;  value_format_name: decimal_1 }
  measure: on_time_reports { type: count_distinct  sql: ${report_id} ;;  filters: [is_on_time: "yes"] }
  measure: on_time_rate { type: number  sql: 1.0 * ${on_time_reports} / NULLIF(${reports}, 0) ;;  value_format_name: percent_1 }
  measure: complete_reports { type: count_distinct  sql: ${report_id} ;;  filters: [is_complete: "yes"] }
  measure: completeness_rate { type: number  sql: 1.0 * ${complete_reports} / NULLIF(${reports}, 0) ;;  value_format_name: percent_1 }
  measure: duplicate_submission_rows { type: sum  sql: ${duplicate_rows} ;; }
  measure: mean_effort_hours { type: average  sql: ${TABLE}.effort_hours ;;  value_format_name: decimal_1 }
}
