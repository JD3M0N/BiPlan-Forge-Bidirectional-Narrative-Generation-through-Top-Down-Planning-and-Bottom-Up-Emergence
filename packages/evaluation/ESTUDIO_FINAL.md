# Estudio final: protocolo y operación

La infraestructura está implementada. Todavía no se han generado las historias del experimento,
reclutado lectores ni validado empíricamente el juez. La demostración usa exclusivamente textos,
proveedores y votos ficticios. No consume cuota ni modifica `Stories/`.

## Protocolo fijado

Participarán aproximadamente 6–8 lectores. El investigador inscribe cinco relatos: dos de
generación directa y tres del sistema. Cada participante aporta una historia con prompt y opciones
libres mediante `/aportar`; puede reemplazarla antes del cierre de recogida. Se admiten prosa directa
(`baseline`), narrativa (`narrative`) e híbrida (`simulated`). El guion queda fuera del estudio.
Las aportaciones con opciones libres permiten estudiar asociaciones, no aislar efectos causales.

Primero se recogen las historias y los perfiles. Después se congela el conjunto, y finalmente se
abre la votación. La congelación exige una versión explícita del generador, cinco relatos
seleccionados con dos líneas base y perfiles completos. Guarda textos, procedencia, familias de
premisa, catálogo, preguntas, semilla y asignaciones; una huella identifica la instantánea.
No se permite inscribir ni modificar relatos después. Los runs originales no se reescriben.

Cada lector recibe hasta diez historias desconocidas, en dos sesiones de hasta cinco. Se excluyen
sus propias historias y las exposiciones registradas. Un ciclo de pares por sesión hace que cada
historia se compare con otras dos por criterio (con dos historias solo hay un par). El sorteo
compensa las posiciones A/B y busca cobertura conectada y pares compartidos entre lectores.
El máximo previsto es treinta decisiones por persona. Las preguntas son las tres formulaciones
de `criterios_humanos.csv`, congeladas junto al estudio.

Se muestra un criterio por pregunta, con A, B y «No puedo decidir». La abstención se conserva y
no es empate ni victoria. El participante recibe el texto íntegro y un archivo de nombre neutro;
no recibe audio, configuración, modelo ni rutas. «Ya conocía esta historia» se pulsa antes de
confirmar la lectura: sustituye sus preguntas pendientes si queda una alternativa elegible; si no,
las anula. El informe refleja la cobertura resultante. `/pausa` y los reinicios conservan votos y
lecturas. La evaluación no depende del `user_data` descartable de la generación.

Los identificadores de Telegram se guardan solo en la base administrativa. La exportación usa
seudónimos. Los prompts y textos siguen siendo material de investigación: revisar su contenido
antes de publicar un conjunto de datos. Marcar al investigador con `--author` permite comparar
acuerdo y rankings humanos con y sin su participación.

## Instalación y demostración sin red

Tras actualizar el repositorio, reinstalar sus paquetes editables para registrar comandos y
dependencias (`pip install -r requirements.txt`). En PowerShell, con el entorno virtual activo:

```powershell
evaluation-demo .cache/evaluation-demo-nueva
.\quality.ps1
```

La carpeta de demostración debe ser nueva. Contiene once relatos artificiales, seis lectores,
180 respuestas, extracciones, tres jueces, rankings y un informe horizontal. `summary.json`
declara `synthetic: true` y `network_calls: 0`. Los resultados no demuestran calidad narrativa
ni generalización; comprueban que las piezas se conectan. El proveedor ficticio solo reconoce
patrones preparados para la prueba.

## Preparar y abrir un estudio real

Estos comandos son instrucciones para una fase posterior: no ejecutarlos para generar el corpus
antes de fijar la versión definitiva y el presupuesto. Guardar cada estudio en su propia carpeta,
fuera de `Stories/`; por ejemplo `Evaluations/tesis-final/` (ignorada por Git).

```powershell
evaluation-study --db Evaluations/tesis-final/study.sqlite3 create tesis-final --version VERSION_FINAL --seed 42
evaluation-study --db Evaluations/tesis-final/study.sqlite3 collect
```

Configurar `ASG_EVALUATION_STUDY=Evaluations/tesis-final/study.sqlite3` en el entorno del bot.
`/evaluar` registra el perfil; `/aportar` reserva la siguiente generación como aportación. Los
comandos `/newstory` y `/settings` siguen disponibles. La reserva se vincula al identificador
persistente del trabajo, por lo que otra generación no debe ocupar su lugar. Una aportación
fallida o en formato guion no se inscribe; se puede repetir `/aportar`.

El investigador puede registrar lectores y relatos desde la CLI. `participant` devuelve el
seudónimo que acepta `--owner`; usarlo también en los relatos seleccionados que el investigador
ya conoce. `--family` agrupa variantes relacionadas aunque sus prompts no sean idénticos.

```powershell
evaluation-study --db Evaluations/tesis-final/study.sqlite3 participant ID_TELEGRAM --profile regular --author
evaluation-study --db Evaluations/tesis-final/study.sqlite3 add RUTA_RUN --curated --family premisa-01
evaluation-study --db Evaluations/tesis-final/study.sqlite3 status
evaluation-study --db Evaluations/tesis-final/study.sqlite3 freeze
evaluation-study --db Evaluations/tesis-final/study.sqlite3 start
```

Repetir `add` para las cinco historias seleccionadas. El resto se inscribe por el bot o con
`add RUTA_RUN --owner SEUDONIMO`. Una nueva contribución reemplaza la anterior manteniendo su ID.
Antes de congelar, comprobar que todas las aportaciones previstas han terminado. `status` permite
revisar cobertura prevista, votos, abstenciones y componentes efectivos. Al finalizar:

```powershell
evaluation-study --db Evaluations/tesis-final/study.sqlite3 close
evaluation-study --db Evaluations/tesis-final/study.sqlite3 export Evaluations/tesis-final/datos.json
```

`generate-baseline "PREMISA" --output CARPETA_NUEVA` está disponible para la futura línea base:
realiza una sola generación directa con el proveedor configurado y conserva prompt, versión,
estado y consumo. Este comando sí consume cuota. No llama al pipeline narrativo ni a la simulación.

## Extracción y auditoría

Los 139 campos de `planilla/rasgos.csv` son el catálogo común. Solo los 27 campos de prioridad
núcleo en T/R/X entran en el juez. T01 controla longitud; los campos de proceso, coste y
configuración se muestran en los informes pero nunca son entradas del juez. Las preguntas H
y los resultados J tampoco son predictores.

```powershell
extract-story-features --study Evaluations/tesis-final/study.sqlite3 --dry-run
extract-story-features --study Evaluations/tesis-final/study.sqlite3
audit-feature-extraction Evaluations/tesis-final/features/ID_RELATO.json --output revision.json
```

Solo la extracción sin `--dry-run` llama al proveedor configurado. Usa una segmentación común
en escenas y rasgos deterministas calculados por código. Para los semánticos, el proveedor devuelve
ocurrencias, etiquetas y citas literales con párrafo; el código verifica localización, elimina
duplicados y deriva el recuento. Las contradicciones necesitan evidencia de ambos hechos. La
comprobación literal no prueba por sí sola que una interpretación semántica sea correcta.

Cada medida conserva valor bruto, valor normalizado, unidad, denominador cuando procede,
evidencias y estado: `measured` (incluido cero), `not_applicable`, `missing` o `failed`.
Los fallos de evidencia permiten una reparación acotada; después se conservan como fallos.
Los lotes completos sobreviven a interrupciones. Texto, catálogo, prompt y modelo forman la
identidad de caché. `--force` repite la extracción y archiva la anterior en `*.history/`.
`--selection all` añade rasgos secundarios; R14 usa atribución de voz entre hablantes elegibles.

Para comparar dos mediciones del mismo texto, pasar `--second OTRA_EXTRACCION.json` a
`audit-feature-extraction`. La ficha de revisión incluye evidencias, ceros y huecos para registrar
fenómenos omitidos. Revisar una muestra manualmente antes del estudio. Contrastar con logs solo
cuando describan el mismo fenómeno: un log no es un techo universal de lo que cuenta la prosa.

Para un corpus externo, `extract-story-features --root RUTA` escribe archivos derivados en
`features/features.json` bajo cada run, sin modificar los artefactos del generador. Después:

```powershell
report-features RUTA --json tabla.json --csv tabla.csv --horizontal horizontal.json --axis C02
```

La tabla mantiene campos ausentes en artefactos antiguos como no medidos. El informe horizontal
agrupa configuraciones y versiones e informa medianas, rangos y tamaños de grupo. No convierte
las opciones libres de los participantes en un experimento causal.

## Preferencias, juez y ranking

```powershell
report-preferences Evaluations/tesis-final/study.sqlite3 --output preferencias.json --bootstrap 1000
fit-preference-judge Evaluations/tesis-final/study.sqlite3 --output juez.json
rank-stories juez.json RUTA_CORPUS --output ranking.json
```

Bradley–Terry regularizado se ajusta por criterio. No se publica un orden global humano cuando
su grafo está desconectado. El acuerdo usa los mismos pares, orientados de forma consistente;
se informa proporción de acuerdo y alfa nominal. Los intervalos se obtienen remuestreando
participantes completos. Se informa cuántas réplicas quedaron conectadas.

Los tres jueces son regresiones logísticas L2 sin intercepto sobre diferencias de rasgos.
Imputación por mediana y estandarización se ajustan una vez por historia única de entrenamiento.
La validación retiene historias y elimina todos los votos que las tocan del entrenamiento;
también retiene familias de premisa. Cada pliegue publica historias, votos y preprocesamiento
de entrenamiento. Se compara con azar y con longitud sola. Las probabilidades fuera de muestra
se agregan antes de construir el ranking de validación: no se mezclan puntuaciones de pliegues
con escalas distintas. Se informa cobertura de predicciones, acierto y concordancia Kendall.

El modelo JSON publica pesos, versiones, huellas, escala fijada en entrenamiento y limitaciones.
Los tres rankings son principales; la media de sus puntuaciones estandarizadas es auxiliar.
El ranking posterior excluye textos incompatibles o extracciones incompletas, y prepara diez
fichas cualitativas en Markdown. Con `--perturbations CASOS.json`, el entrenamiento también
informa diferencias para pares de extracciones `original`/`perturbed` con un `name`; no se exige
que toda perturbación empeore los tres criterios.

Un juez que no generalice es un resultado experimental válido. La interfaz lo marca exploratorio;
no es una medida acreditada de calidad. Los `evaluation.json` históricos y los tres informes
anteriores se conservan con sus contratos originales. Las notas 1–10 quedan fuera de este flujo.

## Pendiente de ejecución experimental

Fijar versión definitiva y presupuesto, generar el corpus, revisar extracciones, realizar el
piloto humano, ejecutar el estudio y redactar el análisis de los resultados reales. No se usa
el juez para elegir automáticamente qué generar ni se modifica ahora la simulación.
