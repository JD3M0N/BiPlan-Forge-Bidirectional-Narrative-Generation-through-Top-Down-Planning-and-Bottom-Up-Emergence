# ASG Core

Shared infrastructure used by the ASG models and applications. The package
centralizes project-root discovery, story paths, safe slugs, atomic file writes,
and MP3 narration through `edge-tts`.

`create_story_audio()` and `create_story_audio_sync()` clean generated Markdown,
detect its language, select a compatible voice, and write `story.mp3` plus
`audio.json`. `TTS_FALLBACK_VOICE` can override the library fallback when voice
discovery is unavailable.
