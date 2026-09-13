# ASG Core

Shared infrastructure used by the ASG models and applications. The package
centralizes project-root discovery, story paths, safe slugs, atomic file writes,
prose craft measurement, and MP3 narration through `edge-tts`.

`create_story_audio()` and `create_story_audio_sync()` clean generated Markdown,
detect its language, select a compatible voice, and write `story.mp3` plus
`audio.json`. `TTS_FALLBACK_VOICE` can override the library fallback when voice
discovery is unavailable.

`craft_metrics()` measures the prose of a generated story: how many paragraphs open
a dialogue line or carry quotation marks, and the average words per sentence and per
paragraph. `prose_paragraphs()` and `split_sentences()` expose the two segmentation
steps it builds on. The figures are deterministic and rounded, so both approaches can
record them in their own artifacts and compare runs across generator versions.
