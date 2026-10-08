"""Show the quota left on every provider a run may spend on, and how many stories still fit."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from asg_core import use_utf8_output

from ..runtime.budget import QuotaLedger, QuotaSlot, window_bounds
from ..runtime.config import ChainEntry, load_settings

PROVIDER_NAMES = {"gemini": "Gemini", "groq": "Groq", "mistral": "Mistral"}
WINDOW_WORDS = {"pacific_day": "hoy", "utc_day": "hoy", "utc_month": "este mes"}
MONTHS = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")
WEEKDAYS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
# How many completed runs the average cost of a story is taken from.
RECENT_RUNS = 10


def _n(value: int) -> str:
    """Write an integer with dots between thousands, as Spanish does."""
    return f"{value:,}".replace(",", ".")


def _when(moment: datetime, now: datetime) -> str:
    """Say when a reset happens: how long until it within a day, the date otherwise."""
    local = moment.astimezone()
    left = moment - now
    if left <= timedelta(days=1):
        hours, minutes = divmod(max(0, int(left.total_seconds())) // 60, 60)
        return f"reinicia en {hours} h {minutes:02d} min ({local:%H:%M} local)"
    return f"reinicia el {local.day} {MONTHS[local.month - 1]} a las {local:%H:%M} local"


def spent_from_logs(
    runs_root: Path, slots: list[QuotaSlot], now: datetime
) -> dict[str, tuple[int, int]]:
    """Count each slot's requests and tokens in its current window from the runs' call logs.

    A 429 consumed nothing and a token count is no call, so neither is counted. Logs cover the
    runs made without the chain and before the ledger existed.
    """
    by_model = {slot.model: slot for slot in slots}
    current = {slot.key: window_bounds(slot.window, now)[0] for slot in slots}
    longest = 32 if any(slot.window == "utc_month" for slot in slots) else 2
    cutoff = (now - timedelta(days=longest)).timestamp()
    spent = {slot.key: [0, 0] for slot in slots}
    for path in runs_root.glob("*/llm_calls.jsonl"):
        if path.stat().st_mtime < cutoff:
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                record = json.loads(line)
                slot = by_model.get(record.get("model"))
                if slot is None or record.get("operation") == "count_tokens":
                    continue
                if str(record.get("error_code")) == "429":
                    continue
                moment = datetime.fromisoformat(record["timestamp"])
            except (ValueError, KeyError, TypeError, AttributeError):
                continue
            if window_bounds(slot.window, moment)[0] != current[slot.key]:
                continue
            spent[slot.key][0] += 1
            spent[slot.key][1] += int(record.get("total_tokens") or 0)
    return {key: (value[0], value[1]) for key, value in spent.items()}


def average_story(runs_root: Path) -> tuple[int, int, int] | None:
    """Return the mean calls and tokens of the latest completed runs, and how many there were."""
    samples = []
    for run in sorted((p for p in runs_root.glob("*") if p.is_dir()), reverse=True):
        try:
            metadata = json.loads((run / "metadata.json").read_text(encoding="utf-8"))
            usage = json.loads((run / "llm_usage.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if metadata.get("status") == "completed" and usage.get("calls"):
            samples.append((int(usage["calls"]), int(usage.get("total_tokens") or 0)))
        if len(samples) == RECENT_RUNS:
            break
    if not samples:
        return None
    return (
        sum(calls for calls, _ in samples) // len(samples),
        sum(tokens for _, tokens in samples) // len(samples),
        len(samples),
    )


def _left(cap: int, used: int, out: bool) -> int | None:
    """Return what a slot has left, or None when it has no cap and is not out."""
    if out:
        return 0
    return max(0, cap - used) if cap else None


def report(settings, *, now: datetime | None = None) -> list[str]:
    """Return the quota panel: one block per provider, one line per model, and what fits."""
    now = now or datetime.now(UTC)
    entries: list[ChainEntry] = settings.quota_entries()
    ledger = QuotaLedger(settings.budget_path) if settings.budget_path else None
    slots = [entry.slot for entry in entries]
    logged = spent_from_logs(settings.output_root, slots, now)
    local = now.astimezone()
    lines = [
        f"Cuotas disponibles · {WEEKDAYS[local.weekday()]} {local.day} "
        f"{MONTHS[local.month - 1]} {local.year}, {local:%H:%M} (hora local)",
        "",
    ]
    width = max(len(slot.model) for slot in slots)
    average = average_story(settings.output_root)
    fits: list[str] = []
    for provider in dict.fromkeys(slot.provider for slot in slots):
        group = [entry for entry in entries if entry.slot.provider == provider]
        rows, requests_left, tokens_left = [], [], []
        total_requests = total_tokens = 0
        for entry in group:
            slot = entry.slot
            stored = ledger.usage(slot) if ledger else (0, 0)
            requests = max(stored[0], logged[slot.key][0])
            tokens = max(stored[1], logged[slot.key][1])
            until = ledger.exhausted_until(slot) if ledger else None
            total_requests += requests
            total_tokens += tokens
            requests_left.append(_left(slot.max_requests, requests, bool(until)))
            tokens_left.append(_left(slot.max_tokens, tokens, bool(until)))
            used = f"{_n(requests)}/{_n(slot.max_requests)}" if slot.max_requests else _n(requests)
            spent = f"{_n(tokens)}/{_n(slot.max_tokens)}" if slot.max_tokens else _n(tokens)
            state = f"AGOTADO hasta {until.astimezone():%d/%m %H:%M}" if until else "disponible"
            rows.append(
                f"  {slot.model:<{width}}  {used:>11} · {spent:>15} tokens · "
                f"{entry.rpm_limit} RPM · {state}"
            )
        caps = [entry.slot.max_requests for entry in group]
        token_caps = [entry.slot.max_tokens for entry in group]
        word = WINDOW_WORDS[group[0].slot.window]
        head = f"{_n(total_requests)}"
        if all(caps):
            head += f"/{_n(sum(caps))} peticiones {word} · quedan {_n(sum(requests_left))}"
        else:
            head += f" peticiones {word} (sin tope)"
        if all(token_caps):
            head += f" · {_n(total_tokens)}/{_n(sum(token_caps))} tokens"
        else:
            head += f" · {_n(total_tokens)} tokens"
        reset = min(window_bounds(entry.slot.window, now)[1] for entry in group)
        name = PROVIDER_NAMES.get(provider, provider)
        lines.append(f"{name:<8} {head} · {_when(reset, now)}")
        lines.extend(rows)
        if average:
            fits.append(f"{name} {_fit(requests_left, tokens_left, average)}")
    lines.append("")
    if average:
        lines.append(
            f"Una historia gasta de media ~{_n(average[0])} llamadas y ~{_n(average[1])} tokens "
            f"(media de los últimos {average[2]} runs completados)."
        )
        lines.append("Caben aprox.: " + " · ".join(fits) + ".")
    else:
        lines.append("Aún no hay runs completados para estimar cuántas historias caben.")
    return lines


def _fit(requests_left: list, tokens_left: list, average: tuple[int, int, int]) -> str:
    """Estimate how many average stories a provider's slots still hold together."""
    bounds = []
    if None not in requests_left and average[0]:
        bounds.append(sum(requests_left) // average[0])
    if None not in tokens_left and average[1]:
        bounds.append(sum(tokens_left) // average[1])
    return str(min(bounds)) if bounds else "sin límite conocido"


def main(argv: list[str] | None = None) -> int:
    """Run the command-line entry point."""
    use_utf8_output()
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    for line in report(load_settings(require_api_key=False)):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
