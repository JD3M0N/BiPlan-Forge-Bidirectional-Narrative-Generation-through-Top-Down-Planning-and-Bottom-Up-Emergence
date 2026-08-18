# ASG Top-Down 3.1

`StoryGenerator` es la única ruta de producción. Separa tres decisiones que no
deben contaminarse entre sí:

1. El sistema de taxonomías recupera una paleta de género y el planificador
   selecciona solo las promesas y posibilidades útiles para esta historia.
2. STORYTELLER determina qué ocurre mediante una STORYLINE causal de eventos
   SVO/SVS aceptados y un NEKG local.
3. El módulo de craft determina cómo preparar expectativas, progresos, pagos,
   arcos de personajes y ciclos try-fail, sin aceptar, rechazar ni modificar
   nodos.

Todas las instrucciones enviadas al modelo están en inglés. El analista conserva
español como idioma predeterminado y el escritor usa siempre el idioma solicitado.

## Taxonomías flexibles

El catálogo SQLite contiene 24 perfiles ingleses de géneros y story engines,
desde `heist-caper` y `whodunit-mystery` hasta `first-contact`,
`family-domestic-drama` y `sports-underdog`. Cada perfil ofrece promesas al
lector, señales de identificación, roles con variaciones, movimientos `core`,
`common` u `optional`, complicaciones, giros opcionales, conclusiones,
subversiones y controles de calidad. No es una plantilla de beats.

La recuperación híbrida devuelve hasta tres candidatos. El plan nuevo usa una
taxonomía primaria y, solo cuando el prompt lo pide explícitamente, un accent.
`taxonomy_application.json` registra las opciones elegidas y
`taxonomy_brief.json` compila descripciones inglesas para los agentes. El
escritor puede fusionar, reordenar u omitir convenciones no esenciales y nunca
expone nombres ni IDs taxonómicos en la ficción.

```python
from asg_top_down import StoryGenerator

generator = StoryGenerator(provider, output_root)
run = generator.generate(prompt_or_request)
print(run.story_path)
```

## Planificación STORYTELLER

El catálogo SQLite reproducible recupera perfiles taxonómicos completos mediante
aliases, señales, FTS y embeddings con fallback local. El planificador crea
premisa, sinopsis y capítulos; genera un
CBN y un CEN por capítulo; y luego propone pseudo-CPN uno a uno. Cada revisión
consulta los ocho eventos más recientes y hasta diez relaciones NEKG, priorizando
el par dirigido sujeto→objeto y después las relaciones incidentes por recencia.

Los siete controles causales —causalidad, intención, conflicto, continuidad,
novedad, avance hacia el final y consistencia del mundo— son bloqueantes. El
capítulo termina cuando al menos un CPN aceptado conecta naturalmente con el CEN,
con un techo de `max(1, min(10, ceil(target_words / 350)))`. Solo los eventos
aceptados actualizan STORYLINE y NEKG. Cada aceptación y rechazo produce un
checkpoint auditable.

## Craft independiente

Después de cerrar STORYLINE, una llamada produce exactamente `variant-1`,
`variant-2` y `variant-3`, y otra selecciona la variante canónica. Cada plan
contiene una línea PPP maestra, entre cero y dos sublíneas, una línea PPP local
por capítulo, hitos observables del slider focal y la cantidad adaptativa de
ciclos Yes-but/No-and. Los contratos no contienen IDs de nodos ni pueden usar
los términos CBN, CPN o CEN.

Cada personaje principal empieza con exactamente dos sliders altos (7–10) y uno
bajo (1–4). El bajo es el foco y debe terminar alto (7–10). El escritor recibe
solo la variante seleccionada, el craft del capítulo actual y el capítulo
anterior completo. El auditor convierte PPP, sliders, try-fail y cada constraint
del usuario en preguntas bloqueantes; permite hasta dos reescrituras y conserva
la mejor versión si una etapa tardía falla.

## Artefactos

`plan.json` es la fuente autoritativa de cada variante:

```text
craft/
  selection.json
  variants/
    variant-N/
      plan.json
      global.json
      chapters/chapter-XXX.json
      chapters/chapter-XXX.md
      draft.md
      craft_audit.json
      craft_revision_history.json
      length_audit.json
      llm_usage.json
      story.md
```

La variante seleccionada también se refleja en `story.md`, `draft.md`,
`chapters/`, `craft_audit.json`, `craft_revision_history.json` y
`length_audit.json` de la raíz para mantener compatibles el CLI, la consola y
Telegram. Los directorios de variantes renderizadas pueden pasarse directamente
a `compare-story-runs`.

Una variante alternativa se redacta sin volver a llamar al analista, planificador,
constructor de mundo, diseñador de personajes, planificador STORYTELLER ni
selector de craft:

```python
alternate = generator.render_variant(run.run_dir, "variant-2")
print(alternate.story_path)
```

La operación es idempotente cuando ya existe su `story.md` y nunca cambia
`craft/selection.json` ni la historia canónica. Los runs v2 terminados siguen
siendo entregables; los parciales reinician desde `request.json`, y
`render_variant` exige artefactos v3.

## Recuperación y límites

`planning_checkpoint/` conserva STORYLINE, NEKG y revisiones tras cada decisión.
`resume()` devuelve inmediatamente un run terminado y reinicia un parcial en un
nuevo directorio. La longitud final se audita con tolerancia −10 %/+20 %. Las
llamadas, tokens, esperas y reintentos se conservan en `llm_usage.json`.

```powershell
compare-story-runs Stories/Top-Down/run/craft/variants/variant-1 `
  Stories/Top-Down/run/craft/variants/variant-2 --output comparacion.html
```
