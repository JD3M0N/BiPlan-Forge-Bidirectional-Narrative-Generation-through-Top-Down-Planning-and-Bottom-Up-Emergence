// El lector de una función: la historia, el log de la función visto desde una visión, sus
// cifras y su configuración. Todo el texto del modelo se pinta con textContent.

import { api } from "../api.js";
import { state, togglePick } from "../store.js";
import { append, clear, formatDate, formatNumber, h, icon, labelsFrom, toast } from "../ui.js";
import { normalizeForm } from "./create.js";
import { badges } from "./library.js";

const AXIS_LABELS = {
  work: "Obra",
  model: "Modelo",
  narrative_profile: "Perfil",
  story_format: "Formato",
  script_method: "Método del guion",
  narrative_voice: "Visión",
  narrator: "Personaje de la visión",
  narration_tone: "Tono del narrador",
  actor_memory: "Memoria de los actores",
  inventory: "Inventario de objetos",
  turns_per_beat: "Turnos por beat",
  promise_ledger: "Ledger de promesas",
  narrative_guidance: "Guía de esqueletos",
  audio_voice: "Voz del audio",
};

export function axisValue(key, value, labels) {
  if (value === null || value === undefined) return "no registrado";
  if (value === true) return "Sí";
  if (value === false) return "No";
  if (value === "") return key === "audio_voice" ? "Automática" : key === "narrator" ? "Automático" : "—";
  if (key === "story_format") return labels.format[value] || value;
  if (key === "script_method") return labels.method[value] || value;
  if (key === "narrative_voice") return labels.voice[value] || value;
  if (key === "actor_memory") return labels.memory[value] || value;
  if (key === "narrative_profile") return labels.profile[value] || value;
  if (key === "audio_voice") return labels.audioVoice[value] || value;
  return String(value);
}

export function renderReader(container, collection, runId) {
  const labels = labelsFrom(state.catalog);
  const body = h("div");
  let detail = null;
  let tab = "historia";

  append(clear(container), [h("div", { class: "skeleton" })]);

  api
    .run(collection, runId)
    .then((data) => {
      detail = data;
      draw();
    })
    .catch((error) => {
      append(clear(container), [
        h("div", { class: "empty" }, error.message, " ", h("a", { href: "#/funciones" }, "Volver")),
      ]);
    });

  function draw() {
    const reference = `${collection}/${runId}`;
    const tabs = [
      ["historia", "Historia"],
      ["funcion", "Función", detail.has_performance],
      ["cifras", "Cifras"],
      ["configuracion", "Configuración"],
    ].filter((item) => item[2] !== false);
    append(clear(container), [
      h(
        "div",
        { class: "page-head" },
        h(
          "div",
          {},
          h("p", { class: "eyebrow" }, h("a", { href: "#/funciones", text: "Funciones" }), ` · ${collection}`),
          h("h1", { class: "page-title", text: detail.title }),
          h("p", { class: "page-sub", text: [formatDate(detail.created_at), detail.model].filter(Boolean).join(" · ") }),
          badges(detail, labels),
        ),
        h(
          "div",
          { class: "dock-actions" },
          h(
            "button",
            {
              class: "btn btn-ghost",
              onclick: () => {
                togglePick(reference);
                toast(state.picks.includes(reference) ? "Añadida a Comparar." : "Quitada de Comparar.");
              },
            },
            icon("compare"),
            "Comparar",
          ),
          h(
            "button",
            {
              class: "btn btn-primary",
              onclick: async () => {
                try {
                  state.form = normalizeForm(await api.replay(collection, runId), state.catalog);
                  location.hash = "#/crear";
                  toast("Misma obra y misma configuración: cambia un eje y estrena.");
                } catch (error) {
                  toast(error.message, { error: true });
                }
              },
            },
            icon("repeat"),
            "Repetir con otra configuración",
          ),
        ),
      ),
      detail.error
        ? h("div", { class: "banner" }, h("div", {}, h("strong", { text: `No terminó: ${detail.error_code}` }), h("ul", {}, h("li", { text: detail.error }))))
        : null,
      h(
        "div",
        { class: "reader-tabs", role: "tablist" },
        tabs.map(([key, text]) =>
          h("button", {
            class: "reader-tab",
            role: "tab",
            "aria-selected": String(tab === key),
            text,
            onclick: () => {
              tab = key;
              draw();
            },
          }),
        ),
      ),
      body,
    ]);
    clear(body);
    if (tab === "historia") drawStory();
    else if (tab === "funcion") drawPerformance();
    else if (tab === "cifras") drawMetrics();
    else drawConfig();
  }

  function drawStory() {
    const story = detail.story;
    if (!story.chapters.length) {
      append(body, [h("div", { class: "empty" }, "Esta función no llegó a escribir su historia.")]);
      return;
    }
    const prose = h("article", { class: "prose" });
    if (detail.has_audio) {
      append(body, [h("audio", { class: "audio", controls: true, preload: "none", src: api.audioUrl(collection, runId) })]);
    }
    append(prose, [h("h1", { text: story.title || detail.title })]);
    for (const chapter of story.chapters) {
      if (chapter.title) append(prose, [h("h2", { text: chapter.title })]);
      append(prose, chapter.paragraphs.map((text) => h("p", { text })));
    }
    append(body, [prose]);
  }

  function drawPerformance() {
    const voiceOption = labels.option.narrative_voice;
    const voices = voiceOption.choices.filter((choice) => choice.status !== "pending");
    const controls = { voice: "", narrator: "" };
    const scenes = h("div");
    const narratorSelect = h("select", { class: "select", "aria-label": "Personaje", disabled: true });
    const voiceSelect = h(
      "select",
      {
        class: "select",
        "aria-label": "Ver como",
        onchange: (event) => {
          controls.voice = event.target.value;
          const takes = voices.find((choice) => choice.value === controls.voice)?.takes_character;
          narratorSelect.disabled = !takes;
          load();
        },
      },
      h("option", { value: "", text: "Todo el log, sin visión" }),
      voices.map((choice) => h("option", { value: choice.value, text: choice.label })),
    );
    narratorSelect.addEventListener("change", (event) => {
      controls.narrator = event.target.value;
      load();
    });

    function load() {
      api
        .performance(collection, runId, controls.voice, controls.narrator)
        .then((data) => {
          if (!narratorSelect.childElementCount) {
            append(narratorSelect, data.cast.map((member) => h("option", { value: member.name, text: member.name })));
          }
          if (data.narrator) narratorSelect.value = (data.cast.find((member) => member.id === data.narrator) || {}).name || "";
          drawScenes(data);
        })
        .catch((error) => {
          append(clear(scenes), [h("div", { class: "empty" }, error.message)]);
        });
    }

    function drawScenes(data) {
      clear(scenes);
      const total = data.scenes.reduce((sum, scene) => sum + scene.turns.length, 0);
      const seen = data.scenes.reduce((sum, scene) => sum + scene.turns.filter((turn) => turn.visible).length, 0);
      if (data.voice) {
        append(scenes, [h("p", { class: "hint is-accent", text: `Esta visión ve ${seen} de ${total} turnos. Lo atenuado no llega al narrador.` })]);
      }
      for (const scene of data.scenes) {
        append(scenes, [
          h(
            "section",
            { class: "scene" },
            h("div", { class: "scene-head" }, h("strong", { text: scene.scene_id }), scene.setting ? ` · ${scene.setting}` : ""),
            scene.turns.map((turn) =>
              h(
                "div",
                { class: `turn${turn.visible ? "" : " is-hidden"}${turn.kind === "world" ? " is-world" : ""}` },
                h(
                  "div",
                  { class: "turn-who" },
                  turn.kind === "world" ? "El mundo" : turn.name,
                  turn.visibility === "whisper"
                    ? h("small", { text: `en voz baja a ${turn.addressed_to.join(", ") || "nadie"}` })
                    : null,
                ),
                h(
                  "div",
                  {},
                  turn.action ? h("span", { class: "turn-action", text: `(${turn.action}) ` }) : null,
                  turn.item
                    ? h("span", {
                        class: `turn-item${data.voice && !turn.item_visible ? " is-hidden" : ""}`,
                        text: `${turn.item} `,
                      })
                    : null,
                  turn.speech ? h("span", { text: turn.speech }) : null,
                  turn.thought
                    ? h("span", {
                        class: `turn-thought${data.voice && !turn.thought_visible ? " is-hidden" : ""}`,
                        text: `Piensa: ${turn.thought}`,
                      })
                    : null,
                ),
              ),
            ),
          ),
        ]);
      }
    }

    append(body, [
      h(
        "div",
        { class: "toolbar" },
        h("span", { class: "field-label", text: "Ver como" }),
        voiceSelect,
        narratorSelect,
      ),
      scenes,
    ]);
    load();
  }

  function drawMetrics() {
    if (!detail.metrics.length) {
      append(body, [h("div", { class: "empty" }, "Esta función no registró cifras.")]);
      return;
    }
    const rows = [];
    let group = "";
    for (const metric of detail.metrics) {
      if (metric.group !== group) {
        group = metric.group;
        rows.push(h("tr", { class: "group-row" }, h("th", { colspan: 2, text: group })));
      }
      rows.push(h("tr", {}, h("th", { text: metric.label }), h("td", { text: formatNumber(metric.value) })));
    }
    append(body, [
      h("div", { class: "table-wrap" }, h("table", { class: "table" }, h("tbody", {}, rows))),
      h("p", { class: "hint", text: "Las puntuaciones del juez LLM son un indicio, no una medida." }),
    ]);
  }

  function drawConfig() {
    const rows = Object.entries(AXIS_LABELS).map(([key, label]) =>
      h(
        "tr",
        {},
        h("th", { text: label }),
        h("td", { text: axisValue(key, detail.axes[key], labels) }),
        h("td", { class: "muted", text: detail.sources[key] || "" }),
      ),
    );
    append(body, [
      h("div", { class: "table-wrap" }, h("table", { class: "table" }, h("thead", {}, h("tr", {}, h("th", { text: "Eje" }), h("th", { text: "Valor" }), h("th", { text: "Leído de" }))), h("tbody", {}, rows))),
      detail.narrated_by ? h("p", { class: "hint", text: `Narró: ${detail.narrated_by}.` }) : null,
      detail.cast.length
        ? h("section", { class: "card" }, h("p", { class: "eyebrow", text: "Reparto de la función" }), h("div", { class: "badges" }, detail.cast.map((member) => h("span", { class: "badge", text: member.name }))))
        : null,
      detail.warnings_list.length
        ? h("section", { class: "card" }, h("p", { class: "eyebrow", text: "Avisos del run" }), h("ul", { class: "warn-list" }, detail.warnings_list.map((text) => h("li", { text }))))
        : null,
    ]);
  }
}
