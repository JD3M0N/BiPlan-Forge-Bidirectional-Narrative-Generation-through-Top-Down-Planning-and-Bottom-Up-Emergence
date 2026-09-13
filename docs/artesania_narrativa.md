# Artesanía narrativa del corpus Top-Down

**Medido el 2026-09-13 con `report-story-craft` de `asg-evaluation` 0.4.0 sobre las 104 historias
de `Stories/`.** Entran en el informe las **74 con versión de generador o de pipeline 6 o
posterior**; de ellas **72 están `completed`** y son las que forman las medianas. Las nueve
historias de la versión 6.5.0 se generaron ese mismo día con Gemini real (`gemini-3.5-flash-lite`)
como línea base de la artesanía.

El documento responde a una pregunta que `story_metrics.json` no podía responder antes: **¿el
pipeline escribe escena o escribe resumen?** Las palabras, los capítulos y los eventos no
distinguen una escena dramatizada de una sinopsis densa.

## Qué se mide

Las primitivas están en `asg_core.craft` (`craft_metrics`, `prose_paragraphs`, `split_sentences`) y
son deterministas: mismo texto, mismas cifras.

- **Párrafo de prosa.** Bloque separado por línea en blanco, descartando encabezados, reglas
  horizontales y bloques de código. Las marcas Markdown se limpian sin tocar la raya ni las
  comillas.
- **`dash_paragraphs`.** Párrafos cuyo primer carácter es raya (U+2014 o U+2013). Es la señal
  fuerte: la convención tipográfica española de línea de diálogo. La raya interior de la acotación
  («—dijo Elena—») **no** cuenta, porque casi siempre vive en un párrafo que ya abre con raya.
- **`quoted_paragraphs`.** Párrafos con comillas en cualquier posición. Señal **débil**: de los
  2890 párrafos de prosa de las historias 6.x, 987 abren con raya (34,2 %) y sólo 15 llevan
  comillas (0,5 %), de los cuales 14 no abrían con raya. Las comillas marcan también pensamiento,
  énfasis y títulos citados, así que suman al conteo pero no lo gobiernan.
- **`dialogue_paragraphs`** es la unión de las dos, y **`dialogue_ratio`** es esa unión dividida
  entre los párrafos de prosa. La ratio estricta de raya sigue siendo recuperable del artefacto.
- **`words_per_sentence`.** Palabras de prosa entre frases. Se corta en `.!?…`, normalizando `...`
  a `…` antes de segmentar; `¿` y `¡` son aperturas, nunca terminadores; ni los decimales
  (`1.500`) ni las abreviaturas conocidas (`Sr.`, `Dr.`, `etc.`) cortan; un párrafo sin terminador
  cuenta una frase.
- **`words_per_paragraph`.** Palabras de prosa entre párrafos de prosa.

## Dónde vive cada cifra

Desde la versión **6.5.0** del generador (`pipeline_version: 6.1`), cada run escribe las cifras en
su `story_metrics.json`, también capítulo a capítulo en `chapter_metrics`, junto a
`chapter_bodies_recovered`, que declara si los encabezados canónicos sobrevivieron: si no, las
cifras por capítulo son cero por pérdida de encabezado y no por capítulo vacío. Ninguna cifra viaja
a ningún prompt: son observaciones, no objetivos.

Para los runs anteriores no hay nada que migrar. `report-story-craft` recalcula la artesanía desde
`story.md`, así que las 65 historias 6.0-6.4.1 son comparables con las nueve de 6.5.0.

## Cómo reproducir esta medición

```powershell
report-story-craft --min-version 6 --csv docs\artesania_narrativa_corpus.csv --group all
report-story-craft --min-version 6.5.0 --group profile     # aísla el lote nuevo
report-story-craft --min-version 0 --include-unversioned --group approach   # incluye Bottom-Up
```

El CSV lleva **una fila por historia y 39 columnas**: identidad y ejes (`approach`, `story`,
`run_id`, `narrative_profile`, `generator_version`, `pipeline_version`, `status`, `model`,
`warnings`, `created_at`, `updated_at`, `duration_seconds`), artesanía recalculada
(`prose_paragraphs`, `prose_sentences`, `prose_words`, `dash_paragraphs`, `quoted_paragraphs`,
`dialogue_paragraphs`, `dialogue_ratio`, `words_per_sentence`, `words_per_paragraph`), lo que el run
registró (`has_story_metrics`, `metrics_words`, `metrics_chapters`, `metrics_events`,
`chapter_bodies_recovered`), el plan y sus artefactos vecinos (`plan_chapters`, `plan_events`,
`plan_dependencies`, `characters`, `world_objects`, `review_notes`, `review_strengths`,
`constraint_checks`) y el consumo del modelo (`llm_calls`, `llm_failed_calls`, `llm_total_tokens`,
`llm_total_wait_seconds`, `blueprint_macroplot`). La clave única es `story`, la ruta relativa: hay
`story.md` anidados cuyo `run_id` se repite. El CSV no se versiona; el comando lo regenera.

## Evolución por versión del generador

Medianas de las historias `completed`, y el contador de historias sin una sola marca de diálogo.

| Versión | n | % párrafos con diálogo | palabras/frase | palabras/párrafo | palabras | sin diálogo |
| --- | --- | --- | --- | --- | --- | --- |
| 6.0.0 | 9 | 21 % | 22,2 | 70,9 | 1641 | 2 |
| 6.1.0 | 20 | 29 % | 26,4 | 91,1 | 2845 | 2 |
| 6.2.0 | 4 | 41 % | 24,4 | 68,5 | 3519 | 0 |
| 6.3.0 | 29 | 32 % | 27,5 | 84,8 | 3495 | 3 |
| 6.4.1 | 1 | 38 % | 20,5 | 61,5 | 1968 | 0 |
| **6.5.0** | **9** | **44 %** | **22,8** | **68,9** | **4157** | **0** |
| Total 6.x | 72 | 33 % | 25,4 | 79,7 | 3069 | 7 |

El rango es tan informativo como la mediana: en 6.1.0 la proporción de diálogo va de 0 % a 54 % y
las palabras por párrafo de 57 a **195**. La dispersión, no el centro, es el problema.

## Por perfil narrativo

| Perfil | n | % diálogo | palabras/frase | palabras/párrafo | palabras | sin diálogo |
| --- | --- | --- | --- | --- | --- | --- |
| Esencial | 25 | 21 % | 22,9 | 76,9 | 1932 | 4 |
| Desarrollada | 19 | 41 % | 24,7 | 74,1 | 3336 | 0 |
| Expansiva | 28 | 31 % | 28,8 | 91,8 | 3859 | 3 |

**Esencial dramatiza la mitad que Desarrollada.** No es sólo que sea más corta: escribe menos
escena por párrafo escrito. Expansiva, la más larga, es también la de frases y párrafos más
grandes: crece engordando el bloque, no añadiendo escena.

## La matriz 6.5.0: nueve historias con Gemini real

Catálogos 4 (drama), 6 (ciencia ficción) y 7 (misterio) de
[prompts_top_down.md](prompts_top_down.md), por los tres perfiles, en serie, con `--no-audio` y
`--profile` explícito. Las nueve terminaron `completed` al primer intento, sin llamadas fallidas y
sin ningún `PLOT_VALIDATION_FAILED`.

| Run | Cat. | Perfil | Cap. | Ev. | Palabras | Párr. | % diálogo | p/frase | p/párrafo | Llamadas | Tokens | Segundos |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `20260913-172347-la-ultima-funcion` | 4 | Esencial | 3 | 6 | 2501 | 36 | 47 % | 20,0 | 68,9 | 16 | 82 927 | 135 |
| `20260913-172607-la-ultima-funcion-en-el-rex` | 4 | Desarrollada | 4 | 8 | 4732 | 73 | 45 % | 18,8 | 64,5 | 15 | 91 890 | 119 |
| `20260913-172813-la-ultima-funcion` | 4 | Expansiva | 5 | 10 | 6697 | 97 | 44 % | 22,8 | 68,7 | 16 | 129 468 | 152 |
| `20260913-173051-el-dominio-de-las-garras-y-las-torres` | 6 | Esencial | 3 | 6 | 2155 | 24 | 21 % | 28,3 | 88,5 | 16 | 81 115 | 100 |
| `20260913-173236-la-era-de-la-garra-y-la-pluma` | 6 | Desarrollada | 4 | 8 | 3352 | 46 | 41 % | 25,4 | 72,2 | 15 | 90 955 | 81 |
| `20260913-173401-el-dominio-de-la-sangre-antigua` | 6 | Expansiva | 5 | 10 | 4194 | 44 | 30 % | 30,3 | 94,5 | 16 | 104 849 | 157 |
| `20260913-173656-la-falsificacion-de-la-aurora` | 7 | Esencial | 3 | 6 | 3370 | 62 | 52 % | 20,6 | 53,9 | 14 | 70 975 | 123 |
| `20260913-173917-el-reflejo-oculto` | 7 | Desarrollada | 4 | 8 | 4794 | 92 | 53 % | 20,3 | 51,8 | 17 | 120 778 | 122 |
| `20260913-174125-la-falsificacion-de-la-aurora` | 7 | Expansiva | 5 | 12 | 5183 | 71 | 44 % | 24,9 | 72,6 | 17 | 124 821 | 126 |

Coste total: **142 llamadas, 0 fallidas, 897 778 tokens y 18,6 minutos** de reloj. Una sola
advertencia en todo el lote (`20260913-173917-el-reflejo-oculto`), y las nueve con
`chapter_bodies_recovered` en verdadero.

Lo que la matriz enseña, y que la tabla por versión no puede: **el contenido manda tanto como el
perfil.** El catálogo 7 (misterio, equipo de cuatro especialistas) da 44-53 % de diálogo y el
catálogo 4 (drama familiar) 44-47 %, mientras el catálogo 6 (dinosaurios, sin personajes humanos
que conversen) baja a 21-41 % con los mismos perfiles y la misma versión. Del perfil no sale una
regla monotónica, pero sí un patrón: **Expansiva es la que menos dramatiza** en los catálogos 4 y
7 y la de párrafos más largos en el 6 y el 7, y el peor caso del lote es la Esencial del catálogo
6, con 21 % de diálogo y 88,5 palabras por párrafo.

## Las ocho historias sin una sola marca de diálogo

| Run | Versión | Perfil | palabras/párrafo | palabras/frase |
| --- | --- | --- | --- | --- |
| `20260901-050219-el-ingenio-del-guerrero-y-la-bestia` | 6.0.0 | Esencial | 76,4 | 22,2 |
| `20260901-051008-el-viejo-y-la-marea` | 6.0.0 | Esencial | 89,0 | 22,3 |
| `20260903-172904-el-dominio-del-mesozoico` | 6.1.0 | Expansiva | **195,1** | 37,3 |
| `20260903-212721-la-era-de-las-escamas-pensantes` | 6.1.0 | Esencial | 131,0 | 30,2 |
| `20260907-020201-el-legado-de-las-escamas` | 6.3.0 | Esencial | 120,0 | 29,1 |
| `20260908-020751-el-guardian-del-ultimo-faro` | 6.3.0 | Esencial | 150,3 | 26,2 |
| `20260911-162223-las-cenizas-del-juramento` | 6.3.0 | Expansiva | 118,2 | 32,4 |
| `20260911-174447-la-sombra-del-volcan` | 6.3.0 | Expansiva | 150,4 | 31,3 |

Seis de las ocho superan las 118 palabras por párrafo, frente a la mediana de 79,7 del corpus: **la
historia sin diálogo y el párrafo-bloque son el mismo síntoma**. Cuatro de los cinco párrafos más
largos del corpus pertenecen a historias con 0 % o menos del 20 % de diálogo. Una de las ocho,
`20260908-020751-el-guardian-del-ultimo-faro`, está `running` para siempre: entra en el CSV y no en
las medianas.

## Avisos de lectura

- **`prose_words` no es `words`.** `words` cuenta el documento entero, encabezados incluidos;
  `prose_words` sólo los párrafos que las cifras describen. Difieren siempre.
- **El diálogo con acotación infla las frases.** `—¿Y ahora? —preguntó ella.` son dos frases para el
  segmentador. Un pipeline que dramatice más bajará `words_per_sentence` por dos causas distintas,
  así que esa cifra no se celebra nunca sin mirar `dialogue_ratio` al lado. La señal primaria es la
  proporción de diálogo.
- **La comparación entre versiones está confundida por el contenido.** Cada versión se probó con
  prompts distintos; la 6.5.0 es la primera que incluye un catálogo de drama. Su 44 % no mide una
  mejora del pipeline: mide su propia mezcla de prompts. Para atribuir un cambio al generador hay
  que repetir **estos nueve prompts**, que es exactamente para lo que existe esta línea base.
- **`duration_seconds` es tiempo de pared** entre la primera y la última escritura de
  `metadata.json`, no latencia del modelo. El `duration_seconds` de `llm_usage.json` mide otra cosa
  y tiene ficha propia en el `TODO.md`.
- **La cobertura no es tasa de éxito.** Un run que falló antes de escribir `story.md` no aparece
  aquí en absoluto; el corpus de artesanía es, por definición, el de historias escritas.
- **Las comillas son señal débil**, y `dialogue_ratio` las incluye. Cuando importe la ratio
  estricta, se calcula con `dash_paragraphs`.
- **`craft_audit.json`, `craft_contract.json` y `craft/variants/`** aparecen en dos runs de agosto de
  una arquitectura abandonada. No tienen ninguna relación con `asg_core.craft` ni con este informe.

## Qué se decide con esto

El crítico dramático **no** recibe todavía estas cifras. La decisión es deliberada: las nueve
historias de 6.5.0 son una línea base limpia, generada sin tocar ningún prompt, contra la que medir
la intervención. Cambiar la métrica y el prompt en la misma tanda habría hecho imposible saber a
cuál atribuir la diferencia. `profiles.py` documenta por qué un número dentro de un prompt gana a
los demás números del sistema, así que la evidencia que reciba el crítico será cualitativa.

El trabajo que abre esta medición está fichado en el `TODO.md`: enriquecer la escena en el prompt
del escritor y dar la artesanía al crítico como evidencia cualitativa; acotar el párrafo-bloque;
revisar si el contrato de Esencial paga su economía en escena; y completar las variantes por perfil
del catálogo de prompts, porque hoy sólo los catálogos 4, 6 y 7 las tienen.
