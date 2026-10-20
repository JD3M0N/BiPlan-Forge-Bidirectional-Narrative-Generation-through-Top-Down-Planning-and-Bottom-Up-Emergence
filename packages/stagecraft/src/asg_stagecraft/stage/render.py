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

from .names import ShortNames
from .perception import item_line, item_moves, stage_direction, visible_text
from .schemas import (
    TACTIC_NAMES,
    ActorDossier,
    BeatBrief,
    CharacterState,
    MemoryRecord,
    Prop,
    SceneBrief,
    SceneCastBrief,
    StageTurn,
)
from .validation import strip_internal_ids

# The only thing the inventory adds to an actor's standing instruction, and only when it is on.
# What each verb requires is arbitrated in stage/inventory.py; this just tells the actor the
# rules it will be held to, so a rejection is never a surprise.
INVENTORY_RULES = (
    "",
    "WHAT YOU ARE CARRYING",
    "- You are told what you are holding and what you can see. Those are the only objects there "
    "are for you: never produce, invent or mention one that is not listed, and never assume you "
    "have something back once you have given it away.",
    "- Use ordered item_actions for multiple moves (take then give); otherwise item_action. "
    "Name each object exactly as listed, with the verb for what you "
    "do: use it, give it to someone present, take it, drop it, hide it, or show it. Most turns "
    "handle nothing; leave the verb as 'none' then.",
    "- You can only use, give, drop, hide or show what is in your own hands. To get hold of "
    "something else you have to take it, and only while it is here.",
    "- Say in your action what you do with it, as the audience would see it. The object is a "
    "move, not a label: reach for one when it gets you what you want.",
    "- Hiding something in public is witnessed: others remember you concealed it. "
    "A whispered hand-over is perceived by its participants only.",
)


def actor_system_prompt(
    dossier: ActorDossier,
    *,
    name: str,
    language: str,
    names: dict[str, str],
    inventory: bool = False,
) -> str:
    """Build the fixed instruction one actor carries for the whole performance.

    The whole dossier is restated on every call rather than summarized once: a persona that is
    only established at the start of a long exchange drifts away from itself, and re-anchoring
    it each turn is the cheapest defence.
    """
    lines = [
        f"You are {name}. You are not an assistant and you are not a narrator: you are this "
        f"person, living this moment. Everything you say, do and think is written in "
        f"{language}, thoughts included.",
        "",
        "WHO YOU ARE",
        f"- What you want: {dossier.want}",
    ]
    lines += [
        f"- {label}: {value}"
        for label, value in (
            ("What you actually need, whether or not you know it", dossier.need),
            ("The injury you carry", dossier.wound),
            ("What you are afraid of", dossier.fear),
            ("What you will not do", dossier.moral_line),
        )
        if value
    ]
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
            "it rather than repeating yourself in new words. Once you have stated your position, "
            "do not state it again: do something about it, give some ground, or move the scene "
            "elsewhere.",
            "- Address someone by name only when it matters; people in a room rarely say each "
            "other's names.",
            "- One move per turn, in a short line, as people talk. Say or do one thing and let "
            "the others answer; a speech is not a turn.",
            "- When someone has just spoken to you, answer that first - take it up, contradict "
            "it or dodge it - and only then push for what you want. Answering is not giving in.",
            "- When you speak to someone in particular, put their name in addressed_to as it "
            "appears under CONTIGO EN ESCENA. To be heard by them alone, whisper.",
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
    if inventory:
        lines.extend(INVENTORY_RULES)
    return "\n".join(lines)


def _objective_blocks(scene: SceneBrief, objective: str) -> list[str]:
    """Return what the actor wants here and, in the closing scene, that it is decided now.

    7.15.1: in the closing scene of the 7.15 navigators run the actors kept the previous
    scene's quarrel and never reached the decision. No plan reaches the actor here: only that
    what it wants now outweighs what it was pursuing before.
    """
    blocks = [f"LO QUE QUIERES AQUÍ: {strip_internal_ids(objective)}"]
    if scene.closes_play:
        blocks.append(
            "Esto se decide ahora: lo que quieres aquí pesa más que lo que perseguías antes."
        )
    return blocks


# How many of its own recent tactics an actor sees, once it has tried at least that many.
TRIED_TACTICS = 3


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
    held: list[Prop] | None = None,
    in_reach: list[Prop] | None = None,
) -> str:
    """Build the variable block one actor reads before taking a turn.

    ``held`` and ``in_reach`` arrive only when the inventory is on, and only ever hold what this
    character can actually see: what is in its own hands, and what is in front of it. A block
    for an object it does not know about would be the plan leaking in by another door.
    """
    blocks = [f"CIRCUNSTANCIAS DADAS:\n{strip_internal_ids(scene.setting)}"]
    # Each person on stage comes with what anyone can see of them. With names alone, the first
    # real run had a character call a woman "muchacho" eleven times.
    others = [_presented(item, names) for item in scene.cast if item.character_id != character_id]
    if others:
        blocks.append("CONTIGO EN ESCENA:\n" + "\n".join(f"- {line}" for line in others))
    if held:
        blocks.append("LO QUE LLEVAS:\n" + "\n".join(f"- {prop_line(item)}" for item in held))
    if in_reach:
        blocks.append("LO QUE VES:\n" + "\n".join(f"- {prop_line(item)}" for item in in_reach))
    blocks.extend(_objective_blocks(scene, objective))
    # Only once there is something decided: the 7.12 run told an actor opening its first scene
    # not to repeat a conversation it had never had.
    moved = any(turn.actor_id == character_id for turn in witnessed if turn.kind == "actor")
    if moved or (state and (state.commitment or state.cover_story)):
        blocks.append(
            "Lo que ya decidiste sigue vigente: juega su coste o una nueva "
            "prueba, no repitas la misma conversación. Puedes actuar en "
            "silencio."
        )
    if len(scene.cast) == 1:
        blocks.append(
            "Estás a solas. Prioriza una acción concreta; no necesitas explicarla en voz alta."
        )
    if state:
        blocks.append(f"CÓMO ESTÁS: {_state_line(state, names)}")
    if gate_facts:
        blocks.append(
            "LO QUE SABES Y OTROS QUIZÁ NO:\n" + "\n".join(f"- {item}" for item in gate_facts)
        )
    if memories:
        blocks.append("LO QUE RECUERDAS:\n" + "\n".join(f"- {item.text}" for item in memories))
    if witnessed:
        seen = (visible_text(turn, character_id, names, own_thoughts=False) for turn in witnessed)
        transcript = "\n".join(line for line in seen if line)
        blocks.append(
            f"LA ESCENA HASTA AHORA:\n{transcript}" if transcript else "LA ESCENA ACABA DE EMPEZAR."
        )
    else:
        blocks.append("LA ESCENA ACABA DE EMPEZAR. Te toca abrirla.")
    blocks.extend(_reply_blocks(witnessed, character_id, names))
    if note:
        blocks.append(f"NOTA DEL DIRECTOR (nunca la menciones):\n{strip_internal_ids(note)}")
    return "\n\n".join(blocks)


def _reply_blocks(witnessed: list[StageTurn], character_id: str, names: dict[str, str]) -> list:
    """What the actor has tried in the scene, and the line it still owes an answer to."""
    blocks: list[str] = []
    tried = [
        TACTIC_NAMES.get(turn.tactic, turn.tactic)
        for turn in witnessed
        if turn.actor_id == character_id and turn.kind == "actor" and turn.tactic
    ][-TRIED_TACTICS:]
    if len(tried) >= TRIED_TACTICS:
        # 7.17: the rule to change tactic had nothing to work with until the actor could see
        # what it had tried, in its own words.
        blocks.append(
            f"LO QUE HAS PROBADO EN ESTA ESCENA: {', '.join(tried)}. Si no funcionó, prueba otra "
            "manera."
        )
    addressed = _unanswered_line(witnessed, character_id, names)
    if addressed:
        # 7.17: the line was there since 7.2 and characters still walked past it ("ignorando la
        # instrucción de la capitana", six times in one chapter of 20261017-184641).
        blocks.append(
            f"TE ACABAN DE DECIR (responde a esto, aunque sea para negarte, antes de seguir con "
            f"lo tuyo):\n{addressed}"
        )
    return blocks


def _unanswered_line(turns: list[StageTurn], character_id: str, names: dict[str, str]) -> str:
    """Return the last line spoken to this character that it has not answered yet.

    Derived from addressed_to, so it needs no model call. The 7.1 scenes were rounds of
    monologues: each character pressed its own agenda and nobody took up what was said to them.
    """
    for turn in reversed(turns):
        if turn.kind != "actor":
            continue
        if turn.actor_id == character_id:
            return ""
        if character_id in turn.addressed_to and turn.speech:
            return visible_text(turn, character_id, names)
    return ""


def director_beat_context(
    *,
    scene: SceneBrief,
    beat: BeatBrief,
    turns: list[StageTurn],
    names: dict[str, str],
    gates: list[str],
    tactics: dict[str, list[str]] | None = None,
    used_events: list[str] | None = None,
    clauses: list[str] | None = None,
    props: list[str] | None = None,
) -> str:
    """Build the block the director reads to open or judge one beat.

    Two deterministic signals ride along. The last tactics of each actor make a deadlock
    visible ("confront, confront, confront"), and the world events already used in the play
    stop the director from reaching for the same thunderclap twice.

    ``props`` is the third, when the inventory is on: who is holding what right now, concealed
    objects included. The director is the one agent allowed to know that, because it can then
    point an actor at an object it is carrying and has forgotten about.
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
    if beat.required_gates:
        blocks.append(
            "REVELACIONES OBLIGATORIAS EN ESTE BEAT:\n"
            + "\n".join(f"- {item}" for item in beat.required_gates)
        )
    if clauses:
        blocks.append(
            "CLAUSULAS FIJAS DEL BEAT (evalua exactamente estas):\n"
            + "\n".join(f"- {item}" for item in clauses)
        )
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
    if props:
        blocks.append(
            "UTILERIA EN JUEGO (sugiere usarla, nunca la dictes; lo escondido solo lo sabe quien "
            "lo lleva):\n" + "\n".join(f"- {item}" for item in props)
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
            pieces.append(f"({stage_direction(speaker, turn.action, names)})")
        for move in item_moves(turn):
            pieces.append(item_line(move, names, concealed_from=len(move.witnesses) == 1))
        if turn.speech:
            aside = ""
            if turn.visibility == "whisper":
                addressed = ", ".join(names.get(item, item) for item in turn.addressed_to)
                aside = f" (en voz baja a {addressed})" if addressed else " (en voz baja)"
            pieces.append(f"{speaker}{aside}: {turn.speech}")
        if turn.thought:
            pieces.append(f"[{speaker} piensa: {turn.thought}]")
        if pieces:
            lines.append(f"{turn.id} {' '.join(piece for piece in pieces if piece)}")
    return "TRANSCRIPCION:\n" + "\n".join(lines)


def scene_log(
    turns: list[StageTurn],
    names: dict[str, str],
    *,
    thoughts: bool,
    key_ids: frozenset[str] | set[str] = frozenset(),
    short_names: bool = False,
    reported: dict[str, str] | None = None,
    gestures: dict[str, str] | None = None,
    retold_thoughts: dict[str, str] | None = None,
    scene_labels: dict[str, str] | None = None,
) -> str:
    """Render one scene's log for the narrator, with or without access to inner life.

    ``key_ids`` are the turns the director cited as evidence that a beat landed. They are marked
    so the narrator knows which moments the chapter turns on and can compress the rest: the
    first real run expanded the log instead of curating it, because every turn looked equal.

    ``reported`` replaces every line of speech the chapter does not turn on with its retelling
    in indirect style (7.16). The narrator copies what it reads: whole, it carried 15 of 15 lines
    into 7.15.1; cut after the first sentence (7.15.2), it copied the stubs. A line with no
    accepted retelling is left out. World events always count as key: the only one in the
    7.15.2 finale never reached the prose. The editorial review and the metrics still read the
    full turns.

    ``gestures`` and ``retold_thoughts`` (7.20) replace a direction, a world event and a thought
    with its retelling in the past tense when there is one: the narrator pasted present-tense
    directions whole into the 7.19 islands run. A thought with no retelling is left out; a
    direction with none keeps its old line. ``scene_labels`` opens each scene with its setting.
    """
    calls = ShortNames(names) if short_names else None
    lines = []
    scene = None
    for turn in turns:
        if scene_labels is not None and turn.scene_id != scene:
            scene = turn.scene_id
            if scene_labels.get(scene):
                lines.append(f"[escena: {scene_labels[scene]}]")
        retold = (gestures or {}).get(turn.id, "")
        # On its own line for every kind of turn: sharing a line with a world event, the mark
        # was copied into the prose as part of the sentence (7.10).
        key = turn.id in key_ids or turn.kind == "world"
        if key:
            lines.append("[clave]")
        if turn.kind == "world":
            lines.append(f"({retold or turn.action})")
            continue
        # The narrator copies what it reads: with short_names it reads a name as prose would.
        speaker = calls.name(turn.actor_id) if calls else names.get(turn.actor_id, turn.actor_id)
        if retold:
            lines.append(retold)
        elif turn.action:
            lines.append(f"({stage_direction(speaker, turn.action, names)})")
        for move in item_moves(turn):
            # The narrator is told what actually changed hands, so it can dramatize the gap
            # between what a character said and what it was quietly doing with an object.
            moved = item_line(move, names, concealed_from=len(move.witnesses) == 1)
            if moved:
                lines.append(f"{speaker} {moved}")
        lines.extend(_speech_line(turn, speaker, names, None if key else reported))
        if thoughts:
            lines.extend(_thought_line(turn, speaker, retold_thoughts))
    return "\n".join(lines)


def _speech_line(
    turn: StageTurn, speaker: str, names: dict[str, str], reported: dict[str, str] | None
) -> list[str]:
    """Render a turn's speech whole, or as its retelling when one is given, or not at all."""
    if not turn.speech:
        return []
    if reported is not None:
        return [reported[turn.id]] if reported.get(turn.id) else []
    aside = ""
    if turn.visibility == "whisper":
        addressed = ", ".join(names.get(item, item) for item in turn.addressed_to)
        aside = f" [en voz baja a {addressed}]" if addressed else " [en voz baja]"
    return [f"{speaker}{aside}: {turn.speech}"]


def _thought_line(turn: StageTurn, speaker: str, retold: dict[str, str] | None) -> list[str]:
    """Render a turn's thought labelled, or as its retelling when thoughts are retold."""
    if not turn.thought:
        return []
    if retold is None:
        return [f"[{speaker} piensa: {turn.thought}]"]
    return [retold[turn.id]] if retold.get(turn.id) else []


def prop_line(prop: Prop) -> str:
    """Name one object for an actor, with what it can see of it and whether it is out of sight."""
    line = f"{prop.name}, {prop.appearance}" if prop.appearance else prop.name
    return f"{line} (lo llevas escondido)" if prop.concealed else line


def _presented(member: SceneCastBrief, names: dict[str, str]) -> str:
    """Name one character on stage together with what anyone can see of them."""
    name = names.get(member.character_id, member.character_id)
    return f"{name}, {member.public_face}" if member.public_face else name


def _state_line(state: CharacterState, names: dict[str, str]) -> str:
    """Describe one character's state in words, never in figures.

    Labels rather than a sentence glued around each value: the values are the character's own
    full sentences, so "sigues comprometido con No descansare" broke the grammar and the gender
    every time. A stance towards someone the cast does not name is left out, never printed as id.
    """
    labelled = (
        ("Te sientes", state.emotion),
        ("Ahora intentas", state.goal),
        ("Te has jurado", state.commitment),
        ("Lo que sostienes ante los demás", state.cover_story),
        ("Cambiarías de idea si", _without_leading_if(state.change_condition)),
    )
    pieces = [f"{label}: {_bare(value)}" for label, value in labelled if _bare(value)]
    pieces.extend(
        f"Con {names[item.character_id]}: {_bare(item.stance)}"
        for item in state.relationships
        if item.character_id in names and _bare(item.stance)
    )
    return ". ".join(pieces) + "." if pieces else "sin nada que te pese"


def _bare(value: str) -> str:
    """Trim a state value so a label can carry it: no outer spaces, no closing full stop."""
    return value.strip().rstrip(".").strip()


def _without_leading_if(value: str) -> str:
    """Drop the "si" a character writes before its own condition, which the label already says."""
    stripped = value.strip()
    head, _, rest = stripped.partition(" ")
    return rest if head.casefold() == "si" and rest else stripped
