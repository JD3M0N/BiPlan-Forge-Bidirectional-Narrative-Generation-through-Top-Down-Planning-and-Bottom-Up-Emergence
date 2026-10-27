# Cómo trabajar fase a fase

Guía para Josue. Las reglas que sigue el agente están en la skill
[`phase`](../.claude/skills/phase/SKILL.md); el plan, en el [roadmap](roadmap.md).

## Las piezas

| Pieza | Qué es |
|---|---|
| **Tarea** (`P04.2`) | Una sesión de Claude y un commit. Si toca código, sube el parche del paquete que toca. |
| **Fase** (`P04`) | Un grupo de tareas con un resultado revisable. |
| **Hito** (`H0`…`H6`) | Un punto en el que pruebas el bot en Telegram o enseñas el avance al tutor antes de seguir. |
| **Tarjeta** | Lo que el agente necesita para una tarea: **Lee / Haz / No hagas / Prueba / Hecho cuando / Modo**. Sin tarjeta, no se ejecuta la tarea. |
| **Estado actual** | La cabecera del roadmap: cuál es la siguiente tarea y la lista «Hechas». |
| **Reglas del tutor** | T1–T11 en [decisions.md](decisions.md) §1. Toda tarea de evaluación, juez o tesis se contrasta con ellas. |

**Modos de una tarjeta:**

| Modo | Qué pasa |
|---|---|
| `S` | Sonnet trabaja directamente. |
| `S+P` | Sonnet te enseña un plan corto y espera tu «ok» antes de tocar código. |
| `O` | Es una decisión de diseño (qué fichas congelan el generador, qué matriz cabe en la cuota, el índice de la tesis…). Sonnet te da las opciones con su recomendación y espera. Decides tú, o cambias a Opus para pensarlo. |

## El ciclo

### 1. Una tarea: `/phase`

```
/clear
/model sonnet
/phase
```

Sonnet:
1. mira `git status`: si hay cambios sin commit, te pregunta qué hacer con ellos;
2. lee el «Estado actual» y la tarjeta de la siguiente tarea, y solo los archivos que dice la
   tarjeta (se orienta con el grafo de graphify si hace falta);
3. si la tarea toca evaluación, juez o tesis, repasa las reglas del tutor;
4. si la tarjeta es `S+P` u `O`, para y espera tu respuesta; si gasta cuota, te enseña antes el
   coste y espera;
5. implementa y pasa las pruebas (`.\run-tests.ps1` completa y `.\quality.ps1`; `latexmk` en la
   tesis; lo que pida la tarjeta);
6. borra la tarjeta, apunta la tarea en «Hechas», pone al día el «Estado actual», sube el parche
   del paquete tocado con su `CHANGELOG.md` y hace el commit en `main` (sin push);
7. **se para** y resume qué cambió y cuál es la siguiente tarea.

Tú revisas el diff (`git show`). Si algo no te gusta, díselo en esa misma sesión antes de pasar a
otra. El push lo haces tú.

También puedes pedir una tarea concreta: `/phase P03.4`.

### 2. La siguiente tarea de la misma fase

Repite el paso 1 en una **sesión nueva** (`/clear`). Cada tarea empieza limpia: así gasta pocos
tokens y no arrastra contexto viejo.

### 3. Al terminar una fase: `/phase cards Pxx`

Cuando Sonnet te avisa de que cerró la última tarea de una fase:

```
/clear
/model opus
/phase cards P04
```

Esto **no implementa nada**. Opus:
1. lee el bloque de P04 en el roadmap, sus fichas en [fichas.md](fichas.md), su contrato (por
   ejemplo `METODOLOGIA.md` o `docs/architecture/evaluation.md`) y el código real que va a tocar;
2. parte la fase en tareas de una sesión (P04.1, P04.2…) y escribe la tarjeta de cada una;
3. revisa tu `TODO.md`: lo ya claro que encaja en P04 pasa a una tarjeta, lo que es para después
   va a [idea-bank.md](future/idea-bank.md) y lo que no está claro se queda donde está;
4. te enseña las tarjetas. **Las apruebas o las corriges**, y él hace un commit solo de
   documentación.

Después vuelves al paso 1. Las tarjetas se escriben justo antes de cada fase, y no todas al
principio, porque así se escriben contra el código como está entonces.

### 4. Al cerrar un hito

| Hito | Qué haces |
|---|---|
| H0 | Repasas el diff de la limpieza. |
| H1 | Pruebas el bot en Telegram con los dos enfoques: el generador queda congelado. |
| H2 | Enseñas al tutor la tablita de rasgos y la lista núcleo. |
| H3 | Cierras la votación. |
| H4 | Enseñas al tutor el juez, el ranking y las diez mejores. |
| H5 | Mandas el borrador de la tesis al tutor. |
| H6 | Entregas. |

## Dónde va cada cosa

| Quiero… | Lo pongo en… |
|---|---|
| apuntar una idea o una tarea suelta | `TODO.md`: es tuyo y los agentes no escriben en él. |
| saber qué toca ahora | «Estado actual» del [roadmap](roadmap.md). |
| saber qué está decidido, y las reglas del tutor | [decisions.md](decisions.md). |
| ver el detalle de una ficha vieja (SIM-1, MED-9…) | [fichas.md](fichas.md), hasta que una tarjeta la absorba. |
| una idea para después de la tesis | [future/idea-bank.md](future/idea-bank.md). |
| el método de evaluación del tutor | [METODOLOGIA.md](../packages/evaluation/METODOLOGIA.md) y su `planilla/`. |
| la tesis | `redaccion/` (LaTeX). |
| ver qué se hizo | los `CHANGELOG.md` de cada paquete y `git log`; lo hecho no se guarda en `planning/`. |
| recuperar el TODO viejo | `git show planning-before-phase:TODO.md`. |

## Cuándo usar cada modelo

- **Sonnet**: todas las tareas `S` y `S+P`.
- **Opus**: `/phase cards`, las tareas `O` y cuando una tarea se complica o hay que decidir algo
  de diseño.

## Si algo se tuerce

- **Sonnet pregunta algo que no está en `decisions.md`**: contesta tú. Si la respuesta es una
  decisión nueva, pídele que la apunte en la tarjeta (o, si es duradera, en `decisions.md`).
- **La tarea es más grande que una sesión**: Sonnet debe parar y proponer partirla. Acepta y que
  reescriba la tarjeta en dos.
- **Falla una prueba que no tiene que ver con la tarea**: que la anote en la tarjeta que
  corresponda y siga, o que pare si bloquea el commit.
- **Una tarea choca con una regla del tutor**: Sonnet para y te avisa. No se cambia una regla
  T1–T11 sin hablarlo con el tutor.
- **No te gusta el resultado**: `git revert <commit>` deshace esa tarea. Como cada tarea es un
  commit, se revierte sola.
- **Sesión cortada a mitad**: abre otra y haz `/phase`; Sonnet ve el árbol sin commit y te
  pregunta qué hacer con ello.

## Ahora mismo

P01 y P02.1 tienen tarjeta: puedes encadenar `/phase` hasta cerrar P01. P02.1 es una decisión
(`O`): hazla con Opus. El primer `/phase cards` será el de **P03**, o el de P02 si P02.1 no deja
escritas sus tarjetas.
