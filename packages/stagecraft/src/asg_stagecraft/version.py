"""Version identifiers persisted with every generated story."""

GENERATOR_NAME = "asg-stagecraft"
__version__ = "7.2.0"
GENERATOR_VERSION = __version__
PIPELINE_VERSION = "7.2"
# Runs written as Top-Down 5.x and 6.x stay readable: renaming the package and adding the
# hybrid stages is additive, so every earlier contract still opens as a StoryRun. 7.1 changed
# what a simulated beat's "achieved" means and added director.jsonl; 7.2 changed what
# llm_usage.json, metadata.json, error_report.json and turns.jsonl record. Earlier runs open.
SUPPORTED_PIPELINE_VERSIONS = frozenset(
    {"5.0", "5.1", "5.2", "5.3", "6.0", "6.1", "6.2", "7.0", "7.1", PIPELINE_VERSION}
)
