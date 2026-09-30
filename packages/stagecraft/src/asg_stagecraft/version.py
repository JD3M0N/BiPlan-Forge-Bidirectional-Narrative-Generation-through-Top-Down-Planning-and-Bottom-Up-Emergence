"""Version identifiers persisted with every generated story."""

GENERATOR_NAME = "asg-stagecraft"
__version__ = "7.5.1"
GENERATOR_VERSION = __version__
PIPELINE_VERSION = "7.5"
# Runs written as Top-Down 5.x and 6.x stay readable: renaming the package and adding the
# hybrid stages is additive, so every earlier contract still opens as a StoryRun. 7.1 changed
# what a simulated beat's "achieved" means and added director.jsonl; 7.2 changed what
# llm_usage.json, metadata.json, error_report.json and turns.jsonl record; 7.3 added
# generation_options.json and brief.json, narration.json contract 2 (a chosen narrator, the
# limited voice, chapters left out when nobody could see them) and RUN_CANCELLED; 7.4 lets the
# performance run on a model of its own, named by metadata.json's stage_model and by each line
# of llm_calls.jsonl. 7.5 adds decision evidence, incremental stage logs and an adaptive mode.
# Earlier runs open.
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
        PIPELINE_VERSION,
    }
)
