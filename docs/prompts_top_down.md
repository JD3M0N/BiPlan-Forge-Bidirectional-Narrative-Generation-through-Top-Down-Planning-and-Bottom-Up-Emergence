# Prompts canónicos para probar el pipeline Top-Down

Este catálogo contiene siete solicitudes narrativas estables para observar cómo
cambia el resultado cuando se modifica el pipeline. Los casos usan perfiles
cualitativos y dejan que el planificador decida los capítulos sin presupuestos
numéricos de palabras. Desarrollada y Expansiva aplican mínimos estructurales de
eventos para que la profundidad no se limite a producir escenas más largas.

El prompt 1 es el caso canónico de regresión con Gemini. La prueba live lee su
texto directamente entre los marcadores `PROMPT_01_START` y `PROMPT_01_END`;
por tanto, este documento es la única fuente del prompt ejecutado. Cambiar ese
texto cambia deliberadamente el caso de referencia.


## 1. Fantasía canónica — caballero, princesa y dragón

**Uso:** prueba oficial de Gemini y referencia principal para comparar versiones.

**Qué pone a prueba:** construcción de un mundo fantástico, motivaciones no
triviales, agencia de los personajes, continuidad de objetos y heridas,
dependencias causales, preparación y resolución del clímax, y cumplimiento de
restricciones explícitas sin recurrir a soluciones arbitrarias.

<!-- PROMPT_01_START -->
Escribe en español un relato de fantasía épica con perfil narrativo Expansiva. Sir Aldren, un caballero veterano atormentado por el fracaso de una misión anterior, debe entrar en una fortaleza levantada sobre un volcán para rescatar a la princesa Elara de un dragón ancestral. Elara no debe ser una víctima pasiva: debe investigar su cautiverio, tomar decisiones arriesgadas y contribuir de forma decisiva a su propia liberación. El dragón debe tener una motivación comprensible relacionada con una antigua promesa rota por el reino, y no ser simplemente un monstruo malvado. Desarrolla una cadena causal clara desde la llegada del caballero hasta el enfrentamiento final; prepara con antelación cualquier objeto, conocimiento o habilidad que resulte decisivo. Mantén la continuidad de lugares, heridas, información y relaciones. Usa un tono aventurero y emotivo, incluye un dilema moral que obligue a Aldren a elegir entre obedecer al rey y hacer lo correcto, y termina con un desenlace cerrado y esperanzador. Evita el deus ex machina, las profecías que resuelven el conflicto por sí solas y las explicaciones sobre el proceso de escritura.
<!-- PROMPT_01_END -->

## 2. Fantasía mágica — el bosque de los recuerdos

**Uso:** contraste fantástico con una estructura de búsqueda y un sistema mágico
basado en costes personales.

**Qué pone a prueba:** reglas del mundo, objetos con función narrativa,
transformación interna, precio de la magia y consistencia entre información
descubierta y decisiones posteriores.

<!-- PROMPT_02_START -->
Escribe en español un relato de fantasía con perfil narrativo Desarrollada. Naira, una joven cartógrafa incapaz de usar magia, debe internarse en un bosque cuyos caminos cambian cada vez que alguien recuerda el pasado. Busca recuperar el nombre robado de su hermano antes de que él pierda por completo su identidad. En este mundo, toda magia exige entregar un recuerdo verdadero y nadie puede recuperar exactamente lo que sacrificó. Haz que Naira resuelva los obstáculos mediante observación, mapas y decisiones, no gracias a un poder oculto repentino. Incluye a una guardiana del bosque que se oponga a Naira por una razón legítima y cuya relación con ella evolucione a partir de acciones concretas. Introduce temprano al menos dos objetos que tengan usos posteriores coherentes. Mantén reglas mágicas constantes, una progresión causal clara y consecuencias visibles para cada sacrificio. Usa un tono maravilloso y melancólico, explora la tensión entre memoria e identidad y ofrece un final agridulce pero completo. Evita resurrecciones, profecías salvadoras y cambios retroactivos de las reglas.
<!-- PROMPT_02_END -->

## 3. Misterio — la última luz del faro

**Uso:** comprobar si el pipeline conserva pistas, cronología, conocimiento de
personajes y una solución deducible.

**Qué pone a prueba:** causalidad estricta, distribución de información,
referencias a lugares y objetos, falsas pistas justificadas y revelación final
sin información nueva decisiva.

<!-- PROMPT_03_START -->
Escribe en español un relato de misterio con perfil narrativo Expansiva. Durante una tormenta que deja incomunicada una pequeña isla, la archivista Mara Vela llega al faro para catalogar sus registros y descubre que el farero ha desaparecido de una habitación cerrada por dentro. En el edificio permanecen su hija, un meteorólogo, la médica de la isla y un contrabandista retirado; todos ocultan algo, pero no todos mienten sobre la desaparición. Construye un misterio de juego limpio: presenta antes de la revelación todas las pistas necesarias para deducir qué ocurrió, incluida una anotación alterada, una pieza del mecanismo del faro y una contradicción horaria. Distingue claramente lo que sabe cada personaje y mantén una cronología consistente durante la tormenta. Incluye al menos una pista falsa que tenga una explicación causal y no sea un engaño del narrador. No uses causas sobrenaturales, gemelos secretos, amnesia ni confesiones que sustituyan la investigación. Usa una atmósfera tensa y aislada, permite que Mara resuelva el caso relacionando evidencias observables y termina revelando tanto el método como el motivo y las consecuencias humanas.
<!-- PROMPT_03_END -->

## 4. Drama — el cine de los domingos

**Uso:** evaluar arcos emocionales, subtexto y causalidad sin depender de acción,
magia o tecnología extraordinaria.

**Qué pone a prueba:** relaciones familiares, objetivos incompatibles, cambios
graduales de motivación, continuidad de recuerdos y resolución ganada mediante
decisiones.

<!-- PROMPT_04_START -->
Escribe en español un drama contemporáneo con perfil narrativo Desarrollada. Tras la muerte de su madre, los hermanos Lucía y Tomás heredan un viejo cine de barrio que será demolido en siete días si no pagan una deuda. Lucía quiere venderlo y regresar a la ciudad donde construyó su carrera; Tomás quiere organizar una última función para demostrar que el lugar todavía importa. Ambos recuerdan de manera diferente el abandono de su padre y creen que la madre favoreció al otro. Desarrolla el conflicto mediante conversaciones, silencios, acciones prácticas y decisiones económicas concretas, sin convertir a ninguno de los dos en villano. Un rollo de película incompleto, una libreta de cuentas y la antigua cabina de proyección deben adquirir significado dramático y participar en la resolución. Haz que cada cambio emocional tenga una causa visible y que la verdad sobre la familia complique el conflicto en lugar de resolverlo de inmediato. Usa un tono íntimo y contenido, evita accidentes oportunistas, enfermedades repentinas y herencias secretas, y termina con una decisión conjunta creíble que implique una pérdida real y una forma limitada de reconciliación.
<!-- PROMPT_04_END -->

## 5. Ciencia ficción — la geometría del mañana

**Uso:** probar coherencia de reglas especulativas, escala del mundo y equilibrio
entre explicación, conflicto personal y consecuencias.

**Qué pone a prueba:** consistencia tecnológica, preparación de soluciones,
continuidad espacial, manejo de información desconocida y cierre temático.

<!-- PROMPT_05_START -->
Escribe en español un relato de ciencia ficción con perfil narrativo Desarrollada. Irena Sol, cartógrafa de una estación orbital envejecida, descubre que varias estrellas parecen cambiar de posición para formar un mensaje que solo es visible desde la órbita de un planeta abandonado. La estación perderá su soporte vital en cuarenta y ocho horas y su comandante quiere usar el último combustible para evacuar, mientras Irena cree que comprender el mensaje puede revelar por qué fracasó la antigua colonia. Establece reglas claras y plausibles para la observación astronómica, las comunicaciones y las limitaciones de combustible; cualquier solución final debe basarse en tecnología o datos presentados previamente. Incluye a un técnico que discrepe honestamente de Irena y cuya relación con ella cambie por las consecuencias de sus decisiones. Mantén consistentes el tiempo disponible, las distancias, los recursos y la información conocida. Usa un tono melancólico y de asombro, combina el descubrimiento científico con un conflicto humano y termina de forma esperanzadora sin viaje temporal, intervención mágica ni rescate externo inesperado.
<!-- PROMPT_05_END -->

## 6. Ciencia ficción — dinosaurios que no se extinguieron

**Uso:** comparación controlada de la extensión y la profundidad producidas por
los perfiles Esencial, Desarrollada y Expansiva mediante tres ejecuciones
independientes del pipeline completo.

**Qué pone a prueba:** adaptación tecnológica a anatomías distintas, variedad
de especies, coherencia física interna, construcción de hechos propios del mundo
y capacidad de cada perfil para ampliar la historia con contenido significativo.
La expresión «hechos reales de ese mundo» se refiere a hechos coherentes y
establecidos dentro del mundo narrativo; no exige que todos sean datos
paleontológicos del mundo real.

### Variante Esencial

<!-- PROMPT_06_ESSENTIAL_START -->
Escribe en español una historia de ciencia ficción con perfil narrativo Esencial sobre un mundo gobernado por dinosaurios que nunca se extinguieron y desarrollaron suficiente inteligencia para dominar el mundo. Narra cómo descubrieron e inventaron los mismos inventos que los humanos, pero adaptados a sus posibilidades y limitaciones físicas; por ejemplo, un dinosaurio de cuello largo no podría manejar una máquina pequeña, pero podría realizar otras tareas acordes con su anatomía. Juega con los distintos tipos y especies de dinosaurios, incorporando hechos reales de ese mundo.
<!-- PROMPT_06_ESSENTIAL_END -->

### Variante Desarrollada

<!-- PROMPT_06_DEVELOPED_START -->
Escribe en español una historia de ciencia ficción con perfil narrativo Desarrollada sobre un mundo gobernado por dinosaurios que nunca se extinguieron y desarrollaron suficiente inteligencia para dominar el mundo. Narra cómo descubrieron e inventaron los mismos inventos que los humanos, pero adaptados a sus posibilidades y limitaciones físicas; por ejemplo, un dinosaurio de cuello largo no podría manejar una máquina pequeña, pero podría realizar otras tareas acordes con su anatomía. Juega con los distintos tipos y especies de dinosaurios, incorporando hechos reales de ese mundo.
<!-- PROMPT_06_DEVELOPED_END -->

### Variante Expansiva

<!-- PROMPT_06_EXPANSIVE_START -->
Escribe en español una historia de ciencia ficción con perfil narrativo Expansiva sobre un mundo gobernado por dinosaurios que nunca se extinguieron y desarrollaron suficiente inteligencia para dominar el mundo. Narra cómo descubrieron e inventaron los mismos inventos que los humanos, pero adaptados a sus posibilidades y limitaciones físicas; por ejemplo, un dinosaurio de cuello largo no podría manejar una máquina pequeña, pero podría realizar otras tareas acordes con su anatomía. Juega con los distintos tipos y especies de dinosaurios, incorporando hechos reales de ese mundo.
<!-- PROMPT_06_EXPANSIVE_END -->

## 7. Misterio — la subasta de la falsificación

**Uso:** segunda comparación controlada de la extensión y la profundidad producidas por
los perfiles Esencial, Desarrollada y Expansiva mediante tres ejecuciones
independientes del pipeline completo, con una premisa distinta a la del prompt 6 para
que la calibración de perfiles no dependa de un único contenido.

**Qué pone a prueba:** reparto de especialidades dentro de un mismo equipo, pistas
materiales de una falsificación, presión de un plazo cerrado y capacidad de cada
perfil para ampliar la historia con subtramas y complicaciones significativas en
lugar de solo alargar la prosa.

### Variante Esencial

<!-- PROMPT_07_ESSENTIAL_START -->
Escribe en español una historia de misterio con perfil narrativo Esencial sobre un equipo de restauradores de arte que descubre, la noche antes de una subasta millonaria, que el cuadro estrella ha sido sustituido por una falsificación casi perfecta. Deben investigar quién hizo el cambio y recuperar el original antes del amanecer sin alertar a la casa de subastas ni a la policía, porque uno de los restauradores tiene una razón personal para evitar que se abra una investigación oficial. Juega con las distintas especialidades del equipo —autenticación, restauración química, logística y seguridad— y con las pistas materiales que deja una falsificación de calidad.
<!-- PROMPT_07_ESSENTIAL_END -->

### Variante Desarrollada

<!-- PROMPT_07_DEVELOPED_START -->
Escribe en español una historia de misterio con perfil narrativo Desarrollada sobre un equipo de restauradores de arte que descubre, la noche antes de una subasta millonaria, que el cuadro estrella ha sido sustituido por una falsificación casi perfecta. Deben investigar quién hizo el cambio y recuperar el original antes del amanecer sin alertar a la casa de subastas ni a la policía, porque uno de los restauradores tiene una razón personal para evitar que se abra una investigación oficial. Juega con las distintas especialidades del equipo —autenticación, restauración química, logística y seguridad— y con las pistas materiales que deja una falsificación de calidad.
<!-- PROMPT_07_DEVELOPED_END -->

### Variante Expansiva

<!-- PROMPT_07_EXPANSIVE_START -->
Escribe en español una historia de misterio con perfil narrativo Expansiva sobre un equipo de restauradores de arte que descubre, la noche antes de una subasta millonaria, que el cuadro estrella ha sido sustituido por una falsificación casi perfecta. Deben investigar quién hizo el cambio y recuperar el original antes del amanecer sin alertar a la casa de subastas ni a la policía, porque uno de los restauradores tiene una razón personal para evitar que se abra una investigación oficial. Juega con las distintas especialidades del equipo —autenticación, restauración química, logística y seguridad— y con las pistas materiales que deja una falsificación de calidad.
<!-- PROMPT_07_EXPANSIVE_END -->

## Lectura esperada de los resultados

Estos prompts no exigen que dos ejecuciones produzcan la misma prosa. La
comparación debe centrarse en propiedades observables: fidelidad al contrato,
riqueza y consistencia del mundo, referencias válidas, estructura del DAG,
continuidad entre capítulos, tratamiento de las restricciones, cumplimiento
cualitativo del perfil, métricas observadas, advertencias y consumo del modelo.
La variabilidad creativa de Gemini
es parte del experimento y debe registrarse, no ocultarse.
