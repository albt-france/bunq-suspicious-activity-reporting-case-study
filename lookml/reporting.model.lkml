# ILLUSTRATIVE, NOT VALIDATED IN A LOOKER INSTANCE.
connection: "reporting_warehouse"      # placeholder connection name
week_start_day: monday

include: "/lookml/*.view.lkml"

explore: reporting_cases {
  label: "Suspicious-activity reporting (SIMULATED)"
  description: "One row per report (first submission). Time to file from the alert; deadlines on Paris dates."
  always_filter: { filters: [reporting_cases.desk: "FR"] }
}
