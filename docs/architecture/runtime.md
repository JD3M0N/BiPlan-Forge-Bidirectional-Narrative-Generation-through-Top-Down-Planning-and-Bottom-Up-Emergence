# Ejecución, artefactos y proveedores

Referencia de contratos vigentes. Lee solo las secciones del subsistema que vayas a cambiar.
Las reglas generales están en [AGENTS.md](../../AGENTS.md).

## Top-Down: artefactos de un run

`ArtifactRepository` (`runtime/storage.py`) crea `Stories/Stagecraft/<AAAAMMDD-HHMMSS>-<slug>/` y
escribe todo de forma atómica. Serializa con `asg_core.artifact_json`, porque necesita el texto
exacto para el hash del manifiesto.

El run contiene:

- estado: `metadata.json` (estado, etapas completadas, warnings, error) y
  `pipeline_manifest.json` (sha256 y tamaño de cada artefacto);
- plan: `request.json`, `world.json`, `characters.json`, `story_plan.json`;
- promesas: `promise_ledger.json`, `promise_audit.json`;
- escritura: `chapters/`, `revisions/`, `draft.md`, `story.md`, `story.mp3`;
- medición: `story_metrics.json`, `llm_calls.jsonl` y `llm_usage.json`.

A esa lista, el guion y el simulado añaden los suyos.

- **Los artefactos guardan también los prompts.** `promise_ledger.json` guarda el contrato **y
  los bloques de prompt exactos** que se inyectaron (`chapter_blocks`, `critic_block`), igual que
  `craft_evidence.json`. Así un run terminado se audita sin volver a derivar qué se le dijo a
  cada agente.
- **`promise_audit.json`** cruza el contrato con los veredictos del crítico. Una promesa que el
  crítico no juzgó cuenta como `broken`, porque el silencio no es un aprobado.
- **`story_metrics.json`** registra tamaño y artesanía observados: palabras, capítulos, eventos,
  proporción de párrafos con diálogo, palabras por frase y por párrafo, también por capítulo.
  Ninguna de esas cifras viaja a ningún prompt: son observaciones, no objetivos.
  Los rasgos T de `asg-evaluation` las recalculan desde `story.md`, así que también miden los
  runs anteriores a 6.5.0, que no las traen.

`version.py` fija la versión del generador y `PIPELINE_VERSION` (7.22), y mantiene
`SUPPORTED_PIPELINE_VERSIONS` para leer los contratos anteriores desde 5.0. Los cambios de
cada contrato se consultan en el [changelog](../../packages/stagecraft/CHANGELOG.md).
`StoryRun` se niega a abrir un run incompleto o de una versión no soportada. Si cambias el
conjunto de artefactos o su significado, sube la versión en vez de romper los runs ya generados:
son datos de la tesis. Una limpieza que no toca artefactos sube solo el parche de
`__version__`, como 7.1.1.

Las ejecuciones anteriores al renombrado siguen en `Stories/Top-Down/` y se siguen leyendo.
`asg-recover --stories Stories/Top-Down` las recupera.

## Top-Down: proveedor y cuota

`runtime/provider.py` expone el `Protocol` `LanguageModelProvider` (`generate_structured` con
esquema Pydantic, y `generate_text`) e implementa `GeminiProvider`. Lo que importa al tocarlo:

- La temperatura sale de perfiles nombrados (`extraction`, `review`, `planning`, `prose`,
  `rewrite`), no de constantes sueltas en los agentes.
- `_gemini_response_schema` borra `additionalProperties` del esquema porque algunos modelos
  Gemini lo rechazan. Pydantic sigue siendo la autoridad local con `extra="forbid"`.
- `_safe_provider_error` clasifica los fallos sin filtrar credenciales ni el contenido del
  prompt.
- Los limitadores de RPM (`_LIMITERS` en `provider.py`, con las clases de `runtime/quota.py`) se
  **comparten a nivel de proceso**: dos generaciones concurrentes respetan un único presupuesto
  de RPM.
  - La clave de cada limitador es (huella de la clave, modelo, capacidad), porque Gemini cuenta la
    cuota por proyecto y por modelo. Desde 7.4, dos modelos no comparten ventana aunque tengan el
    mismo RPM.
  - El limitador de TPM, en cambio, es por instancia.
- **Los actores pueden ir con un modelo propio** (7.4; solo los actores desde 7.13).
  - `GEMINI_STAGE_MODEL`, `GEMINI_STAGE_API_KEY` y `GEMINI_STAGE_RPM_LIMIT`; vacíos heredan los
    principales.
  - Si difieren, `provider_from_settings` devuelve un `RoutedProvider`, que enruta por la etapa
    y el agente que `_call_agent` ya declara (`call_context`). Solo `STAGE_MODEL_CALLS`
    (`("performance", "actor")`: turnos y reflexiones) va al modelo de la función. El director
    de escena juzga si un beat se cumplió, y un juicio flojo fuerza el beat, así que sigue en el
    principal con el casting, la narración, los constructores y la auditoría.
  - Los dos proveedores comparten `usage_records` y los callbacks del run, así que el pipeline
    ve uno solo. Ningún agente ni doble de test sabe del reparto.
  - `metadata.json` lo registra en `stage_model`, que es `None` si la función usó `model`. El eje
    `stage_model` de `evaluation/pairing.py` impide emparejar funciones de modelos distintos.
- **La prosa que lee el lector puede ir con un modelo propio** (7.12), `GEMINI_PROSE_MODEL`.
  - Solo las llamadas de `PROSE_CALLS` (capítulos del Drafter, Writer y narrador, no su revisión)
    van a ese modelo, por etapa y agente, en el mismo `RoutedProvider`.
  - Tiene su propio tope diario (`GEMINI_PROSE_DAILY_REQUESTS`, 20 por defecto: el gratuito de
    Flash). Cuando se agota, o cuando el modelo de la función o de la prosa da un 401/403,
    `RoutedProvider` pasa esa ruta al principal durante el resto del run, sin perderlo.
  - `metadata.json` lo registra en `prose_model`; el eje `prose_model` de `pairing.py` solo lo da
    por usado si aparece en `models_used`. Sin cadena; con `ASG_LLM_CHAIN` se ignora.
- **Un 503 se espera poco y se cede** (7.13). Cada 5xx espera `GEMINI_OVERLOAD_WAIT` (10 s) y
  reintenta en el mismo modelo, con una cuenta aparte de `GEMINI_MAX_RETRIES`. Al
  `GEMINI_OVERLOAD_ATTEMPTS`-ésimo (6) sale `ProviderOverloadedError`, y la cadena o el
  enrutador pasan solo esa llamada al siguiente modelo.
  - **Cada 503 cuenta como petición del cupo diario**: el 13 de octubre de 2026, 301 de las 500
    de 3.5 Flash-Lite fueron 503.
  - Una paciencia larga (60 s × 10 en el borrador 7.12.2) no ahorra cuota: la quema esperando.
  - Una corta (un reintento en 7.12.1) gastaba la segunda ranura con cualquier pico.
- **La cadena de proveedores** (7.7), `ASG_LLM_CHAIN=gemini,groq,mistral`.
  - `FailoverProvider` prueba sus ranuras (proveedor y modelo; Groq da una por modelo) en orden.
    Si una da un 429 diario o mensual (`ProviderDailyQuotaError`), la misma llamada se repite en
    la siguiente. Un 401 o 403 (`ProviderUnavailableError`, desde 7.9.1) también salta, y esa
    ranura queda fuera solo en ese proceso: Groq da 403 a redes bloqueadas aunque la clave valga.
  - `runtime/budget.py` es el libro: SQLite en `.cache/llm_budget.sqlite3`, compartido entre
    procesos. Salta una ranura agotada sin gastar la petición, con una ventana por proveedor.
    Los topes son configuración, nunca constantes. `asg-budget` lo muestra.
  - `OpenAICompatibleProvider` habla con Groq y Mistral sobre httpx. Comparte con
    `GeminiProvider` la base `_RecordingProvider`, que reintenta, valida y registra.
  - `metadata.json` guarda `models_used`. Un run que saltó de modelo tiene el eje `model`
    compuesto y no se empareja con uno puro.
  - Con cadena, `GEMINI_STAGE_MODEL` es la segunda ranura de Gemini, justo tras la principal:
    3.5 → 3.1 → Groq → Mistral. Desde 7.13 las llamadas de `STAGE_MODEL_CALLS` (los actores)
    empiezan por ella: 3.1 → 3.5 → resto. `FailoverProvider.stage_model_name` la registra en
    `metadata.json`.
  - Con la cadena vacía no hay failover, pero desde 7.8.3 cada `GeminiProvider` apunta sus
    intentos en el libro (`provider.quota`), así que `asg-budget` y las auditorías también
    cuentan. Con cadena lo apunta solo `FailoverProvider`: no dupliques el cargo.
  - `asg-generate` se niega a arrancar (código 3) si lo que queda hoy no alcanza para la
    media de ese formato (`tools/budget.preflight`); `--force` lo salta.

Los tests inyectan un `FakeProvider` (ver `packages/stagecraft/tests/test_generator_v5.py`), que es
la forma canónica de probar el pipeline. Se le pasa una secuencia de respuestas estructuradas y
puede forzar fallos en llamadas concretas.

## core

- `find_project_root` sube por el árbol buscando un directorio con `Stories/` y `packages/`. Se
  puede forzar con `ASG_PROJECT_ROOT`, útil si se despliega en un contenedor.
- `files.py` da la escritura atómica UTF-8 (`atomic_write_text`, `atomic_write_json`,
  `atomic_write_csv`) y `artifact_json`, el formato JSON de los artefactos por separado.
- `locks.py` da `file_lock`, que serializa las extracciones de rasgos de un mismo texto.
- `console.py` da `use_utf8_output`, lo primero que llaman los comandos de Stagecraft, de
  evaluation y el bot. Sin él, una consola de Windows imprime mojibake.
- `audio.py` hace la narración con edge-tts.
- `craft.py` calcula las cifras de artesanía de la prosa (`craft_metrics`), puras y
  deterministas. Vive en `core` porque la usan `writing/audit.py` y `evaluation`, y `evaluation`
  no puede importar `stagecraft`.

## Precauciones

- **Dos serializadores de JSON distintos a propósito.**
  - `agents/base.json_text` serializa lo que viaja al **prompt**: convierte modelos Pydantic y no
    añade salto de línea final.
  - `asg_core.artifact_json` serializa lo que va a **disco**.
  - No unificarlos: cambiaría cada prompt, y hay tests que fijan su texto literal.
- **Un `GEMINI_BILLING_LIMIT_EXHAUSTED` del corpus no es facturación.** Los tres que hay son la
  cuota diaria gratuita: su `error_report.json` trae
  `quota_id: GenerateRequestsPerDayPerProjectPerModel-FreeTier`. El proveedor los clasificó mal
  porque el 429 estándar de Gemini contiene la palabra «billing»; desde 7.2.0 manda `quota_id`.
  En un run anterior, lee `quota_id`, no el código.
- **Un run se cancela con `should_cancel`, nunca lanzando desde un callback.** El callback de
  progreso también corre dentro del bucle de reintentos del proveedor, que convierte cualquier
  excepción en un `ProviderError` degradable, y `_record_failure` vuelve a emitir eventos. El
  pipeline consulta `should_cancel` al entrar en `_call_agent` y lanza `RunCancelledError`, que
  está en `NON_DEGRADABLE_ERRORS`. El bot también pasa `should_cancel` a `generate()`.
- **Los dobles de audio de los tests reciben solo `story_path`.** Por eso el pipeline pasa
  `voice=` a `create_story_audio_sync` solo cuando hay una voz elegida.
