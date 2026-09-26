# Guion teatral: un contrato, dos métodos

El Top-Down puede entregar, además de la historia narrativa de siempre, un **guion teatral**
por actos y escenas: reparto, diálogos y acotaciones. Es el paso previo a una simulación
Bottom-Up donde los personajes se interpretan como actores, así que el guion tiene que ser
legible por máquina, no solo por una persona.

No sabíamos qué método daría un mejor guion, así que se implementaron **los dos**, con el mismo
contrato de salida, para poder compararlos a ciegas y quedarse con uno. Ese es justamente el
ítem abierto en `TODO.md`: **medir y borrar el que pierda**.

## Cómo se elige

`StoryFormat` (`narrative` | `script`) y `ScriptMethod` (`native` | `adapted`) viven en
`packages/stagecraft/src/asg_stagecraft/formats.py`. El formato por defecto es `narrative`, así que
no elegir nada no cambia nada.

- CLI: `generate-story "<prompt>" --format script --script-method native`
- `.env`: `ASG_STORY_FORMAT=script`, `ASG_SCRIPT_METHOD=native`
- Consola: pregunta tras el prompt, con el valor de `.env` como opción por defecto (Enter)
- Telegram: `/newstory` abre con tres botones antes de pedir el prompt

## Dos métodos, un solo contrato

- **Nativo** (`script_stages.ScriptStagesMixin._write_script`): tras la etapa `promises`, el
  `PlaywrightAgent` escribe cada capítulo del plan directamente como un acto de escenas
  estructurado, con el mismo bucle de reparación que usan `graph.py` y `promises.py`. Después lo
  revisa el `ScriptCriticAgent` y lo corrige el `ScriptWriterAgent`.
- **Adaptado** (`_adapt_story`): el pipeline narrativo corre entero, sin tocar — mismo Drafter,
  mismo Writer, mismo Drama Critic, mismos prompts —, guarda su prosa final como `prose.md`, y
  el `ScriptAdapterAgent` convierte cada capítulo final en un acto a través del **mismo**
  validador (`script.py`).

Los dos terminan en el mismo `assemble_play(...)` y en el mismo `PlayScript`, guardado como
`script.json` y renderizado a `story.md`. Eso es lo que hace comparables los dos métodos:
`compare-story-runs` a ciegas sobre `story.md`, y `script_metrics.json` con las mismas cifras en
ambos.

### Campos de `script.json`

| Campo | Qué es |
|---|---|
| `title`, `language`, `script_method` | Metadatos del guion completo |
| `cast_heading`, `act_label`, `scene_label` | Rótulos localizados («Personajes», «Acto», «Escena») |
| `cast` | Reparto completo: id, nombre y descripción |
| `acts[].chapter_id`, `acts[].title` | Un acto por capítulo del plan |
| `acts[].scenes[].event_ids` | Los eventos del plan que esa escena escenifica, en su orden |
| `acts[].scenes[].location_id` | Ubicación de la escena, o `null` si ninguno de sus eventos declara una |
| `acts[].scenes[].cast[].character_id` | Un personaje en escena |
| `acts[].scenes[].cast[].objective` | **En inglés**, como el plan y los personajes: qué persigue ese personaje en esa escena. Nunca se imprime |
| `acts[].scenes[].lines[]` | Diálogo (`speaker_id`, `parenthetical`, `text`) o acotación (`actor_ids`, `text`) |

## Qué valida `script.py` y qué solo corrige

El validador normaliza más de lo que rechaza: cuando una forma tiene una sola corrección
posible, se corrige en vez de gastar un intento pidiéndole al modelo que la repare. Se
normalizan en silencio los espacios sobrantes, los paréntesis que envuelven una acotación o el
escenario, los guiones al inicio de un diálogo, el `speaker_id`/parentético que sobra en una
acotación, el reparto o los eventos duplicados, el orden de los eventos dentro de una escena y
una ubicación deducible cuando todos los eventos de la escena coinciden.

Lo que sí rechaza, en este orden: los eventos citados existen en el plan; pertenecen al
capítulo del acto; las escenas avanzan en el orden del plan (un evento puede continuar en la
escena siguiente); todo evento del capítulo está en alguna escena; la ubicación existe; los
eventos de una escena no están en ubicaciones distintas; la ubicación de la escena coincide con
la de sus eventos; el reparto son personajes conocidos; todo diálogo tiene hablante; el hablante
está en el reparto de la escena; los actores de una acotación están en el reparto; el acto tiene
al menos una réplica.

Dos cosas quedan solo como observación, nunca como rechazo: un participante de un evento que no
sale en ninguna escena que lo escenifica, y un miembro del reparto que ni habla ni actúa
(«reparto ocioso»). Ambas se cuentan en `script_metrics.json` (`absent_participants`,
`idle_cast`).

## Reparación

Un acto rechazado se guarda en `acts/act-NNN-attempt-NNN.json` (o `adaptation/...` en el método
adaptado), con el mensaje de error exacto. Ese mismo mensaje, en inglés y ASCII, se reinyecta
literal en el siguiente intento junto al índice de anclas legales (`ACT ANCHOR INDEX`), igual
que hace `_record_rejected_plan` con `graph.py`. Son 3 intentos por acto; agotados, el run aborta
con `SCRIPT_VALIDATION_FAILED` — en la etapa `drafting` para el nativo, en `adaptation` para el
adaptado, donde `prose.md` queda pero `story.md` nunca se escribe.

## Convención de render

`script_render.py` sigue la convención española de teatro impreso: `NOMBRE.—(parentético) texto`
para el diálogo, y `(texto)` en párrafo aparte para las acotaciones. No usa `*` ni `_`: Telegram
escapa todo lo que no sea un encabezado, el lector de audio quita las marcas de Markdown pero no
sus caracteres, y el HTML de comparación a ciegas los mostraría tal cual. Solo el código emite
encabezados `#`/`##`/`###`; el modelo nunca puede colar uno.

## Artefactos por método

**Nativo**: `script_presentation.json`, `acts/act-NNN.json` (+ intentos), `draft.md`,
`review.json`, `promise_audit.json`, `writer/act-NNN-attempt-NNN.json`, `revisions/act-NNN.json`,
`revision_report.json`, `script.json`, `script_metrics.json`, `story.md`. No escribe
`story_metrics.json`, `craft_evidence.json`, `chapters/` ni `draft_presentation.json`.

**Adaptado**: todo lo narrativo hasta `revision_report.json`, más `prose.md`,
`script_presentation.json`, `adaptation/act-NNN.json` (+ intentos), `script.json`,
`script_metrics.json`, `story.md`.

`script.json` se escribe siempre antes que `story.md`, así que todo run que tenga `story.md`
—el criterio de `recover-story-runs`— también trae su guion.

## Versionado

`PIPELINE_VERSION` se queda en 6.2: el formato de salida es aditivo y conmutable, así que el
predicado de qué trae un run es `metadata.story_format` (o la presencia de `script.json`), no la
versión del pipeline. Ojo con esto al leer un `story.md` con herramientas pensadas para prosa:
`report-story-craft` filtra los guiones por defecto porque `craft_metrics` mide diálogo por
comillas o raya inicial de párrafo, y `NOMBRE.—texto` no cumple ninguna de las dos: mediría casi
0% de diálogo en un guion perfectamente hablado.

## Cómo comparar

- `compare-story-runs <run-nativo> <run-adaptado>` para una comparación ciega sobre `story.md`.
- `script_metrics.json` de cada run, con las mismas cifras en los dos métodos.
- La tasa de intentos rechazados en `acts/*-attempt-*.json` / `adaptation/*-attempt-*.json`.
- La tasa de `SCRIPT_VALIDATION_FAILED` y de avisos `SCRIPT_REVISION_REJECTED`.
- `llm_usage.json`, para el coste: el adaptado paga el pipeline narrativo completo más N+1
  llamadas estructuradas de adaptación.

**Asimetría conocida**: en el método adaptado, `promise_audit.json` audita lo que la *prosa*
entregó, no lo que el guion escenifica — el `ScriptAdapterAgent` no recibe obligaciones de
promesa, porque su contrato es la fidelidad a la prosa ya escrita y juzgada. En el método
nativo, en cambio, el `PlaywrightAgent` y el `ScriptCriticAgent` sí reciben y juzgan las
obligaciones de promesa directamente sobre el guion.

Como con cualquier medición de este repositorio, un n pequeño no basta: la variación de plan a
plan es la confusión principal entre correr el mismo prompt dos veces. La idea pendiente en
`TODO.md` es forzar los dos métodos a partir de un único plan congelado para poder comparar solo
la escritura, no la planificación.
