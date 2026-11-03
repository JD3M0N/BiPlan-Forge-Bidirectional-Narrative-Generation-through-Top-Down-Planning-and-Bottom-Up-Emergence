# Changelog

## [2.1.9] - 2026-11-02

- P07.4: `asg-perturb DB --out DIR [--seed N]` writes two deterministic perturbations of each
  frozen study text, `DIR/<id>-shuffled` (chapters reordered, or paragraph thirds when there are
  no chapters; never the original order) and `DIR/<id>-no-ending` (strict prefix without the last
  fifth of body paragraphs), each with `story.md` and `perturbation.json` (origin, type, rule,
  seed, hashes). `--casos JSON` pairs the study extractions with compatible extractions of the
  perturbed texts (`build_cases`) for `asg-judge --perturbations`. No change of point of view.

## [2.1.8] - 2026-11-02

- P07.3: `train_judge` (judge `MODEL_VERSION` 3) publishes `length_baseline` as
  `{by_story, by_family}`, a `coverage` (tested / total votes) in every validation and, per
  criterion, `collinearity` (pairs with |r| >= 0.8, condition number, constant features) over the
  training stories. Estimator, `C`, preprocessing and validation are unchanged; judges saved with
  version 2 must be retrained.

## [2.1.7] - 2026-11-02

- P07.2: `asg-study --db DB import-votes CSV --protocolo JSON` loads transcribed paper votes
  (`StudyRepository.import_votes`) in one transaction, all or nothing. It checks the frozen
  pool, criterion, A/B/abstention, repeated reader/pair/criterion, repeated question and the
  15-question cap, and refuses readers that already have questions. It keeps the transcribed
  position and A/B order, leaves `seconds` null and writes `votos-importados.json` (protocol,
  CSV SHA-256, counts) beside the database. Schema 10 and `next_question` are unchanged.

## [2.1.6] - 2026-10-30

- P05.3 (MED-5): `asg-report-features ROOT --horizontal OUT --manifest MANIFEST [--matrix CSV]`
  writes a report paired by source plan (`horizontal_paired.py`, no model calls). For each
  matrix cell it gives the median, minimum, maximum and pair count of derived minus source
  (checked against C18), grouped by `pipeline_version` with `generator_version` as data, core
  features first, then P and K; unmeasured features read `no medido`, never zero. Bases and
  baselines get their own cells with raw values. A noise reading applies the rule of
  `decisions.md` section 2 (spread between repetitions of the bases; six pairs, five equal
  signs). Output is JSON plus a CSV next to it. Without `--manifest`, `--horizontal` and
  `--axis` are unchanged.

## [2.1.5] - 2026-10-30

- P04.9: the core list is fixed at 24 features. R15, R17, X09 and X24 become secondary after
  the extractor validation (no measured test-retest pairs or no judged quotes); they are still
  measured and published. The catalog hash changes, so earlier cached extractions are archived.
  Counts in the judge error message and comments follow the new total.

## [2.1.4] - 2026-10-28

- P04.6: `asg-audit-features` writes a human review sheet (`--hoja`, `--texto`, `--alcance`),
  summarizes test-retest over several stories (`--pares`) and aggregates filled sheets
  (`--veredictos`), without model calls. The sheet is a CSV with one row per extracted
  occurrence (quote and containing paragraph) and one row for each feature with none (zero,
  `not_applicable`, `failed`), where omissions are noted; features computed by code are left
  out and the partial scope keeps the P04.3 sample. The summary gives exact agreement, mean
  relative difference, Spearman rank correlation and state changes per feature, and says
  whether it meets the P04.3 threshold. The verdict aggregate gives precision, coverage and
  "insufficient evidence" (fewer than 5 judged). `review_worksheet` is unchanged.

## [2.1.3] - 2026-10-28

- P04.5: `asg-audit-features X.json --run DIR` adds `compare_with_logs`, which contrasts the
  extracted counts with the run's own log, by story and feature, without model calls: X02/X03
  against scene presence, X08 and X29 against the replicas per actor (X08 also by actor), X10
  against P37, X13 against P36, X16 against P21, X17 against P39 and X18 against P40. Each row
  gives the text value, the log value and, where the log is a ceiling, whether the text rises
  above it (more than 10 % or +1). What the run did not record is "not_measured" with its
  reason, never zero; an extraction of another text is refused. P37 (turns with the `lie`
  tactic) is now computed in the feature report; it stays `por_construir` in the catalog.

## [2.1.2] - 2026-10-28

- P04.4: catalog changes decided in P04.2. R12 becomes secondary; R18 and the new X29
  (dialogue share, normalized entropy of X08's turns per speaker, derived by code) join the
  core list, now 28 features. R15, R23 (now "scenes with change", a proportion over X05), X09
  and X24 (now a count of answered questions, no denominator) are redefined; P35 is marked as
  existing. Cached extractions are archived by the new catalog hash.

## [2.1.1] - 2026-10-28

- P03.2: new `asg-corpus <Stories> [--json] [--csv]` and `corpus.py`, a read-only inventory of
  the stored runs: format (and whether it was inferred), versions, status, `story.md`, and an
  `eligible`/`excluded` verdict with its reason, plus the MED-6 anomalies. `judge._ineligible`
  now takes the status, format and generator reasons from `corpus.exclusion_reason`, so runs
  before Stagecraft 7 are excluded from the ranking with "Generador anterior a Stagecraft 7".

## [2.1.0] - 2026-10-25

- Extraction protocol 3 (`EXTRACTION_VERSION` 3; the prompt stays `evidence-2`). A batch is
  validated field by field: one invalid quote, scene or label no longer discards the other
  eleven fields. Only the invalid fields are asked again, once; those still invalid stay
  `failed` with their reason, and a later run retries just them. Extraction no longer raises
  on invalid evidence, only on an invalid scene partition or a provider error.
- X24 is `not_applicable` when X23 opened no question, instead of a permanent `failed`; while
  X23 is not measured, X24 is no longer requested. Protocol 2 extractions become incompatible
  and are archived on re-extraction.

## [2.0.2] - 2026-10-24

- The study writes its audit timestamps with `asg_core.audit_timestamp` instead of its own copy.
  Requires `asg-core>=0.8.0`. No change to the stored rows.

## [2.0.1] - 2026-10-23

- Removed unused report discovery/grouping helpers and their private support types.
  Tolerant artifact readers and public commands retain their behavior.

## [2.0.0] - 2026-10-12

A single pairwise study for the thesis close, as the tutor asked: human pairs, evidence-quoted
features and a learned judge. Breaks compatibility.

- `study.py` is rewritten with one mode: collection, evaluation (`open` freezes the pool) and
  closed. Questions are assigned lazily, one at a time, so anyone may vote: the criterion
  cycles, a reader never sees their own or a known story, never repeats a pair and criterion,
  prefers stories already read and the least compared pairs, and stops at 15 questions. The
  database is created on first use (schema 10); the schemas 1-4 of the retired studies are
  refused and their files stay as data.
- `evaluation-study` keeps `status`, `add`, `exclude`/`include`, `author`, `open`, `close` and
  `export`.
- Removed: the fixed, rolling and pack modes, publication, bundles and restore, the offline demo
  (`evaluation-demo`), the legacy 1-10 `evaluation.json` (`report-evaluations`), and the
  `report-story-craft`, `report-simulations` and `report-llm-usage` commands.
  `simulation_report` stays as the library the process features read.

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
