# Hoja de ruta

Las tareas se agrupan por subsistema. Cada una describe el resultado esperado y una
condición concreta para considerarla terminada.

## Calidad e infraestructura

- [ ] **Recuperar la línea base de calidad.** Resolver la discrepancia entre la política
  actual de voz española y su prueba, añadir los docstrings en inglés que exige la suite
  y aplicar el formato pendiente. **Finalizada cuando:** las 155 pruebas pasan (con las 2
  pruebas de integración opcionales omitidas), `ruff check .` y `ruff format --check .`
  terminan sin errores.
- [ ] **Automatizar las comprobaciones en integración continua.** Crear un flujo que
  instale el monorepo y ejecute Ruff, la comprobación de formato, las pruebas Python,
  `pip check` y la prueba PowerShell de sincronización de Railway. **Finalizada cuando:**
  cada cambio se valida automáticamente en un entorno limpio y un fallo bloquea la
  comprobación correspondiente.

## Core y audio

- [ ] **Hacer configurable y reproducible la narración de historias.** Definir voces por
  idioma y región, una selección determinista y un fallback seguro; documentar la
  configuración y conservar en `audio.json` la voz y el idioma realmente utilizados.
  **Finalizada cuando:** se pueden cambiar las voces sin editar el código y existen
  pruebas para detección de idioma, selección configurada, fallback, reintentos, limpieza
  de archivos parciales y fallos controlados.

## Telegram

- [ ] **Aceptar solicitudes de historias mediante notas de voz.** Descargar y transcribir
  el audio recibido, mostrar el texto resultante para que el usuario lo confirme o corrija
  y solo entonces incorporarlo al flujo libre o guiado. **Finalizada cuando:** una nota de
  voz válida puede iniciar una solicitud y los formatos, tamaños o transcripciones no
  válidos generan mensajes claros sin añadir trabajos a la cola.
- [ ] **Mostrar en la consola el estado operativo de la cola.** Presentar el trabajo en
  ejecución, usuario, posición, etapa, porcentaje y solicitudes pendientes, actualizando
  la vista cuando cambien la cola o el progreso. **Finalizada cuando:** el operador puede
  conocer la carga y la etapa actual sin consultar Telegram ni la base SQLite, y el estado
  mínimo necesario se conserva durante la ejecución.
- [ ] **Definir una política segura para ejecuciones interrumpidas.** Medir primero si hay
  un caso de uso que justifique reanudar desde los checkpoints existentes; mientras no
  exista reanudación segura, permitir reiniciar, notificar o descartar explícitamente los
  trabajos `recovery_pending`. **Finalizada cuando:** ningún trabajo queda indefinidamente
  bloqueado y la política elegida está documentada y cubierta por pruebas de reinicio.
- [ ] **Versionar y mantener la cola persistente.** Incorporar migraciones compatibles para
  `telegram_queue.sqlite3` y definir cuánto tiempo se conservan trabajos terminados,
  errores y prompts. **Finalizada cuando:** una base creada por una versión anterior se
  actualiza sin perder trabajos activos y los registros vencidos pueden depurarse de forma
  verificable.

## Generación Top-Down

- [ ] **Calibrar los perfiles Esencial, Desarrollada y Expansiva.** Ejecutar un corpus común
  y comparar profundidad, cantidad de conflictos y subtramas, desarrollo de personajes,
  capítulos, eventos y longitud observada. **Finalizada cuando:** los perfiles producen
  diferencias narrativas medibles y documentadas, y una historia Expansiva no resulta
  indistinguible de una Esencial por falta de desarrollo.
- [ ] **Mapear la extensión solicitada por el usuario a un perfil narrativo.** Reconocer
  expresiones libres y cantidades de palabras o capítulos, dar precedencia a un perfil
  nombrado explícitamente y registrar el perfil seleccionado junto con su justificación.
  **Finalizada cuando:** casos representativos en español e inglés se asignan de forma
  consistente a Esencial, Desarrollada o Expansiva sin prometer una longitud exacta.
- [ ] **Evaluar e integrar taxonomías o arquetipos cuando aporten calidad.** Comparar, sobre
  los mismos casos, historias generadas con y sin una guía taxonómica y medir su efecto en
  originalidad, coherencia y satisfacción. **Finalizada cuando:** el experimento y la
  decisión quedan documentados y, si existe una mejora, el pipeline incorpora un brief
  opcional y auditable sin restaurar la complejidad completa del subsistema anterior.
- [ ] **Evaluar un grafo explícito de lugares antes de añadir estado espacial dinámico.**
  Comparar el modelo actual basado en `locations` y `location_id` con relaciones y
  transiciones explícitas entre lugares. **Finalizada cuando:** se documenta el impacto en
  errores de continuidad y coste de generación, y el grafo solo se adopta si ofrece una
  mejora medible.

## Evaluación y documentación

- [ ] **Crear un benchmark narrativo reproducible.** Mantener un conjunto versionado de
  prompts y un procedimiento común para recoger métricas automáticas y evaluaciones
  humanas de perfiles, taxonomías y cambios futuros. **Finalizada cuando:** dos versiones
  del generador pueden compararse bajo las mismas condiciones y los resultados conservan
  la configuración necesaria para repetir el experimento.
- [ ] **Documentar los contratos públicos con ejemplos ejecutables.** Cubrir las fachadas de
  `asg_core`, `asg_top_down`, `asg_evaluation` y `asg_escape_room`, además de callbacks,
  errores y artefactos principales, con ejemplos mínimos de entrada, salida y fallo.
  **Finalizada cuando:** la documentación describe el contrato Top-Down 6.0, aclara la
  compatibilidad relevante con ejecuciones anteriores y los ejemplos se validan en las
  pruebas o en la integración continua.
