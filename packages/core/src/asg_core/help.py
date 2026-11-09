"""The asg help command: one line per project command."""

from __future__ import annotations

import argparse

from .console import use_utf8_output

COMMANDS = (
    ("asg help", "muestra esta lista"),
    ("asg-telegram", "inicializa el bot de telegram"),
    ("asg-studio", "abre StageCraft, la interfaz web local (--demo sin cuota)"),
    ("asg-generate", "genera una historia desde la terminal"),
    ("asg-baseline", "genera una línea base de un solo prompt"),
    ("asg-study", "administra el estudio: status, add, exclude, author, open, close, export"),
    ("asg-features", "extrae los rasgos con cita de las historias (gasta cuota)"),
    ("asg-audit-features", "revisa una extracción de rasgos o la compara con otra"),
    ("asg-report-features", "tabla de rasgos y análisis horizontal"),
    ("asg-corpus", "inventario del corpus: qué runs entran al ranking y cuáles son anomalías"),
    ("asg-preferences", "preferencias humanas: Bradley-Terry y acuerdo"),
    ("asg-judge", "entrena el juez aprendido con los votos"),
    ("asg-perturb", "perturba por código los textos del estudio (barajado, sin desenlace)"),
    ("asg-rank", "ordena el corpus con el juez y prepara las diez mejores"),
    ("asg-results", "regenera las tablas y figuras de la tesis desde Evaluations/"),
    ("asg-latex", "compila la tesis en una copia temporal y deja el PDF en redaccion/tesis/"),
    ("asg-budget", "cuota gastada y cuántas historias caben hoy"),
    ("asg-matrix", "lanza una matriz de experimentos en serie con cuota y manifiesto"),
    ("asg-recover", "cierra o descarta runs atascados"),
    ("asg-recompute", "recalcula las métricas de un run simulado"),
)


def parser() -> argparse.ArgumentParser:
    """Build the small root parser; project tools remain independent executables."""
    result = argparse.ArgumentParser(
        prog="asg", description="Herramientas del generador automático de historias."
    )
    result.add_subparsers(dest="command", required=True).add_parser(
        "help", help="muestra todos los comandos disponibles"
    )
    return result


def main(argv: list[str] | None = None) -> int:
    """Handle asg help and print every project command with its description."""
    use_utf8_output()
    parser().parse_args(argv)
    width = max(len(name) for name, _ in COMMANDS)
    for name, text in COMMANDS:
        print(f"{name.ljust(width)} || {text}")
    print("\nAñade --help a cualquiera para ver sus opciones.")
    return 0
