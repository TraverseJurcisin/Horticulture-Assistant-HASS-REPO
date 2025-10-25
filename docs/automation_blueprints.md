# Automation blueprints

The integration ships Home Assistant blueprints that demonstrate how to use the
new device triggers and logging services without writing YAML from scratch. Copy
or import these from the `blueprints/automation/horticulture_assistant/`
directory inside your Home Assistant configuration folder.

## Harvest notification

File: `blueprints/automation/horticulture_assistant/harvest_notification.yaml`

- **Trigger:** Device trigger fired when a harvest is recorded for the selected
  plant profile.
- **Default action:** Persistent notification summarising the harvest amount,
  unit, and optional notes.
- **Customisation:** Replace the default action sequence with your own mobile
  push, messaging, or logging actions. The harvest metadata is exposed via
  `trigger.event.data` and includes the profile ID, amount, unit, notes, and any
  subtype recorded by the logging service.

## Scheduled irrigation log

File: `blueprints/automation/horticulture_assistant/scheduled_irrigation_log.yaml`

- **Trigger:** Time pattern (defaults to every hour). Adjust the schedule input
  to run the automation whenever irrigation or inspection logging should occur.
- **Action:** Calls `horticulture_assistant.record_cultivation_event` with the
  provided profile ID, summary, and optional tags. You can append additional
  actions—like toggling a smart valve or sending a notification—through the
  `extra_actions` input.

## Status recovery watchdog

File: `blueprints/automation/horticulture_assistant/status_recovery_watchdog.yaml`

- **Trigger:** Device trigger that fires when the plant status enters warning
  or critical states.
- **Logic:** Waits for the plant to recover within the configured timeout. If
  recovery does not occur, the automation checks the device condition
  `status_problem` and runs the configured escalation actions.
- **Default action:** Persistent notification that highlights the unresolved
  problem state. Replace the `actions` input with SMS, mobile push, or other
  remediation flows for your environment.

### Tips

- Use the device selector to ensure you pick the correct plant device created
  by the integration. This automatically configures the proper device trigger.
- When referencing profile IDs in the scheduled blueprint, match the `id` field
  from the profile JSON file or the identifier shown on the integration's
  options page.
- Blueprint defaults are intentionally conservative. Adjust the notification
  text, schedule cadence, or additional actions to match your workflow.
