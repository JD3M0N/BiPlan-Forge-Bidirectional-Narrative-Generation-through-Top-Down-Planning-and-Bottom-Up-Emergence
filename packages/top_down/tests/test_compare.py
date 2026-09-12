import pytest
from asg_top_down.compare import build_comparison, main


def _run(tmp_path, name, text):
    run_dir = tmp_path / name
    run_dir.mkdir()
    (run_dir / "story.md").write_text(text, encoding="utf-8")
    return run_dir


@pytest.mark.parametrize("names", [("a", "b"), ("a", "b", "c")], ids=["two-runs", "three-runs"])
def test_build_comparison_accepts_two_or_more_runs(tmp_path, names):
    output = tmp_path / "out.html"
    runs = [_run(tmp_path, name, f"Texto {name}") for name in names]
    build_comparison(runs, output)
    document = output.read_text(encoding="utf-8")
    assert document.count("<article>") == len(names)
    for name in names:
        assert f"Historia {name.upper()}" in document
        assert f"Texto {name}" in document
    if len(names) == 3:
        assert "repeat(3,1fr)" in document


def test_cli_rejects_a_single_run(tmp_path, capsys):
    run_dir = _run(tmp_path, "a", "Historia uno")
    with pytest.raises(SystemExit):
        main([str(run_dir)])
    assert "al menos dos" in capsys.readouterr().err
