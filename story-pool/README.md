# Pool público de historias

El bot publica aquí únicamente textos autorizados por sus participantes y revisados por
el investigador. Las semillas seleccionadas también se revisan antes de publicarse.

`manifest.json` enumera códigos neutros y huellas; cada relato está en `ID.md`.
La huella usa SHA-256 del texto serializado como JSON canónico UTF-8,
igual que el estudio (asg_evaluation.catalog.digest). Este directorio no contiene
los votos, prompts, opciones, identidades ni bases administrativas.

Descarga los textos con `git pull --ff-only` o desde GitHub. Para obtener los resultados
privados del estudio, sigue [la guía de transferencia](../apps/telegram/ROLLING_STUDY.md).

No copies automáticamente `Stories/`, `Evaluations/` o el ZIP privado de semillas aquí.
