# Roadmap de redacción de la tesis

Partes de la tesis en el orden en que se escriben, una por sesión, con la skill `write_thesis`
(`/write_thesis` o `/write_thesis R03`). El LaTeX vive en [tesis/](tesis/) (plantilla oficial de
MatCom, `github.com/matcom/thesis`) y se compila con `latexmk` dentro de esa carpeta. Es la fase
P10 de [planning/roadmap.md](../planning/roadmap.md).

Referencias de forma: la presentación «Estructura de una tesis» de la facultad y la tesis de
Roger Fuentes ([docs/Roger Fuentes Rodríguez.pdf](../docs/)). El estilo de escritura está en
[.claude/skills/write_thesis/estilo.md](../.claude/skills/write_thesis/estilo.md).

## Estado

- **Siguiente:** R07 · Capítulo 5 (b), **bloqueada** hasta cerrar P07, P08 y P09 en
  `planning/roadmap.md` (el 2026-11-01 la siguiente tarea allí es P07.1). R08–R11 dependen de R07
  o de R08, así que no hay otra parte que se pueda escribir antes.
- **Extensión acumulada:** 38,4 de 50 cuartillas (sin figuras, tablas, anexos ni bibliografía).
- **Hechas:**
  - R00 · portada sin marcadores: título provisional «Generación narrativa bidireccional:
    planificación *Top-Down* y emergencia *Bottom-Up*» (traducción del nombre del repo), Josue
    Rolando Naranjo Sieiro, un solo tutor («Tutor:», etiqueta nueva `\advisorlabel` en la
    clase), noviembre de 2026 y enlace al repo partido en dos líneas; índice con Introducción,
    los cinco capítulos, Conclusiones y Recomendaciones. 1 pág., 0 \todo
  - R01 · estado del arte en seis secciones (dirigida por la trama, simulación de personajes y
    paradoja narrativa, híbridos, consistencia y personajes, evaluación en cuatro subsecciones,
    posición del autor); `Bibliography.bib` con las 51 entradas citadas (37 de la planilla, 14
    verificadas en la web el 2026-11-01); `uhthesis.cls` sin las redefiniciones autor-año de
    `\cite`, que quitaban los corchetes. 8 págs. (2–9), 0 \todo
  - R02 · introducción sin secciones: contexto, antecedentes (Fuentes Rodríguez), problemática
    en tres viñetas con cita, actualidad, novedad (generador + metodología, T10), importancia,
    problema como pregunta, objeto, campo, Objetivo General, cinco Objetivos Específicos (uno
    por capítulo) e hipótesis H1–H3, con las correspondencias en comentarios LaTeX; sin
    referencias nuevas. La sigla LLMs pasa a definirse aquí y el Cap. 1 pierde su definición y
    el «con los mismos tutores» (Roger tuvo dos; esta tesis, uno). 4 págs. (1–4), 0 \todo
  - R03 · capítulo 2 en seis secciones (arquitectura con figura TikZ y «el modelo propone, el
    código decide»; plan como grafo acíclico con orden $\sigma$ y contrato de promesas; guion;
    función: reparto y compuertas, actores con memoria propia y la fórmula de recuperación,
    director; narrador; mecanismos opcionales con la Tabla 2.1 de estados congelados); una
    referencia nueva, `piad2026` (B02, ensayo «Promises, Progress, and Payoffs»); `tikz` y
    `array` en el preámbulo. 9 págs. (13–21; ≈ 8 sin figura ni tabla, 12,5 % sobre el
    presupuesto), 0 \todo
  - R04 · capítulo 3 en siete secciones (las tres evaluaciones con figura TikZ; rasgos con cita
    literal verificada por párrafo, catálogo por capas, lista núcleo de 24 en la Tabla 3.1 y
    validación del extractor con sus umbrales; análisis horizontal con la matriz emparejada y la
    regla de ruido; pares a ciegas con las preguntas exactas en la Tabla 3.2, conjunto,
    asignación, parada y Bradley-Terry; juez como Bradley-Terry con covariables, validado por
    historia y por familia; ranking y diez mejores, con T11 como trabajo futuro; amenazas). La
    rúbrica (`piad2026`, §3.8) se comprobó en el PDF; sin referencias nuevas. 10 págs. (22–31;
    ≈ 7,5 sin figura ni tablas, ≈ 7 % sobre el presupuesto), 0 \todo
  - R05 · capítulo 4 en seis secciones, con el estado del repositorio el 2026-11-01 (organización
    en cinco paquetes con la Tabla 4.1 de versiones y líneas, la restricción de que la evaluación
    no importa el generador, cada mecanismo con su módulo puro y la Tabla 4.2 de comandos;
    proveedores, validación con Pydantic, perfiles de temperatura y cuota en tres capas con la
    cifra de los 503; artefactos atómicos, `--plan-from`/`--narrate-from` y contratos versionados;
    extractor, estudio, Bradley-Terry, juez y matriz; bot y StageCraft; 907 pruebas y las cuatro
    de contrato con su nombre, y los límites de la reproducibilidad). Seis referencias nuevas de
    software verificadas en la web (`pydantic2026`, `google2026`, `virtanen2020`, `pedregosa2011`,
    `ptb2026`, `fastapi2026`); comando `\codigo` en `Thesis.tex` para partir rutas y nombres de
    pruebas solo tras `/ . _ -`. Studio es 0.3.0 desde el 2026-10-27: corregido el «Estado actual»
    de `planning/roadmap.md`, que decía 0.2.2. 7 págs. (32–38; ≈ 5 sin tablas, ≈ 2 % sobre el
    presupuesto), 0 \todo
  - R06 · capítulo 5 (a) en cuatro secciones: condiciones y corpus (los dos modelos; inventario del
    2026-10-28, 331 y 116 elegibles, y `asg-corpus` repetido el 2026-11-01, 346 y 130, 26 de 7.22;
    las 9 líneas base); validaciones del generador (modo fijo y adaptativo de 7.5 y los 62
    contextos para H2; Tabla 5.1 con P02.1 y P02.2; P02.3; la validación de 7.22 con 3 de 6
    *beats* forzados; lectura exploratoria de H3); validación del extractor (tres desviaciones,
    Tabla 5.2 por rasgo, regla de salida y huella del catálogo), y análisis horizontal (Tabla 5.3
    de coste desde los `llm_calls.jsonl`, 14 de 35 unidades, las dos irregularidades de la matriz,
    Tabla 5.4 del piloto con n = 1, sin resultados interpretables y la parte mecánica de H1 sin
    datos suficientes). Tablas a mano con su fuente en comentarios; sin referencias nuevas.
    9 págs. (39–47; ≈ 5,9 sin tablas, ≈ 18 % sobre el presupuesto), 0 \todo

## Reglas comunes

- Una parte por sesión y un commit por parte: `TESIS R03: <resumen>`, en `main`, sin
  `Co-Authored-By` y sin push.
- Toda parte se contrasta con las reglas del tutor T1–T11 (`planning/decisions.md` §1). T11 (el
  juez como función objetivo y el algoritmo genético) solo aparece como trabajo futuro.
- Ninguna cifra sin fuente del repo con fecha y alcance. Si falta, va `\todo{dato: …}`.
- Ninguna referencia inventada: sale de `packages/evaluation/planilla/bibliografia.csv` o se
  verifica en la web (DOI, ACL Anthology, arXiv) antes de entrar a `tesis/Bibliography.bib`.
  Las marcadas «revisar cifras en el PDF» no aportan cifras sin comprobarlas.
- Presupuesto: ≤ 50 cuartillas en total y la introducción ≤ 10. Si una parte se pasa más de un
  20 % de su presupuesto, se avisa antes del commit.
- **Todavía no:** agradecimientos, dedicatoria y opinión del tutor (comentados en
  `tesis/Thesis.tex`).

## Índice y presupuesto

| Orden en la tesis | Parte | Archivo | Págs. |
|---|---|---|---|
| Resumen / *Abstract* | R10 | `FrontMatter/Abstract.tex` | 1 + 1 |
| Introducción | R02 | `MainMatter/Introduction.tex` | 5 |
| 1. Estado del arte | R01 | `MainMatter/Background.tex` | 9 |
| 2. Generador híbrido de historias | R03 | `MainMatter/Generator.tex` | 8 |
| 3. Metodología de evaluación | R04 | `MainMatter/Evaluation.tex` | 7 |
| 4. Implementación | R05 | `MainMatter/Implementation.tex` | 5 |
| 5. Experimentos y resultados | R06 + R07 | `MainMatter/Experiments.tex` | 5 + 4 |
| Conclusiones | R08 | `BackMatter/Conclusions.tex` | 2 |
| Recomendaciones | R09 | `BackMatter/Recomendations.tex` | 1 |
| Bibliografía, glosario, anexos | R11 | `Bibliography.bib`, `BackMatter/` | — |

Total previsto: ≈ 46 cuartillas. Páginas de Roger por tipo de parte (páginas del PDF): resumen
6–7, introducción 11–17, estado del arte 18–34, modelo 35–44, implementación 45–50,
experimentos 51–69, conclusiones 70–71, recomendaciones 72.

**Pregunta abierta:** la presentación pide Arial 12 e interlineado 1,5; la plantilla oficial (y
Roger) usan Computer Modern 12 pt e interlineado simple. Se mantiene la plantilla hasta que
Josue o el tutor digan otra cosa.

---

## Tarjetas

### R00 · Portada e índice

- **Archivo:** `tesis/Thesis.tex`.
- **Lee:** este roadmap.
- **Contenido:** preguntar a Josue el título (provisional vale), su nombre completo, si hay un
  segundo tutor, el mes y año de entrega y el enlace al repositorio; sustituir los marcadores
  rojos de la portada.
- **Hecho cuando:** `latexmk` compila, la portada no tiene marcadores rojos y el índice muestra
  Introducción, los cinco capítulos, Conclusiones y Recomendaciones.

### R01 · Capítulo 1: Estado del arte

- **Archivo:** `tesis/MainMatter/Background.tex` (+ `Bibliography.bib`).
- **Lee:** `docs/resumen.md` (Tesis en tres frases, contexto), `planilla/bibliografia.csv`
  (columnas `que_aporta` y `que_se_adopta`), `packages/evaluation/METODOLOGIA.md` §1–§2.
- **Roger:** págs. 18–34 (apertura con definiciones, secciones por familia de enfoques).
- **Contenido:**
  1. Apertura: conceptos de historia, trama, discurso, evento, plan; anuncio de secciones.
  2. Generación dirigida por la trama (*Top-Down*): estructuras (Propp, Freytag), grafos y
     planificación (TALE-SPIN, planificación de tramas, DOC B39, Agents' Room B07,
     prefiguración y pago B34).
  3. Generación por simulación de personajes (*Bottom-Up*) y la **paradoja narrativa**.
  4. Sistemas híbridos: Façade, Thespian, Virtual Storyteller, Sabre; su versión con LLM:
     Generative Agents (B31), StoryBox, WSE-bench, SOTOPIA (B33), FANToM (B32).
  5. Consistencia y personajes en LLM: ConStory-Bench (B25), Finding Flawed Fictions (B26),
     CharacterEval (B28), TimeChara (B30), PersonaGym (B29).
  6. Evaluación de historias: criterios humanos (HANNA B04, TTCW B06, B35, B36), escalas y sus
     problemas (B11, B12–B16), comparaciones por pares y Elo (B17, B18), jueces LLM y sus sesgos
     (B05, B10, B21–B24, B09), métricas automáticas (B38, B43); la tesis de Roger (B03) como
     antecedente directo.
  7. Posición del autor: qué se adopta y qué hueco queda (planificación + simulación con
     memoria propia; evaluación por recuentos con cita y pares a ciegas).
- **Extensión:** 9 págs.
- **Depende de:** R00.
- **Hecho cuando:** cada sistema o resultado citado tiene entrada verificada en el `.bib`;
  compila sin citas indefinidas.

### R02 · Introducción

- **Archivo:** `tesis/MainMatter/Introduction.tex`.
- **Lee:** `docs/resumen.md`, `planning/decisions.md` §1, el capítulo 1 ya escrito.
- **Roger:** págs. 11–17.
- **Contenido** (en este orden, como pide la presentación): contexto; antecedentes del
  problema; breve presentación de la problemática (paradoja narrativa, pérdida de compromisos y
  riqueza en LLM, evaluación poco fiable); actualidad; novedad científica; importancia teórica
  y práctica; **diseño teórico**: problema científico (como pregunta), objeto de estudio, campo
  de acción, **Objetivo General**, **Objetivos Específicos** (en infinitivo, más que generales),
  **hipótesis** H1–H3 de `docs/resumen.md` en forma enunciativa y verificable; estructura del
  documento por capítulos.
- **Extensión:** 5 págs. (≤ 10).
- **Depende de:** R01.
- **Hecho cuando:** cada objetivo específico apunta a un capítulo, y cada hipótesis, a un
  experimento de R06 o R07 (dejar la correspondencia escrita como comentario LaTeX).
- **Nota de R01:** el capítulo 1 define historia, discurso, evento, trama, plan,
  *Top-Down*/*Bottom-Up* y la paradoja narrativa (en sentido amplio: Louchart y Aylett más la
  tensión trama–personaje de Riedl y Young). La sigla «*Large Language Models* (LLMs)» se define
  en la Sección 1.1; como la introducción va antes, si la usa, se define allí y se quita la
  definición del capítulo 1. El hueco que se declara está al final de `sec:posicion`.

### R03 · Capítulo 2: Generador híbrido de historias

- **Archivo:** `tesis/MainMatter/Generator.tex`.
- **Lee:** `docs/resumen.md` (Plan validado, Guion, Función simulada, Inventario),
  `docs/architecture/generation.md`, `docs/architecture/simulation.md`.
- **Roger:** págs. 35–44 (arquitectura primero con una figura, luego cada componente).
- **Contenido:** arquitectura en una figura (petición → plan → guion → función → log → narrador
  → historia; Top-Down, Bottom-Up y discurso); plan como DAG validado y perfiles; promesas
  apertura–progreso–pago; guion teatral (nativo y adaptado); función simulada: actores que no
  ven el guion, memoria propia (público, susurro, pensamiento) y recuperación determinista,
  compuertas de conocimiento, director que sugiere y cierra beats, modo fijo y adaptativo;
  narrador que cura sin inventar y sus puntos de vista; inventario («el modelo propone, el
  código decide»). Cada mecanismo, con la hipótesis que justifica su complejidad (H3).
- **Extensión:** 8 págs. Conceptual: sin nombres de módulos salvo cuando aclaran.
- **Depende de:** R02.
- **Hecho cuando:** figura de arquitectura incluida y citada; ningún mecanismo apagado por
  defecto se presenta como parte del predeterminado congelado (`generator-frozen`, 7.22).
- **Nota de R01:** la posición del autor (`sec:posicion`) ya promete de dónde sale cada pieza;
  conviene citarlas al describirlas: plan validado (`yang2023`, `huot2025`), promesas codificadas
  (`yun2026`), memoria propia sin almacén común (`park2023`), director que sugiere
  (`theune2003`), personajes limitados a lo que creen (`ware2021`), narrador separado de los
  agentes (`chen2026a`) y «cada mecanismo se gana su complejidad» (`chen2026b`, WSE-bench).
- **Nota de R02:** la introducción presenta en negrita la **función** (los personajes
  representan el plan escena a escena, como en el teatro); aquí se precisa sin volver a
  resaltarla. H3 quedó así: «más mecanismos no implican una historia mejor: que un mecanismo
  mejore medidas de la prosa no basta para que los lectores prefieran a ciegas las historias que
  lo usan». Los mecanismos apagados en el predeterminado congelado (brazos de 7.17, inventario,
  narración por selección) se presentan como aplicación de H3, no como parte del predeterminado.

### R04 · Capítulo 3: Metodología de evaluación

- **Archivo:** `tesis/MainMatter/Evaluation.tex`.
- **Lee:** `packages/evaluation/METODOLOGIA.md`, `planning/decisions.md` §1–§2,
  `docs/architecture/evaluation.md`, `packages/evaluation/planilla/rasgos.csv` (solo lectura).
- **Roger:** págs. 51–54 (métodos de evaluación), para contrastar: él usó escala 1–10; aquí no.
- **Contenido:** las dos evaluaciones y la intermedia (T1); la máquina cuenta, no juzga:
  rasgos contables con cita literal verificada por código (T2, T3), capas y lista núcleo; la
  tablita por historia y el análisis horizontal (T4); evaluación humana por pares a ciegas con
  tres criterios (T5, T7) y línea base de un solo prompt (T6); el juez como regresión de rasgos
  a rankings, validado fuera de muestra (T8); ranking del corpus y las diez mejores (T9);
  amenazas a la validez (jueces LLM que se prefieren, ruido entre corridas).
- **Extensión:** 7 págs.
- **Depende de:** R02.
- **Hecho cuando:** cada regla T1–T9 aparece y se cita su motivación en la literatura de R01;
  ninguna escala numérica se presenta como juicio de calidad.
- **Nota de R01:** la motivación ya está en la Sección 1.5 (`sec:criterios-humanos`,
  `sec:escalas-pares`, `sec:jueces-llm`, `sec:metricas-automaticas`): remitir con `\ref` en vez de
  repetirla. Faltan en el `.bib` B01 (audio), B02 (rúbrica Sanderson), B08, B37 y B41, si se
  citan.
- **Nota de R03:** B02 ya está en el `.bib` como `piad2026` (el documento completo; la rúbrica
  *Flash Fiction* es su §3.8): citarla con esa clave. Términos fijados en el capítulo 2, para no
  redefinirlos: **registro** de la función (el *log*), **suceso del mundo**, **contrato de
  promesas** (el *ledger*), **compuertas de conocimiento**, **brazo de control**, «configuración
  congelada» (2026-10-28). Las medidas de diagnóstico de la función se presentaron como
  comprobaciones del mecanismo, no de calidad (remitiendo a este capítulo).

### R05 · Capítulo 4: Implementación

- **Archivo:** `tesis/MainMatter/Implementation.tex`.
- **Lee:** `AGENTS.md`, `docs/architecture/runtime.md`, `docs/architecture/interfaces.md`,
  los `README.md` de `packages/*` y `apps/*`.
- **Roger:** págs. 45–50.
- **Contenido:** monorepo y dependencias entre paquetes (`core ← evaluation ← stagecraft ←
  telegram, studio`); proveedores, cuotas y reintentos; artefactos persistidos y contratos
  versionados (`pipeline_version`); comandos `asg-*` principales; bot de Telegram y
  `asg-studio` para la lectura a ciegas; pruebas y reproducibilidad.
- **Extensión:** 5 págs. Aquí sí van nombres de código en `\texttt{}`.
- **Depende de:** R03, R04.
- **Hecho cuando:** las versiones citadas coinciden con el «Estado actual» de
  `planning/roadmap.md` en la fecha de escritura, y esa fecha consta en el texto.
- **Nota de R03:** el capítulo 2 es conceptual y no nombra módulos ni pruebas; aquí se puede
  dar a cada mecanismo su módulo (`planning/graph.py`, `stage/memory.py`, `stage/voices.py`…) y
  nombrar las pruebas de contrato que allí solo se mencionan (los actores no ven el plan, el
  inventario apagado no cambia nada, la visión no toca lo anterior a la narración). La
  Figura 2.1 (`Graphics/arquitectura.tex`, TikZ) puede reutilizarse con `\ref{fig:arquitectura}`.
- **Nota de R04:** el capítulo 3 tampoco nombra código ni modelos. Aquí van: el extractor y su
  modelo (`features.py`: `locate` comprueba la cita en su párrafo, una reparación y si no
  `failed`), la planilla (`rasgos.csv`, `criterios_humanos.csv`), `study.py` (asignación
  perezosa, esquema 10), `preferences.py` (Bradley-Terry de cresta, *bootstrap* por lectores) y
  `judge.py` (`LogisticRegression` de scikit-learn, `C = 1`, sin intercepto, `MODEL_VERSION` 2):
  la mención a scikit-learn de T8 quedó para este capítulo. La Figura 3.1
  (`Graphics/evaluacion.tex`) se puede citar con `\ref{fig:evaluacion}`.

### R06 · Capítulo 5 (a): Experimentos con datos cerrados

- **Archivo:** `tesis/MainMatter/Experiments.tex` (primeras secciones).
- **Lee:** `docs/resumen.md` (validaciones 7.5, P02.1, P02.2, P02.3, 7.22, líneas base),
  `METODOLOGIA.md` §3 («Validación del extractor») y §10, «Hechas» de P03–P05 en
  `planning/roadmap.md`, salidas en `Evaluations/validacion-extractor/` y
  `Evaluations/horizontal/`.
- **Roger:** págs. 54–69.
- **Contenido:** corpus y elegibilidad; validaciones del generador antes de congelarlo;
  validación del extractor (precisión, test-retest, cobertura sin medir); análisis horizontal
  parcial (14 de 35 unidades, cerrado por cuota el 2026-10-30). Las tablas, de P09 si ya
  existen (`redaccion/tablas/`, `redaccion/figuras/`); si no, a mano con su fuente en un
  comentario.
- **Extensión:** 5 págs.
- **Depende de:** R04.
- **Hecho cuando:** cada tabla lleva n, fecha y alcance; los resultados nulos o incompletos se
  dicen como tales.
- **Nota de R02:** aquí se contrastan H1 (celdas M03 frente a su base M01, 14 de 35 unidades) y
  H3 (P02.1, empate 2–2–1 en 5 pares, y P02.2, A 3 – B 1 en 4 pares, con un solo lector: evidencia
  exploratoria). La auditoría de 62 contextos de 7.5 es evidencia indirecta de H2: muestra el
  aislamiento, no que mejore las escenas. Correspondencias en comentarios de `Introduction.tex`.
- **Nota de R03:** el capítulo 2 (`sec:opcionales`, `sec:director`) ya adelanta, en una frase
  cada una y remitiendo aquí, P02.1 (2–2–1 en 5 pares), P02.2 (A 3 – B 1 en 4 pares), los 3 de 6
  *beats* forzados de la validación de 7.22 (5 de 10 en una anterior) y que el guion adaptado,
  la guía compositiva, el inventario, las cláusulas por tipo y el modo adaptativo quedaron sin
  comparación a ciegas. Aquí van con su detalle y su alcance; la Tabla 2.1 (`tab:mecanismos`)
  da los estados congelados y no hace falta repetirlos.
- **Nota de R04:** el capítulo 3 da el diseño y remite aquí lo medido. Los umbrales de la
  validación del extractor (`sec:validacion-extractor`), la matriz y la regla de ruido
  (`sec:horizontal`) ya están escritos: citarlos con `\ref`, no repetirlos. También quedó dicho
  que la lista provisional de 28 rasgos (2026-10-28) quedó en 24 (2026-10-30). El capítulo 3 no
  da cifras del corpus ni de elegibilidad: van aquí, con su fecha.
- **Nota de R05:** el capítulo 4 (`sec:proveedores`) ya explica la cuota (≈ 500 peticiones
  diarias por modelo, inferida; los 503 del 2026-10-13) y termina diciendo que «acotó lo que se
  pudo generar»: aquí van las cifras de coste por formato y por unidad de la matriz, con su fecha,
  y el cierre de P05 por cuota, sin volver a explicar el mecanismo. `asg-matrix`,
  `asg-report-features`, `asg-corpus` y `--plan-from`/`--narrate-from` están descritos en
  `sec:herramientas` y `sec:artefactos`: citarlos con `\ref`. Los modelos se nombraron como «la
  configuración de ejemplo del repositorio» (`gemini-3.5-flash-lite` principal y
  `gemini-3.1-flash-lite` para los actores); si un experimento usó otros, decirlo aquí con su
  fuente (`models_used` de `metadata.json`).

### R07 · Capítulo 5 (b): Estudio humano, juez y ranking

- **Archivo:** `tesis/MainMatter/Experiments.tex` (secciones finales).
- **Lee:** bloques P06–P09 de `planning/roadmap.md`, `decisions.md` §2 (juez para P08),
  salidas de `asg-rank` y de P09.
- **Contenido:** estudio humano (diseño de P06 y lo que realmente se recogió: piloto y votos
  disponibles); juez (`fitted` o `insufficient`, ambos válidos); ranking y las diez mejores;
  respuesta a H1–H3 con lo que los datos permiten.
- **Extensión:** 4 págs.
- **Depende de:** **P07, P08 y P09 cerradas** en `planning/roadmap.md`. Si no lo están, la skill
  para.
- **Hecho cuando:** cada hipótesis tiene una respuesta (confirmada, refutada o sin datos
  suficientes) con su evidencia.
- **Nota de R02:** H2 (memoria propia frente a compartida) no tiene experimento: EXP-2 pasó a
  idea-bank el 2026-10-30. Josue decidió el 2026-11-01 mantenerla en la introducción y
  responderla aquí «sin datos suficientes», como limitación declarada. H1 se completa con los
  pares narrativo–simulado del piloto, si los hay.
- **Nota de R04:** `sec:conjunto` y `sec:agregacion` describen el estudio de P06.1 tal como se
  diseñó y dicen que «el estudio completo no llegó a ejecutarse»; aquí va lo recogido. El juez
  de `sec:juez` es el de `MODEL_VERSION` 2: una historia con un núcleo `failed` no entra. Si
  P07.1 (c) adopta imputar los fallidos, corregir esa frase en el capítulo 3. Las
  perturbaciones se describen como «escenas barajadas o sin su desenlace» (P07.4), y las diez
  mejores salen del ranking auxiliar (`top_ten` de `rank_features`).
- **Nota de R06:** el párrafo de apertura del capítulo nombra el estudio humano, el juez, el
  ranking y la respuesta a las hipótesis sin `\ref` (comentario `% R07` en `Experiments.tex`):
  añadir allí las referencias a las secciones nuevas. R06 termina con un párrafo de transición; el
  cierre del capítulo va al final de R07. Lo que ya quedó dicho, para citarlo con `\ref` y no
  repetirlo: H1 mecánica «sin datos suficientes» (`sec:resultados-horizontal`, `tab:piloto`), H3
  exploratoria con un solo lector (`sec:validaciones`, `tab:lecturas`), H2 con solo la evidencia
  indirecta de los 62 contextos (`sec:val-modo`). El corpus elegible del 2026-11-01 es de 130
  ejecuciones (26 de 7.22); si P08 hace otro inventario, dar su fecha. Las tablas de R06 se
  hicieron a mano (`tab:lecturas`, `tab:extractor`, `tab:coste`, `tab:piloto`); si P09 genera
  `redaccion/tablas/`, sustituirlas o cotejarlas. Las extracciones de la validación del extractor
  tienen la huella anterior del catálogo: el juez de P07 no puede usarlas sin repetirlas.

### R08 · Conclusiones

- **Archivo:** `tesis/BackMatter/Conclusions.tex`.
- **Lee:** la tesis escrita; `planning/decisions.md` §1 (T10, T11).
- **Roger:** págs. 70–71 (para la forma; evitar su tono grandilocuente).
- **Contenido:** una conclusión por objetivo específico, en el mismo orden; aportaciones (T10:
  el generador más la metodología de evaluación); limitaciones y dificultades (cuota, estudio
  sin la muestra prevista, extractor parcial); T11 como trabajo futuro.
- **Extensión:** 2 págs.
- **Depende de:** R07.
- **Hecho cuando:** ninguna conclusión afirma algo que no esté demostrado en el cuerpo.
- **Nota de R02:** los cinco objetivos específicos, en orden: analizar el estado del arte;
  diseñar el generador híbrido; diseñar la metodología de evaluación; implementar el generador y
  las herramientas de evaluación; evaluar experimentalmente el generador.
- **Nota de R05:** la conclusión del cuarto objetivo se apoya en el capítulo 4: cinco paquetes
  con dependencias en un sentido (la evaluación no importa el generador), validadores puros, 907
  pruebas el 2026-11-01 (2 omitidas, las de la API real) y cuatro pruebas de contrato nombradas en
  `sec:pruebas`. La cuota aparece como restricción práctica, no como fallo de diseño.
- **Nota de R06:** limitaciones ya escritas en el capítulo 5 para recogerlas sin ampliarlas: la
  validación del extractor es provisional (cobertura sin medir, veredictos de precisión propuestos
  por Claude y aceptados por el autor, 6 de 12 extracciones incompletas); el análisis horizontal se
  quedó en 14 de 35 unidades y sin resultados interpretables; la función fuerza la mitad de los
  *beats* (3 de 6 en 7.22). Las lecturas de P02.1 y P02.2 son de un solo lector, el autor.

### R09 · Recomendaciones

- **Archivo:** `tesis/BackMatter/Recomendations.tex`.
- **Lee:** `planning/future/idea-bank.md` (solo los titulares), R08.
- **Roger:** pág. 72.
- **Contenido:** qué ampliar (completar la matriz, estudio con más lectores, árbitro de acciones
  físicas…), aplicación a otras esferas, condiciones para usar los resultados.
- **Nota de R04:** el capítulo 3 (`sec:ranking`) promete que las Recomendaciones recogen el juez
  como función objetivo (generar muchas y quedarse la mejor) y el algoritmo genético (T11).
- **Nota de R06:** cifras ya escritas para «completar la matriz»: faltan 21 unidades, unas 300–450
  llamadas al modelo principal (≈ un día de cuota) más la extracción de toda la matriz y de las 9
  líneas base. También pendiente en el capítulo 5: medir la cobertura del extractor, repetir las
  extracciones incompletas y repetir la muestra con la huella vigente del catálogo.
- **Extensión:** 1 pág.
- **Depende de:** R08.

### R10 · Resumen y *Abstract*

- **Archivo:** `tesis/FrontMatter/Abstract.tex`.
- **Roger:** págs. 6–7 (forma; sus cifras sin respaldo, no).
- **Contenido:** ≈ 250 palabras: objeto, objetivos, método, resultados más relevantes y
  aportaciones; no un índice de capítulos. Después, la misma versión en inglés.
- **Depende de:** R08.
- **Hecho cuando:** 200–300 palabras cada uno y las cifras coinciden con el capítulo 5.
- **Nota de R06:** cifras de la primera mitad del capítulo 5 que el resumen podría usar: 130
  ejecuciones elegibles el 2026-11-01; extractor validado sobre 12 historias (provisional); matriz
  horizontal en 14 de 35 unidades, sin resultados interpretables.

### R11 · Bibliografía, glosario y anexos

- **Archivos:** `tesis/Bibliography.bib`, `tesis/BackMatter/`.
- **Contenido:** depurar el `.bib` (sin entradas sin citar, datos completos); glosario con
  `nomencl` si hace falta (`\makenomenclature` ya está activo); anexos numerados y referenciados
  desde el texto (catálogo de rasgos, prompts de la matriz, ejemplos de historias).
- **Nota de R01:** la bibliografía da 5 cajas desbordadas porque parte los títulos en inglés con
  los patrones del español; probar `langid = {english}` en esas entradas (con `english` cargado
  en `babel`) o `autolang`.
- **Nota de R05:** siguen siendo esas 5 cajas; las seis entradas de software de R05 no añaden
  ninguna. `virtanen2020` lleva «and others» (solo se verificó el primer autor; completar la lista
  desde el DOI si se quiere). Para nombres de código largos en anexos, usar `\codigo{…}` (definido
  en `Thesis.tex`), que solo parte tras `/ . _ -`.
- **Nota de R06:** la Tabla 5.2 (`tab:extractor`) nombra los rasgos sin su id (R01, X10…), como la
  Tabla 3.1; el anexo del catálogo debería dar la correspondencia nombre ↔ id. R06 no añade cajas
  desbordadas.
- **Depende de:** R08.

### R12 · Repaso de coherencia

- **Contenido:** objetivos ↔ conclusiones, hipótesis ↔ resultados, cifras ↔ fuentes, extensión
  total ≤ 50, `\todo` restantes, avisos de compilación (referencias indefinidas, cajas
  desbordadas). Lista de pendientes para Josue antes de **H5** (borrador al tutor).
- **Depende de:** R10, R11.
