# Estilo de la tesis

Sale de tres fuentes: la tesis de Roger Fuentes (`docs/Roger Fuentes Rodríguez.pdf`, misma
facultad y tutor, misma plantilla), la presentación «Estructura de una tesis» de la facultad y
las reglas del repo sobre mediciones. Se copia de Roger la forma; no su manera de afirmar.

## Voz y registro

- Español académico, claro y preciso. Primera persona del plural moderada («proponemos»,
  «en este capítulo describimos») alternada con impersonal («se describe», «se analiza»).
  Nunca primera del singular.
- Párrafos de 4 a 8 líneas, cada uno con una idea. Frases que se entienden a la primera; nada
  de cadenas de subordinadas.
- Viñetas solo para listas reales: objetivos específicos, dimensiones de un problema,
  criterios. En ese caso, como Roger, el rótulo en negrita seguido de dos puntos:
  `\item \textbf{Coherencia narrativa prolongada:} …`.
- Español de verdad: «modelo de lenguaje», «evaluación por pares», «línea base». Los términos
  sin traducción establecida van en inglés y en cursiva.

## Términos, siglas y énfasis

- Concepto clave en su primera aparición: `\textbf{historia}`, `\textbf{agentes
  conversacionales}`. Después, sin énfasis.
- Término en inglés: `\textit{prompt}`, `\textit{few-shot}`; la primera vez, con su explicación
  entre paréntesis, como hace Roger: «\textit{Retrieval-Augmented Generation} (RAG) (técnica
  que combina…)».
- Siglas definidas una sola vez: «\textit{Large Language Models} (LLMs)». Después, la sigla.
- Nombres de sistemas de la literatura en versalitas o tal cual (SCHEHERAZADE, Façade); nombres
  de módulos, comandos y artefactos propios en `\texttt{}` y solo en los capítulos de
  implementación y experimentos.

## Estructura de cada capítulo

- Abre con un párrafo que dice qué hace el capítulo y anuncia sus secciones con referencia
  cruzada y el nombre en negrita, como Roger: «Primero se describe la **Arquitectura**
  (Sección~\ref{sec:arquitectura})…».
- Secciones (`\section`) y, si hace falta, subsecciones (`\subsection`); no más hondo.
  Cada una con `\label{sec:…}`.
- Cierra con un párrafo breve que resume lo que el capítulo deja establecido y enlaza con el
  siguiente. El estado del arte termina con la **posición del autor**.
- La introducción no lleva número (`introduction`); sus rótulos del diseño teórico van en
  negrita dentro del texto, como Roger: **problema**, **hipótesis**, **Objetivo General**,
  **Objetivos Específicos** (en infinitivo: «Analizar…», «Diseñar…», «Implementar…»,
  «Evaluar…»). Termina con un párrafo que recorre los capítulos.

## Citas, figuras y tablas

- Citas numéricas por orden de aparición (`\cite{clave}`; la clase usa biblatex `numeric` con
  `sorting=none`). Toda afirmación sobre la literatura lleva cita; el autor por su apellido
  cuando importa: «Gervás~\cite{gervas2009} investigó…», «Young et al.~\cite{…}».
- Claves del `.bib`: `apellidoAño` en minúsculas (`park2023`, `chhun2022`).
- Figuras y tablas con `\caption` y `\label` (`fig:…`, `tab:…`), citadas en el texto **antes**
  de aparecer: «Como se muestra en la Figura~\ref{fig:arquitectura}…». Leyenda en una línea,
  descriptiva.
- Tablas con `booktabs` (`\toprule`, `\midrule`, `\bottomrule`), sin líneas verticales; números
  con coma decimal, como en `docs/resumen.md`.

## Lo que no se copia de Roger

- **Cifras sin respaldo.** Roger escribe «una mejora del 20 % en coherencia» sin decir de qué
  medida ni sobre cuántas historias. Aquí cada resultado lleva n, fecha y alcance («en 5 pares
  leídos por un solo lector, el 2026-10-27…»).
- **Conclusiones grandilocuentes.** Nada de «no es opcional, sino necesaria» ni «revolucionar
  industrias». Se concluye lo que el cuerpo demuestra y se nombran las limitaciones.
- **Escalas como juicio.** Roger usó valoraciones 1–10; esta tesis no (T5). Si se menciona su
  estudio, es como antecedente que motiva el cambio a pares.
- **Resultados negativos escondidos.** Un juez que no generaliza, un estudio sin la muestra
  prevista o una matriz incompleta se presentan como tales (`planning/decisions.md` §2).

## Comprobación antes de cerrar una parte

- ¿Cada párrafo dice algo que el lector no sabía en el anterior?
- ¿Cada cifra tiene fuente en el repo y cada referencia está en el `.bib` verificada?
- ¿Algún término definido dos veces, o usado antes de definirse?
- ¿La parte cabe en su presupuesto de páginas?
