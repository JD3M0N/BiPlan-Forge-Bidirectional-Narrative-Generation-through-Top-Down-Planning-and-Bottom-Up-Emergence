---
name: write_thesis
description: Escribe en LaTeX la siguiente parte de la tesis según redaccion/write_thesis_roadmap.md (estado del arte, introducción, capítulos, conclusiones, resumen…), con la plantilla de MatCom en redaccion/tesis/ y el estilo de la tesis de Roger Fuentes. Usar cuando el usuario escribe /write_thesis o /write_thesis R03, o pide «la siguiente parte de la tesis» o «escribe el capítulo X».
---

# /write_thesis

Redacción de la tesis, una parte por sesión. El plan está en `redaccion/write_thesis_roadmap.md`
y el estilo, en [estilo.md](estilo.md) (en esta carpeta). Todo en español, salvo el *abstract*.

## Usos

| Invocación | Qué haces |
|---|---|
| `/write_thesis` | La parte que dice «Siguiente» en el «Estado» del roadmap de redacción. |
| `/write_thesis R03` | Esa parte concreta, si sus dependencias están hechas. |

## Escribir una parte

1. **Árbol.** `git status --short`. Si hay cambios sin commit ajenos a la parte, enséñalos y
   pregunta qué hacer; no los toques sin respuesta.
2. **Leer poco.** Lee `AGENTS.md`, el «Estado», las «Reglas comunes» y la tarjeta de la parte
   en el roadmap de redacción, y [estilo.md](estilo.md). Después, **solo** lo que dice **Lee**
   y las páginas de **Roger** de la tarjeta (`docs/Roger Fuentes Rodríguez.pdf`, con `pages`).
   Si `graphify-out/graph.json` existe, úsalo para orientarte en el código.
3. **Dependencias.** Si una parte de **Depende de** no está en «Hechas», o la tarjeta exige
   fases de `planning/roadmap.md` que no están cerradas (R07 necesita P07, P08 y P09), **para y
   dilo**: propone la parte que sí se puede escribir.
4. **Reglas del tutor.** Lee `planning/decisions.md` §1 (T1–T11) y contrasta el contenido. Si la
   tarjeta o el texto chocan con una regla (una escala como juicio de calidad, el LLM que juzga,
   el juez como función objetivo fuera del trabajo futuro…), **para y avisa**.
5. **Escribir** en el archivo de la tarjeta, siguiendo [estilo.md](estilo.md):
   - Cifras: solo de una fuente del repo, con fecha, n y alcance. Si falta, `\todo{dato: …}`;
     nunca la inventes ni la redondees a favor.
   - Referencias: de `packages/evaluation/planilla/bibliografia.csv` o verificadas en la web
     (DOI, ACL Anthology, arXiv, editorial) antes de añadirlas a `redaccion/tesis/Bibliography.bib`.
     Si no puedes verificarla, `\todo{cita: …}`. Las marcadas «revisar cifras en el PDF» no
     aportan cifras sin comprobarlas.
   - Figuras en `redaccion/tesis/Graphics/` (o las de P09 en `redaccion/figuras/`); tablas con
     `booktabs`.
6. **Compilar.** `asg-latex` desde la raíz (MiKTeX): compila en una copia en `%TEMP%` y deja el
   PDF y el log en `redaccion/tesis/`. Debe terminar con 0, sin citas ni referencias
   indefinidas ni cajas desbordadas (las cuenta al final). Si falta un paquete de LaTeX, instálalo con
   `miktex packages install <paquete>` (el diálogo de instalación automática falla) y vuelve a
   compilar; no hagas un bucle de compilaciones.
7. **Medir.** Cuenta las páginas de la parte en el PDF (y las palabras en el resumen). Si pasa
   más de un 20 % del presupuesto de la tarjeta, dilo antes del commit y propone qué recortar.
8. **Cerrar.**
   - En el roadmap de redacción: la parte pasa a «Hechas» con una línea
     (`R03 · <qué quedó>, N págs., M \todo`), «Siguiente» apunta a la próxima parte que se pueda
     escribir y se pone al día la extensión acumulada.
   - Si al escribir decidiste algo que afecta a otra parte (un término, una figura compartida,
     un objetivo), anótalo en la tarjeta de esa parte.
   - Commit en `main` con mensaje `TESIS R03: <resumen en español>`. **Sin** `Co-Authored-By`.
     **Sin** push. No incluyas artefactos de compilación (los ignora `redaccion/tesis/.gitignore`).
9. **Parar y resumir:** qué se escribió (secciones), páginas frente al presupuesto, `\todo` que
   quedan y por qué, referencias nuevas verificadas y la siguiente parte. Al cerrar R12,
   recuerda **H5**: Josue manda el borrador al tutor.

**Una parte por sesión.** Si la parte no cabe en una sesión (un capítulo largo), para antes de
escribir y propone partirla en dos tarjetas en el roadmap; con el «ok», escribe solo la primera.

## Nunca

- Escribir agradecimientos, dedicatoria u opinión del tutor sin que Josue lo pida.
- Inventar cifras, referencias o resultados, o presentar como predeterminado un mecanismo que
  el generador congelado tiene apagado.
- Cambiar decisiones de `planning/decisions.md`, datos de `Evaluations/`, `Stories/` o
  `packages/evaluation/planilla/rasgos.csv`; escribir en `TODO.md`; tocar
  `redaccion/presentaciones/`.
- Push, `--no-verify` o commits con coautor.
