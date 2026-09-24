import hashlib
import json

import pytest
from asg_top_down.errors import RunArtifactError
from asg_top_down.generator import StoryRun
from asg_top_down.recovery import (
    DISCARDED_CODE,
    RECOVERED_CODE,
    close_stalled_run,
    discard_stalled_run,
    main,
    stalled_runs,
)
from asg_top_down.version import PIPELINE_VERSION

STORY = "# Historia\n\nUn faro se apaga.\n"


def make_run(
    root,
    name,
    *,
    status="running",
    version=PIPELINE_VERSION,
    story=True,
    stages=("drafting", "story"),
    manifest=True,
):
    run_dir = root / name
    run_dir.mkdir(parents=True)
    metadata = {
        "run_id": name,
        "model": "fake",
        "created_at": "2026-09-01T00:00:00+00:00",
        "updated_at": "2026-09-01T00:00:00+00:00",
        "status": status,
        "completed_stages": list(stages),
        "warnings": [],
    }
    if version is not None:
        metadata["pipeline_version"] = version
    content = json.dumps(metadata, ensure_ascii=False, indent=2) + "\n"
    (run_dir / "metadata.json").write_text(content, encoding="utf-8")
    if story:
        (run_dir / "story.md").write_text(STORY, encoding="utf-8")
    if manifest:
        (run_dir / "pipeline_manifest.json").write_text(
            json.dumps(
                {
                    "pipeline_version": version,
                    "run_id": name,
                    "completed_stages": list(stages),
                    "artifacts": {
                        "metadata.json": {
                            "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                            "bytes": len(content.encode("utf-8")),
                        }
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    return run_dir


def metadata_of(run_dir):
    return json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))


def test_only_running_runs_are_reported_as_stalled(tmp_path) -> None:
    make_run(tmp_path, "stalled")
    make_run(tmp_path, "done", status="completed")
    make_run(tmp_path, "broken", status="failed")
    (tmp_path / "not-a-run").mkdir()
    assert [run.run_dir.name for run in stalled_runs(tmp_path)] == ["stalled"]


def test_a_stalled_run_is_recoverable_only_with_a_story_and_a_supported_version(
    tmp_path,
) -> None:
    make_run(tmp_path, "a-with-story")
    make_run(tmp_path, "b-no-story", story=False)
    make_run(tmp_path, "c-no-version", version=None)
    make_run(tmp_path, "d-old-version", version="4.1")
    verdicts = {run.run_dir.name: run.recoverable for run in stalled_runs(tmp_path)}
    assert verdicts == {
        "a-with-story": True,
        "b-no-story": False,
        "c-no-version": False,
        "d-old-version": False,
    }


def test_closing_a_stalled_run_makes_it_openable_and_leaves_an_audit_line(tmp_path) -> None:
    run_dir = make_run(tmp_path, "recoverable")
    close_stalled_run(run_dir)
    metadata = metadata_of(run_dir)
    assert metadata["status"] == "completed"
    assert len(metadata["warnings"]) == 1
    assert metadata["warnings"][0].startswith(f"[{RECOVERED_CODE}]")
    assert "story" in metadata["warnings"][0]
    assert StoryRun(run_dir).story_path.read_text(encoding="utf-8") == STORY


def test_closing_refreshes_the_hash_the_manifest_keeps_of_metadata(tmp_path) -> None:
    run_dir = make_run(tmp_path, "recoverable")
    close_stalled_run(run_dir)
    manifest = json.loads((run_dir / "pipeline_manifest.json").read_text(encoding="utf-8"))
    recorded = manifest["artifacts"]["metadata.json"]
    written = (run_dir / "metadata.json").read_text(encoding="utf-8").encode("utf-8")
    assert recorded["sha256"] == hashlib.sha256(written).hexdigest()
    assert recorded["bytes"] == len(written)


def test_closing_a_run_without_a_manifest_still_works(tmp_path) -> None:
    run_dir = make_run(tmp_path, "no-manifest", manifest=False)
    close_stalled_run(run_dir)
    assert metadata_of(run_dir)["status"] == "completed"
    assert not (run_dir / "pipeline_manifest.json").exists()


@pytest.mark.parametrize(
    ("name", "kwargs", "match"),
    [
        ("already-done", {"status": "completed"}, "no está en running"),
        ("no-story", {"story": False}, "no llego a escribir"),
        ("no-version", {"version": None}, "no soportada"),
    ],
    ids=["already-completed", "never-wrote-a-story", "unsupported-version"],
)
def test_closing_refuses_a_run_it_cannot_rescue(tmp_path, name, kwargs, match) -> None:
    run_dir = make_run(tmp_path, name, **kwargs)
    with pytest.raises(RunArtifactError, match=match):
        close_stalled_run(run_dir)


def test_discarding_marks_the_run_failed_and_explains_why(tmp_path) -> None:
    run_dir = make_run(tmp_path, "abandoned", story=False, version=None, stages=("world",))
    discard_stalled_run(run_dir)
    metadata = metadata_of(run_dir)
    assert metadata["status"] == "failed"
    assert metadata["error_code"] == DISCARDED_CODE
    assert metadata["error_stage"] == "world"
    report = json.loads((run_dir / "error_report.json").read_text(encoding="utf-8"))
    assert report["code"] == DISCARDED_CODE
    assert report["run_id"] == "abandoned"


def test_discarding_refuses_a_run_that_is_not_stalled(tmp_path) -> None:
    run_dir = make_run(tmp_path, "done", status="completed")
    with pytest.raises(RunArtifactError, match="no está en running"):
        discard_stalled_run(run_dir)


def test_no_transition_ever_removes_an_artifact(tmp_path) -> None:
    closed = make_run(tmp_path, "recoverable")
    discarded = make_run(tmp_path, "abandoned", story=False, version=None)
    before = {path.name for path in closed.iterdir()}
    close_stalled_run(closed)
    discard_stalled_run(discarded)
    assert before <= {path.name for path in closed.iterdir()}
    assert (discarded / "metadata.json").is_file()


def test_the_command_lists_without_writing_unless_asked(tmp_path, capsys) -> None:
    run_dir = make_run(tmp_path, "recoverable")
    assert main(["--stories", str(tmp_path)]) == 0
    assert metadata_of(run_dir)["status"] == "running"
    assert "No se escribió nada" in capsys.readouterr().out
    assert main(["--stories", str(tmp_path), "--all"]) == 0
    assert metadata_of(run_dir)["status"] == "completed"


def test_the_command_reports_an_empty_directory(tmp_path, capsys) -> None:
    assert main(["--stories", str(tmp_path), "--all"]) == 0
    assert "No hay ejecuciones en running" in capsys.readouterr().out
