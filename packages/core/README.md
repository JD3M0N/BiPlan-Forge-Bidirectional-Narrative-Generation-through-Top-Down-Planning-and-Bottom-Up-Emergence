# ASG Core

Shared infrastructure used by the ASG models and applications. The package
centralizes project-root discovery, story paths, safe slugs, atomic file writes,
prose craft measurement, and MP3 narration through `edge-tts`.

`atomic_write_text`, `atomic_write_json` and `atomic_write_csv` write through a
temporary file and `os.replace`, so a reader never sees half a file. `artifact_json` is
the repository JSON format on its own, for writers that hash what they persist.
`use_utf8_output()` is the first call of every command-line entry point, so Spanish
output survives a legacy Windows console.

`create_story_audio()` and `create_story_audio_sync()` clean generated Markdown,
detect its language, select a compatible voice, and write `story.mp3` plus
`audio.json`. `TTS_FALLBACK_VOICE` can override the library fallback when voice
discovery is unavailable.

`craft_metrics()` measures the prose of a generated story: how many paragraphs open
a dialogue line or carry quotation marks, and the average words per sentence and per
paragraph. `prose_paragraphs()` and `split_sentences()` expose the two segmentation
steps it builds on. The figures are deterministic and rounded, so a run can record them
in its own artifacts and runs can be compared across generator versions.
