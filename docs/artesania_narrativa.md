# Artesanía narrativa del corpus Top-Down

**Medido el 2026-09-17 con `report-story-craft` de `asg-evaluation` 0.4.0 sobre las 125 historias
de `Stories/`.** Entran en el informe las **95 con versión de generador o de pipeline 6 o
posterior**; de ellas **93 están `completed`** y son las que forman las medianas. Las nueve
historias de la versión 6.5.0 se generaron el 13 de septiembre con Gemini real
(`gemini-3.5-flash-lite`) como línea base de la artesanía, y las nueve de **6.6.0** repiten esos
mismos nueve prompts sobre la versión que interviene en el prompt del Drafter: son el par con el que
se mide la intervención. **Doce historias más, del 17 de septiembre, replican esa matriz sobre la
misma versión sin tocar nada**: son el suelo de ruido con el que hay que leer cualquier diferencia
de este documento, y están en «El lote del 2026-09-17».

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
`story.md`, así que las 65 historias 6.0-6.4.1 son comparables con las de 6.5.0 y 6.6.0.

Desde **6.6.0** (`pipeline_version: 6.2`) hay un segundo artefacto, `craft_evidence.json`, que no
mide: **traduce**. `asg_top_down.craft_evidence` aplica tres umbrales a cada capítulo del borrador
—sin diálogo, diálogo escaso, párrafo-bloque— y escribe el veredicto en palabras, más el bloque
exacto que se le entregó al crítico dramático. Los umbrales viven en código y ninguna cifra entra
en el prompt. Un capítulo sin carencias no genera línea, y un borrador sano deja el bloque vacío:
el crítico sólo recibe texto cuando hay algo que señalar.

## Cómo reproducir esta medición

```powershell
report-story-craft --min-version 6 --csv docs\artesania_narrativa_corpus.csv --group all
report-story-craft --min-version 6.6.0 --group profile     # aísla la versión, no el lote
report-story-craft --min-version 0 --include-unversioned --group approach   # incluye Bottom-Up
```

**Un lote no es una versión.** Los dos lotes de 6.6.0 comparten versión de generador y de pipeline,
así que `--min-version` no los separa: el lote se aísla filtrando en el CSV las filas cuyo `run_id`
empieza por su fecha (`20260913-22` y `20260917-`). Cualquier medición que compare réplicas tiene
que cortar por ahí.

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
| 6.5.0 | 9 | 44 % | 22,8 | 68,9 | 4157 | 0 |
| **6.6.0** | **21** | **47 %** | **26,8** | **34,6** | **3469** | **0** |
| Total 6.x | 93 | 39 % | 25,4 | 74,2 | 3101 | 7 |

El rango es tan informativo como la mediana: en 6.1.0 la proporción de diálogo va de 0 % a 54 % y
las palabras por párrafo de 57 a **195**. La dispersión, no el centro, es el problema.

## Por perfil narrativo

| Perfil | n | % diálogo | palabras/frase | palabras/párrafo | palabras | sin diálogo |
| --- | --- | --- | --- | --- | --- | --- |
| Esencial | 32 | 32 % | 22,9 | 70,6 | 1836 | 4 |
| Desarrollada | 26 | 42 % | 24,1 | 64,3 | 3402 | 0 |
| Expansiva | 35 | 34 % | 28,9 | 81,0 | 3950 | 3 |

Sobre el corpus entero, Esencial sigue diez puntos por debajo de Desarrollada. **Esa lectura es
falsa**, y la sección «Dónde nace el defecto» la desmonta: la brecha viene del contenido y de la
versión con que se probó cada perfil, no del contrato del perfil. Cuando los tres corren sobre los
mismos prompts, la diferencia desaparece. La propia tabla lo enseña al crecer: los doce runs del
17-09 añadieron cuatro Esenciales generadas con la versión nueva y su mediana saltó de 21 % a 32 %
sin que el contrato del perfil cambiara una palabra. Esta tabla se conserva porque es el agregado
del corpus histórico, no porque el perfil explique lo que muestra.

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

## Dónde nace el defecto

Las tablas anteriores dicen *cuánto* diálogo hay. Esta sección responde *dónde* se pierde, medido
sobre el mismo corpus el 2026-09-13.

### La revisión no toca la artesanía: todo se decide en el borrador

Comparando `draft.md` contra `story.md` con `craft_metrics` en las 72 historias 6.x completadas, el
cambio mediano de `dialogue_ratio` es **+0,000**, la peor caída **−0,03** y la mejor subida +0,15.
Las **siete historias con cero diálogo ya tenían cero diálogo en su borrador**: ninguna perdió la
escena al revisarse, porque nunca la tuvo. La etapa de revisión es neutra en artesanía.

La consecuencia es de diseño: el problema pertenece al Drafter y al crítico que juzga su borrador,
no al Writer. Reescribir con notas no crea escena que el borrador no trajo.

### El diálogo decae con la posición del capítulo

Sobre los 36 capítulos de la matriz 6.5.0, agrupados por posición dentro de su historia:

| Posición del capítulo | n | % diálogo (mediana) |
| --- | --- | --- |
| Primero | 9 | 50 % |
| Intermedios | 18 | 41 % |
| Último | 9 | 36 % |

Y las palabras por párrafo se mueven en sentido contrario: los capítulos finales de
`20260913-173401-el-dominio-de-la-sangre-antigua` llegan a 176 y 217 frente a las 69 de su primer
capítulo, con 0 % de diálogo en los dos. El pipeline **empieza dramatizando y termina resumiendo**,
es decir colapsa exactamente donde está el desenlace.

### Diálogo y párrafo-bloque son la misma señal

Sobre las 72 historias, la correlación entre `dialogue_ratio` y `words_per_paragraph` es
**−0,63 de Pearson y −0,64 de Spearman**. No son dos defectos que coincidan: son dos vistas del
mismo. Un párrafo se alarga porque nadie habla dentro de él. Esto cierra la pregunta que el
`TODO.md` dejaba abierta —si el corte de párrafo arrastra al diálogo o es independiente— y evita
una intervención separada para la longitud de párrafo.

Para calibrar umbrales sobre esa distribución: la mediana de `dialogue_ratio` es 0,33, el primer
cuartil 0,19 y el décimo percentil 0,07; el 28 % de las historias queda en 0,20 o menos. En
`words_per_paragraph` la mediana es 80 y el percentil 90 está en 120.

### La brecha del perfil Esencial no sobrevive a la línea base

El corpus completo daba 21 % a Esencial frente a 41 % a Desarrollada, y de ahí salió la sospecha de
que `PROFILE_GUIDANCE` pagaba su economía en escena. **No se sostiene.** En la matriz 6.5.0, donde
los tres perfiles corren sobre los mismos tres catálogos, las medianas son **47 %, 45 % y 44 %**
para Esencial, Desarrollada y Expansiva. Y por capítulo, sobre los 36 de la matriz: 43 %, 43 % y
38 %.

La brecha del corpus completo era confusión por contenido y por versión —Esencial se usó más en los
lotes antiguos y en el catálogo de dinosaurios, que es el que menos conversa—, no un defecto del
contrato del perfil. El perfil no es la variable que hay que tocar.

### El crítico es ciego a la artesanía

De las **129 notas** repartidas en 87 `review.json`, sólo **4** son de categoría `voice_style`. En
las siete historias sin una sola marca de diálogo el crítico levantó nueve notas —cinco de `pacing`,
dos de `language`, una de `setup_payoff` y una de `dramatic_structure`— y **ninguna** sobre escena o
voz. El crítico lee el borrador completo y no dispone de ninguna evidencia de si lo que lee es
escena o sinopsis, así que no lo señala.

## La matriz 6.6.0: la intervención medida contra su línea base

Los mismos nueve prompts, el mismo modelo y el mismo procedimiento que la matriz 6.5.0, sobre la
versión que pide escena en el prompt del Drafter y da al crítico la evidencia cualitativa. Las nueve
terminaron `completed` al primer intento, ninguna con advertencias —la línea base tenía una— y las
nueve con `chapter_bodies_recovered` en verdadero.

| Run | Cat. | Perfil | Cap. | Ev. | Palabras | Párr. | % diálogo | p/frase | p/párrafo | Llamadas | Tokens | Segundos |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `20260913-220124-la-ultima-funcion-del-circulo` | 4 | Esencial | 2 | 5 | 1778 | 63 | 41 % | 23,2 | 28,0 | 13 | 63 186 | 115 |
| `20260913-220343-la-ultima-funcion` | 4 | Desarrollada | 4 | 8 | 3962 | 106 | 48 % | 28,7 | 37,1 | 15 | 83 152 | 167 |
| `20260913-220639-la-ultima-funcion-del-circulo` | 4 | Expansiva | 5 | 10 | 5284 | 133 | 47 % | 29,0 | 39,5 | 16 | 114 701 | 261 |
| `20260913-221104-la-era-de-las-garras-y-el-acero` | 6 | Esencial | 3 | 6 | 1715 | 50 | 42 % | 31,8 | 33,7 | 15 | 70 466 | 127 |
| `20260913-221341-la-era-de-la-escama` | 6 | Desarrollada | 4 | 8 | 2798 | 62 | 47 % | 28,3 | 44,8 | 15 | 76 991 | 184 |
| `20260913-221653-el-legado-de-la-escama-eterna` | 6 | Expansiva | 5 | 10 | 3991 | 106 | 45 % | 29,7 | 37,3 | 17 | 116 511 | 262 |
| `20260913-222125-la-falsificacion-de-la-aurora` | 7 | Esencial | 3 | 6 | 1866 | 71 | 44 % | 21,6 | 25,9 | 15 | 68 677 | 165 |
| `20260913-222416-el-falso-lienzo-de-la-medianoche` | 7 | Desarrollada | 4 | 8 | 3496 | 112 | 49 % | 22,7 | 31,0 | 17 | 113 081 | 266 |
| `20260913-222932-el-refugio-de-los-pigmentos` | 7 | Expansiva | 5 | 10 | 4462 | 128 | 55 % | 29,8 | 34,6 | 20 | 153 503 | 337 |

Coste: **143 llamadas y 860 268 tokens**, frente a 142 y 897 778 de la línea base. La intervención
es gratis en consumo.

### Qué cambió, prompt a prompt idéntico

| Cifra | 6.5.0 | 6.6.0 |
| --- | --- | --- |
| % diálogo (mediana) | 44 % | **47 %** |
| % diálogo (mínimo) | **21 %** | **41 %** |
| % diálogo (máximo) | 53 % | 55 % |
| palabras/párrafo (mediana) | 68,9 | **34,6** |
| palabras/párrafo (máximo) | 94,5 | 44,8 |
| Capítulos con cero diálogo | 3 | **0** |
| Advertencias del lote | 1 | 0 |

**Lo que se movió no es la mediana, es el suelo.** La mediana sube tres puntos, que por sí solos no
probarían nada con n=9; el mínimo salta de 21 % a 41 %, el rango se estrecha de 32 puntos a 14, y
los tres capítulos que no tenían una sola marca de diálogo desaparecen. La dispersión era el
problema declarado en este documento desde la primera medición, y es lo que se corrigió.

Por catálogo, la mejora se concentra donde estaba el defecto. El catálogo 6 —dinosaurios, sin
personajes humanos que conversen, el peor de la línea base— pasa de 21/41/30 % a **42/47/45 %** en
los tres perfiles. Los catálogos 4 y 7, que ya dramatizaban, se mueven poco: no había nada que
arreglar en ellos.

### El decaimiento hacia el desenlace se reduce, no desaparece

| Posición del capítulo | 6.5.0 | 6.6.0 |
| --- | --- | --- |
| Primero | 50 % | 50 % |
| Intermedios | 41 % | **48 %** |
| Último | 36 % | 39 % |

La cláusula «un desenlace es una escena, no un resumen de cómo acabaron las cosas» recuperó sobre
todo los capítulos **intermedios**, que eran los que más cedían. El último capítulo sigue siendo el
que menos dramatiza, con una brecha de 11 puntos frente al primero donde antes había 14. El
desenlace sigue tirando hacia el resumen: el efecto es real pero parcial, y queda ficha abierta.

### Lo que hay que mirar con desconfianza

- **El canal de evidencia no se ejercitó ni una vez.** Los nueve borradores salieron por encima de
  los tres umbrales, así que `craft_evidence.json` quedó vacío en los nueve y el crítico nunca vio
  el bloque `CRAFT OBSERVATIONS`. **Toda la mejora medida viene del prompt del Drafter.** El canal
  es hoy una red de seguridad sin evidencia propia de que funcione; para probarlo hace falta un caso
  que dispare los umbrales, y el lote del 17-09 muestra que provocarlo con estos umbrales y este
  Drafter no es posible.
- **Las historias son un 17 % más cortas** (mediana de 4157 a 3469 palabras) con el mismo número de
  capítulos y eventos planificados, salvo el catálogo 4 Esencial, que planificó 2 capítulos y 5
  eventos en lugar de 3 y 6, dentro de su banda. La escena dramatizada gasta menos palabras por
  evento que la sinopsis densa; no hay evento perdido, pero conviene vigilarlo.
- **Las palabras por frase suben** de 22,8 a 28,7, en contra de lo que hace el diálogo con acotación.
  La causa es la estructura nueva: un párrafo es ahora un beat, a menudo una sola frase larga, donde
  antes un bloque empaquetaba varias frases cortas. Es otra razón para no leer nunca
  `words_per_sentence` sin `dialogue_ratio` al lado.
- **La crítica no se degradó.** 21 notas frente a 17, ninguna de `causal_continuity` ni de
  `world_continuity` en ninguno de los dos lotes; el aumento está en `agency` (de 1 a 5). Las dos
  `failed_calls` del lote nuevo son reintentos transitorios que después tuvieron éxito, contados
  como dice la ficha del `TODO.md` sobre esa cifra.

## El lote del 2026-09-17: la réplica que da el suelo de ruido

Doce historias más, **sin ninguna intervención**: el mismo generador 6.6.0, el mismo modelo y el
mismo procedimiento que la matriz anterior, cuatro días después. Nueve repiten exactamente los nueve
prompts de las dos matrices; las tres restantes repiten el catálogo 6 en los tres perfiles, buscando
el caso que dispare los umbrales de `craft_evidence`. La única variable del lote es la ejecución, de
modo que todo lo que separe estas doce de las nueve del 13-09 es variabilidad del modelo, no del
pipeline. Eso es justo lo que faltaba: hasta ahora cada versión tenía una sola muestra y ninguna
forma de saber cuánto vale una diferencia de tres puntos.

Las doce terminaron `completed` al primer intento, sin advertencias y con `chapter_bodies_recovered`
en verdadero.

| Run | Cat. | Perfil | Cap. | Ev. | Palabras | Párr. | % diálogo | p/frase | p/párrafo | Llamadas | Tokens | Segundos |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `20260917-043723-la-ultima-funcion-del-rex` | 4 | Esencial | 3 | 6 | 2610 | 69 | 54 % | 23,3 | 37,5 | 15 | 84 114 | 148 |
| `20260917-043959-la-ultima-funcion-del-ideal` | 4 | Desarrollada | 4 | 9 | 3882 | 134 | 40 % | 22,9 | 28,8 | 16 | 113 609 | 179 |
| `20260917-044306-la-ultima-funcion-del-circulo` | 4 | Expansiva | 5 | 13 | 4879 | 149 | 52 % | 20,3 | 32,5 | 16 | 116 053 | 124 |
| `20260917-044517-la-era-de-las-garras-y-las-plumas` | 6 | Esencial | 2 | 5 | 1645 | 42 | 45 % | 31,3 | 38,7 | 13 | 53 913 | 72 |
| `20260917-045757-la-era-de-las-grandes-ideas` | 6 | Esencial * | 3 | 6 | 1400 | 58 | 40 % | 22,3 | 23,8 | 13 | 55 255 | 74 |
| `20260917-044654-la-era-de-las-escamas-pensantes` | 6 | Desarrollada | 4 | 8 | 2774 | 69 | 62 % | 28,5 | 39,7 | 16 | 86 516 | 134 |
| `20260917-045917-la-era-de-las-escamas-pensantes` | 6 | Desarrollada * | 4 | 8 | 2986 | 81 | 52 % | 23,1 | 36,5 | 15 | 83 374 | 108 |
| `20260917-044916-el-dominio-de-la-fronda` | 6 | Expansiva | 5 | 10 | 3798 | 99 | 53 % | 28,8 | 38,0 | 16 | 99 212 | 110 |
| `20260917-050112-el-imperio-de-la-escama-eterna` | 6 | Expansiva * | 5 | 10 | 3730 | 115 | 43 % | 26,8 | 32,2 | 16 | 108 373 | 136 |
| `20260917-045114-la-falsificacion-de-medianoche` | 7 | Esencial | 2 | 4 | 1813 | 67 | 37 % | 20,0 | 26,8 | 13 | 55 860 | 91 |
| `20260917-045255-el-secreto-del-falso-lazaro` | 7 | Desarrollada | 4 | 9 | 3648 | 113 | 44 % | 21,7 | 32,0 | 13 | 78 539 | 106 |
| `20260917-045448-la-ultima-pincelada` | 7 | Expansiva | 5 | 12 | 4349 | 94 | 67 % | 30,9 | 46,0 | 18 | 129 514 | 181 |

Las filas marcadas con `*` son las tres repeticiones del catálogo 6. Coste: **180 llamadas, 1
fallida —un reintento transitorio que después tuvo éxito—, 1 064 332 tokens y 24,4 minutos** de
reloj.

### Lo que cuesta una réplica: unos diez puntos

Los mismos nueve prompts, la misma versión, cuatro días de diferencia:

| Cat. | Perfil | 6.5.0 | 6.6.0 (13-09) | 6.6.0 (17-09) | Δ entre réplicas |
| --- | --- | --- | --- | --- | --- |
| 4 | Esencial | 47 % | 41 % | 54 % | +12 |
| 4 | Desarrollada | 45 % | 48 % | 40 % | −9 |
| 4 | Expansiva | 44 % | 47 % | 52 % | +5 |
| 6 | Esencial | 21 % | 42 % | 45 % | +3 |
| 6 | Desarrollada | 41 % | 47 % | 62 % | +16 |
| 6 | Expansiva | 30 % | 45 % | 53 % | +7 |
| 7 | Esencial | 52 % | 44 % | 37 % | −6 |
| 7 | Desarrollada | 53 % | 49 % | 44 % | −5 |
| 7 | Expansiva | 44 % | 55 % | 67 % | +12 |

El cambio mediano entre las dos corridas de la misma versión es **+5 puntos**, con desviación de 8,8
y un rango de −9 a +16. Y las tres repeticiones internas del catálogo 6, donde coinciden prompt,
versión, modelo y hasta la hora, se separan igual:

| Catálogo 6, mismo prompt dos veces | % diálogo | Δ | palabras | Δ |
| --- | --- | --- | --- | --- |
| Esencial | 45 % y 40 % | 6 | 1645 y 1400 | 245 |
| Desarrollada | 62 % y 52 % | 10 | 2774 y 2986 | 212 |
| Expansiva | 53 % y 43 % | 9 | 3798 y 3730 | 68 |

La consecuencia es metodológica y vale para todo el documento: **una sola historia dice poco, y con
n=9 una diferencia de medianas por debajo de unos cinco puntos no se puede leer.** El +3 de 6.5.0 a
6.6.0 caía dentro de ese margen —la sección anterior ya avisaba de que por sí solo no probaría
nada—, y ahora está medido contra qué se comparaba.

### El suelo sube; la dispersión no se estrecha

| Lote | n | mediana | IQR | rango | desv. |
| --- | --- | --- | --- | --- | --- |
| 6.5.0 | 9 | 44 % | 35-49 (14 pts) | 21-53 (32 pts) | 10,4 |
| 6.6.0 (13-09) | 9 | 47 % | 43-49 (6 pts) | 41-55 (14 pts) | 4,3 |
| 6.6.0 (17-09) | 12 | 48 % | 41-53 (13 pts) | 37-67 (30 pts) | 9,2 |

La afirmación de la sección anterior —«el rango se estrecha de 32 puntos a 14»— **no sobrevive a la
réplica**: con doce historias vuelve a 30 puntos y la desviación regresa al orden de la línea base.
Lo que se estrechó el 13-09 fue suerte de muestra pequeña. Lo que sí replica es el otro extremo, que
es el que la intervención perseguía:

| Cifra | 6.5.0 | 6.6.0 (13-09) | 6.6.0 (17-09) |
| --- | --- | --- | --- |
| Mínimo por historia | 21 % | 41 % | 37 % |
| Máximo por historia | 53 % | 55 % | 67 % |
| Mínimo por capítulo | 0,00 | 0,33 | 0,28 |
| Capítulos sin una sola marca | 3 | 0 | 0 |
| Palabras/párrafo, peor capítulo | 217,0 | 52,7 | 64,6 |

**El suelo subió y se quedó arriba; el techo subió también, y por eso el rango no se cierra.**
Veintiuna historias consecutivas de 6.6.0 sin un solo capítulo mudo, frente a tres capítulos mudos
en nueve de la línea base, y ningún párrafo-bloque en ninguna de las dos réplicas. Ésa es la parte
de la intervención que la variabilidad del modelo no se lleva por delante.

### El decaimiento hacia el desenlace replica

| Posición del capítulo | 13-09 (n=9) | 17-09 (n=12) | 6.6.0 completo (n=21) |
| --- | --- | --- | --- |
| Primero | 50 % | 50 % | 50 % |
| Intermedios | 48 % | 56 % | 50 % |
| Último | 39 % | 43 % | 41 % |

El último capítulo es el que menos dramatiza en los dos lotes, y lo es **en 13 de las 21 historias**
contadas una a una. Sobre la muestra doble la brecha contra el primer capítulo es de **9 puntos**.
El vaivén de los intermedios entre réplicas —48 % y 56 %— cabe holgadamente en el ruido que mide la
sección anterior; el signo de la brecha del último no cambia ni una sola vez. Ésta es la medida
previa contra la que habrá que juzgar la intervención sobre el desenlace: mover la mediana del
último capítulo menos de cinco puntos no significará nada, y la cifra que conviene vigilar es
cuántas historias dejan de tener su capítulo más mudo al final.

### El canal de evidencia no se puede ejercitar con estos umbrales

Cero de doce, otra vez, y **no por poco**. Sobre los 46 capítulos del lote:

| Umbral de `craft_evidence.py` | Lo peor del lote 17-09 | Lo peor de 6.5.0 |
| --- | --- | --- |
| `dialogue_ratio` menor que 0,20 | mínimo 0,28 | mínimo 0,00 |
| `words_per_paragraph` de 120 o más | máximo 64,6 | máximo 217,0 |

Ningún capítulo se queda cerca: el peor está a ocho centésimas del umbral de diálogo y a 55 palabras
del de párrafo-bloque. Los mismos umbrales sobre la línea base habrían disparado **siete veces** en
nueve historias. Están calibrados sobre el primer cuartil y el percentil 90 del corpus 6.x, es decir
sobre una distribución que incluye todo lo anterior a la intervención y que el Drafter **ya no
produce**.

La vía que proponía el `TODO.md` —provocar el caso con un prompt que tienda al resumen— ya se
intentó por donde parecía más prometedora: seis corridas del catálogo 6, el peor de la línea base,
dos por cada perfil. No basta, porque el prompt que resumía ya no resume. Con el Drafter actual el
canal sólo puede probarse recalibrando los umbrales sobre la distribución nueva, o construyendo el
borrador a mano en un test. Mientras tanto, 21 historias consecutivas dicen que la red de seguridad
nunca se ha tensado, y ésa es toda su evidencia disponible.

### Tamaño y planificación

La mediana de palabras del lote es 3317 frente a 3496 del anterior, dentro del ruido. Lo que sí se
mueve es el plan: el catálogo 4 Expansiva planificó **13 eventos** donde la réplica anterior puso 10,
el 7 Desarrollada 9 donde puso 8, y dos Esenciales se quedaron en 2 capítulos. Todo cae dentro de la
banda de su perfil y ninguna corrida disparó `PLOT_VALIDATION_FAILED`, pero conviene recordar que el
planificador no es más estable que la prosa: el conteo de eventos también es una variable aleatoria
dentro de su banda, no una constante del perfil.

## El canal de evidencia sí se tensó: el caso del 2026-09-20

La sección anterior cerraba diciendo que 21 historias consecutivas dejaban la red de seguridad sin
tensar. **Ya no es cierto.** Al crecer el corpus a 23 ejecuciones 6.6.0 terminadas, una de ellas
—`20260920-135822-el-computo-de-la-deriva`— disparó el canal por primera vez, y lo recorrió entero:

1. `craft_evidence.json` salió con bloque no vacío: `chapter_1`, con `dialogue_ratio` 0,1765,
   por debajo del umbral de 0,20. El veredicto fue `RARE_DIALOGUE`.
2. El crítico dramático recibió el bloque `CRAFT OBSERVATIONS` y reaccionó exactamente como pide
   su instrucción de sistema: dos notas sobre ese capítulo y sólo sobre ése, una `voice_style`
   («Stage the confrontation and initial discovery as a live spoken scene…») y una `pacing`.
3. El Writer reescribió el capítulo y el candidato se aceptó al primer intento: 424 → 589 palabras,
   `final_source` `revision` en `revision_report.json`.

O sea que el canal funciona de punta a punta en producción, no sólo en test. **Pero el lazo no se
cierra.** Tras la reescritura, el `dialogue_ratio` de `chapter_1` quedó en 0,1765, exactamente el
mismo, y las palabras por párrafo subieron de 24,9 a 34,7: las 165 palabras añadidas fueron
narración, no escena. `_writer_candidate_issue` acepta el candidato sin comprobar nunca que el
déficit que originó la nota se haya reparado. Queda como ficha abierta en el `TODO.md`.

### La recalibración: se mueve un umbral, no los dos

Medido sobre los **90 capítulos de las 23 ejecuciones 6.6.0 terminadas**, leyendo el
`chapter_metrics` que `story_metrics.json` guarda desde 6.5.0, contra los 36 capítulos de la línea
base:

| | 6.5.0 (36 cap.) | 6.6.0 (90 cap.) |
| --- | --- | --- |
| `dialogue_ratio` mínimo | 0,00 | 0,1765 |
| capítulos por debajo de 0,20 | 4 | **1** |
| capítulos sin una sola marca de diálogo | 3 | 0 |
| `words_per_paragraph` máximo | 217,0 | **64,64** |
| capítulos de 120 palabras por párrafo o más | 3 | **0** |

Los dos umbrales tienen diagnósticos opuestos, y por eso sólo se mueve uno:

- **`LOW_DIALOGUE_RATIO` se queda en 0,20.** Disparó 1 vez en 90 capítulos, sobre el mínimo real de
  la distribución. Eso es precisamente lo que debe hacer una red de seguridad, y el caso del 20-09
  lo demuestra.
- **`BLOCK_PARAGRAPH_WORDS` baja de 120 a 90.** El máximo observado en 6.6.0 es 64,64 y el p99 es
  55,9: el techo de 120 estaba a casi el doble de la distribución entera y no era alcanzable. A 90
  sigue quedando fuera de la prosa sana —no incordia— pero vuelve a ser alcanzable ante una
  regresión del tipo que producía 6.5.0.

El criterio que gobierna la decisión, y que conviene dejar escrito porque contradice la calibración
original: **un umbral puesto en un cuartil de la distribución sana dispara sobre un cuarto de los
capítulos sanos y deja de significar nada.** La calibración de 6.5.0 usaba el primer cuartil y el
percentil 90 del corpus 6.x; esa elección sólo tenía sentido mientras el corpus mezclaba prosa
anterior y posterior a la intervención. El umbral correcto de una red de seguridad va justo fuera de
la distribución sana, no dentro de ella.

El cambio va en `asg-top-down` **6.7.0**, así que las cifras de este documento anteriores a esa
versión se leen con el techo de 120 y las posteriores con el de 90.

## Avisos de lectura

- **`prose_words` no es `words`.** `words` cuenta el documento entero, encabezados incluidos;
  `prose_words` sólo los párrafos que las cifras describen. Difieren siempre.
- **El diálogo con acotación infla las frases.** `—¿Y ahora? —preguntó ella.` son dos frases para el
  segmentador. Un pipeline que dramatice más bajará `words_per_sentence` por dos causas distintas,
  así que esa cifra no se celebra nunca sin mirar `dialogue_ratio` al lado. La señal primaria es la
  proporción de diálogo.
- **La comparación entre versiones está confundida por el contenido.** Cada versión se probó con
  prompts distintos; la 6.5.0 es la primera que incluye un catálogo de drama. Su 44 % no mide una
  mejora del pipeline: mide su propia mezcla de prompts. El único par comparable de la tabla es
  **6.5.0 contra 6.6.0**, porque son los mismos nueve prompts sobre el mismo modelo; el resto de
  las filas no se comparan entre sí.
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

El crítico dramático **ya recibe** la artesanía, y el Drafter tiene contrato de escena. La
intervención se aplicó en 6.6.0 sobre la línea base limpia de 6.5.0, con los nueve mismos prompts,
y está medida más arriba: el suelo de diálogo sube de 21 % a 41 %, desaparecen los capítulos sin
una sola marca y el párrafo-bloque se reduce a la mitad, sin coste extra de tokens y sin notas de
continuidad nuevas.

La forma de la intervención respeta la regla que `profiles.py` documenta —un número dentro de un
prompt gana a los demás números del sistema—: los umbrales viven en `asg_top_down.craft_evidence`,
en código, y sólo su veredicto viaja, redactado en palabras. `craft_evidence.json` deja por escrito
en cada run qué vio exactamente el crítico, y el manifiesto lo cubre con su sha256.

Lo que esta medición deja abierto, releído tras la réplica del 17-09:

- **El canal de evidencia sigue sin probarse en vivo, y ya se sabe por qué.** Veintiuna historias
  consecutivas de 6.6.0 dejaron el bloque vacío, y el peor capítulo de las doce últimas está a ocho
  centésimas del umbral de diálogo y a 55 palabras del de párrafo-bloque. Los umbrales están
  calibrados sobre una distribución que el Drafter ya no produce: para ejercitarlos hay que
  recalibrarlos o construir el borrador a mano en un test, no generar más historias.
- **El último capítulo sigue dramatizando menos que el primero**, 9 puntos por debajo sobre las 21
  historias de 6.6.0, y es el más mudo en 13 de ellas. El decaimiento se redujo, no se cerró, y
  replica.
- **La dispersión no se corrigió.** El estrechamiento del rango que celebraba la matriz del 13-09 no
  aparece en la réplica; lo que la intervención sostiene es el suelo, no la varianza.
- **Completar las variantes por perfil del catálogo de prompts**, porque hoy sólo los catálogos 4,
  6 y 7 las tienen y la matriz no puede crecer sin ellas.
