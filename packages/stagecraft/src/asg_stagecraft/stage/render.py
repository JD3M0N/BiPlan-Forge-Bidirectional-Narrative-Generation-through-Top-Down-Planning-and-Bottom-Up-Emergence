"""The exact text handed to an actor, to the director, and to the narrator.

Pure and deterministic, like promise_brief.py: the blocks built here are the whole variable
half of every stage prompt, and each one is persisted next to the turn it produced so a finished
run can be audited without re-deriving what any agent was told.

One rule governs the actor blocks and is worth stating plainly: **no plan vocabulary crosses
into them**. An actor is given circumstances, an objective, a note and its own memory. It never
sees an event ID, an event title, a later scene, or the script's own lines - which is what keeps
the performance an improvisation rather than a recitation, and what stops a character from
foreshadowing a scene it has not lived yet.
"""

from __future__ import annotations

from .perception import visible_text
from .schemas import (
    ActorDossier,
    BeatBrief,
    CharacterState,
    MemoryRecord,
    SceneBrief,
    SceneCastBrief,
    StageTurn,
)
from .validation import strip_internal_ids


def actor_system_prompt(
    dossier: ActorDossier,
    *,
    name: str,
    language: str,
    names: dict[str, str],
) -> str:
    """Build the fixed instruction one actor carries for the whole performance.

    The whole dossier is restated on every call rather than summarized once: a persona that is
    only established at the start of a long exchange drifts away from itself, and re-anchoring
    it each turn is the cheapest defence.
    """
    lines = [
        f"You are {name}. You are not an assistant and you are not a narrator: you are this "
        f"person, living this moment. Everything you say is spoken in {language}.",
        "",
        "WHO YOU ARE",
        f"- What you want: {dossier.want}",
    ]
    if dossier.need:
        lines.append(f"- What you actually need, whether or not you know it: {dossier.need}")
    if dossier.wound:
        lines.append(f"- The injury you carry: {dossier.wound}")
    if dossier.fear:
        lines.append(f"- What you are afraid of: {dossier.fear}")
    if dossier.moral_line:
        lines.append(f"- What you will not do: {dossier.moral_line}")
    if dossier.secret:
        hidden = ", ".join(names.get(item, item) for item in dossier.secret_from)
        kept = f" You keep it from: {hidden}." if hidden else ""
        lines.append(f"- What you hide: {dossier.secret}.{kept}")
    lines.append(f"- How you speak: {dossier.voice}")
    if dossier.mannerisms:
        lines.append(
            "- Habits that surface under pressure (rarely, never twice in a row): "
            f"{'; '.join(dossier.mannerisms)}"
        )
    if dossier.tactics:
        lines.append(f"- How you get your way, in order: {'; '.join(dossier.tactics)}")
    if dossier.triggers:
        lines.append(f"- What sets you off: {'; '.join(dossier.triggers)}")
    if dossier.behavior_rules:
        lines.append(f"- Rules you never break: {'; '.join(dossier.behavior_rules)}")
    if dossier.relationships:
        lines.append("")
        lines.append("WHO THE OTHERS ARE TO YOU")
        for item in dossier.relationships:
            other = names.get(item.character_id, item.character_id)
            detail = f" You want from them: {item.wants_from_them}." if item.wants_from_them else ""
            private = f" Privately: {item.private_opinion}." if item.private_opinion else ""
            lines.append(f"- {other}: {item.stance}.{detail}{private}")
    lines.extend(
        [
            "",
            "HOW YOU PLAY",
            "- You know only what you have lived through or been told. If you do not know "
            "something, you do not know it: guess, ask, or be wrong, but never narrate a fact "
            "you never learned.",
            "- Play for what you want, using one tactic at a time. When a tactic fails, change "
            "it rather than repeating yourself in new words.",
            "- One move per turn, in a short line, as people talk. Say or do one thing and let "
            "the others answer; a speech is not a turn.",
            "- Speak only for yourself. Never describe what another character thinks or decides.",
            "- Your action is a stage direction: third person, without your own name, only what "
            "an audience could see ('cruza los brazos', never 'cruzo los brazos'). Do not repeat "
            "a gesture you have already made.",
            "- Your thought is subtext: what you do not say. Leave it empty when it would only "
            "repeat your words or your plan. Nobody else ever perceives it.",
            "- When you are given a note, play it without ever mentioning it or hinting that it "
            "exists.",
            "- If your part is to obstruct, wound, refuse or betray, do it fully, without "
            "softening into agreement or apology - until the scene gives your character a reason "
            "they would accept. When a note tells you the ground has shifted, let it shift, in "
            "your own way: a character who never moves is not strong, only stuck.",
            "- Never mention that any of this is a story, a scene or a script.",
        ]
    )
    return "\n".join(lines)


def actor_turn_context(
    *,
    scene: SceneBrief,
    objective: str,
    state: CharacterState | None,
    note: str,
    gate_facts: list[str],
    memories: list[MemoryRecord],
    witnessed: list[StageTurn],
    character_id: str,
    names: dict[str, str],
) -> str:
    """Build the variable block one actor reads before taking a turn."""
    blocks = [f"CIRCUNSTANCIAS DADAS:\n{strip_internal_ids(scene.setting)}"]
    # Each person on stage comes with what anyone can see of them. With names alone, the first
    # real run had a character call a woman "muchacho" eleven times.
    others = [_presented(item, names) for item in scene.cast if item.character_id != character_id]
    if others:
        blocks.append("CONTIGO EN ESCENA:\n" + "\n".join(f"- {line}" for line in others))
    blocks.append(f"LO QUE QUIERES AQUI: {strip_internal_ids(objective)}")
    if state:
        blocks.append(f"COMO ESTAS: {_state_line(state, names)}")
    if gate_facts:
        blocks.append(
            "LO QUE SABES Y OTROS QUIZA NO:\n" + "\n".join(f"- {item}" for item in gate_facts)
        )
    if memories:
        blocks.append("LO QUE RECUERDAS:\n" + "\n".join(f"- {item.text}" for item in memories))
    if witnessed:
        transcript = "\n".join(
            visible_text(turn, character_id, names)
            for turn in witnessed
            if visible_text(turn, character_id, names)
        )
        blocks.append(
            f"LA ESCENA HASTA AHORA:\n{transcript}" if transcript else "LA ESCENA ACABA DE EMPEZAR."
        )
    else:
        blocks.append("LA ESCENA ACABA DE EMPEZAR. Te toca abrirla.")
    if note:
        blocks.append(f"NOTA DEL DIRECTOR (nunca la menciones):\n{strip_internal_ids(note)}")
    return "\n\n".join(blocks)


def director_beat_context(
    *,
    scene: SceneBrief,
    beat: BeatBrief,
    turns: list[StageTurn],
    names: dict[str, str],
    gates: list[str],
    tactics: dict[str, list[str]] | None = None,
    used_events: list[str] | None = None,
) -> str:
    """Build the block the director reads to open or judge one beat.

    Two deterministic signals ride along. The last tactics of each actor make a deadlock
    visible ("confront, confront, confront"), and the world events already used in the play
    stop the director from reaching for the same thunderclap twice.
    """
    cast = "\n".join(
        f"- {_presented(item, names)} ({item.character_id}) quiere: {item.objective}"
        for item in scene.cast
    )
    blocks = [
        f"ESCENA {scene.number}:\n{scene.setting}",
        f"EN ESCENA:\n{cast}",
        (
            "EL BEAT QUE FALTA POR CONSEGUIR:\n"
            f"- Lo que tiene que pasar: {beat.outcome}\n"
            f"- Para que sirve: {beat.purpose}\n"
            f"- El conflicto: {beat.conflict}"
        ),
    ]
    if beat.promise_brief:
        blocks.append(f"LO QUE ESTE MOMENTO LE DEBE AL LECTOR:\n{beat.promise_brief}")
    if gates:
        blocks.append(
            "QUIEN SABE QUE (no se lo digas a nadie que no lo sepa ya):\n"
            + "\n".join(f"- {item}" for item in gates)
        )
    if tactics:
        blocks.append(
            "ULTIMAS TACTICAS DE CADA UNO:\n"
            + "\n".join(
                f"- {names.get(key, key)}: {', '.join(value)}"
                for key, value in sorted(tactics.items())
                if value
            )
        )
    if used_events:
        blocks.append(
            "EVENTOS DEL MUNDO YA USADOS:\n" + "\n".join(f"- {item}" for item in used_events)
        )
    blocks.append(transcript(turns, names) if turns else "LA ESCENA AUN NO HA EMPEZADO.")
    return "\n\n".join(blocks)


def transcript(turns: list[StageTurn], names: dict[str, str]) -> str:
    """Render the full performed transcript, thoughts included, for the director and the audit."""
    lines = []
    for turn in turns:
        if turn.kind == "world":
            lines.append(f"{turn.id} ({turn.action})")
            continue
        speaker = names.get(turn.actor_id, turn.actor_id)
        pieces = []
        if turn.action:
            pieces.append(f"({speaker} {turn.action})")
        if turn.speech:
            aside = ""
            if turn.visibility == "whisper":
                addressed = ", ".join(names.get(item, item) for item in turn.addressed_to)
                aside = f" (en voz baja a {addressed})" if addressed else " (en voz baja)"
            pieces.append(f"{speaker}{aside}: {turn.speech}")
        if turn.thought:
            pieces.append(f"[{speaker} piensa: {turn.thought}]")
        if pieces:
            lines.append(f"{turn.id} {' '.join(pieces)}")
    return "TRANSCRIPCION:\n" + "\n".join(lines)


def scene_log(
    turns: list[StageTurn],
    names: dict[str, str],
    *,
    thoughts: bool,
    key_ids: frozenset[str] | set[str] = frozenset(),
) -> str:
    """Render one scene's log for the narrator, with or without access to inner life.

    ``key_ids`` are the turns the director cited as evidence that a beat landed. They are marked
    so the narrator knows which moments the chapter turns on and can compress the rest: the
    first real run expanded the log instead of curating it, because every turn looked equal.
    """
    lines = []
    for turn in turns:
        mark = "[clave] " if turn.id in key_ids else ""
        if turn.kind == "world":
            lines.append(f"{mark}({turn.action})")
            continue
        speaker = names.get(turn.actor_id, turn.actor_id)
        if mark:
            lines.append(mark.strip())
        if turn.action:
            lines.append(f"({speaker} {turn.action})")
        if turn.speech:
            aside = ""
            if turn.visibility == "whisper":
                addressed = ", ".join(names.get(item, item) for item in turn.addressed_to)
                aside = f" [en voz baja a {addressed}]" if addressed else " [en voz baja]"
            lines.append(f"{speaker}{aside}: {turn.speech}")
        if thoughts and turn.thought:
            lines.append(f"[{speaker} piensa: {turn.thought}]")
    return "\n".join(lines)


def _presented(member: SceneCastBrief, names: dict[str, str]) -> str:
    """Name one character on stage together with what anyone can see of them."""
    name = names.get(member.character_id, member.character_id)
    return f"{name}, {member.public_face}" if member.public_face else name


def _state_line(state: CharacterState, names: dict[str, str]) -> str:
    """Describe one character's state in words, never in figures."""
    pieces = []
    if state.emotion:
        pieces.append(f"te sientes {state.emotion}")
    if state.goal:
        pieces.append(f"ahora mismo intentas {state.goal}")
    for item in state.relationships:
        other = names.get(item.character_id, item.character_id)
        pieces.append(f"con {other}: {item.stance}")
    return "; ".join(pieces) or "sin nada que te pese"
