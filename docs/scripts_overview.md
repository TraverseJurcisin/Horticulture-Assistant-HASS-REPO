# Command Line Scripts

The `scripts/` directory contains command line utilities for quick
analysis and management tasks. Each script can be executed directly with
Python. Some highlights are:

- **precision_fertigation.py** – generate nutrient schedules and injector
  volumes for a crop stage. Supports optional nutrient synergy and stock
  solution recipes.
- **fertigation_plan.py** – output a daily fertigation schedule in JSON
  format for the specified number of days.
- **environment_optimize.py** – recommend environment adjustments for the
  current sensor readings using built in guidelines.
- **monitor_schedule.py** – produce a combined pest and disease scouting
  schedule based on crop stage and risk factors.

Run a script with `-h` to see all available options. These utilities work
with the datasets under `data/` and respect any custom directories
specified by the environment variables described in
`docs/custom_data_dirs.md`.
