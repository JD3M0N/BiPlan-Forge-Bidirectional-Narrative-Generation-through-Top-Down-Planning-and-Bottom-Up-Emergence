"""The matrix runner resumes without repeating calls and pairs derived runs by plan (P05.2)."""

import json
from pathlib import Path

import pytest
from asg_stagecraft.runtime.config import Settings
from asg_stagecraft.tools import matrix as matrix_module
from asg_stagecraft.tools.matrix import execute, select
from stage_fakes import StageFakeProvider
from test_generator_v5 import major_story_review

HEADER = (
    "celda,eje,nivel,formato,obras,flags,desde,repeticiones,"
    "llamadas_principal_unidad,llamadas_funcion_unidad"
)
ROWS = [
    "D,formato,baseline,baseline,PROMPT_01_ESSENTIAL,asg-baseline,,1,1,0",
    "A,base,base,simulated,PROMPT_01_ESSENTIAL,--format simulated --profile essential,,2,133,103",
    "B,formato,narrativo,narrative,PROMPT_01_ESSENTIAL,"
    "--format narrative --profile essential,A:plan,2,26,0",
    "C,tono,sombrío,simulated,PROMPT_01_ESSENTIAL,"
    "--format simulated --profile essential --tone sombrío,A:narrate,2,30,0",
    "TOTAL,,,,,,,,,",
]
PROMPT = "Escribe un relato de misterio con perfil narrativo Esencial."


def quiet(_line: str) -> None:
    """Swallow the runner's progress lines."""


def layout(tmp_path: Path) -> tuple[Path, Settings]:
    """Write a small matrix and its catalog; return the CSV and settings rooted in tmp_path."""
    folder = tmp_path / "planilla"
    folder.mkdir()
    (folder / "m.csv").write_text("\n".join([HEADER, *ROWS]) + "\n", encoding="utf-8")
    (folder / "prompts.md").write_text(
        f"<!-- PROMPT_01_ESSENTIAL_START -->\n{PROMPT}\n<!-- PROMPT_01_ESSENTIAL_END -->\n",
        encoding="utf-8",
    )
    settings = Settings(
        api_key="x", model="fake-model", output_root=tmp_path / "Stories" / "Stagecraft"
    )
    return folder / "m.csv", settings


def provider() -> StageFakeProvider:
    """Return a fake provider whose reviews let a simulated run complete."""
    return StageFakeProvider(story_review=major_story_review())


def manifest_path(tmp_path: Path) -> Path:
    """Return the manifest the runner writes by default for the matrix m.csv."""
    return tmp_path / "Evaluations" / "horizontal" / "manifiesto-m.json"


def manifest_of(tmp_path: Path) -> dict:
    """Read the units of the default manifest."""
    return json.loads(manifest_path(tmp_path).read_text(encoding="utf-8"))["units"]


def runs(settings: Settings) -> list[Path]:
    """List the run folders under the output root."""
    return sorted(p for p in settings.output_root.glob("*") if p.is_dir())


def calls(fake: StageFakeProvider) -> int:
    """Count the provider calls made so far."""
    return len(fake.structured_calls) + len(fake.text_calls)


def test_a_matrix_that_dies_halfway_completes_on_relaunch_without_repeating_calls(tmp_path) -> None:
    matrix, settings = layout(tmp_path)
    fake = provider()
    checked = []

    def arm_before_the_fourth_unit(_settings, _format) -> None:
        checked.append(1)
        fake.quota_error_at_stage = "narrator" if len(checked) == 4 else None

    code = execute(
        matrix,
        settings,
        provider_factory=lambda: fake,
        check=arm_before_the_fourth_unit,
        repetitions=[1],
        out=quiet,
    )
    assert code == 3
    units = manifest_of(tmp_path)
    assert [units[u]["estado"] for u in ("D/01/r1", "A/01/r1", "B/01/r1")] == ["completed"] * 3
    assert units["C/01/r1"]["estado"] == "failed"
    failed_run = units["C/01/r1"]["run"]
    assert len(runs(settings)) == 3

    fake.quota_error_at_stage = None
    before = calls(fake)
    kwargs = {"provider_factory": lambda: fake, "check": lambda *_: None, "repetitions": [1]}
    assert execute(matrix, settings, out=quiet, **kwargs) == 0
    units = manifest_of(tmp_path)
    assert units["C/01/r1"]["estado"] == "completed"
    assert units["C/01/r1"]["fallidos"] == [failed_run]
    assert units["C/01/r1"]["run"] != failed_run
    # Only the failed unit ran again: the three finished runs, the failed one and its retry.
    assert len(runs(settings)) == 4
    assert calls(fake) > before
    after = calls(fake)
    assert execute(matrix, settings, out=quiet, **kwargs) == 0
    assert calls(fake) == after


def test_derived_runs_of_different_formats_share_their_sources_plan_byte_for_byte(
    tmp_path,
) -> None:
    """MED-5: a narrative draft and a new narration come from the same frozen plan."""
    matrix, settings = layout(tmp_path)
    code = execute(
        matrix,
        settings,
        provider_factory=provider,
        check=lambda *_: None,
        repetitions=[1],
        out=quiet,
    )
    assert code == 0
    units = manifest_of(tmp_path)
    source = tmp_path / units["A/01/r1"]["run"]
    for unit in ("B/01/r1", "C/01/r1"):
        derived = tmp_path / units[unit]["run"]
        assert units[unit]["fuente"] == "A/01/r1"
        assert (derived / "story_plan.json").read_bytes() == (
            source / "story_plan.json"
        ).read_bytes()
        reused = json.loads((derived / "source_run.json").read_text(encoding="utf-8"))
        assert reused["run_id"] == source.name
    narrative = tmp_path / units["B/01/r1"]["run"] / "metadata.json"
    assert json.loads(narrative.read_text(encoding="utf-8"))["story_format"] == "narrative"


def test_dry_run_counts_the_pending_calls_and_never_touches_the_provider(tmp_path) -> None:
    matrix, settings = layout(tmp_path)

    def no_provider():
        raise AssertionError("a dry run must not build a provider")

    lines: list[str] = []
    assert execute(matrix, settings, dry=True, provider_factory=no_provider, out=lines.append) == 0
    total = next(line for line in lines if line.startswith("total"))
    # D 1 + A 2x133 + B 2x26 + C 2x30 main calls, and 2x103 stage calls.
    assert total.split()[1:] == ["7", "379", "206"]
    assert runs(settings) == []


def test_an_existing_run_stands_for_its_unit_and_a_wrong_one_is_refused(tmp_path) -> None:
    matrix, settings = layout(tmp_path)
    kwargs = {"provider_factory": provider, "check": lambda *_: None, "out": quiet}
    assert execute(matrix, settings, cells=["A"], repetitions=[1], **kwargs) == 0
    first = manifest_of(tmp_path)["A/01/r1"]["run"]
    seeds = matrix.parent / "semillas.json"
    seeds.write_text(json.dumps({"A/01/r1": first}), encoding="utf-8")
    manifest_path(tmp_path).unlink()
    fake = provider()
    kwargs["provider_factory"] = lambda: fake
    assert execute(matrix, settings, cells=["A", "B"], repetitions=[1], **kwargs) == 0
    units = manifest_of(tmp_path)
    assert units["A/01/r1"]["semilla"] is True
    assert units["A/01/r1"]["run"] == first
    # The seed and the narrative draft only: A was not run again.
    assert len(runs(settings)) == 2
    seeds.write_text(json.dumps({"A/01/r2": "Stories/Stagecraft/inexistente"}), encoding="utf-8")
    assert execute(matrix, settings, cells=["A"], **kwargs) == 2


def test_a_unit_whose_source_is_not_complete_is_blocked_without_spending(tmp_path) -> None:
    matrix, settings = layout(tmp_path)
    fake = provider()
    code = execute(
        matrix,
        settings,
        provider_factory=lambda: fake,
        check=lambda *_: None,
        cells=["B"],
        repetitions=[1],
        out=quiet,
    )
    assert code == 1
    assert calls(fake) == 0
    assert manifest_of(tmp_path)["B/01/r1"]["estado"] == "pendiente"


def test_a_refusal_of_the_preflight_stops_the_matrix_with_the_manifest_written(tmp_path) -> None:
    matrix, settings = layout(tmp_path)
    fake = provider()
    code = execute(
        matrix, settings, provider_factory=lambda: fake, check=lambda *_: "queda 0", out=quiet
    )
    assert code == 3
    assert calls(fake) == 0
    assert set(manifest_of(tmp_path)) >= {"A/01/r1", "C/01/r2"}


@pytest.mark.parametrize(
    ("cells", "works", "repetitions", "expected"),
    [(["A"], None, None, 2), (None, ["01"], [2], 3), (["B", "C"], ["02"], None, 0)],
)
def test_select_filters_by_cell_work_and_repetition(
    tmp_path, cells, works, repetitions, expected
) -> None:
    matrix, settings = layout(tmp_path)
    catalog = (matrix.parent / "prompts.md").read_text(encoding="utf-8")
    units, problems = matrix_module.expand(matrix_module.read_cells(matrix), catalog, settings)
    assert problems == []
    assert len(select(units, cells, works, repetitions)) == expected
