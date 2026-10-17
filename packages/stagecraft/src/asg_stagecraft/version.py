"""Version identifiers persisted with every generated story."""

GENERATOR_NAME = "asg-stagecraft"
__version__ = "7.17.0"
GENERATOR_VERSION = __version__
PIPELINE_VERSION = "7.17"
# Runs written as Top-Down 5.x and 6.x stay readable: renaming the package and adding the
# hybrid stages is additive, so every earlier contract still opens as a StoryRun. 7.1 changed
# what a simulated beat's "achieved" means and added director.jsonl; 7.2 changed what
# llm_usage.json, metadata.json, error_report.json and turns.jsonl record; 7.3 added
# generation_options.json and brief.json, narration.json contract 2 (a chosen narrator, the
# limited voice, chapters left out when nobody could see them) and RUN_CANCELLED; 7.4 lets the
# performance run on a model of its own, named by metadata.json's stage_model and by each line
# of llm_calls.jsonl. 7.5 adds decision evidence, incremental stage logs and an adaptive mode.
# 7.6 adds the optional inventory: a props stage, props.json, stage/inventory.jsonl and
# performance.json contract 4, whose turns may carry an arbitrated object move. A run
# without the option writes none of them. 7.7 adds the optional provider chain and
# metadata.json's models_used, the models that answered, so a run that failed over between
# providers can be told from a single-model one. 7.8 adds opt-in compositional guidance,
# narrative_retrieval.json and blueprint contract 2 with frozen downstream blocks. 7.9 has the
# director write in the fiction language and restate objectives, matches required gates by key
# rather than by wording, and adds performance.json contract 5: turns record form repairs.
# 7.10 adds cited evidence to beats and narration. 7.11 stops writing the retired 1-10
# evaluation.json template. 7.12 answers the first readers outside the project:
# request.json's style_request, metadata.json's prose_model, narration.json contract 4
# (a review cannot send a narrated chapter to the fallback; the best attempt ships) and
# craft notes that reach the Writer whatever the critic said. 7.13 changes what stage_model
# means: only the actors run on it, with or without a chain, while the director stays on the
# main model; a structured brief's cast reaches the character designer and the casting
# director verbatim. 7.14 adds localization.json, the reader-facing fields a localizer
# rewrote out of English; a casting's last attempt drops a broken gate instead of the bible; the
# actor's thought schema asks for subtext, never a plan, and the actor no longer rereads its own
# earlier thoughts. 7.15 has the narrator curate rather than transcribe (a measured second
# attempt), rejects a position restated in the same scene once, and empties plan thoughts.
# 7.16 hands the narrator the lines a chapter does not turn on in indirect style, saved as
# narration/chapter-NNN-reported.json, lets the world carry out a choice already made in the
# play's last beat, and has a third character cut into a duet. 7.17 adds six arms, all off by
# default: style examples, a line editor (line_edits/), scene cards (scene_cards.json), an
# anchored critic (review_anchors.json), a narration from selected moments
# (narration/chapter-NNN-selection.json) and typed clauses; and, always on, name candidates
# (name_choices.json), dossier knowledge sources and cover stories, the Writer's measured
# acceptance and the stricter turn rules. Earlier runs open.
SUPPORTED_PIPELINE_VERSIONS = frozenset(
    {
        "5.0",
        "5.1",
        "5.2",
        "5.3",
        "6.0",
        "6.1",
        "6.2",
        "7.0",
        "7.1",
        "7.2",
        "7.3",
        "7.4",
        "7.5",
        "7.6",
        "7.7",
        "7.8",
        "7.9",
        "7.10",
        "7.11",
        "7.12",
        "7.13",
        "7.14",
        "7.15",
        "7.16",
        PIPELINE_VERSION,
    }
)
