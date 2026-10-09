# Changelog

## [1.3.0] - 2026-10-09

- Added `report-llm-usage` (MED-2): calls, attempts, failed attempts, tokens, latency and quota
  waiting of every run, split by agent and by stage from `llm_calls.jsonl` and grouped by
  approach. A log written before 7.2, without the agent of each call, is reported as not
  measured. `usage_report.aggregate_calls` is the one aggregation `report-simulations` and the
  feature extractor's K06 now share.
- `artifacts.read_json_lines` is the tolerant JSONL reader every report uses.

## [1.2.0] - 2026-10-08

- `StudyRepository` gains `find_participant`, `contribution` (enrolled and pending),
  `release_contribution` (frees a reservation whose job failed, so a retry can claim it),
  `progress` (answered and planned questions, per session) and `participant_ids`.
- `catalog.guidance()` reads `que_mirar` from `criterios_humanos.csv`, and `freeze` stores it in
  the study snapshot next to the catalog. The catalog hash is unchanged, so existing extraction
  caches stay valid.

## [1.1.0] - 2026-10-05

- Extraction protocol 2 (`EXTRACTION_VERSION` 2, prompt `evidence-2`): duplicates are now
  dropped only when label and evidence coincide, so R12's want and need on one quote count 2.
  X02 publishes per-character participation (`breakdown`), X08 per-speaker dialogue, and X08
  and X11 are always extracted as auxiliary fields; the judge keeps its 27 inputs. Earlier
  extractions become incompatible and are archived on re-extraction.
- `report-features` and `rank-stories` take `--study DB` and reuse the frozen study's
  extractions by text hash, without provider calls. `evaluation-demo` now builds its table,
  horizontal report and ranking through those public commands.
- Judges (model schema 2) record their `extraction_protocol` (extractor version, prompt
  version and model). Training rejects mixed protocols and ranking excludes rows measured
  with another one.

## [1.0.0] - 2026-10-04

- Versioned SQLite studies, immutable corpus snapshots, reproducible blind assignments,
  idempotent votes, exposure exclusions and pseudonymous exports.
- Evidence-backed extraction of 27 core text features, optional secondary features, resumable
  batches, archived repeated measurements, review worksheets and unified feature reports.
- Regularized Bradley–Terry, participant bootstrap, three pairwise logistic judges with
  story/family holdout validation, length controls and transparent JSON coefficients.
- Offline synthetic end-to-end demonstration and an executable study guide in ESTUDIO_FINAL.md.
  Real corpus generation, human collection and empirical validation remain future work.

## [Unreleased]

- Added `METODOLOGIA.md`: the thesis evaluation method from the tutor's instructions (countable
  story features, blind pairwise human judgments on three criteria, a single-prompt baseline, and
  a judge learned from those pairs), with the state of the art it rests on. The six 1-10 metrics
  of `evaluation.json` stay as a legacy instrument.
- Added `planilla/`: the CSV sources (features, human criteria, configuration, generation matrix,
  templates, bibliography) and `build_planilla.py`, which rebuilds `planilla_evaluacion.xlsx` and
  the per-story template from them using only the standard library. No package code changed.

## [0.9.0] - 2026-10-02

- `pairing` gains the `inventory` axis ("Inventario de objetos") for simulated runs, read
  from `performance.json`'s settings. No performance before Stagecraft 7.6 could track
  objects, so a run that does not say is reported as running without one, which keeps the
  whole earlier corpus pairable against a run that has an inventory.
- `report-simulations` reports the prop figures of a performance that had an inventory
  (`props`, `item_actions`, `item_repairs`, `props_used_ratio`, `hidden_item_actions`,
  `secret_handoffs`, `item_witness_share`) and groups by `inventory`. A run without one
  reports them as unmeasured, never as zero.

## [0.8.0] - 2026-09-28

- `pairing` gains the `stage_model` axis ("Modelo de la función"), a pairing axis for simulated
  runs. It reads `metadata.json`'s `stage_model` (Stagecraft 7.4), or `model` when the run names
  none, since every earlier performance ran on the main model. Runs whose actors used different
  models are never a clean pair and get their own warning.

## [0.7.0] - 2026-09-27

- Added `pairing`: `read_run_config` rebuilds every axis a run was asked with, from
  `generation_options.json` when the run has it (7.3) and from `metadata.json`, `performance.json`
  and `narration.json` otherwise, keeping what was never recorded as `None`. `pair_runs` puts two
  to four runs side by side, says which axes differ and whether the comparison is clean (same
  work, model and profile, one arm changed), and warns in Spanish about what it cannot support.
  `run_measurements` gathers the story, performance, judge and cost figures of one run.

## [0.6.0] - 2026-09-26

- `report-story-craft` reads `failed_calls` as not measured for runs before pipeline 7.2, where
  it counted failed attempts rather than failed calls.
- The reports take a run's narrative profile from `metadata.json` when `request.json` is
  missing, so a run that failed in analysis still lands on the profile axis.

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
