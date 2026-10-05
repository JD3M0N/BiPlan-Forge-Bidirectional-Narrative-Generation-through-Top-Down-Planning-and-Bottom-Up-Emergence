"""A direct baseline makes one provider call and preserves provenance on failure."""

import json
from unittest.mock import Mock

import pytest
from asg_stagecraft.tools.baseline import generate_baseline


def test_direct_baseline_calls_provider_once_without_pipeline(tmp_path):
    provider = Mock(usage_records=[])
    provider.generate_text.return_value = "Una historia completa."
    output = tmp_path / "baseline"
    generate_baseline(provider, "Una premisa", output, model="fake")
    provider.generate_text.assert_called_once()
    assert json.loads((output / "metadata.json").read_text())["status"] == "completed"
    assert json.loads((output / "request.json").read_text())["original_prompt"] == "Una premisa"
    with pytest.raises(FileExistsError):
        generate_baseline(provider, "Otra premisa", output, model="fake")
    assert provider.generate_text.call_count == 1


def test_failed_baseline_is_never_enrollable(tmp_path):
    provider = Mock(usage_records=[])
    provider.generate_text.side_effect = RuntimeError("offline")
    with pytest.raises(RuntimeError):
        generate_baseline(provider, "Una premisa", tmp_path / "failed", model="fake")
    assert json.loads((tmp_path / "failed" / "metadata.json").read_text())["status"] == "failed"
