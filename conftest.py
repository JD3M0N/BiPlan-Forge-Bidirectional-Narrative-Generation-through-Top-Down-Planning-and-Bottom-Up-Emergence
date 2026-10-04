import os

import pytest


@pytest.fixture(autouse=True, scope="session")
def skip_fsync():
    """Turn ``os.fsync`` into a no-op for the whole suite.

    Production code fsyncs every artifact, manifest and JSONL line it writes. On the repo's
    disk each fsync costs ~125 ms, so a single fake pipeline run spent seconds waiting on it
    and the suite could take more than 40 minutes. No test measures durability against a
    power cut, so the flush buys nothing here; production keeps it.
    """
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(os, "fsync", lambda descriptor: None)
        yield
