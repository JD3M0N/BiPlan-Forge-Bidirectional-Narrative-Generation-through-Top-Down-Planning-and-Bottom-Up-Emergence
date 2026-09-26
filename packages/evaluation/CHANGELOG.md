# Changelog

## [0.5.0] - 2026-09-26

- Added the internal `artifacts` module with the tolerant readers the three reports copied:
  JSON loading, string and number fields, the version, profile and format labels, run
  discovery and grouping. The reports' output and CSV bytes are unchanged.
- The three report commands use `asg_core.atomic_write_csv`, `stories_path` and
  `use_utf8_output`, so they now require `asg-core` 0.5.0.
- `docs/evaluation_metrics.md` moved into this README, which now also covers
  `report-story-craft` and `report-simulations`.

## [0.4.0] - 2026-09-13

- Added `report-story-craft` and the `craft_report` module: prose craft recomputed from
  every `story.md`, paired with the plan, character, world, review, usage and blueprint
  artifacts of its run, summarized with median and range, and exported as one CSV row per
  story. `--min-version` defaults to 6, which also keeps unversioned runs out of the report.
- Moved the two Spanish report formatters to `text.py`, shared with `report-evaluations`.

## [0.3.0] - 2026-09-13

- Recognized any entry without scores as a pending template, wherever it sits in the list.
- Named the failing entry and field instead of blaming the first metric.
- Locked the whole read-modify-write cycle across threads and processes.
- Added a public reader with aggregation by story, profile, generator version, and approach.
- Added the `report-evaluations` command with CSV export.

## [0.2.0] - 2026-08-27

- Adopted shared filesystem helpers from `asg-core`.
- Removed the unused story-evaluation migration API.
