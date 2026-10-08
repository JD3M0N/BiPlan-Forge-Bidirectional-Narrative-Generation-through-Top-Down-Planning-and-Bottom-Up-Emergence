# Comparación de guías narrativas

`hybrid_v1` conserva el comportamiento previo. `compositional_v2` es experimental:
no se considera superior hasta evaluar historias con personas. Desactivar
`narrative_guidance` omite ambas estrategias y sus bloques de prompt.

Las seis solicitudes JSON son material propuesto para revisión humana antes de generar.
Hay dos por perfil: reencuentro y fuga; descubrimiento y robo; rivalidad política y viaje.
Incluyen exclusiones explícitas y conflictos relacionales para no medir solo misterios.
Cada archivo es un `StoryRequest` congelado: no vuelve a pasar por el analista.

## Preparación sin cuota

Desde la raíz del repositorio:

```powershell
$caseRoot = "packages/stagecraft/experiments/guidance"
plan-guidance-experiment "$caseRoot/essential-reunion.json" "$caseRoot/developed-discovery.json" "$caseRoot/expansive-rivalry.json" --model MODELO_FIJO --output .cache/guidance-pilot.json

$casePaths = (Get-ChildItem -LiteralPath $caseRoot -Filter *.json).FullName
plan-guidance-experiment @casePaths --full --model MODELO_FIJO --output .cache/guidance-full.json
```

El primer manifiesto contiene 9 trabajos. El segundo contiene 36: seis premisas,
tres brazos y dos repeticiones. Cada trabajo incluye la petición completa, su hash,
las opciones y el modelo. El orden usa una semilla fija; las identidades de los trabajos
permiten reconocer los del piloto, aunque cambie el orden de ejecución de la matriz.

Los brazos son sin guía, `hybrid_v1` y `compositional_v2`. Todos usan narrativa y audio
desactivado; las demás opciones coinciden. `--options` permite fijarlas desde un JSON.
El preparador no lee credenciales, no construye proveedores y no ejecuta trabajos.
Rechaza sobrescribir un manifiesto existente.

`--pilot-usage` acepta los `llm_usage.json` de un piloto posterior para estimar el coste
desde su consumo medio. Sin ellos usa 16 llamadas y 84 000 tokens por historia como
referencia histórica, no como medición de v2. El presupuesto siempre se marca como no
autorizado: hay que revisar el total, el modelo y la cuota disponible antes de generar.

## Ejecución posterior

Cuando se autorice el presupuesto, el ejecutor debe leer cada trabajo, validar sus
`request` y `options` con `StoryRequest` y `GenerationOptions`, y usar
`StoryGenerator.from_options(...).generate(request)`. Registrar la correspondencia entre
`job_id` y carpeta de run. No usar `generate_from_plan`: el plan es una variable de resultado.

Usar el modelo exacto declarado y desactivar cadenas de proveedores durante la comparación.
Un run que cambie de modelo no es un par limpio; el informe registra `models_used`.
Las incidencias y reparaciones forman parte del resultado, no se eliminan para favorecer
un brazo. No regenerar hasta conseguir una historia preferida.

Reutilizar las nueve historias piloto solo si no cambian generador, catálogo, prompts,
opciones ni peticiones. Si algo cambia, conservarlas como piloto y comenzar otra matriz.

## Lectura humana

Presentar pares del mismo caso y repetición, ocultando brazo, guía, modelo y archivos de
planificación. Aleatorizar izquierda/derecha independientemente del orden de generación.
Preguntar por creatividad, desarrollo de personajes e interés de la trama, con el instrumento
humano ya existente; no crear una puntuación de cumplimiento de patrones.

Registrar además incumplimientos explícitos, subtramas gratuitas y giros que sustituyan la
premisa. Informar variación por lector y por premisa, junto con llamadas, tokens, abstenciones
y degradaciones. Las 36 historias son evidencia exploratoria, no demostración general.
Mantener `hybrid_v1` por defecto hasta decidir a partir de esos resultados.

## Contrato técnico v2

- El catálogo se distribuye dentro del paquete como JSON y se valida al cargarlo.
- Recuperación envía los 34 patrones; exige cobertura completa, IDs únicos y referencias
  válidas a requisitos para declarar incompatibilidad. Ordena por relevancia semántica,
  orden estable del catálogo para desempatar; la evidencia léxica es solo diagnóstica.
- Selecciona hasta diez pertinentes; solo cuando no hay ninguno ofrece débiles. Tras dos
  intentos inválidos o no disponibles, conserva el diagnóstico y se abstiene sin llamar a composición.
  Cuota, configuración y cancelación se propagan.
- Desde 7.8.1, el esquema de respuesta exige `connection` no vacío para cada selección nueva,
  incluida la principal. El lector conserva la compatibilidad con los blueprints v2 anteriores.
  La reparación contextual identifica el campo y adjunta el borrador rechazado.
- Composición acepta hasta un patrón principal. Esencial admite además un local;
  Desarrollada, un secundario y un local; Expansiva, tres adicionales. Son máximos.
  Las capas del catálogo son orientativas. Una composición puede abstenerse o usar solo
  recursos locales, con su conexión al conflicto central.
- Preguntas y movimientos: máximo dos de cada uno, con referencia al patrón y posición
  original. La desviación creativa es opcional. Los roles tienen vocabulario validado;
  las apariencias u ocupaciones siguen siendo abiertas.
- Se permite una reparación por etapa, además de los reintentos internos del proveedor.
  Un fallo de composición se guarda en `narrative_composition_error.json` y la historia
  continúa sin guía. Una abstención se guarda como blueprint válido con bloques vacíos.
- `narrative_retrieval.json` conserva petición, catálogo, hash, juicios y candidatos.
  `narrative_blueprint.json`, contrato 2, conserva elecciones y bloques exactos. Los escritores
  y críticos no reciben esos bloques; solo personajes y planificación.

La validez de referencias y límites se comprueba en código. La pertinencia de una explicación
o su cumplimiento semántico siguen siendo juicios del modelo que deben revisarse en el experimento.

## Validación real de 7.8.1 (2026-10-09)

Se reprodujo la omisión de `connection` con Gemini 3.5 Flash Lite usando la petición y
recuperación guardadas del caso `20261009-150449-el-dato-ausente`. La primera respuesta
omitió el campo en las selecciones; el esquema anterior lo declaraba opcional, aunque
la validación contextual lo exigía para alcances secundarios y locales.

Después de la corrección, tres repeticiones de `compose_patterns` con esa misma entrada
produjeron composiciones válidas al primer intento, con todas sus conexiones explícitas.
Las respuestas de reproducción y verificación están en `.cache/guidance-connection-before-20261009-111302`
y `.cache/guidance-connection-after-20261009-111545`, respectivamente.

La nueva historia completa está en
`Stories/Stagecraft/20261009-151602-el-dato-ausente/story.md`: 2 111 palabras, cuatro capítulos,
17 llamadas y 96 158 tokens. La recuperación necesitó una reparación por referencias a
restricciones en un juicio que no estaba marcado como incompatible; la composición pasó
al primer intento y la historia terminó con la guía activa, sin avisos. Se verificaron los
35 artefactos del manifiesto, los bloques persistidos y la lectura del blueprint anterior
con conexión principal vacía. La suite pasó con 827 pruebas y dos omitidas; lint, formato
y dependencias también pasaron.

Esta prueba confirma la corrección del fallo observado y el funcionamiento de la reparación
acotada. No demuestra superioridad literaria ni garantiza ausencia de futuras respuestas inválidas.

## Fidelidad y fallos desde 7.8.2

El analista realiza una extracción y una revisión adicional contra el prompt original. Esta segunda llamada corrige afirmaciones no respaldadas y conserva el alcance de las restricciones. Se aplica a ambas estrategias y añade una llamada de extracción por encargo.

La recuperación v2 registra los borradores estructurados rechazados en `rejected_drafts`, compatible con artefactos anteriores que omiten el campo. Los errores precisan el patrón y todas las referencias que deben corregirse. Tras dos intentos fallidos no hay candidatos léxicos: la composición registra `retrieval_failed`, con bloques vacíos y cero llamadas. Si la recuperación válida no ofrece candidatos, registra `no_eligible_candidates`.
