"""Version identifiers persisted with every generated story."""

GENERATOR_NAME = "asg-stagecraft"
__version__ = "7.8.3"
GENERATOR_VERSION = __version__
PIPELINE_VERSION = "7.8"
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
# narrative_retrieval.json and blueprint contract 2 with frozen downstream blocks.
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
        "7.5",
        "7.6",
        "7.7",
        PIPELINE_VERSION,
    }
)
