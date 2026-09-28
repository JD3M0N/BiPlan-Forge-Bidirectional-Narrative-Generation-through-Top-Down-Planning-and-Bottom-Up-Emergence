// El cajón de progreso: sigue una función en marcha, en cualquier vista. Pregunta al servidor
// cada segundo por los eventos nuevos y solo añade líneas al registro, sin repintarlo.

import { api } from "../api.js";
import { state } from "../store.js";
import { append, clear, h, icon, toast } from "../ui.js";

const STEPS = [
  ["analysis", "Análisis"],
  ["world", "Mundo"],
  ["characters", "Reparto"],
  ["planning", "Plan"],
  ["promises", "Promesas"],
  ["writing", "Escritura"],
  ["casting", "Casting"],
  ["performance", "Función"],
  ["narration", "Narración"],
  ["story", "Historia"],
  ["audio", "Audio"],
];
const STAGE_TO_STEP = {
  analysis: "analysis",
  architecture: "world",
  world: "world",
  characters: "characters",
  planning: "planning",
  plan_review: "planning",
  promises: "promises",
  drafting: "writing",
  critique: "writing",
  revision: "writing",
  adaptation: "writing",
  casting: "casting",
  performance: "performance",
  narration: "narration",
  story: "story",
  audio: "audio",
  completed: "done",
};
const WARN = /fallback|failed|skipped|rejected|forced|absent|missing|rate_limit|cancel/;
const STATUS = {
  queued: "En cola",
  running: "En escena",
  completed: "Terminada",
  failed: "Falló",
  cancelled: "Cancelada",
};

let timer = null;
let lastSeq = 0;
let minimized = false;
let lastIndex = 0;
const parts = {};

export function startJob(snapshot) {
  state.job = snapshot;
  lastSeq = 0;
  lastIndex = 0;
  minimized = false;
  build(snapshot);
  update(snapshot);
  poll();
}

export async function resumeJobs() {
  try {
    const jobs = await api.jobs();
    const live = jobs.find((job) => ["queued", "running"].includes(job.status));
    if (live) startJob(live);
  } catch {
    /* sin trabajos que retomar */
  }
}

function poll() {
  clearTimeout(timer);
  timer = setTimeout(async () => {
    if (!state.job) return;
    try {
      const snapshot = await api.job(state.job.id, lastSeq);
      update(snapshot);
      if (["queued", "running"].includes(snapshot.status)) poll();
      else finish(snapshot);
    } catch {
      poll();
    }
  }, 1000);
}

function steps(storyFormat) {
  const simulated = storyFormat === "simulated";
  return STEPS.filter(([key]) => simulated || !["casting", "performance", "narration"].includes(key));
}

function build(snapshot) {
  const root = document.getElementById("drawer-root");
  clear(root);
  parts.status = h("span", { class: "eyebrow" });
  parts.title = h("strong");
  parts.spinner = h("span", { class: "spinner", "aria-hidden": "true" });
  parts.fill = h("div", { class: "bar-fill" });
  parts.description = h("p", { class: "help" });
  parts.steps = h("div", { class: "steps" });
  parts.counters = h("div", { class: "counters" });
  parts.log = h("div", { class: "log", role: "log", "aria-live": "polite" });
  parts.actions = h("div", { class: "dock-actions" });
  parts.drawer = h(
    "section",
    { class: "drawer", "aria-label": "Función en marcha" },
    h(
      "div",
      { class: "drawer-head" },
      parts.spinner,
      h("div", { class: "drawer-title" }, parts.status, parts.title),
      h(
        "button",
        {
          class: "icon-btn",
          "aria-label": "Minimizar",
          onclick: () => {
            minimized = !minimized;
            parts.drawer.classList.toggle("is-min", minimized);
          },
        },
        icon("chevron"),
      ),
    ),
    h(
      "div",
      { class: "drawer-body" },
      h("div", { class: "bar", role: "progressbar", "aria-valuemin": 0, "aria-valuemax": 100 }, parts.fill),
      parts.description,
      parts.steps,
      parts.counters,
      parts.log,
      parts.actions,
    ),
  );
  root.append(parts.drawer);
  renderActions(snapshot);
}

function renderActions(snapshot) {
  clear(parts.actions);
  const live = ["queued", "running"].includes(snapshot.status);
  if (live) {
    append(parts.actions, [
      h(
        "button",
        {
          class: "btn btn-sm btn-danger",
          disabled: snapshot.cancel_requested,
          onclick: async () => {
            try {
              update(await api.cancel(snapshot.id));
              toast("Cancelación pedida: se detendrá antes de la siguiente llamada al modelo.");
            } catch (error) {
              toast(error.message, { error: true });
            }
          },
        },
        icon("stop"),
        snapshot.cancel_requested ? "Cancelando…" : "Cancelar",
      ),
    ]);
    return;
  }
  if (snapshot.run_id) {
    append(parts.actions, [
      h(
        "a",
        { class: "btn btn-sm btn-primary", href: `#/funciones/${snapshot.collection}/${snapshot.run_id}` },
        "Abrir la función",
      ),
    ]);
  }
  append(parts.actions, [
    h(
      "button",
      {
        class: "btn btn-sm btn-ghost",
        onclick: () => {
          clear(document.getElementById("drawer-root"));
          state.job = null;
        },
      },
      "Cerrar",
    ),
  ]);
}

function update(snapshot) {
  const previous = state.job;
  state.job = snapshot;
  const progress = snapshot.progress || {};
  parts.status.textContent = STATUS[snapshot.status] || snapshot.status;
  parts.title.textContent = snapshot.title || "Función";
  parts.spinner.hidden = !["queued", "running"].includes(snapshot.status);
  parts.fill.style.width = `${Math.max(2, progress.percent || 0)}%`;
  parts.fill.parentElement.setAttribute("aria-valuenow", String(progress.percent || 0));
  parts.description.textContent =
    snapshot.status === "failed" && snapshot.error
      ? `${snapshot.error.summary} ${snapshot.error.recommendation || ""}`
      : progress.description || "";
  const current = STAGE_TO_STEP[progress.stage] || progress.stage;
  const order = steps(snapshot.story_format).map(([key]) => key);
  // A stage the stepper does not show keeps the last step reached lit, instead of none.
  const found = current === "done" ? order.length : order.indexOf(current);
  if (found >= 0) lastIndex = found;
  const index = found >= 0 ? found : lastIndex;
  clear(parts.steps);
  append(
    parts.steps,
    steps(snapshot.story_format).map(([key, label], position) =>
      h("span", {
        class: `step${position < index ? " is-done" : ""}${position === index ? " is-current" : ""}`,
        text: label,
      }),
    ),
  );
  clear(parts.counters);
  append(parts.counters, [
    h("span", {}, h("strong", { text: String(snapshot.counters?.agents ?? 0) }), " llamadas a agentes"),
    snapshot.story_format === "simulated"
      ? h("span", {}, h("strong", { text: String(snapshot.counters?.turns ?? 0) }), " turnos representados")
      : null,
  ]);
  for (const event of snapshot.events || []) {
    lastSeq = Math.max(lastSeq, event.seq);
    const warn = WARN.test(event.kind);
    parts.log.append(
      h(
        "div",
        { class: `log-line${warn ? " is-warn" : ""}` },
        h("span", { class: "log-stage", text: `${event.stage || "—"} · ` }),
        event.message,
      ),
    );
  }
  while (parts.log.childElementCount > 300) parts.log.firstElementChild.remove();
  parts.log.scrollTop = parts.log.scrollHeight;
  if (!previous || previous.status !== snapshot.status || previous.cancel_requested !== snapshot.cancel_requested) {
    renderActions(snapshot);
  }
}

function finish(snapshot) {
  renderActions(snapshot);
  if (snapshot.status === "completed") {
    toast("La función ha terminado.", {
      action: snapshot.run_id
        ? { label: "Abrir", href: `#/funciones/${snapshot.collection}/${snapshot.run_id}` }
        : null,
      timeout: 9000,
    });
  } else if (snapshot.status === "failed") {
    toast(snapshot.error?.summary || "La función falló.", { error: true, timeout: 9000 });
  } else if (snapshot.status === "cancelled") {
    toast("Función cancelada.");
  }
}
