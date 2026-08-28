# Prompts canónicos para probar el pipeline Top-Down

Este catálogo contiene cinco solicitudes narrativas estables para observar cómo
cambia el resultado cuando se modifica el pipeline. Todos los casos solicitan
aproximadamente 2500 palabras, pero no fijan el número de capítulos: esa decisión
queda en manos de la lógica vigente del generador.

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
Escribe en español un relato de fantasía épica de aproximadamente 2500 palabras. Sir Aldren, un caballero veterano atormentado por el fracaso de una misión anterior, debe entrar en una fortaleza levantada sobre un volcán para rescatar a la princesa Elara de un dragón ancestral. Elara no debe ser una víctima pasiva: debe investigar su cautiverio, tomar decisiones arriesgadas y contribuir de forma decisiva a su propia liberación. El dragón debe tener una motivación comprensible relacionada con una antigua promesa rota por el reino, y no ser simplemente un monstruo malvado. Desarrolla una cadena causal clara desde la llegada del caballero hasta el enfrentamiento final; prepara con antelación cualquier objeto, conocimiento o habilidad que resulte decisivo. Mantén la continuidad de lugares, heridas, información y relaciones. Usa un tono aventurero y emotivo, incluye un dilema moral que obligue a Aldren a elegir entre obedecer al rey y hacer lo correcto, y termina con un desenlace cerrado y esperanzador. Evita el deus ex machina, las profecías que resuelven el conflicto por sí solas y las explicaciones sobre el proceso de escritura.
<!-- PROMPT_01_END -->

## 2. Fantasía mágica — el bosque de los recuerdos

**Uso:** contraste fantástico con una estructura de búsqueda y un sistema mágico
basado en costes personales.

**Qué pone a prueba:** reglas del mundo, objetos con función narrativa,
transformación interna, precio de la magia y consistencia entre información
descubierta y decisiones posteriores.

<!-- PROMPT_02_START -->
Escribe en español un relato de fantasía de aproximadamente 2500 palabras. Naira, una joven cartógrafa incapaz de usar magia, debe internarse en un bosque cuyos caminos cambian cada vez que alguien recuerda el pasado. Busca recuperar el nombre robado de su hermano antes de que él pierda por completo su identidad. En este mundo, toda magia exige entregar un recuerdo verdadero y nadie puede recuperar exactamente lo que sacrificó. Haz que Naira resuelva los obstáculos mediante observación, mapas y decisiones, no gracias a un poder oculto repentino. Incluye a una guardiana del bosque que se oponga a Naira por una razón legítima y cuya relación con ella evolucione a partir de acciones concretas. Introduce temprano al menos dos objetos que tengan usos posteriores coherentes. Mantén reglas mágicas constantes, una progresión causal clara y consecuencias visibles para cada sacrificio. Usa un tono maravilloso y melancólico, explora la tensión entre memoria e identidad y ofrece un final agridulce pero completo. Evita resurrecciones, profecías salvadoras y cambios retroactivos de las reglas.
<!-- PROMPT_02_END -->

## 3. Misterio — la última luz del faro

**Uso:** comprobar si el pipeline conserva pistas, cronología, conocimiento de
personajes y una solución deducible.

**Qué pone a prueba:** causalidad estricta, distribución de información,
referencias a lugares y objetos, falsas pistas justificadas y revelación final
sin información nueva decisiva.

<!-- PROMPT_03_START -->
Escribe en español un relato de misterio de aproximadamente 2500 palabras. Durante una tormenta que deja incomunicada una pequeña isla, la archivista Mara Vela llega al faro para catalogar sus registros y descubre que el farero ha desaparecido de una habitación cerrada por dentro. En el edificio permanecen su hija, un meteorólogo, la médica de la isla y un contrabandista retirado; todos ocultan algo, pero no todos mienten sobre la desaparición. Construye un misterio de juego limpio: presenta antes de la revelación todas las pistas necesarias para deducir qué ocurrió, incluida una anotación alterada, una pieza del mecanismo del faro y una contradicción horaria. Distingue claramente lo que sabe cada personaje y mantén una cronología consistente durante la tormenta. Incluye al menos una pista falsa que tenga una explicación causal y no sea un engaño del narrador. No uses causas sobrenaturales, gemelos secretos, amnesia ni confesiones que sustituyan la investigación. Usa una atmósfera tensa y aislada, permite que Mara resuelva el caso relacionando evidencias observables y termina revelando tanto el método como el motivo y las consecuencias humanas.
<!-- PROMPT_03_END -->

## 4. Drama — el cine de los domingos

**Uso:** evaluar arcos emocionales, subtexto y causalidad sin depender de acción,
magia o tecnología extraordinaria.

**Qué pone a prueba:** relaciones familiares, objetivos incompatibles, cambios
graduales de motivación, continuidad de recuerdos y resolución ganada mediante
decisiones.

<!-- PROMPT_04_START -->
Escribe en español un drama contemporáneo de aproximadamente 2500 palabras. Tras la muerte de su madre, los hermanos Lucía y Tomás heredan un viejo cine de barrio que será demolido en siete días si no pagan una deuda. Lucía quiere venderlo y regresar a la ciudad donde construyó su carrera; Tomás quiere organizar una última función para demostrar que el lugar todavía importa. Ambos recuerdan de manera diferente el abandono de su padre y creen que la madre favoreció al otro. Desarrolla el conflicto mediante conversaciones, silencios, acciones prácticas y decisiones económicas concretas, sin convertir a ninguno de los dos en villano. Un rollo de película incompleto, una libreta de cuentas y la antigua cabina de proyección deben adquirir significado dramático y participar en la resolución. Haz que cada cambio emocional tenga una causa visible y que la verdad sobre la familia complique el conflicto en lugar de resolverlo de inmediato. Usa un tono íntimo y contenido, evita accidentes oportunistas, enfermedades repentinas y herencias secretas, y termina con una decisión conjunta creíble que implique una pérdida real y una forma limitada de reconciliación.
<!-- PROMPT_04_END -->

## 5. Ciencia ficción — la geometría del mañana

**Uso:** probar coherencia de reglas especulativas, escala del mundo y equilibrio
entre explicación, conflicto personal y consecuencias.

**Qué pone a prueba:** consistencia tecnológica, preparación de soluciones,
continuidad espacial, manejo de información desconocida y cierre temático.

<!-- PROMPT_05_START -->
Escribe en español un relato de ciencia ficción de aproximadamente 2500 palabras. Irena Sol, cartógrafa de una estación orbital envejecida, descubre que varias estrellas parecen cambiar de posición para formar un mensaje que solo es visible desde la órbita de un planeta abandonado. La estación perderá su soporte vital en cuarenta y ocho horas y su comandante quiere usar el último combustible para evacuar, mientras Irena cree que comprender el mensaje puede revelar por qué fracasó la antigua colonia. Establece reglas claras y plausibles para la observación astronómica, las comunicaciones y las limitaciones de combustible; cualquier solución final debe basarse en tecnología o datos presentados previamente. Incluye a un técnico que discrepe honestamente de Irena y cuya relación con ella cambie por las consecuencias de sus decisiones. Mantén consistentes el tiempo disponible, las distancias, los recursos y la información conocida. Usa un tono melancólico y de asombro, combina el descubrimiento científico con un conflicto humano y termina de forma esperanzadora sin viaje temporal, intervención mágica ni rescate externo inesperado.
<!-- PROMPT_05_END -->

## Lectura esperada de los resultados

Estos prompts no exigen que dos ejecuciones produzcan la misma prosa. La
comparación debe centrarse en propiedades observables: fidelidad al contrato,
riqueza y consistencia del mundo, referencias válidas, estructura del DAG,
continuidad entre capítulos, tratamiento de las restricciones, auditoría de
longitud, advertencias y consumo del modelo. La variabilidad creativa de Gemini
es parte del experimento y debe registrarse, no ocultarse.
