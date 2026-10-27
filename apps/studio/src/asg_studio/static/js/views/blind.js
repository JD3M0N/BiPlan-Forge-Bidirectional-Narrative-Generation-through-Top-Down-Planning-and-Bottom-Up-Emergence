// Lectura ciega: dos historias anónimas, X e Y, lado a lado, y un voto por par (X, Y o «no
// distingo»). Nunca enseña de dónde sale cada historia: el servidor no manda ni run_id, ni
// título, ni ejes. Atajos: ← → para moverse, 1 = X, 2 = Y, 3 = no distingo.
//   #/ciega · #/ciega/<lectura>/<par> · #/ciega/<lectura>/fin

import { api } from "../api.js";
import { append, clear, h, toast } from "../ui.js";

const CHOICES = [
  { value: "x", label: "Prefiero X", key: "1" },
  { value: "ninguno", label: "No distingo", key: "3" },
  { value: "y", label: "Prefiero Y", key: "2" },
];

export function renderBlind(container, parts) {
  const [, name, which] = parts;
  if (!name) return renderSessions(container);
  if (which === "fin") return renderEnd(container, name);
  return renderPair(container, name, Number.parseInt(which, 10) || 1);
}

function head(title, sub) {
  return h(
    "div",
    { class: "page-head" },
    h("div", {}, h("h1", { class: "page-title", text: title }), sub ? h("p", { class: "page-sub", text: sub }) : null),
  );
}

function renderSessions(container) {
  append(clear(container), [head("Lectura ciega"), h("div", { class: "skeleton" })]);
  api
    .readings()
    .then((sessions) => {
      const intro = head(
        "Lectura ciega",
        "Lee cada par sin saber qué mecanismo generó cada historia y elige cuál te gustó más.",
      );
      if (!sessions.length) {
        append(clear(container), [
          intro,
          h("div", { class: "empty" }, "No hay lecturas preparadas en Evaluations/estudio/lecturas."),
        ]);
        return;
      }
      append(clear(container), [
        intro,
        h(
          "div",
          { class: "blind-list" },
          sessions.map((session) =>
            h(
              "a",
              { class: "blind-session", href: `#/ciega/${encodeURIComponent(session.name)}/${next(session)}` },
              h("strong", { text: session.name }),
              h("span", {
                class: "blind-progress",
                text: `${session.voted} de ${session.total} pares votados`,
              }),
            ),
          ),
        ),
      ]);
    })
    .catch((error) => append(clear(container), [head("Lectura ciega"), h("div", { class: "empty" }, error.message)]));
}

function next(session) {
  return session.voted >= session.total ? "fin" : Math.min(session.voted + 1, session.total);
}

function renderPair(container, name, number) {
  append(clear(container), [head("Lectura ciega"), h("div", { class: "skeleton" })]);
  let active = true;
  let current = null;

  const go = (target) => {
    location.hash = `#/ciega/${encodeURIComponent(name)}/${target}`;
  };

  async function cast(winner) {
    if (!current) return;
    try {
      await api.vote(name, current.number, winner);
    } catch (error) {
      toast(error.message, { error: true });
      return;
    }
    if (current.number >= current.total) go("fin");
    else go(current.number + 1);
  }

  const onKey = (event) => {
    if (!active || !current || event.ctrlKey || event.metaKey || event.altKey) return;
    if (event.target instanceof HTMLElement && /^(INPUT|TEXTAREA|SELECT)$/.test(event.target.tagName)) return;
    if (event.key === "ArrowLeft" && current.number > 1) go(current.number - 1);
    else if (event.key === "ArrowRight" && current.number < current.total) go(current.number + 1);
    else {
      const choice = CHOICES.find((item) => item.key === event.key);
      if (choice) cast(choice.value);
    }
  };
  document.addEventListener("keydown", onKey);

  api
    .readingPair(name, number)
    .then((pair) => {
      current = pair;
      const column = (letter, story) =>
        h(
          "section",
          { class: "blind-col", "aria-label": `Historia ${letter}` },
          h("h2", { class: "blind-label", text: `Historia ${letter}` }),
          h(
            "div",
            { class: "prose blind-prose" },
            story.chapters.map((chapter) => [
              chapter.title ? h("h2", { text: chapter.title }) : null,
              chapter.paragraphs.map((text) => h("p", { text })),
            ]),
          ),
        );
      const bar = h(
        "div",
        { class: "blind-bar" },
        h("button", {
          class: "btn btn-ghost",
          type: "button",
          disabled: pair.number <= 1,
          onclick: () => go(pair.number - 1),
          text: "← Anterior",
        }),
        h("span", { class: "blind-count", text: `Par ${pair.number} de ${pair.total}` }),
        CHOICES.map((choice) =>
          h("button", {
            class: `btn ${pair.vote === choice.value ? "btn-primary" : "btn-ghost"}`,
            type: "button",
            title: `Atajo: ${choice.key}`,
            onclick: () => cast(choice.value),
            text: choice.label,
          }),
        ),
        h("button", {
          class: "btn btn-ghost",
          type: "button",
          disabled: pair.number >= pair.total,
          onclick: () => go(pair.number + 1),
          text: "Siguiente →",
        }),
      );
      append(clear(container), [
        head(
          "Lectura ciega",
          pair.vote
            ? "Ya votaste este par; puedes cambiar el voto."
            : "Lee las dos y elige. Atajos: 1 = X, 2 = Y, 3 = no distingo; ← → para moverte.",
        ),
        h("div", { class: "blind-pair" }, column("X", pair.x), column("Y", pair.y)),
        bar,
      ]);
    })
    .catch((error) => append(clear(container), [head("Lectura ciega"), h("div", { class: "empty" }, error.message)]));

  return () => {
    active = false;
    document.removeEventListener("keydown", onKey);
  };
}

function renderEnd(container, name) {
  append(clear(container), [head("Lectura ciega"), h("div", { class: "skeleton" })]);
  api
    .readings()
    .then((sessions) => {
      const session = sessions.find((item) => item.name === name);
      if (!session) throw new Error("No existe esa lectura.");
      const pending = session.voted < session.total;
      append(clear(container), [
        head(
          pending ? "Faltan pares por votar" : "Lectura terminada",
          `${session.voted} de ${session.total} pares votados. Los votos están guardados.`,
        ),
        h(
          "div",
          { class: "blind-end" },
          Array.from({ length: session.total }, (_, index) =>
            h("a", { class: "btn btn-ghost", href: `#/ciega/${encodeURIComponent(name)}/${index + 1}`, text: `Par ${index + 1}` }),
          ),
        ),
      ]);
    })
    .catch((error) => append(clear(container), [head("Lectura ciega"), h("div", { class: "empty" }, error.message)]));
}
