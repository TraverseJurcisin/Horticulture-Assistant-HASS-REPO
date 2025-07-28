# Customizing Data Directories

Horticulture Assistant reads reference datasets such as pH guidelines and fertigation recipes from the `data/` directory. In some deployments you may wish to override or extend these files with your own versions. Three environment variables control where the helper functions look for datasets:

| Variable | Purpose |
| --- | --- |
| `HORTICULTURE_DATA_DIR` | Changes the base directory containing all default datasets. |
| `HORTICULTURE_EXTRA_DATA_DIRS` | Adds one or more additional directories (separated by `:` on Linux) that are searched before the defaults. |
| `HORTICULTURE_OVERLAY_DIR` | Points to a directory of files that overwrite anything loaded from the other paths. |

After modifying these variables, call `plant_engine.utils.clear_dataset_cache()` so cached paths and file contents are refreshed.

A typical setup might use a read-only `data/` directory from version control and an overlay directory under your Home Assistant configuration directory:

```bash
export HORTICULTURE_OVERLAY_DIR=~/hass_config/horticulture_overlay
```

Place any JSON or YAML files with the same relative path under the overlay directory to override the default versions. If you only wish to add new dataset files without replacing existing ones, use `HORTICULTURE_EXTRA_DATA_DIRS` instead:

```bash
export HORTICULTURE_EXTRA_DATA_DIRS=~/my_custom_data
```

Multiple directories can be specified by separating them with `:` on Linux/macOS or `;` on Windows.
