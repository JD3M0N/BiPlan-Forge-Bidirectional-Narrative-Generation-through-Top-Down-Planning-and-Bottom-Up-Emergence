// Crear: la obra, el reparto y el riel de opciones. El riel se pinta entero desde el catálogo;
// los campos de texto actualizan el estado sin repintar, para no robar el foco a quien escribe.

import { api } from "../api.js";
import { startJob } from "./progress.js";
import { loadDraft, saveDraft, state } from "../store.js";
import {
  append,
  clear,
  confirmDialog,
  h,
  icon,
  labelsFrom,
  modal,
  renderOption,
  toast,
} from "../ui.js";

let uid = 0;
const nextUid = () => `m${Date.now().toString(36)}${(uid += 1)}`;

function emptyBrief() {
  return { title: "", plot: "", genre: "", setting: "", notes: "", cast: [] };
}

export function freshForm(catalog) {
  return { mode: "brief", brief: emptyBrief(), prompt: "", options: { ...catalog.defaults } };
}

// Une un borrador o una función repetida con los valores por defecto, sin aceptar claves que
// el catálogo ya no conoce.
export function normalizeForm(raw, catalog) {
  const base = freshForm(catalog);
  if (!raw || typeof raw !== "object") return base;
  const options = { ...base.options };
  for (const key of Object.keys(options)) {
    if (raw.options && key in raw.options) options[key] = raw.options[key];
  }
  const brief = { ...emptyBrief(), ...(raw.brief || {}) };
  brief.cast = (brief.cast || []).map((member) => ({
    uid: member.uid || nextUid(),
    name: member.name || "",
    role: member.role || "",
    pronoun: member.pronoun || "",
    description: member.description || "",
    secret: member.secret || "",
  }));
  return {
    mode: raw.mode === "prompt" ? "prompt" : "brief",
    brief,
    prompt: raw.prompt || "",
    options,
  };
}

function takesCharacter(catalog, voice) {
  const option = labelsFrom(catalog).option.narrative_voice;
  return Boolean(option?.choices.find((choice) => choice.value === voice)?.takes_character);
}

function payload(form, catalog) {
  const options = { ...form.options };
  const cast = form.brief.cast.filter((member) => member.name.trim());
  if (!takesCharacter(catalog, options.narrative_voice)) {
    options.narrator = "";
  } else if (form.mode === "brief" && !options.narrator) {
    // «Automático» en la ficha es el protagonista que el autor marcó, si marcó uno.
    const lead = cast.find((member) => member.role === "protagonista");
    options.narrator = lead ? lead.name.trim() : "";
  }
  if (!options.audio) options.audio_voice = "";
  return {
    mode: form.mode,
    brief:
      form.mode === "brief"
        ? {
            title: form.brief.title,
            plot: form.brief.plot,
            genre: form.brief.genre,
            setting: form.brief.setting,
            notes: form.brief.notes,
            cast: cast.map(({ name, role, pronoun, description, secret }) => ({
              name,
              role,
              pronoun,
              description,
              secret,
            })),
          }
        : null,
    prompt: form.mode === "prompt" ? form.prompt : "",
    options,
  };
}

export function renderCreate(container) {
  const catalog = state.catalog;
  if (!state.form) state.form = normalizeForm(loadDraft(), catalog);
  const form = state.form;
  const labels = labelsFrom(catalog);
  const persist = () => saveDraft(form);

  const obra = h("div");
  const castCard = h("section", { class: "card", "aria-labelledby": "cast-title" });
  const rail = h("aside", { class: "rail", "aria-label": "Opciones de la función" });
  const summary = h("div", { class: "summary", "aria-live": "polite" });
  const cost = h("span", { class: "cost" });

  function setOption(key, value, { silent = false } = {}) {
    form.options[key] = value;
    if (key === "narrative_voice" && !takesCharacter(catalog, value)) form.options.narrator = "";
    persist();
    renderSummary();
    if (!silent) renderRail();
  }

  const ctx = () => ({
    values: form.options,
    set: setOption,
    setMany: (values) => {
      Object.assign(form.options, values);
      persist();
      renderSummary();
      renderRail();
    },
    cast: form.brief.cast,
    mode: form.mode,
    sample: (voice) => playSample(voice),
  });

  function renderRail() {
    const scroll = rail.scrollTop;
    clear(rail);
    const context = ctx();
    for (const group of catalog.groups) {
      const outside = group.applies_to && !group.applies_to.includes(form.options.story_format);
      const groupCtx = { ...context, disabled: Boolean(outside) };
      append(rail, [
        h(
          "section",
          { class: `group${outside ? " is-dimmed" : ""}`, "aria-label": group.label },
          h("p", { class: "eyebrow", text: group.label }),
          outside ? h("p", { class: "group-note", text: group.note }) : null,
          group.id === "narration" && !outside && form.options.actor_memory === "shared"
            ? h("p", {
                class: "group-note",
                text: "Con memoria compartida los actores recuerdan todo lo público, pero el narrador sigue viendo solo las escenas en las que estuvo.",
              })
            : null,
          group.options.map((option) => renderOption(option, groupCtx)),
        ),
      ]);
    }
    rail.scrollTop = scroll;
  }

  function renderSummary() {
    clear(summary);
    const options = form.options;
    const simulated = options.story_format === catalog.simulated;
    const pills = [[labels.format[options.story_format] || options.story_format, true]];
    if (options.story_format === "script") pills[0][0] += ` · ${labels.method[options.script_method]}`;
    if (simulated) {
      let vision = labels.voice[options.narrative_voice] || options.narrative_voice;
      const character = payload(form, catalog).options.narrator;
      if (character) vision += ` · ${character}`;
      pills.push([vision, false]);
      pills.push([labels.memory[options.actor_memory] || options.actor_memory, false]);
      pills.push([`${options.turns_per_beat} turnos por beat`, false]);
      if (options.narration_tone) pills.push([`Tono: ${options.narration_tone}`, false]);
    }
    pills.push([
      options.narrative_profile ? `Perfil ${labels.profile[options.narrative_profile]}` : "Perfil automático",
      false,
    ]);
    if (!options.promise_ledger) pills.push(["Sin ledger", false]);
    if (!options.narrative_guidance) pills.push(["Sin guía", false]);
    pills.push([
      options.audio ? `Audio: ${labels.audioVoice[options.audio_voice] || "automático"}` : "Sin audio",
      false,
    ]);
    append(
      summary,
      pills.map(([text, accent]) => h("span", { class: `pill${accent ? " is-accent" : ""}`, text })),
    );
    cost.textContent = catalog.cost[options.story_format] || "";
  }

  function field(label, input, extra) {
    return h("label", { class: "field" }, h("span", { class: "field-label", text: label }), input, extra);
  }

  function bound(tag, attrs, target, key, after) {
    return h(tag, {
      ...attrs,
      value: target[key] || "",
      oninput: (event) => {
        target[key] = event.target.value;
        persist();
        if (after) after(event.target.value);
      },
    });
  }

  function renderObra() {
    clear(obra);
    const modeSwitch = h(
      "div",
      { class: "segmented", role: "group", "aria-label": "Cómo describir la obra" },
      [
        ["brief", "Ficha"],
        ["prompt", "Prompt libre"],
      ].map(([mode, text]) =>
        h("button", {
          type: "button",
          "aria-pressed": String(form.mode === mode),
          text,
          onclick: () => {
            form.mode = mode;
            persist();
            renderObra();
            renderCast();
            renderRail();
            renderSummary();
          },
        }),
      ),
    );
    const head = h(
      "div",
      { class: "card-head" },
      h(
        "div",
        {},
        h("p", { class: "eyebrow", text: "La obra" }),
        h("h2", { class: "card-title", text: form.mode === "brief" ? "Ficha" : "Prompt libre" }),
      ),
      modeSwitch,
    );
    const body =
      form.mode === "brief"
        ? h(
            "div",
            { class: "stack" },
            h(
              "div",
              { class: "grid-2" },
              field(
                "Título (orientativo)",
                bound("input", { class: "input", maxlength: 120, placeholder: "El faro cerrado por dentro" }, form.brief, "title"),
              ),
              field(
                "Género",
                bound("input", { class: "input", maxlength: 80, placeholder: "Misterio, ciencia ficción…" }, form.brief, "genre"),
              ),
            ),
            field(
              "Trama",
              bound(
                "textarea",
                {
                  class: "textarea is-tall",
                  maxlength: 4000,
                  required: true,
                  placeholder:
                    "Qué pasa, a quién y qué está en juego. Por ejemplo: la noche antes de una subasta, un equipo de restauradores descubre que el cuadro estrella es una falsificación…",
                },
                form.brief,
                "plot",
              ),
            ),
            field(
              "Ambientación",
              bound("input", { class: "input", maxlength: 400, placeholder: "Dónde y cuándo ocurre" }, form.brief, "setting"),
            ),
            field(
              "Notas",
              bound("textarea", { class: "textarea", maxlength: 1500, placeholder: "Cualquier otra indicación: final, restricciones, referencias…" }, form.brief, "notes"),
            ),
          )
        : h(
            "div",
            { class: "stack" },
            field(
              "Prompt",
              bound(
                "textarea",
                {
                  class: "textarea is-tall",
                  maxlength: 8000,
                  placeholder: "Escribe la petición completa, tal cual se enviará al analista.",
                },
                form,
                "prompt",
              ),
              h("p", {
                class: "hint",
                text: "El texto exacto sirve para emparejar funciones con los prompts del catálogo de la tesis. Con prompt libre, escribe a mano el nombre del personaje de la visión.",
              }),
            ),
          );
    append(obra, [h("section", { class: "card" }, head, body)]);
  }

  function renderCast() {
    clear(castCard);
    castCard.hidden = form.mode !== "brief";
    const cast = form.brief.cast;
    const limit = catalog.brief.max_cast;
    const add = h(
      "button",
      {
        type: "button",
        class: "btn btn-sm",
        disabled: cast.length >= limit,
        onclick: () => {
          cast.push({ uid: nextUid(), name: "", role: cast.length ? "" : "protagonista", pronoun: "", description: "", secret: "" });
          persist();
          renderCast();
          renderRail();
          castCard.querySelector(".member:last-child input")?.focus();
        },
      },
      icon("plus"),
      "Añadir personaje",
    );
    const list = h("div", { class: "cast" });
    if (!cast.length) {
      append(list, [
        h(
          "div",
          { class: "empty" },
          "Sin reparto, el generador inventa los personajes. Añade los tuyos para fijar sus nombres y poder narrar desde uno de ellos.",
        ),
      ]);
    }
    for (const member of cast) {
      const avatar = h("div", {
        class: `avatar${member.role === "protagonista" ? " is-lead" : ""}`,
        text: initials(member.name),
        "aria-hidden": "true",
      });
      const name = h("input", {
        class: "input",
        maxlength: 80,
        placeholder: "Nombre",
        "aria-label": "Nombre del personaje",
        value: member.name,
        oninput: (event) => {
          const old = member.name;
          member.name = event.target.value;
          if (form.options.narrator && form.options.narrator === old) form.options.narrator = member.name;
          avatar.textContent = initials(member.name);
          persist();
          renderRail();
          renderSummary();
        },
      });
      const role = h(
        "select",
        {
          class: "select",
          "aria-label": "Rol",
          value: member.role,
          onchange: (event) => {
            member.role = event.target.value;
            persist();
            renderCast();
            renderRail();
            renderSummary();
          },
        },
        catalog.brief.roles.map((choice) => h("option", { value: choice.value, text: choice.label })),
      );
      const pronoun = h(
        "select",
        {
          class: "select",
          "aria-label": "Pronombre",
          value: member.pronoun,
          onchange: (event) => {
            member.pronoun = event.target.value;
            persist();
          },
        },
        catalog.brief.pronouns.map((choice) => h("option", { value: choice.value, text: choice.label })),
      );
      const remove = h(
        "button",
        {
          type: "button",
          class: "icon-btn",
          "aria-label": `Quitar a ${member.name || "este personaje"}`,
          onclick: () => {
            form.brief.cast = cast.filter((item) => item.uid !== member.uid);
            if (form.options.narrator === member.name) form.options.narrator = "";
            persist();
            renderCast();
            renderRail();
            renderSummary();
          },
        },
        icon("trash"),
      );
      const more = h(
        "div",
        { class: "member-more" },
        bound("input", { class: "input", maxlength: 600, placeholder: "Quién es y qué quiere", "aria-label": "Descripción" }, member, "description"),
        bound("input", { class: "input", maxlength: 400, placeholder: "Qué oculta (opcional)", "aria-label": "Secreto" }, member, "secret"),
      );
      append(list, [h("div", { class: "member" }, avatar, name, role, pronoun, remove, more)]);
    }
    append(castCard, [
      h(
        "div",
        { class: "card-head" },
        h(
          "div",
          {},
          h("p", { class: "eyebrow", text: `Reparto · ${cast.length}/${limit}` }),
          h("h2", { class: "card-title", id: "cast-title", text: "Personajes" }),
        ),
        add,
      ),
      list,
    ]);
  }

  async function preview() {
    try {
      const result = await api.preview(payload(form, catalog));
      const copy = (text) => () =>
        navigator.clipboard?.writeText(text).then(() => toast("Copiado."), () => toast("No se pudo copiar.", { error: true }));
      modal({
        title: "Lo que se enviará",
        body: h(
          "div",
          { class: "stack" },
          h("div", { class: "card-head" }, h("p", { class: "eyebrow", text: "Prompt para el analista" }), h("button", { class: "btn btn-sm btn-ghost", onclick: copy(result.prompt) }, "Copiar")),
          h("pre", { class: "code", text: result.prompt }),
          h("div", { class: "card-head" }, h("p", { class: "eyebrow", text: "El mismo run desde la terminal" }), h("button", { class: "btn btn-sm btn-ghost", onclick: copy(result.command) }, "Copiar")),
          h("pre", { class: "code", text: result.command }),
          form.mode === "brief"
            ? h("p", { class: "hint", text: "Guarda la ficha como brief.json junto al comando; cada función la conserva en su carpeta." })
            : null,
        ),
      });
    } catch (error) {
      toast(error.message, { error: true });
    }
  }

  async function launch() {
    if (state.job && ["queued", "running"].includes(state.job.status)) {
      toast("Ya hay una función en marcha: la nueva esperará su turno.");
    }
    const job = payload(form, catalog);
    if (job.mode === "brief" && !job.brief.plot.trim()) {
      toast("Escribe la trama antes de estrenar.", { error: true });
      obra.querySelector("textarea")?.focus();
      return;
    }
    if (job.options.story_format === catalog.simulated) {
      const ok = await confirmDialog(
        "¿Estrenar la función?",
        `${catalog.cost.simulated} Se puede cancelar mientras corre.`,
        "Estrenar",
      );
      if (!ok) return;
    }
    try {
      const snapshot = await api.submit(job);
      startJob(snapshot);
    } catch (error) {
      toast(error.message, { error: true });
    }
  }

  const dock = h(
    "div",
    { class: "dock" },
    summary,
    cost,
    h(
      "div",
      { class: "dock-actions" },
      h("button", { type: "button", class: "btn btn-ghost", onclick: preview }, icon("code"), "Ver prompt"),
      h(
        "button",
        { type: "button", class: "btn btn-primary", onclick: launch, title: "Ctrl+Enter" },
        icon("spark"),
        "Estrenar",
        h("kbd", {}, "Ctrl ↵"),
      ),
    ),
  );

  activeLaunch = launch;

  append(clear(container), [
    h(
      "div",
      { class: "page-head" },
      h(
        "div",
        {},
        h("h1", { class: "page-title", text: "Nueva función" }),
        h("p", { class: "page-sub", text: "Escribe la obra, reparte los papeles y decide cómo se cuenta." }),
      ),
      h(
        "button",
        {
          type: "button",
          class: "btn btn-sm btn-ghost",
          onclick: () => {
            state.form = freshForm(catalog);
            saveDraft(state.form);
            renderCreate(container);
          },
        },
        "Empezar de cero",
      ),
    ),
    h("div", { class: "layout-create" }, h("div", { class: "stack" }, obra, castCard), rail),
    dock,
  ]);
  renderObra();
  renderCast();
  renderRail();
  renderSummary();
  return () => {
    if (activeLaunch === launch) activeLaunch = null;
  };
}

// Un solo atajo para toda la página: Ctrl+Enter estrena la función de la vista Crear abierta.
let activeLaunch = null;
document.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter" && activeLaunch) {
    event.preventDefault();
    activeLaunch();
  }
});

function initials(name) {
  const parts = (name || "").trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "?";
  return (parts[0][0] + (parts[1]?.[0] || "")).toUpperCase();
}

let sampleAudio = null;
function playSample(voice) {
  if (!voice) {
    toast("Elige una voz concreta para escucharla.");
    return;
  }
  if (sampleAudio) sampleAudio.pause();
  sampleAudio = new Audio(api.sampleUrl(voice));
  sampleAudio.play().catch(() => toast("No se pudo reproducir la muestra: hace falta conexión.", { error: true }));
}
