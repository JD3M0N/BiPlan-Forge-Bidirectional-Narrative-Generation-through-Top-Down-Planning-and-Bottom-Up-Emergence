"""A FakeProvider that can also answer the casting, performance and narration stages.

Extends the narrative double rather than replacing it, so a simulated run exercises the real
planning and scripting stages first and only then reaches the new ones. Every response is
deterministic and derived from the prompt it was given, which is what lets the end-to-end test
assert that two identical runs produce identical logs.
"""

from __future__ import annotations

import json
import re

from asg_stagecraft.runtime.errors import GeminiDailyQuotaError
from asg_stagecraft.stage.schemas import (
    ActorDossier,
    ActorRelationship,
    ActorTurnDraft,
    ActorTurnWithItemsDraft,
    BeatCheckDraft,
    BeatDirection,
    CastBibleDraft,
    FutureConflict,
    FutureRevision,
    ItemActionDraft,
    KnowledgeGate,
    OutcomePart,
    PromiseStoryAuditDraft,
    PromiseStoryCheck,
    PropDraft,
    PropListDraft,
    ReflectionDraft,
    RelationshipState,
    RevisedScene,
)
from test_generator_v5 import FakeProvider

# (speech, action, thought, tactic) tuples with no shared vocabulary between neighbours, so a
# scene can run several turns without tripping the repetition rule.
_SCRIPTED_MOVES = [
    (
        "El expediente salio de aqui anoche y quiero saber quien lo movio.",
        "cierra la puerta con el pie",
        "Si miente lo voy a notar en las manos.",
        "confront",
    ),
    (
        "Nadie toco nada. Estuve sola toda la tarde revisando cajas.",
        "se apoya contra el archivador",
        "No puede probar nada de lo que esta diciendo.",
        "deny",
    ),
    (
        "Entonces explicame por que faltan tres carpetas del estante bajo.",
        "senala el hueco en la balda",
        "Le tiembla la voz cuando habla del estante.",
        "investigate",
    ),
    (
        "Puede que alguien de mantenimiento las bajara al sotano sin avisar.",
        "aparta la mirada hacia la ventana",
        "Necesito ganar tiempo hasta manana.",
        "deflect",
    ),
    (
        "Bajemos juntas ahora mismo y lo comprobamos en dos minutos.",
        "descuelga las llaves del gancho",
        "Si se niega, ya tengo mi respuesta.",
        "test",
    ),
    (
        "Prefiero que hablemos de esto cuando vuelva la directora.",
        "se cruza de brazos",
        "Con testigos delante no se atrevera a insistir.",
        "stall",
    ),
]


def _lap_words(stem: str, lap: int, count: int) -> str:
    """Return words no other round of the scripted moves shares."""
    return " ".join(f"{stem}{lap}{chr(97 + index)}" for index in range(count))


_CAST_IDS = re.compile(r"WRITE ONE DOSSIER FOR EACH OF THESE IDS: (.+)")
_OPENING_CAST = re.compile(r"^- .+ \((\S+)\) quiere:", re.MULTILINE)
_TURN_IDS = re.compile(r"^(\S+-scene-\d+-t\d+)", re.MULTILINE)
_PROP_HOLDERS = re.compile(r"ONLY THESE IDS MAY HOLD AN OBJECT: (.+)")


class StageFakeProvider(FakeProvider):
    """Answer every stage agent deterministically, with optional injected failures."""

    def __init__(
        self,
        *args,
        fail_casting_call: set[int] | None = None,
        fail_props_call: set[int] | None = None,
        fail_actor_call: set[int] | None = None,
        fail_director=False,
        fail_narrator_call: set[int] | None = None,
        quota_error_at_stage: str | None = None,
        empty_turn_once=False,
        repeat_turn_once=False,
        beat_never_achieved=False,
        beat_needs_world=False,
        **kwargs,
    ) -> None:
        """Configure the stage responses and the failures a test wants to force."""
        super().__init__(*args, **kwargs)
        self.fail_casting_calls = set(fail_casting_call or ())
        self.fail_props_calls = set(fail_props_call or ())
        self.fail_actor_calls = set(fail_actor_call or ())
        self.fail_narrator_calls = set(fail_narrator_call or ())
        self.fail_director = fail_director
        self.quota_error_at_stage = quota_error_at_stage
        self.empty_turn_once = empty_turn_once
        self.repeat_turn_once = repeat_turn_once
        self.beat_never_achieved = beat_never_achieved
        self.beat_needs_world = beat_needs_world
        self.check_modes: list[str] = []
        self.casting_number = 0
        self.props_number = 0
        self.actor_number = 0
        self.director_number = 0
        self.narrator_number = 0
        self.actor_contexts: list[str] = []
        self.narrator_prompts: list[str] = []
        self._last_speech: dict[str, str] = {}

    def generate_structured(self, *, system_instruction, prompt, schema, profile):
        """Route the stage schemas here and leave every other schema to the narrative double."""
        if schema is CastBibleDraft:
            self.structured_calls.append((schema.__name__, system_instruction, prompt))
            return self._cast_bible(prompt)
        if schema is PropListDraft:
            self.structured_calls.append((schema.__name__, system_instruction, prompt))
            return self._props(prompt)
        # issubclass, not identity: the inventory asks for the schema with an object field, and
        # the double must answer whichever one the run requested.
        if isinstance(schema, type) and issubclass(schema, ActorTurnDraft):
            self.structured_calls.append((schema.__name__, system_instruction, prompt))
            self.actor_contexts.append(prompt)
            return self._turn(system_instruction, prompt, items=schema is ActorTurnWithItemsDraft)
        if schema is BeatDirection:
            self.structured_calls.append((schema.__name__, system_instruction, prompt))
            return self._direction(prompt)
        if schema is BeatCheckDraft:
            self.structured_calls.append((schema.__name__, system_instruction, prompt))
            return self._check(system_instruction, prompt)
        if schema is FutureConflict:
            self.structured_calls.append((schema.__name__, system_instruction, prompt))
            return FutureConflict()
        if schema is PromiseStoryAuditDraft:
            self.structured_calls.append((schema.__name__, system_instruction, prompt))
            ledger = json.loads(prompt.split("LEDGER:\n", 1)[1].split("\n\nPERFORMED TURNS:", 1)[0])
            return PromiseStoryAuditDraft(
                checks=[
                    PromiseStoryCheck(
                        promise_id=item["id"], opened=False, progressed=False, paid=False
                    )
                    for item in ledger["promises"]
                ]
            )
        if schema is FutureRevision:
            self.structured_calls.append((schema.__name__, system_instruction, prompt))
            remaining = json.loads(prompt)["remaining"]
            return FutureRevision(
                reason="Los personajes dejaron el hito abierto.",
                scenes=[RevisedScene(scene_id=item["scene_id"], keep=False) for item in remaining],
            )
        if schema is ReflectionDraft:
            self.structured_calls.append((schema.__name__, system_instruction, prompt))
            return self._reflection(prompt)
        return super().generate_structured(
            system_instruction=system_instruction, prompt=prompt, schema=schema, profile=profile
        )

    def generate_text(self, *, system_instruction, prompt, profile):
        """Answer the narrator here and leave the Drafter and Writer to the narrative double."""
        if "You are the Narrator" in system_instruction:
            self.text_calls.append((system_instruction, prompt))
            self.narrator_prompts.append(prompt)
            self.narrator_number += 1
            if self.quota_error_at_stage == "narrator":
                raise GeminiDailyQuotaError("daily quota exhausted")
            if self.narrator_number in self.fail_narrator_calls:
                raise RuntimeError("narrator unavailable")
            return (
                f"Narracion del capitulo {self.narrator_number}.\n\n"
                "—Nadie mas lo sabe —dijo Ana.\n\n"
                "Ana cerro el archivo y salio sin mirar atras."
            )
        return super().generate_text(
            system_instruction=system_instruction, prompt=prompt, profile=profile
        )

    # -- casting -------------------------------------------------------------------------

    def _cast_bible(self, prompt: str) -> CastBibleDraft:
        """Build one dossier per requested ID, plus a gate only the first character holds."""
        self.casting_number += 1
        if self.quota_error_at_stage == "casting":
            raise GeminiDailyQuotaError("daily quota exhausted")
        if self.casting_number in self.fail_casting_calls:
            raise RuntimeError("casting director unavailable")
        match = _CAST_IDS.search(prompt)
        ids = [item.strip() for item in match.group(1).split(",")] if match else ["ana"]
        dossiers = [
            ActorDossier(
                character_id=character_id,
                want=f"get what {character_id} came for",
                need="to stop hiding",
                wound="an old betrayal",
                fear="being found out",
                moral_line="will not hand anyone over",
                secret=f"{character_id} took the file" if character_id == ids[0] else "",
                secret_from=ids[1:2] if character_id == ids[0] else [],
                public_face="una archivera de mediana edad, con gafas y la voz baja",
                voice="clipped, concrete, never raises her voice",
                mannerisms=["taps the folder"],
                tactics=["reason", "press", "threaten"],
                triggers=["When cornered, they go quiet."],
                behavior_rules=["Never explain twice."],
                initial_knowledge=["El archivo cierra a las ocho."],
                relationships=[
                    ActorRelationship(
                        character_id=other,
                        stance="wary",
                        wants_from_them="the truth",
                        history="they worked together once",
                        private_opinion="cannot be trusted",
                    )
                    for other in ids
                    if other != character_id
                ],
                initial_emotion="tense",
                initial_goal="find out who else knows",
            )
            for character_id in ids
        ]
        gates = [
            KnowledgeGate(
                id="gate-1",
                fact="El archivo tiene una copia fuera del edificio.",
                known_by=ids[:1],
                revealed_by=ids[0],
                how="confession",
            )
        ]
        return CastBibleDraft(dossiers=dossiers, knowledge_gates=gates)

    # -- the props -----------------------------------------------------------------------

    def _props(self, prompt: str) -> PropListDraft:
        """Dress the stage with props derived from the cast the prompt names.

        One carried in the open, one carried concealed and one lying in the location, so a run
        exercises every branch of the arbiter: holding, hiding, taking from the floor.
        """
        self.props_number += 1
        if self.quota_error_at_stage == "props":
            raise GeminiDailyQuotaError("daily quota exhausted")
        if self.props_number in self.fail_props_calls:
            raise RuntimeError("prop master unavailable")
        match = _PROP_HOLDERS.search(prompt)
        ids = [item.strip() for item in match.group(1).split(",")] if match else ["ana"]
        return PropListDraft(
            props=[
                PropDraft(
                    name="Una llave de laton",
                    appearance="pequena y gastada por el uso",
                    holder_id=ids[0],
                ),
                PropDraft(
                    name="Un cuaderno cosido",
                    appearance="con la cubierta manchada",
                    holder_id=ids[0],
                    concealed=True,
                ),
                PropDraft(name="Un farol apagado", appearance="con el cristal roto"),
            ]
        )

    # -- the performance -----------------------------------------------------------------

    def _draft(self, items: bool, *, prompt: str = "", **fields) -> ActorTurnDraft:
        """Build a turn in whichever shape the run asked for, with an object move when it did."""
        if not items:
            return ActorTurnDraft(**fields)
        return ActorTurnWithItemsDraft(**fields, item_action=self._item_action(prompt))

    def _item_action(self, prompt: str) -> ItemActionDraft:
        """Propose one object move derived from what this actor's own context listed.

        Every proposal is built from the block the actor was shown, so it is always one the
        arbiter should accept: a test that wants a rejection asks for it by name instead.
        """
        held = _listed(prompt, "LO QUE LLEVAS")
        seen = _listed(prompt, "LO QUE VES")
        others = _listed(prompt, "CONTIGO EN ESCENA")
        step = self.actor_number % 4
        if step == 1 and held:
            return ItemActionDraft(verb="use", item=held[0])
        if step == 2 and held and others:
            return ItemActionDraft(verb="give", item=held[-1], target=others[0])
        if step == 3 and seen:
            return ItemActionDraft(verb="take", item=seen[0])
        return ItemActionDraft()

    def _turn(self, system_instruction: str, prompt: str, *, items: bool = False) -> ActorTurnDraft:
        """Answer one actor turn, honoring any failure the test injected."""
        self.actor_number += 1
        if self.quota_error_at_stage == "actor":
            raise GeminiDailyQuotaError("daily quota exhausted")
        if self.actor_number in self.fail_actor_calls:
            raise RuntimeError("actor unavailable")
        speaker = system_instruction.split(".", 1)[0].replace("You are ", "").strip()
        if self.empty_turn_once and self.actor_number == 1:
            self.empty_turn_once = False
            return self._draft(items, thought="", action="", speech="", tactic="stall")
        if self.repeat_turn_once and speaker in self._last_speech:
            repeated = self._last_speech[speaker]
            self.repeat_turn_once = False
            return self._draft(items, speech=repeated, action="", thought="", tactic="deny")
        # Every line is lexically distinct on purpose. A double that restated itself would be
        # rejected by the repetition rule, which is correct behaviour but would leave the happy
        # path untested: scenes would end after a single accepted turn.
        speech, action, thought, tactic = _SCRIPTED_MOVES[self.actor_number % len(_SCRIPTED_MOVES)]
        # The engine compares a line against everything its speaker said in the whole play, so a
        # scripted move that comes round again carries words of its own round: the happy path
        # must not trip a rule it is not testing. Gestures always carry them, because the
        # gesture rule measures containment and an added clause alone would not change it.
        lap = self.actor_number // len(_SCRIPTED_MOVES)
        if lap:
            speech = f"{speech} {_lap_words('ronda', lap, 6)}"
        action = f"{action} {_lap_words('paso', lap, 2)}"
        self._last_speech[speaker] = speech
        return self._draft(
            items, thought=thought, action=action, speech=speech, tactic=tactic, prompt=prompt
        )

    def _direction(self, prompt: str) -> BeatDirection:
        """Open a beat with the first character the brief lists on stage."""
        self.director_number += 1
        if self.quota_error_at_stage == "director":
            raise GeminiDailyQuotaError("daily quota exhausted")
        if self.fail_director:
            raise RuntimeError("stage manager unavailable")
        match = _OPENING_CAST.search(prompt)
        opening = match.group(1) if match else "ana"
        return BeatDirection(opening_actor_id=opening, notes=[f"{opening}: empuja hasta que ceda"])

    def _check(self, system_instruction: str, prompt: str) -> BeatCheckDraft:
        """Show the beat's one clause as soon as the transcript holds a turn, unless told not to.

        ``beat_never_achieved`` keeps the clause unshown on every rung, so the beat climbs the
        whole ladder and is forced; ``beat_needs_world`` shows it only on the final reading,
        after the world has stepped in, so the beat lands as intervened.
        """
        self.director_number += 1
        if self.quota_error_at_stage == "director":
            raise GeminiDailyQuotaError("daily quota exhausted")
        if self.fail_director:
            raise RuntimeError("stage manager unavailable")
        mode = _mode_of(system_instruction)
        self.check_modes.append(mode)
        turn_ids = _TURN_IDS.findall(prompt)
        held_back = self.beat_never_achieved or (self.beat_needs_world and mode != "final")
        if held_back or not turn_ids:
            cast = _OPENING_CAST.findall(prompt)
            turning = cast[-1] if cast and mode in {"turn", "stall"} else ""
            return BeatCheckDraft(
                parts=[OutcomePart(part="the file is handed over", shown=False)],
                turning_actor_id=turning,
                notes=[f"{turning}: ya no tiene sentido seguir negandolo"] if turning else [],
                stage_event=(
                    "Se abre la puerta y la directora deja la carpeta perdida sobre la mesa."
                    if mode == "stall"
                    else ""
                ),
            )
        return BeatCheckDraft(
            parts=[OutcomePart(part="the file is handed over", shown=True, evidence=turn_ids[-1:])]
        )

    def _reflection(self, prompt: str) -> ReflectionDraft:
        """Close a scene with a first-person summary and one consolidated stance."""
        if self.quota_error_at_stage == "reflection":
            raise GeminiDailyQuotaError("daily quota exhausted")
        return ReflectionDraft(
            summary="Sali de alli sabiendo que no me lo habian contado todo.",
            beliefs=["Ahora se que alguien mas tiene una copia."],
            relationships=[RelationshipState(character_id="ana", stance="desconfianza")],
            emotion="inquieta",
            goal="averiguar quien mas lo sabe",
            importance=0.7,
        )


def _listed(prompt: str, heading: str) -> list[str]:
    """Read back the names one block of an actor's context listed, in order."""
    block = prompt.split(heading + ":\n", 1)
    if len(block) == 1:
        return []
    names = []
    for line in block[1].splitlines():
        if not line.startswith("- "):
            break
        names.append(line[2:].split(",", 1)[0].split(" (")[0].strip())
    return names


def _mode_of(system_instruction: str) -> str:
    """Tell which rung of the escalation ladder a director call was made on."""
    if "The world has already stepped in" in system_instruction:
        return "final"
    if "The scene has used its time" in system_instruction:
        return "stall"
    if "Name turning_actor_id" in system_instruction:
        return "turn"
    return "check"
