# Banco de ideas

Lo que no entra en ninguna fase de la tesis. Nada de aquí se ejecuta sin pasar antes por
una tarjeta del [roadmap](../roadmap.md). Una idea no lleva ID; lo recibe al subir. Las fichas
con ID conservan el del antiguo `TODO.md`.

## Trabajo posterior a la tesis (el tutor)

- **El juez como función objetivo** [06:21–07:43]: generar N historias con distintas
  combinaciones de parámetros y devolver la mejor; después, un algoritmo genético sobre los
  parámetros. Es la recomendación para el trabajo siguiente, no parte de esta tesis.

## Ingeniería aplazada

### ING-3 · Dividir `pipeline.py`

*Área:* ingeniería · *Cuota:* sin cuota · *Depende de:* —

- **Síntoma.**
  - `pipeline.py` tiene 671 líneas; las etapas ya viven en mixins de planificación, escritura,
    guion, actuación y narración. La telemetría está en `runtime/reporting.py`.
  - Los mixins comparten estado mediante `self`; el repositorio opcional sigue obligando a
    comprobar su presencia antes de utilizarlo.
  - Falta convertir las etapas en unidades con estado y pruebas propios.
- **Qué hacer.**
  - El bucle de reintento ya está en `writing/revision_loop.py` (7.18). El del narrador
    (`stage/stages.py`) se queda aparte a propósito: tiene revisión editorial, candidato
    reservado y su propia severidad.
  - Al final, convertir las etapas en clases con estado propio, que es lo que elimina los asserts.
  - No hacerlo de paso dentro de otro cambio.
- **Hecho cuando.**
  - Plan, borrador, revisión y función son unidades con test propio.
  - El estado deja de pasarse como parámetros posicionales.
  - Los artefactos generados no cambian.

### ING-5 · CI, tipos y dependencias

*Área:* ingeniería · *Cuota:* sin cuota · *Depende de:* —

- **Síntoma.**
  - **CI solo prueba una plataforma.** Corre solo en `windows-latest` con Python 3.12. Desde
    7.21.2 el mínimo declarado es 3.12, así que CI sí cubre la versión mínima, pero 3.15,
    que `setup.ps1` acepta y tiene sus propias restricciones, no se comprueba nunca.
  - **Sin tipos ni cobertura en CI.** No hay paso de comprobación de tipos ni informe de
    cobertura en el workflow de calidad.
  - **Dependencias.** Las cotas internas se alinearon en 7.21.2 con la minor vigente de cada
    paquete; nada comprueba que no vuelvan a quedarse atrás.
- **Qué hacer.**
  - Ampliar la matriz de CI a Linux y a 3.15, con su archivo de restricciones.
  - Añadir pyright o mypy, empezando por `core`.
  - Informar de la cobertura, sin umbral al principio.
  - Un test o un paso de CI que falle si una cota interna queda por debajo de la minor instalada.
- **Hecho cuando.** CI prueba las dos versiones de Python que `setup.ps1` acepta, y una
  dependencia interna demasiado vieja falla al instalar, no al importar.

### ING-10 · Lo que queda por trocear de la función

*Área:* ingeniería · *Cuota:* sin cuota · *Depende de:* ING-3

- **Síntoma.** La limpieza de 7.21.2 partió los dos módulos de esquemas en paquetes por
  secciones y dejó identificados los que siguen siendo demasiado grandes:
  - `stage/engine.py`, 1650 líneas: `PerformanceEngine` tiene 41 métodos, un `__init__` de
    107 líneas y un `_play_turn` de 175. Los métodos agrupan solos en turno, mundo y
    arbitraje, derivación de hechos, memoria y estancamiento.
  - `runtime/provider.py`, 1354 líneas: contexto y errores, los dos clientes concretos y la
    composición (`RoutedProvider`, `FailoverProvider`, la factoría) no se tocan entre sí.
  - `stage/stages.py`, 1076 líneas: `_perform_play` ocupa 248 y el bloque de revisión del
    futuro, otras 200 seguidas.
  - `BeatCheckDraft.world_effect` no lo lee nadie, pero viaja al director como JSON schema:
    retirarlo cambia lo que ve el modelo.
- **Qué hacer.** Trocear por esas costuras, con el patrón de mixins que el paquete ya usa, y
  retirar el campo muerto en la misma subida de `PIPELINE_VERSION`. Después de ING-3, no a la
  vez: las etapas con estado propio cambian dónde cae cada corte.
- **Hecho cuando.** Ningún módulo de la función pasa de 700 líneas, los artefactos no cambian
  salvo el campo retirado, y el par medido lo confirma.

## Ideas sin decidir


### La temperatura no llega a `gemini-3.5-flash-lite`

Desde el 21 de julio de 2026, Gemini acepta `temperature`, `top_p` y `top_k` en 3.5 Flash-Lite y
3.6 Flash, pero los ignora. Google anuncia un 400 en generaciones futuras y pide llevar el control
a la instrucción de sistema. Así que los cinco perfiles de `_DEFAULT_GENERATION_PROFILES` no hacen
nada en el modelo principal: el actor no escribe a 0,9 ni el crítico a 0,2. `gemini-3.1-flash-lite`
sí los respeta, lo que es otra diferencia entre una función con `GEMINI_STAGE_MODEL` y una sin él.
Decidir si los runs 7.x anteriores a esa fecha se separan de los posteriores, y qué hacer con los
perfiles antes de que un modelo nuevo los rechace.

### Caché de contexto en la función

Una función gasta en torno al 63 % de los tokens de un run simulado: los actores el 41 %, las
reflexiones el 11–12 % y las lecturas del director el 8–9 %. El actor lee unos 19 tokens por cada
token que escribe, y su prefijo de sistema no cambia en toda la obra, pero `cached_tokens` es 0 en
todos los runs. Medir cuánto ahorraría la caché de contexto de Gemini antes de comprometerse. Parte
de esa proporción era la memoria sin tope, ya acotada en 7.2.0: medir sobre un run 7.2.

### Memoria completa frente a memoria recuperada

Las funciones 7.0 y 7.1 recuperaban toda la memoria y aun así repetían. Con el tope de 7.2, los
dos runs Esenciales no perdieron el hilo, pero una obra Expansiva podría. La literatura de contexto largo (*Lost in the Middle*, *Context
Rot*) predice que la memoria entera empeora al crecer, pero en una obra de seis escenas puede no
notarse. Medir las dos cosas sobre el mismo plan antes de fijar el tope para siempre.

### Muestras de voz en el dossier

Si MED-7 confirma que las voces se parecen, probar a dar a cada actor una o dos frases de muestra de
su voz, ajenas a la trama, escritas por el casting. Riesgo: que el actor las repita, por el mismo
autorrefuerzo que obligó a dejar de recuperar el material propio del actor en 7.2.0.

### El estatus como eje del dossier

Johnstone (*Impro*, 1979) describe cada interacción como una transacción de estatus. Un estatus por
relación en el dossier daría al director una palanca distinta de «confiesa», y al actor más tácticas
que gritar.

### Tensión medida por predicción de finales

La métrica 100-Endings (Sui et al. 2026) mide la tensión como la frecuencia con que un modelo falla
al predecir el final, frase a frase, y ordena bien lo que los jueces LLM ordenan mal. Cuesta muchas
llamadas por historia: evaluar si compensa como complemento de la lectura a ciegas.

### Un árbitro de acciones físicas más allá de los objetos

Desde 7.6 los objetos se arbitran en código: quién lleva qué, quién lo ve y qué puede hacer con
ello. Lo que sigue sin comprobarse es el resto de lo físico: «aparta a Mara de un empujón» no
tiene consecuencias, y una puerta se abre porque alguien lo dice. El Game Master de Concordia
juzga la plausibilidad de cualquier acción, no solo las que tocan un objeto. Solo compensa si la
lectura encuentra incoherencias físicas que el inventario no cubre; medirlo es EXP-6.

### Unificar los contratos de prompt duplicados

- **La regla del evento, tres veces.** «Cada evento debe cambiar conflicto, conocimiento,
  relaciones, recursos, riesgos o consecuencias» está escrita casi literal dos veces en
  `planning/profiles.py` y una en `planning/repair.py`.
- **Los perfiles, a mano.** `agents/analyst.py` repite en `PROFILE_ALIASES` y `EXPLICIT_PROFILE`
  los nombres de perfil que ya dan `NarrativeProfile` y `PROFILE_LABELS`.
- **Detección desigual.** El bot no tiene selector de perfil y depende del analista o del `.env`.

### Grafo explícito de lugares

Comparar el modelo actual de `locations` y `location_id` con relaciones y transiciones
explícitas. Documentar el efecto en errores de continuidad y en coste, y adoptarlo solo si mejora
algo medible.

### Audio a varias voces

Tanto `performance.json` como `script.json` distinguen quién dice cada réplica, pero
`create_story_audio` sintetiza el documento entero con una sola voz. Una voz por personaje saldría
casi gratis de cualquiera de los dos. Cambia el contrato de `audio.json`, así que merece su propia
medición.

### Rechazar las peticiones que no son historias

«dame una receta para hacer chesscake» produjo una historia, y el prompt «G» produjo tres runs.
El analista podría negarse con un mensaje claro, sobre todo en el bot.
