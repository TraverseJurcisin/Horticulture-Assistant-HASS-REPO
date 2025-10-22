# Command Line Scripts

The `scripts/` directory contains command line utilities for quick
analysis and management tasks. Each script can be executed directly with
Python. Some highlights are:

- **precision_fertigation.py** – generate nutrient schedules and injector
  volumes for a crop stage. Supports optional nutrient synergy and stock
  containing the full schedule, cost details and injection volumes.
- **fertigation_plan.py** – output a daily fertigation schedule in JSON
  format for the specified number of days.
- **environment_optimize.py** – recommend environment adjustments for the
  current sensor readings using built in guidelines.
- **monitor_schedule.py** – produce a combined pest and disease scouting
  schedule based on crop stage and risk factors.
- **pest_plan.py** – generate a JSON pest management plan for specified pests.
- **validate_profiles.py** – validate bundled BioProfile JSON against the
  Draft 2020-12 schema and enforce trailing newline/JSON formatting rules.
- **validate_logs.py** – lint run and harvest histories across all profiles
  using the new schema library, surfacing any invalid entries.

Run a script with `-h` to see all available options. These utilities work
with the datasets under `data/` and respect any custom directories
specified by the environment variables described in
`docs/custom_data_dirs.md`.
