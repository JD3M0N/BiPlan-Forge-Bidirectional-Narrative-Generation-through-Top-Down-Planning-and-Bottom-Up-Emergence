// Funciones: todas las funciones guardadas, con filtros y una bandeja para compararlas.

import { api } from "../api.js";
import { state, togglePick } from "../store.js";
import { append, clear, formatDate, h, icon, labelsFrom } from "../ui.js";

const FORMATS = [
  ["", "Todas"],
  ["simulated", "Simuladas"],
  ["narrative", "Narrativas"],
  ["script", "Guiones"],
];

export function badges(run, labels) {
  const items = [];
  items.push([labels.format[run.story_format] || run.story_format || "¿formato?", true]);
  if (run.story_format === "simulated") {
    if (run.narrative_voice) items.push([labels.voice[run.narrative_voice] || run.narrative_voice]);
    if (run.actor_memory) items.push([labels.memory[run.actor_memory] || run.actor_memory]);
  }
  if (run.narrative_profile) items.push([labels.profile[run.narrative_profile] || run.narrative_profile]);
  if (run.pipeline_version) items.push([`v${run.pipeline_version}`]);
  const status = { failed: "falló", running: "en curso" }[run.status] || run.status;
  if (run.status !== "completed") items.push([status, false, true]);
  return h(
    "div",
    { class: "badges" },
    items.map(([text, accent, bad]) =>
      h("span", { class: `badge${accent ? " is-accent" : ""}${bad ? " is-bad" : ""}`, text }),
    ),
  );
}

export function renderLibrary(container) {
  const labels = labelsFrom(state.catalog);
  const filters = { collection: "Stagecraft", format: "", query: "" };
  const grid = h("div", { class: "runs" });
  const tray = h("div");

  function renderTray() {
    clear(tray);
    if (!state.picks.length) return;
    append(tray, [
      h(
        "div",
        { class: "tray" },
        h("span", { text: `${state.picks.length} para comparar` }),
        h(
          "a",
          {
            class: "btn btn-sm btn-primary",
            href: `#/comparar?runs=${encodeURIComponent(state.picks.join(","))}`,
            "aria-disabled": String(state.picks.length < 2),
          },
          icon("compare"),
          "Comparar",
        ),
      ),
    ]);
  }

  function renderGrid() {
    clear(grid);
    if (!state.runs) {
      append(grid, [1, 2, 3, 4, 5, 6].map(() => h("div", { class: "skeleton" })));
      return;
    }
    const query = filters.query.trim().toLowerCase();
    const runs = state.runs.filter(
      (run) =>
        (!filters.collection || run.collection === filters.collection) &&
        (!filters.format || run.story_format === filters.format) &&
        (!query || `${run.title} ${run.run_id}`.toLowerCase().includes(query)),
    );
    if (!runs.length) {
      append(grid, [h("div", { class: "empty" }, "No hay funciones con estos filtros.")]);
      return;
    }
    for (const run of runs) {
      const reference = `${run.collection}/${run.run_id}`;
      const picked = state.picks.includes(reference);
      const pick = h("input", {
        type: "checkbox",
        class: "switch pick",
        checked: picked,
        "aria-label": `Comparar ${run.title}`,
        onclick: (event) => {
          event.stopPropagation();
          togglePick(reference);
          renderGrid();
          renderTray();
        },
      });
      append(grid, [
        h(
          "a",
          { class: `run${picked ? " is-picked" : ""}`, href: `#/funciones/${reference}` },
          pick,
          h("h3", { class: "run-title", text: run.title }),
          h(
            "div",
            { class: "run-meta" },
            [formatDate(run.created_at), run.words ? `${run.words.toLocaleString("es-ES")} palabras` : null, run.model]
              .filter(Boolean)
              .join(" · "),
          ),
          badges(run, labels),
        ),
      ]);
    }
  }

  const collectionSelect = h(
    "select",
    {
      class: "select",
      "aria-label": "Colección",
      value: filters.collection,
      onchange: (event) => {
        filters.collection = event.target.value;
        renderGrid();
      },
    },
    h("option", { value: "Stagecraft", text: "Stagecraft" }),
    h("option", { value: "Top-Down", text: "Top-Down (histórico)" }),
    h("option", { value: "", text: "Todas las colecciones" }),
  );
  const formatButtons = FORMATS.map(([value, text]) =>
    h("button", {
      type: "button",
      class: "filter",
      "aria-pressed": String(filters.format === value),
      text,
      onclick: (event) => {
        filters.format = value;
        for (const button of event.target.parentElement.querySelectorAll(".filter")) {
          button.setAttribute("aria-pressed", String(button === event.target));
        }
        renderGrid();
      },
    }),
  );

  append(clear(container), [
    h(
      "div",
      { class: "page-head" },
      h(
        "div",
        {},
        h("h1", { class: "page-title", text: "Funciones" }),
        h("p", { class: "page-sub", text: "Cada función guardada, con su obra, su configuración y sus cifras." }),
      ),
    ),
    h(
      "div",
      { class: "toolbar" },
      h("input", {
        class: "input",
        type: "search",
        placeholder: "Buscar por título…",
        "aria-label": "Buscar",
        oninput: (event) => {
          filters.query = event.target.value;
          renderGrid();
        },
      }),
      collectionSelect,
      h("div", { class: "summary", role: "group", "aria-label": "Formato" }, formatButtons),
    ),
    grid,
    tray,
  ]);
  renderGrid();
  renderTray();
  // Always read the list again: a run may have finished since it was last shown.
  {
    api
      .runs()
      .then((runs) => {
        state.runs = runs;
        renderGrid();
      })
      .catch((error) => {
        clear(grid);
        append(grid, [h("div", { class: "empty" }, error.message)]);
      });
  }
}
