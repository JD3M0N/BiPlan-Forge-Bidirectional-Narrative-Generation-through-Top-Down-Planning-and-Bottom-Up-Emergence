"""Pure rendering for the in-chat run-options panel: no I/O, only text and keyboards."""

from __future__ import annotations

import html
from collections.abc import Mapping

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from .contract import OptionSpec, OptionValue

BACK = InlineKeyboardButton("‹ Volver", callback_data="opt:home")


def visible_specs(
    specs: tuple[OptionSpec, ...], values: Mapping[str, OptionValue]
) -> list[OptionSpec]:
    """Return only the option specs that apply to the currently chosen format."""
    return [spec for spec in specs if spec.applies(values)]


def value_label(spec: OptionSpec, value: OptionValue) -> str:
    """Describe one option's current value the way the panel shows it."""
    if spec.kind == "toggle":
        return "activado" if value else "desactivado"
    if spec.kind == "integer":
        return str(value)
    if spec.kind == "text":
        return str(value) if value else "(sin definir)"
    choice = spec.choice_for(value)
    return choice.label if choice else str(value)


def describe_options(specs: tuple[OptionSpec, ...], values: Mapping[str, OptionValue]) -> str:
    """Summarize every applicable option but the format, for a launch confirmation card."""
    lines = [
        f"• {spec.label}: {value_label(spec, values.get(spec.key))}"
        for spec in visible_specs(specs, values)
        if spec.key != "format"
    ]
    return "\n".join(lines)


def panel_text(specs: tuple[OptionSpec, ...], values: Mapping[str, OptionValue]) -> str:
    """Render the options panel's header message."""
    lines = ["<b>Opciones de la historia</b>", ""]
    for spec in visible_specs(specs, values):
        label = html.escape(value_label(spec, values.get(spec.key)))
        lines.append(f"{html.escape(spec.label)}: {label}")
    return "\n".join(lines)


def panel_keyboard(
    specs: tuple[OptionSpec, ...], values: Mapping[str, OptionValue]
) -> InlineKeyboardMarkup:
    """Build the top-level panel keyboard, one row per applicable option."""
    rows = []
    for spec in visible_specs(specs, values):
        if spec.kind == "toggle":
            mark = "✅" if values.get(spec.key) else "⬜"
            rows.append(
                [InlineKeyboardButton(f"{mark} {spec.label}", callback_data=f"opt:tog:{spec.key}")]
            )
        else:
            current = value_label(spec, values.get(spec.key))
            rows.append(
                [
                    InlineKeyboardButton(
                        f"{spec.label}: {current}", callback_data=f"opt:open:{spec.key}"
                    )
                ]
            )
    rows.append(
        [
            InlineKeyboardButton("Restablecer", callback_data="opt:reset"),
            InlineKeyboardButton("Listo", callback_data="opt:done"),
        ]
    )
    return InlineKeyboardMarkup(rows)


def _countries(spec: OptionSpec) -> list[str]:
    """Return the distinct choice groups of a spec, in their declared order."""
    seen: list[str] = []
    for choice in spec.choices:
        if choice.group and choice.group not in seen:
            seen.append(choice.group)
    return seen


def choice_keyboard(spec: OptionSpec, values: Mapping[str, OptionValue]) -> InlineKeyboardMarkup:
    """Build the submenu for a choice option, grouped by country when it has groups."""
    countries = _countries(spec)
    if not countries:
        rows = [
            [
                InlineKeyboardButton(
                    ("✓ " if choice.value == values.get(spec.key) else "") + choice.label,
                    callback_data=f"opt:set:{spec.key}:{index}",
                )
            ]
            for index, choice in enumerate(spec.choices)
        ]
        rows.append([BACK])
        return InlineKeyboardMarkup(rows)
    rows = [
        [
            InlineKeyboardButton(
                ("✓ " if choice.value == values.get(spec.key) else "") + choice.label,
                callback_data=f"opt:set:{spec.key}:{index}",
            )
        ]
        for index, choice in enumerate(spec.choices)
        if not choice.group
    ]
    rows += [
        [InlineKeyboardButton(country, callback_data=f"opt:grp:{spec.key}:{group_index}")]
        for group_index, country in enumerate(countries)
    ]
    rows.append([BACK])
    return InlineKeyboardMarkup(rows)


def group_keyboard(
    spec: OptionSpec, values: Mapping[str, OptionValue], group_index: int
) -> InlineKeyboardMarkup:
    """Build the submenu listing one group's choices, such as one country's voices."""
    countries = _countries(spec)
    country = countries[group_index]
    rows = [
        [
            InlineKeyboardButton(
                ("✓ " if choice.value == values.get(spec.key) else "") + choice.label,
                callback_data=f"opt:set:{spec.key}:{index}",
            )
        ]
        for index, choice in enumerate(spec.choices)
        if choice.group == country
    ]
    rows.append([InlineKeyboardButton("‹ Volver", callback_data=f"opt:open:{spec.key}")])
    return InlineKeyboardMarkup(rows)


def integer_keyboard(spec: OptionSpec, value: OptionValue) -> InlineKeyboardMarkup:
    """Build a numeric picker between a spec's minimum and maximum, four per row."""
    numbers = range(int(spec.minimum or 0), int(spec.maximum or 0) + 1)
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for number in numbers:
        mark = "• " if number == value else ""
        label = f"{mark}{number}"
        row.append(InlineKeyboardButton(label, callback_data=f"opt:int:{spec.key}:{number}"))
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([BACK])
    return InlineKeyboardMarkup(rows)


def text_prompt(spec: OptionSpec) -> str:
    """Describe what to type for a free-text option, with its length limit."""
    limit = f" (máximo {spec.max_length} caracteres)" if spec.max_length else ""
    return f"Escribe el nuevo valor de «{spec.label}»{limit}, o usa los botones."


def text_keyboard(spec: OptionSpec) -> InlineKeyboardMarkup:
    """Build the keyboard offered while a free-text option is being edited."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Borrar", callback_data=f"opt:clr:{spec.key}"),
                InlineKeyboardButton("Cancelar", callback_data="opt:home"),
            ]
        ]
    )


def parse_callback(data: str) -> tuple[str, str | None, str | None]:
    """Split one ``opt:...`` callback into its action, key and extra index."""
    parts = data.split(":")
    action = parts[1]
    key = parts[2] if len(parts) > 2 else None
    extra = parts[3] if len(parts) > 3 else None
    return action, key, extra
