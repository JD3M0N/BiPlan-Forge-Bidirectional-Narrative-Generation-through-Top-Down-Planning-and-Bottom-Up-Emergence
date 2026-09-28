// Arranque de StageCraft: estado del servidor, catálogo de opciones y enrutado por el hash.
//   #/crear · #/funciones · #/funciones/<colección>/<función> · #/comparar?runs=a,b

import { api } from "./api.js";
import { state } from "./store.js";
import { append, clear, h, toast } from "./ui.js";
import { renderCompare } from "./views/compare.js";
import { renderCreate } from "./views/create.js";
import { renderLibrary } from "./views/library.js";
import { resumeJobs } from "./views/progress.js";
import { renderReader } from "./views/reader.js";

const view = document.getElementById("view");
let cleanup = null;

function route() {
  if (typeof cleanup === "function") cleanup();
  cleanup = null;
  const hash = location.hash.replace(/^#\/?/, "") || "crear";
  const [path, query = ""] = hash.split("?");
  const parts = path.split("/").map(decodeURIComponent);
  const params = new URLSearchParams(query);
  const name = parts[0] || "crear";
  for (const tab of document.querySelectorAll(".tab")) {
    if (tab.dataset.view === name) tab.setAttribute("aria-current", "page");
    else tab.removeAttribute("aria-current");
  }
  if (name === "funciones" && parts.length >= 3) {
    renderReader(view, parts[1], parts[2]);
  } else if (name === "funciones") {
    renderLibrary(view);
  } else if (name === "comparar") {
    renderCompare(view, params);
  } else {
    cleanup = renderCreate(view);
  }
  window.scrollTo({ top: 0 });
}

function showStatus(health) {
  const status = document.getElementById("status");
  const text = status.querySelector(".status-text");
  status.classList.toggle("is-ready", health.key_present || health.demo);
  status.classList.toggle("is-missing", !health.key_present && !health.demo);
  text.textContent = health.demo
    ? "Demostración · sin llamadas al modelo"
    : health.key_present
      ? `${health.model} · Stagecraft ${health.generator_version}`
      : "Falta GEMINI_API_KEY en .env";
  status.title = health.key_present
    ? "Lista para generar."
    : "Puedes explorar y comparar; para generar hace falta la clave de Gemini.";
  if (health.demo) {
    document.querySelector(".brand").append(h("span", { class: "demo-chip", text: "DEMO" }));
  }
}

async function boot() {
  try {
    const [health, catalog] = await Promise.all([api.health(), api.catalog()]);
    state.health = health;
    state.catalog = catalog;
    showStatus(health);
  } catch (error) {
    append(clear(view), [h("div", { class: "empty" }, `No se pudo contactar con StageCraft: ${error.message}`)]);
    return;
  }
  window.addEventListener("hashchange", route);
  route();
  resumeJobs();
  if (!state.health.key_present && !state.health.demo) {
    toast("Sin GEMINI_API_KEY no se puede estrenar, pero sí explorar y comparar funciones.", {
      timeout: 8000,
    });
  }
}

boot();
