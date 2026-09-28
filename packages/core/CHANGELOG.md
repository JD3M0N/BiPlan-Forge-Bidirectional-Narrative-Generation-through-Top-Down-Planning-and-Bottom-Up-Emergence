# Changelog

## [0.6.0] - 2026-09-27

- `create_story_audio` and `create_story_audio_sync` accept a `voice`: the story is read with that
  edge-tts voice instead of the one the detected language picks, and a finished audio is reused
  only when it was read with the same voice.
- Added `NARRATION_VOICES` (the 45 Spanish edge-tts voices, with country and gender),
  `NARRATION_VOICE_NAMES` and `create_voice_sample`/`create_voice_sample_sync`, which read one
  line with a voice so an interface can let a person hear it first.

## [0.5.1] - 2026-09-26

- `slugify` strips the trailing dash a truncation can leave, so a run folder never ends in one.

## [0.5.0] - 2026-09-26

- Added `artifact_json`, the repository JSON format on its own, for writers that must hash the
  exact text they persist; `atomic_write_json` now builds on it.
- Added `atomic_write_csv` and `use_utf8_output`, which replace the copies the report and
  tool entry points of evaluation and Stagecraft carried.

## [0.4.0] - 2026-09-13

- Added `craft_metrics`, `prose_paragraphs` and `split_sentences`: deterministic prose
  craft figures over story Markdown, with the dialogue dash counted apart from quotation
  marks and Spanish sentence segmentation that survives ellipsis, abbreviations and the
  opening question and exclamation signs.

## [0.3.0] - 2026-09-13

- Added `file_lock`, a sidecar lock shared by threads and by separate processes.

## [0.1.0] - 2026-08-27

- Added shared project-root discovery, story paths, safe slugs, and atomic writes.
