import json

from asg_stagecraft.tools.audit_stage import (
    AuditFinding,
    ChapterAudit,
    SceneAudit,
    audit_run,
    keep_previous,
    main,
    manifest_hash,
    parser,
    score,
)


class JudgeProvider:
    """A judge that returns canned verdicts and records what it was asked to look at."""

    model_name = "fake-judge"

    def __init__(self, scene_findings=None, chapter_findings=None) -> None:
        self.scene_findings = scene_findings or []
        self.chapter_findings = chapter_findings or []
        self.prompts = []

    def generate_structured(self, *, system_instruction, prompt, schema, profile):
        self.prompts.append((schema.__name__, prompt))
        if schema is SceneAudit:
            return SceneAudit(findings=list(self.scene_findings))
        return ChapterAudit(findings=list(self.chapter_findings))


def build_run(tmp_path):
    """Write the smallest run shape the auditor reads."""
    run = tmp_path / "20260101-000000-una"
    (run / "stage" / "chapter-1-scene-1").mkdir(parents=True)
    (run / "memory" / "ana").mkdir(parents=True)
    (run / "narration").mkdir(parents=True)
    (run / "pipeline_manifest.json").write_text('{"artifacts": {}}', encoding="utf-8")
    (run / "performance.json").write_text(
        json.dumps(
            {
                "settings": {"actor_memory": "own"},
                "scenes": [
                    {
                        "scene_id": "chapter-1-scene-1",
                        "chapter_id": "chapter-1",
                        "number": 2,
                        "turns": [{"actor_id": "ana"}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (run / "narration.json").write_text(
        json.dumps(
            {
                "narrative_voice": "omniscient",
                "chapters": [{"chapter_id": "chapter-1", "chapter_index": 1}],
            }
        ),
        encoding="utf-8",
    )
    (run / "stage" / "chapter-1-scene-1" / "transcript.md").write_text(
        "TRANSCRIPCION:\nt001 Ana: Lo sabia.\n", encoding="utf-8"
    )
    (run / "memory" / "ana" / "records.json").write_text(
        json.dumps(
            [
                {"text": "Ana vio la carta", "scene_number": 1},
                {"text": "algo de esta escena", "scene_number": 2},
            ]
        ),
        encoding="utf-8",
    )
    (run / "narration" / "chapter-001.md").write_text(
        "Ana lo sabia desde el principio.\n", encoding="utf-8"
    )
    return run


def leak():
    return AuditFinding(
        kind="knowledge_leak",
        severity=3,
        character_id="ana",
        evidence="Ana: Lo sabia.",
        explanation="Ana names a fact her memory does not hold.",
    )


def test_the_penalty_scheme_matches_the_one_it_borrows() -> None:
    assert score([]) == 100.0
    assert score([leak()]) == 85.0
    assert score([leak()] * 10) == 0.0


def test_a_clean_run_scores_perfectly_and_writes_no_findings(tmp_path) -> None:
    run = build_run(tmp_path)
    report = audit_run(run, JudgeProvider())
    assert report["knowledge_leaks"] == 0
    assert report["knowledge_score"] == 100.0
    assert report["narration_score"] == 100.0
    assert report["actor_memory"] == "own"
    assert report["narrative_voice"] == "omniscient"


def test_findings_are_counted_and_scored(tmp_path) -> None:
    run = build_run(tmp_path)
    report = audit_run(run, JudgeProvider(scene_findings=[leak()]))
    assert report["knowledge_leaks"] == 1
    assert report["knowledge_score"] == 85.0
    assert report["scenes"][0]["findings"][0]["character_id"] == "ana"


def test_the_judge_only_sees_what_a_character_knew_before_the_scene(tmp_path) -> None:
    run = build_run(tmp_path)
    judge = JudgeProvider()
    audit_run(run, judge)
    scene_prompt = next(prompt for name, prompt in judge.prompts if name == "SceneAudit")
    assert "Ana vio la carta" in scene_prompt
    assert "algo de esta escena" not in scene_prompt


def test_the_narration_judge_gets_the_log_and_the_prose(tmp_path) -> None:
    run = build_run(tmp_path)
    judge = JudgeProvider()
    audit_run(run, judge)
    chapter_prompt = next(prompt for name, prompt in judge.prompts if name == "ChapterAudit")
    assert "Ana lo sabia desde el principio." in chapter_prompt
    assert "TRANSCRIPCION" in chapter_prompt


def test_scenes_only_skips_the_narration_judge(tmp_path) -> None:
    run = build_run(tmp_path)
    judge = JudgeProvider()
    report = audit_run(run, judge, scenes_only=True)
    assert report["chapters"] == []
    assert not any(name == "ChapterAudit" for name, _ in judge.prompts)


def test_the_audit_records_which_run_it_described(tmp_path) -> None:
    run = build_run(tmp_path)
    report = audit_run(run, JudgeProvider())
    assert report["source_manifest_sha256"] == manifest_hash(run)
    assert report["model"] == "fake-judge"


def test_the_cli_refuses_a_run_without_a_performance(tmp_path, capsys) -> None:
    assert main([str(tmp_path)]) == 2
    assert "no contiene una función representada" in capsys.readouterr().err


def test_the_parser_accepts_its_flags() -> None:
    args = parser().parse_args(["some-run", "--scenes-only", "--model", "x"])
    assert args.scenes_only is True
    assert args.model == "x"


def test_a_deliberate_lie_filed_as_a_contradiction_is_set_aside_not_scored(tmp_path) -> None:
    """Contract 1 scored a well-played liar as a breach; a lie is a tactic, not a leak."""
    lie = AuditFinding(
        kind="contradiction",
        severity=4,
        character_id="elena",
        evidence="Elena: Nunca entre en la torre.",
        explanation="Elena says the opposite of what she did.",
    )
    run = build_run(tmp_path)
    report = audit_run(run, JudgeProvider(scene_findings=[lie, leak()]))
    assert report["contract_version"] == "2"
    assert report["knowledge_leaks"] == 1
    assert report["knowledge_score"] == 85.0
    assert report["scenes"][0]["set_aside"][0]["kind"] == "contradiction"


def test_the_knowledge_judge_is_told_a_lie_is_not_a_leak(tmp_path) -> None:
    run = build_run(tmp_path)
    instructions = []

    class Recording(JudgeProvider):
        def generate_structured(self, *, system_instruction, prompt, schema, profile):
            instructions.append((schema.__name__, system_instruction))
            return super().generate_structured(
                system_instruction=system_instruction, prompt=prompt, schema=schema, profile=profile
            )

    audit_run(run, Recording())
    knowledge = next(text for name, text in instructions if name == "SceneAudit")
    assert "playing a tactic, not leaking knowledge" in knowledge


def test_an_earlier_report_is_kept_rather_than_overwritten(tmp_path) -> None:
    destination = tmp_path / "audit" / "audit.json"
    destination.parent.mkdir()
    destination.write_text('{"audited_at": "2026-09-26T04:10:00+00:00"}', encoding="utf-8")
    kept = keep_previous(destination)
    assert kept is not None and kept.name == "audit-20260926041000.json"
    assert not destination.exists()
    assert keep_previous(destination) is None
