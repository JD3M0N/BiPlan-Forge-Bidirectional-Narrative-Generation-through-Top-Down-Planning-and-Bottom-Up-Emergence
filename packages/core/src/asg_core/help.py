"""The asg-help command: one line per project command."""

from __future__ import annotations

from .console import use_utf8_output

COMMANDS = (
    ("asg-help", "muestra esta lista"),
    ("asg-telegram", "inicializa el bot de telegram"),
    ("asg-studio", "abre StageCraft, la interfaz web local (--demo sin cuota)"),
    ("asg-generate", "genera una historia desde la terminal"),
    ("asg-baseline", "genera una línea base de un solo prompt"),
    ("asg-study", "administra el estudio: status, add, exclude, author, open, close, export"),
    ("asg-features", "extrae los rasgos con cita de las historias (gasta cuota)"),
    ("asg-audit-features", "revisa una extracción de rasgos o la compara con otra"),
    ("asg-report-features", "tabla de rasgos y análisis horizontal"),
    ("asg-preferences", "preferencias humanas: Bradley-Terry y acuerdo"),
    ("asg-judge", "entrena el juez aprendido con los votos"),
    ("asg-rank", "ordena el corpus con el juez y prepara las diez mejores"),
    ("asg-budget", "cuota gastada y cuántas historias caben hoy"),
    ("asg-recover", "cierra o descarta runs atascados"),
    ("asg-recompute", "recalcula las métricas de un run simulado"),
)


def main() -> int:
    """Print every command with its description."""
    use_utf8_output()
    width = max(len(name) for name, _ in COMMANDS)
    for name, text in COMMANDS:
        print(f"{name.ljust(width)} || {text}")
    print("\nAñade --help a cualquiera para ver sus opciones.")
    return 0
