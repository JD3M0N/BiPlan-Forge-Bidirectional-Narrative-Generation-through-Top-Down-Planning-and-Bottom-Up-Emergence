// Comparar: de dos a cuatro funciones eje por eje. Resalta lo que difiere, dice si la
// comparación está emparejada y pone las cifras lado a lado, con «no medido» donde falten.

import { api } from "../api.js";
import { setPicks, state } from "../store.js";
import { append, clear, formatNumber, h, labelsFrom } from "../ui.js";
import { axisValue } from "./reader.js";

export function renderCompare(container, params) {
  const labels = labelsFrom(state.catalog);
  const requested = (params.get("runs") || "").split(",").filter(Boolean);
  const references = requested.length ? requested : state.picks;
  if (requested.length) setPicks(requested);

  const head = h(
    "div",
    { class: "page-head" },
    h(
      "div",
      {},
      h("h1", { class: "page-title", text: "Comparar funciones" }),
      h("p", {
        class: "page-sub",
        text: "Una comparación limpia: misma obra, mismo modelo y mismo perfil, y un solo eje distinto.",
      }),
    ),
  );

  if (references.length < 2) {
    append(clear(container), [
      head,
      h(
        "div",
        { class: "empty" },
        "Elige al menos dos funciones en ",
        h("a", { href: "#/funciones", text: "Funciones" }),
        " con su interruptor, o usa «Comparar» desde el lector de una función.",
      ),
    ]);
    return;
  }

  append(clear(container), [head, h("div", { class: "skeleton" })]);
  api
    .compare(references)
    .then((data) => draw(data))
    .catch((error) => append(clear(container), [head, h("div", { class: "empty" }, error.message)]));

  function draw(data) {
    const works = {};
    const letter = (digest) => {
      if (!digest) return "no registrado";
      if (!(digest in works)) works[digest] = `Obra ${String.fromCharCode(65 + Object.keys(works).length)}`;
      return works[digest];
    };
    const arms = data.differing_axes.filter((key) => !["work", "model", "narrative_profile"].includes(key));
    const label = Object.fromEntries(data.axes.map((axis) => [axis.key, axis.label]));
    const banner = h(
      "div",
      { class: `banner${data.clean ? " is-clean" : ""}` },
      h(
        "div",
        {},
        h("strong", {
          text: data.clean
            ? `Comparación limpia: difieren solo en ${label[arms[0]].toLowerCase()}.`
            : data.differing_axes.length
              ? `Difieren en ${data.differing_axes.length} ${data.differing_axes.length === 1 ? "eje" : "ejes"}: ${data.differing_axes.map((key) => label[key].toLowerCase()).join(", ")}.`
              : "No difieren en ningún eje registrado.",
        }),
        data.warnings.length ? h("ul", {}, data.warnings.map((text) => h("li", { text }))) : null,
      ),
    );
    const columns = h(
      "tr",
      {},
      h("th", { text: "" }),
      data.runs.map((run) =>
        h(
          "th",
          {},
          h("a", { href: `#/funciones/${run.reference}`, text: run.title }),
          h("div", { class: "run-meta", text: run.pipeline_version ? `v${run.pipeline_version}` : "" }),
        ),
      ),
    );
    const axisRows = data.axes.map((axis) => {
      const values = data.runs.map((run) =>
        axis.key === "work" ? letter(run.axes.work) : axisValue(axis.key, run.axes[axis.key], labels),
      );
      const applies = data.runs.map(
        (run) => !axis.formats.length || axis.formats.includes(run.axes.story_format),
      );
      return h(
        "tr",
        { class: data.differing_axes.includes(axis.key) ? "is-diff" : "" },
        h("th", { text: axis.label }),
        values.map((value, index) =>
          h("td", { class: applies[index] ? "" : "muted", text: applies[index] ? value : "no aplica" }),
        ),
      );
    });
    const narratedRow = h(
      "tr",
      {},
      h("th", { text: "Narró" }),
      data.runs.map((run) => h("td", { class: run.narrated_by ? "" : "muted", text: run.narrated_by || "—" })),
    );
    const metricRows = [];
    let group = "";
    for (const metric of data.metrics) {
      if (metric.group !== group) {
        group = metric.group;
        metricRows.push(h("tr", { class: "group-row" }, h("th", { colspan: data.runs.length + 1, text: group })));
      }
      const known = metric.values.filter((value) => value !== null);
      const differs = new Set(known).size > 1;
      metricRows.push(
        h(
          "tr",
          { class: differs ? "is-diff" : "" },
          h("th", { text: metric.label }),
          metric.values.map((value) => h("td", { class: value === null ? "muted" : "", text: formatNumber(value) })),
        ),
      );
    }
    append(clear(container), [
      head,
      banner,
      h("p", { class: "eyebrow section-label", text: "Configuración" }),
      h(
        "div",
        { class: "table-wrap" },
        h("table", { class: "table" }, h("thead", {}, columns), h("tbody", {}, axisRows, narratedRow)),
      ),
      h("p", { class: "eyebrow section-label", text: "Cifras" }),
      h(
        "div",
        { class: "table-wrap" },
        h("table", { class: "table" }, h("thead", {}, columns.cloneNode(true)), h("tbody", {}, metricRows)),
      ),
      h("p", {
        class: "hint",
        text: "Las cifras de los jueces LLM son indicio, no medida; con una función por brazo, cualquier diferencia es solo una pista.",
      }),
    ]);
  }
}
