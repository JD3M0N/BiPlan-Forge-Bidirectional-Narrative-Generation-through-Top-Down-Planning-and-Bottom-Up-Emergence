from __future__ import annotations

from copy import deepcopy
import re
from typing import Any, Mapping


ARCHITECT_PROMPT = "The Architect"
PLANNING_ROOM_PROMPT = "The Planning Room"
WORLD_BUILDER_PROMPT = "The World Builder"
DIRECTOR_PROMPT = "The Director"
CHARACTER_SIMULATOR_PROMPT = "The Character Simulator"
PLOT_WEAVER_PROMPT = "The Plot Weaver"
DRAMA_COACH_PROMPT = "The Drama Coach"
DEPENDENCY_MANAGER_PROMPT = "The Dependency Manager"
COORDINATOR_PROMPT = "The Coordinator/ReIO"
CHAPTER_WRITER_PROMPT = "The Chapter Writer"
CHAPTER_WRITER_BATCH_PROMPT = "The Chapter Writer Batch"
QUALITY_EVALUATOR_PROMPT = "The Quality Evaluator"
QUALITY_REWRITER_PROMPT = "The Quality Rewriter"
NARRATOR_PROMPT = QUALITY_REWRITER_PROMPT

DEFAULT_STORY_REQUEST: dict[str, Any] = {
    "characters": [
        {
            "name": "Ayla",
            "role": "aprendiz",
            "description": "Joven disciplinada que teme perder sus recuerdos",
        }
    ],
    "style": "fantasia melancolica",
    "plot": "Una aprendiz descubre un reloj que rompe el tiempo y debe elegir entre la ciudad y su memoria.",
    "length": "medium",
    "language": "es",
}

DEFAULT_AGENT_PAYLOADS: dict[str, dict[str, Any]] = {
    ARCHITECT_PROMPT: {
        "premise": "Una aprendiz encuentra un reloj que abre grietas temporales.",
        "synopsis": "Ayla intenta salvar su ciudad mientras cada uso del reloj le cuesta un recuerdo.",
        "beats": [
            {
                "title": "La llamada",
                "purpose": "Introducir el artefacto y la mision",
                "stakes": "El tiempo local empieza a deshacerse",
            }
        ],
        "seed_events": [
            {
                "id": "E1",
                "summary": "Ayla descubre el reloj umbral en la torre.",
                "purpose": "Abrir el conflicto temporal",
                "characters": ["Ayla"],
                "dependencies": [],
            }
        ],
        "climax": "La protagonista decide romper el reloj para salvar a su mentora.",
        "resolution": "La ciudad sobrevive pero ella pierde el ultimo recuerdo de su padre.",
    },
    WORLD_BUILDER_PROMPT: {
        "characters": [
            {
                "name": "Ayla",
                "role": "aprendiz",
                "description": "Joven precisa y obsesionada con el orden",
                "desire": "Salvar la ciudad",
                "fear": "Repetir el fracaso de su padre",
            }
        ],
        "locations": [
            {
                "name": "Archivo del Reloj",
                "description": "Una torre silenciosa con mecanismos y polvo brillante",
                "mood": "solemne",
            }
        ],
        "objects": [
            {"name": "Reloj umbral", "significance": "Abre fisuras entre momentos cercanos"}
        ],
        "rules": ["Cada uso del reloj borra un recuerdo humano."],
        "initial_state": "La torre esta quieta, Ayla conserva sus recuerdos y el reloj esta sellado.",
        "entity_relations": [
            {"source": "Ayla", "relation": "custodia", "target": "Reloj umbral"}
        ],
    },
    DIRECTOR_PROMPT: {
        "acts": [
            {
                "abstract_act": "Tentacion del costo",
                "purpose": "Forzar una decision sin manipular directamente a Ayla",
                "target_event_ids": ["E1"],
                "environmental_intervention": "El reloj muestra una vision de la ciudad cayendo.",
                "expected_pressure": "Ayla debe elegir entre memoria y deber.",
            }
        ],
        "constraints": ["El Director solo altera ambiente e informacion."],
    },
    CHARACTER_SIMULATOR_PROMPT: {
        "actions": [
            {
                "character": "Ayla",
                "event_id": "E1",
                "intention": "Entender el reloj sin perder el control",
                "action": "Ayla prueba el mecanismo con cautela.",
                "memory_used": "Recuerda las advertencias de su padre.",
                "reflection": "Comprende que toda solucion tendra un costo.",
                "world_delta": "Aparece una grieta de tiempo en el Archivo del Reloj.",
            }
        ],
        "memory_updates": ["Ayla asocia el reloj con la perdida de recuerdos."],
    },
    PLOT_WEAVER_PROMPT: {},
    COORDINATOR_PROMPT: {},
    CHAPTER_WRITER_PROMPT: {},
    DRAMA_COACH_PROMPT: {
        "revised_beats": [
            {
                "title": "Traicion del mentor",
                "purpose": "Subir el conflicto emocional",
                "stakes": "Ayla duda de su mision",
            }
        ],
        "tension_notes": ["La mentora intenta quedarse con el reloj."],
        "character_arc_notes": ["Ayla aprende a aceptar la perdida."],
        "pacing_notes": ["Alternar descubrimientos con decisiones irreversibles."],
        "suspense_devices": ["Presagio del recuerdo perdido."],
    },
    DEPENDENCY_MANAGER_PROMPT: {
        "is_consistent": True,
        "issues": [],
        "fixes_applied": ["Se mantiene la regla de perdida de memoria."],
        "narrator_guidance": ["Mantener tono melancolico y preciso."],
        "dependency_notes": ["E1 no depende de eventos previos."],
    },
    QUALITY_EVALUATOR_PROMPT: {
        "relevance": 4.5,
        "coherence": 4.4,
        "empathy": 4.1,
        "surprise": 3.8,
        "engagement": 4.2,
        "complexity": 4.0,
        "orchestration": 4.3,
        "overall": 4.2,
        "blocking_issues": [],
        "notes": ["La historia conserva causalidad y arco emocional."],
    },
    QUALITY_REWRITER_PROMPT: {
        "title": "El reloj de la torre muda",
        "summary": "Ayla intenta salvar su ciudad mientras cada uso del reloj le cuesta un recuerdo.",
        "story_text": "## Capitulo 1\n\nAyla subio la torre al anochecer y corrigio la grieta temporal.",
    },
}

INCONSISTENT_DEPENDENCY_PAYLOAD: dict[str, Any] = {
    "is_consistent": False,
    "issues": ["El objeto crucial desaparece antes del climax."],
    "fixes_applied": [],
    "narrator_guidance": ["No narrar hasta resolver la contradiccion."],
}


class FakeGeminiClient:
    def __init__(
        self,
        *,
        fail_on: str | None = None,
        inconsistent_dependency: bool = False,
        invalid_payload_for: str | None = None,
        custom_payloads: Mapping[str, dict[str, Any]] | None = None,
        blocking_quality_once: bool = False,
        blocking_quality_always: bool = False,
    ) -> None:
        self.fail_on = fail_on
        self.inconsistent_dependency = inconsistent_dependency
        self.invalid_payload_for = invalid_payload_for
        self.custom_payloads = dict(custom_payloads or {})
        self.blocking_quality_once = blocking_quality_once
        self.blocking_quality_always = blocking_quality_always
        self.quality_calls = 0
        self.call_count = 0

    async def generate_json(self, prompt: str) -> dict[str, Any]:
        self.call_count += 1
        if self.fail_on and self.fail_on in prompt:
            raise RuntimeError("Synthetic agent failure")

        if PLANNING_ROOM_PROMPT in prompt:
            if self.invalid_payload_for == PLANNING_ROOM_PROMPT:
                return {"unexpected": "shape"}
            return self._build_planning_room_payload(prompt)

        if CHAPTER_WRITER_BATCH_PROMPT in prompt:
            if self.invalid_payload_for == CHAPTER_WRITER_BATCH_PROMPT:
                return {"unexpected": "shape"}
            return self._build_chapter_batch_payload(prompt)

        for marker, default_payload in DEFAULT_AGENT_PAYLOADS.items():
            if marker not in prompt:
                continue

            if self.invalid_payload_for == marker:
                return {"unexpected": "shape"}

            if marker == DEPENDENCY_MANAGER_PROMPT and self.inconsistent_dependency:
                return deepcopy(INCONSISTENT_DEPENDENCY_PAYLOAD)

            if marker == PLOT_WEAVER_PROMPT:
                return self._build_plot_weave_payload(prompt)

            if marker == COORDINATOR_PROMPT:
                return self._build_context_payload(prompt)

            if marker == CHAPTER_WRITER_PROMPT:
                return self._build_chapter_payload(prompt)

            if marker == QUALITY_EVALUATOR_PROMPT:
                self.quality_calls += 1
                if self.blocking_quality_always or (self.blocking_quality_once and self.quality_calls == 1):
                    payload = deepcopy(default_payload)
                    payload["blocking_issues"] = ["El cierre contradice el costo del reloj."]
                    payload["overall"] = 2.0
                    return payload

            payload = self.custom_payloads.get(marker, default_payload)
            return deepcopy(payload)

        raise AssertionError("Prompt desconocido")

    def _chapter_count(self, prompt: str) -> int:
        match = re.search(r"exactly\s+(\d+)\s+chapters", prompt)
        return int(match.group(1)) if match else 3

    def _chapter_index(self, prompt: str) -> int:
        match = (
            re.search(r"Target chapter index:\s*(\d+)", prompt)
            or re.search(r'"chapter_index":\s*(\d+)', prompt)
            or re.search(r'"index":\s*(\d+)', prompt)
        )
        return int(match.group(1)) if match else 1

    def _chapter_indexes(self, prompt: str) -> list[int]:
        matches = [int(index) for index in re.findall(r'"index":\s*(\d+)', prompt)]
        if not matches:
            return [1]
        return list(range(1, max(matches) + 1))

    def _build_planning_room_payload(self, prompt: str) -> dict[str, Any]:
        plot_weave = self._build_plot_weave_payload(prompt)
        dependency = (
            deepcopy(INCONSISTENT_DEPENDENCY_PAYLOAD)
            if self.inconsistent_dependency
            else deepcopy(DEFAULT_AGENT_PAYLOADS[DEPENDENCY_MANAGER_PROMPT])
        )
        return {
            "architect_outline": deepcopy(DEFAULT_AGENT_PAYLOADS[ARCHITECT_PROMPT]),
            "world_bible": deepcopy(DEFAULT_AGENT_PAYLOADS[WORLD_BUILDER_PROMPT]),
            "director_plan": deepcopy(DEFAULT_AGENT_PAYLOADS[DIRECTOR_PROMPT]),
            "simulation_log": deepcopy(DEFAULT_AGENT_PAYLOADS[CHARACTER_SIMULATOR_PROMPT]),
            "event_graph": plot_weave["event_graph"],
            "entity_graph": plot_weave["entity_graph"],
            "chapter_plan": plot_weave["chapter_plan"],
            "drama_revision": deepcopy(DEFAULT_AGENT_PAYLOADS[DRAMA_COACH_PROMPT]),
            "dependency_review": dependency,
        }

    def _build_plot_weave_payload(self, prompt: str) -> dict[str, Any]:
        chapter_count = self._chapter_count(prompt)
        event_graph = []
        chapters = []
        narrative_order = []
        for index in range(1, chapter_count + 1):
            event_id = f"E{index}"
            narrative_order.append(event_id)
            event_graph.append(
                {
                    "id": event_id,
                    "summary": f"Ayla enfrenta la consecuencia temporal {index}.",
                    "svo": {"subject": "Ayla", "verb": "enfrenta", "object": f"consecuencia {index}"},
                    "characters": ["Ayla"],
                    "location": "Archivo del Reloj",
                    "time": f"noche {index}",
                    "dependencies": [] if index == 1 else [f"E{index - 1}"],
                    "dramatic_role": "climax" if index == chapter_count else "turn",
                }
            )
            chapters.append(
                {
                    "index": index,
                    "title": f"Capitulo {index}",
                    "abstract": f"Ayla avanza por la grieta temporal {index}.",
                    "event_ids": [event_id],
                    "target_words": 600,
                }
            )
        return {
            "event_graph": event_graph,
            "entity_graph": [{"source": "Ayla", "relation": "usa", "target": "Reloj umbral"}],
            "chapter_plan": {"chapters": chapters, "narrative_order": narrative_order},
        }

    def _build_context_payload(self, prompt: str) -> dict[str, Any]:
        index = self._chapter_index(prompt)
        return {
            "chapter_index": index,
            "relevant_events": [f"E{index}"],
            "summary": f"Contexto comprimido para el capitulo {index}.",
            "continuity_constraints": ["Cada uso del reloj borra un recuerdo humano."],
        }

    def _build_chapter_payload(self, prompt: str) -> dict[str, Any]:
        index = self._chapter_index(prompt)
        return {
            "chapter_index": index,
            "title": f"Capitulo {index}",
            "text": f"Ayla atraviesa el capitulo {index} y protege la ciudad sin olvidar el costo.",
            "rewritten": False,
            "notes": ["Mantiene tono melancolico."],
        }

    def _build_chapter_batch_payload(self, prompt: str) -> dict[str, Any]:
        return {
            "chapters": [
                {
                    "chapter_index": index,
                    "title": f"Capitulo {index}",
                    "text": f"Ayla atraviesa el capitulo {index} y protege la ciudad sin olvidar el costo.",
                    "rewritten": False,
                    "notes": ["Mantiene tono melancolico."],
                }
                for index in self._chapter_indexes(prompt)
            ]
        }


def build_story_request(**overrides: Any) -> dict[str, Any]:
    payload = deepcopy(DEFAULT_STORY_REQUEST)
    payload.update(overrides)
    return payload
