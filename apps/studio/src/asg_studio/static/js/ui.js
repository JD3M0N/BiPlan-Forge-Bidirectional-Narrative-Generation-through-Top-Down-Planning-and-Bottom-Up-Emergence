// Piezas de interfaz: construir nodos sin innerHTML, iconos, avisos, diálogos y los controles
// que pintan cada opción del catálogo según su «kind». Añadir un tipo de opción en el servidor
// es añadir aquí su renderizador; un test comprueba que ninguno falta.

export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  let value;
  for (const [key, raw] of Object.entries(attrs || {})) {
    if (raw === undefined || raw === null || raw === false) continue;
    if (key === "class") el.className = raw;
    else if (key === "text") el.textContent = raw;
    else if (key === "value") value = raw;
    else if (key === "dataset") Object.assign(el.dataset, raw);
    else if (key.startsWith("on") && typeof raw === "function") {
      el.addEventListener(key.slice(2).toLowerCase(), raw);
    } else if (raw === true) el.setAttribute(key, "");
    else el.setAttribute(key, String(raw));
  }
  append(el, children);
  if (value !== undefined) el.value = value;
  return el;
}

export function append(el, children) {
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return el;
}

export function clear(el) {
  while (el.firstChild) el.removeChild(el.firstChild);
  return el;
}

// Iconos propios, constantes: nunca contienen texto que venga del modelo o del usuario.
const ICONS = {
  plus: '<path d="M8 3v10M3 8h10"/>',
  trash: '<path d="M3 4.5h10M6.5 4.5V3h3v1.5M4.5 4.5l.6 8.5h5.8l.6-8.5"/>',
  eye: '<path d="M1.5 8S4 3.5 8 3.5 14.5 8 14.5 8 12 12.5 8 12.5 1.5 8 1.5 8z"/><circle cx="8" cy="8" r="2"/>',
  play: '<path d="M5 3.5v9l7-4.5z"/>',
  stop: '<rect x="4" y="4" width="8" height="8" rx="1"/>',
  chevron: '<path d="M4 6l4 4 4-4"/>',
  close: '<path d="M4 4l8 8M12 4l-8 8"/>',
  repeat: '<path d="M3 7a5 5 0 019-3l1 1M13 9a5 5 0 01-9 3l-1-1M12 2v3H9M4 14v-3h3"/>',
  compare: '<path d="M5.5 2.5v11M10.5 2.5v11M2.5 5h6M7.5 11h6"/>',
  spark: '<path d="M8 2v3M8 11v3M2 8h3M11 8h3M4 4l2 2M10 10l2 2M12 4l-2 2M6 10l-2 2"/>',
  code: '<path d="M6 4L2 8l4 4M10 4l4 4-4 4"/>',
  volume: '<path d="M3 6.5h2.5L9 3.5v9l-3.5-3H3z"/><path d="M11.5 5.5a3.5 3.5 0 010 5"/>',
};

export function icon(name) {
  const span = h("span", { class: "icon", "aria-hidden": "true" });
  span.innerHTML =
    '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" ' +
    `stroke-linecap="round" stroke-linejoin="round">${ICONS[name] || ""}</svg>`;
  return span;
}

export function toast(message, { error = false, action = null, timeout = 5200 } = {}) {
  const root = document.getElementById("toasts");
  const node = h(
    "div",
    { class: `toast${error ? " is-error" : ""}`, role: error ? "alert" : "status" },
    h("span", { text: message }),
    action ? h("a", { class: "btn btn-sm", href: action.href, text: action.label }) : null,
  );
  root.append(node);
  setTimeout(() => node.remove(), timeout);
}

export function modal({ title, body, actions = [] }) {
  const dialog = h("dialog", { class: "modal", "aria-label": title });
  const close = () => {
    dialog.close();
    dialog.remove();
  };
  append(dialog, [
    h(
      "div",
      { class: "modal-head" },
      h("strong", { text: title }),
      h("button", { class: "icon-btn", "aria-label": "Cerrar", onclick: close }, icon("close")),
    ),
    h("div", { class: "modal-body" }, body),
    actions.length
      ? h(
      "div",
      { class: "modal-foot" },
      actions.map((action) =>
        h(
          "button",
          {
            class: `btn ${action.primary ? "btn-primary" : "btn-ghost"}`,
            onclick: () => {
              close();
              if (action.onClick) action.onClick();
            },
          },
          action.label,
        ),
      ),
    )
      : null,
  ]);
  dialog.addEventListener("cancel", () => dialog.remove());
  document.body.append(dialog);
  dialog.showModal();
  return close;
}

export function confirmDialog(title, text, confirmLabel) {
  return new Promise((resolve) => {
    let answered = false;
    const done = (value) => {
      if (!answered) {
        answered = true;
        resolve(value);
      }
    };
    modal({
      title,
      body: h("p", { text }),
      actions: [
        { label: "Cancelar", onClick: () => done(false) },
        { label: confirmLabel, primary: true, onClick: () => done(true) },
      ],
    });
    document.querySelector("dialog.modal:last-of-type")?.addEventListener("close", () =>
      done(false),
    );
  });
}

// ---- etiquetas legibles --------------------------------------------------------------

export function labelsFrom(catalog) {
  const byKey = {};
  for (const group of catalog.groups) {
    for (const option of group.options) byKey[option.key] = option;
  }
  const mapOf = (key) =>
    Object.fromEntries((byKey[key]?.choices || []).map((choice) => [choice.value, choice.label]));
  const voices = {};
  for (const group of byKey.audio_voice?.groups || []) {
    for (const choice of group.choices) {
      voices[choice.value] = group.label ? `${choice.label} (${group.label})` : choice.label;
    }
  }
  return {
    option: byKey,
    voice: mapOf("narrative_voice"),
    memory: mapOf("actor_memory"),
    profile: mapOf("narrative_profile"),
    audioVoice: voices,
    format: { narrative: "Narrativa", script: "Guion", simulated: "Simulada" },
    method: { native: "nativo", adapted: "adaptado" },
  };
}

export function formatNumber(value) {
  if (value === null || value === undefined) return "no medido";
  if (!Number.isFinite(value)) return String(value);
  if (Number.isInteger(value)) return value.toLocaleString("es-ES");
  return value.toLocaleString("es-ES", { maximumFractionDigits: 3 });
}

export function formatDate(iso) {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString("es-ES", { dateStyle: "medium", timeStyle: "short" });
}

// ---- controles del catálogo -----------------------------------------------------------

function enabled(option, ctx) {
  if (option.status === "pending" || ctx.disabled) return false;
  for (const [key, allowed] of Object.entries(option.enabled_when || {})) {
    if (!allowed.includes(ctx.values[key])) return false;
  }
  return true;
}

function pendingChip(roadmap) {
  return h("span", { class: "chip-pending", "data-tip": roadmap || "", tabindex: 0 }, "PENDIENTE");
}

function choiceGrid(choices, isChecked, onPick, isEnabled) {
  const described = choices.every((choice) => choice.description);
  return h(
    "div",
    { class: `choices${described ? " is-single" : ""}`, role: "radiogroup" },
    choices.map((choice) => {
      const pending = choice.status === "pending";
      return h(
        "button",
        {
          type: "button",
          class: `choice${pending ? " is-pending" : ""}`,
          role: "radio",
          "aria-checked": String(isChecked(choice)),
          disabled: pending || !isEnabled,
          title: pending ? choice.roadmap : null,
          onclick: () => onPick(choice),
        },
        h("span", { class: "choice-title", text: choice.label }),
        described ? h("span", { class: "choice-desc", text: choice.description }) : null,
        pending ? pendingChip(choice.roadmap) : null,
      );
    }),
  );
}

export const RENDERERS = {
  preset: (option, ctx) =>
    choiceGrid(
      option.choices,
      // A script needs its method to match; the other formats fix the method themselves.
      (choice) =>
        choice.sets.story_format === ctx.values.story_format &&
        (ctx.values.story_format !== "script" ||
          choice.sets.script_method === ctx.values.script_method),
      (choice) => ctx.setMany(choice.sets),
      enabled(option, ctx),
    ),
  choice: (option, ctx) =>
    choiceGrid(
      option.choices,
      (choice) => (ctx.values[option.key] ?? null) === choice.value,
      (choice) => ctx.set(option.key, choice.value),
      enabled(option, ctx),
    ),
  toggle: (option, ctx) =>
    h(
      "label",
      { class: "switch-row" },
      h(
        "span",
        {},
        option.status === "pending"
          ? "Aún no disponible"
          : ctx.values[option.key]
            ? "Activado"
            : "Desactivado",
      ),
      h("input", {
        type: "checkbox",
        class: "switch",
        role: "switch",
        checked: option.status === "available" && Boolean(ctx.values[option.key]),
        disabled: !enabled(option, ctx),
        "aria-label": option.label,
        onchange: (event) => ctx.set(option.key, event.target.checked),
      }),
    ),
  integer: (option, ctx) => {
    const output = h("span", { class: "range-value", text: String(ctx.values[option.key]) });
    return h(
      "div",
      { class: "range-row" },
      h("input", {
        type: "range",
        class: "range",
        min: option.min,
        max: option.max,
        step: 1,
        value: ctx.values[option.key],
        disabled: !enabled(option, ctx),
        "aria-label": option.label,
        oninput: (event) => {
          output.textContent = event.target.value;
          ctx.set(option.key, Number(event.target.value), { silent: true });
        },
        onchange: (event) => ctx.set(option.key, Number(event.target.value)),
      }),
      output,
    );
  },
  text: (option, ctx) => {
    const counter = h("span", { class: "counter" });
    const refresh = (value) => {
      counter.textContent = `${value.length}/${option.max_length}`;
    };
    const input = h("input", {
      class: "input",
      maxlength: option.max_length,
      placeholder: option.placeholder || "",
      value: ctx.values[option.key] || "",
      disabled: !enabled(option, ctx),
      "aria-label": option.label,
      oninput: (event) => {
        refresh(event.target.value);
        ctx.set(option.key, event.target.value, { silent: true });
      },
    });
    refresh(ctx.values[option.key] || "");
    return h("div", { class: "field" }, input, counter);
  },
  character: (option, ctx) => {
    const isOn = enabled(option, ctx);
    if (ctx.mode === "prompt") {
      return h("input", {
        class: "input",
        maxlength: option.max_length,
        placeholder: "Nombre tal como aparece en tu prompt",
        value: ctx.values[option.key] || "",
        disabled: !isOn,
        "aria-label": option.label,
        oninput: (event) => ctx.set(option.key, event.target.value, { silent: true }),
      });
    }
    const names = ctx.cast.map((member) => member.name).filter(Boolean);
    const lead = ctx.cast.find((member) => member.role === "protagonista" && member.name);
    return h(
      "div",
      { class: "field" },
      h(
        "select",
        {
          class: "select",
          disabled: !isOn,
          "aria-label": option.label,
          value: names.includes(ctx.values[option.key]) ? ctx.values[option.key] : "",
          onchange: (event) => ctx.set(option.key, event.target.value),
        },
        h("option", { value: "", text: "Automático · el protagonista del reparto" }),
        names.map((name) => h("option", { value: name, text: name })),
      ),
      names.length
        ? null
        : h("p", { class: "hint is-accent", text: "Añade un personaje al reparto para elegirlo." }),
      lead && !ctx.values[option.key] && isOn
        ? h("p", { class: "hint", text: `Por defecto narrará ${lead.name}.` })
        : null,
    );
  },
  audio_voice: (option, ctx) => {
    const isOn = enabled(option, ctx);
    const select = h(
      "select",
      {
        class: "select",
        disabled: !isOn,
        "aria-label": option.label,
        value: ctx.values[option.key] || "",
        onchange: (event) => ctx.set(option.key, event.target.value),
      },
      option.groups.map((group) =>
        group.label
          ? h(
              "optgroup",
              { label: group.label },
              group.choices.map((choice) => h("option", { value: choice.value, text: choice.label })),
            )
          : group.choices.map((choice) => h("option", { value: choice.value, text: choice.label })),
      ),
    );
    const listen = h(
      "button",
      {
        type: "button",
        class: "btn btn-sm btn-ghost",
        disabled: !isOn,
        onclick: () => ctx.sample(select.value),
      },
      icon("volume"),
      "Escuchar",
    );
    return h("div", { class: "range-row" }, select, listen);
  },
};

export function renderOption(option, ctx) {
  const pending = option.status === "pending";
  const control = (RENDERERS[option.kind] || RENDERERS.text)(option, ctx);
  return h(
    "div",
    { class: `option${pending ? " is-pending" : ""}`, dataset: { key: option.key } },
    h(
      "div",
      { class: "option-head" },
      h("span", { class: "label", text: option.label }),
      pending ? pendingChip(option.roadmap) : null,
    ),
    option.help ? h("p", { class: "help", text: option.help }) : null,
    control,
    pending && option.measures
      ? h("p", { class: "hint", text: `Mediría: ${option.measures}` })
      : null,
  );
}
