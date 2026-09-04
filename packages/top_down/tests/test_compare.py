import pytest
from asg_top_down.compare import build_comparison, main


def _run(tmp_path, name, text):
    run_dir = tmp_path / name
    run_dir.mkdir()
    (run_dir / "story.md").write_text(text, encoding="utf-8")
    return run_dir


def test_build_comparison_accepts_two_runs(tmp_path):
    output = tmp_path / "out.html"
    build_comparison(
        [_run(tmp_path, "a", "Historia uno"), _run(tmp_path, "b", "Historia dos")],
        output,
    )
    document = output.read_text(encoding="utf-8")
    assert document.count("<article>") == 2
    assert "Historia A" in document
    assert "Historia B" in document
    assert "Historia uno" in document
    assert "Historia dos" in document


def test_build_comparison_accepts_three_or_more_runs(tmp_path):
    output = tmp_path / "out.html"
    runs = [_run(tmp_path, name, f"Texto {name}") for name in ("a", "b", "c")]
    build_comparison(runs, output)
    document = output.read_text(encoding="utf-8")
    assert document.count("<article>") == 3
    assert "Historia A" in document
    assert "Historia B" in document
    assert "Historia C" in document
    assert "repeat(3,1fr)" in document


def test_cli_rejects_a_single_run(tmp_path, capsys):
    run_dir = _run(tmp_path, "a", "Historia uno")
    with pytest.raises(SystemExit):
        main([str(run_dir)])
    assert "al menos dos" in capsys.readouterr().err
