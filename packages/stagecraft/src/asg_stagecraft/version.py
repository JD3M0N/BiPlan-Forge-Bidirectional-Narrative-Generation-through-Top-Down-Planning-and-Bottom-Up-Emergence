"""Version identifiers persisted with every generated story."""

GENERATOR_NAME = "asg-stagecraft"
__version__ = "7.0.0"
GENERATOR_VERSION = __version__
PIPELINE_VERSION = "7.0"
# Runs written as Top-Down 5.x and 6.x stay readable: renaming the package and adding the
# hybrid stages is additive, so every earlier contract still opens as a StoryRun.
SUPPORTED_PIPELINE_VERSIONS = frozenset(
    {"5.0", "5.1", "5.2", "5.3", "6.0", "6.1", "6.2", PIPELINE_VERSION}
)
