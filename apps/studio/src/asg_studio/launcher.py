"""The asg-studio command: start StageCraft on this machine and open it in the browser."""

from __future__ import annotations

import argparse
import threading
import webbrowser

from asg_core import find_project_root, use_utf8_output

from .app import LOCAL_HOSTS, create_app
from .demo import demo_factory


def parser() -> argparse.ArgumentParser:
    """Build the command-line parser of asg-studio."""
    result = argparse.ArgumentParser(
        description="Abre StageCraft, la interfaz gráfica de Stagecraft, en el navegador"
    )
    result.add_argument("--host", default="127.0.0.1", help="Dirección en la que escuchar")
    result.add_argument("--port", type=int, default=8765, help="Puerto en el que escuchar")
    result.add_argument(
        "--no-browser", action="store_true", help="No abre el navegador al arrancar"
    )
    result.add_argument(
        "--demo",
        action="store_true",
        help="Modo demostración: enseña el progreso sin llamar a Gemini ni escribir runs",
    )
    return result


def main(argv: list[str] | None = None) -> int:
    """Run the StageCraft server until it is stopped."""
    use_utf8_output()
    args = parser().parse_args(argv)
    import uvicorn

    root = find_project_root()
    stories = root / "Stories"
    hosts = tuple({*LOCAL_HOSTS, args.host})
    if args.host not in LOCAL_HOSTS:
        print(
            "Aviso: StageCraft escucha fuera de este equipo. Cualquiera en la red podría "
            "lanzar generaciones y gastar tu cuota de Gemini."
        )
    application = create_app(
        stories_root=stories,
        generator_factory=demo_factory(stories) if args.demo else None,
        allowed_hosts=hosts,
        demo=args.demo,
        cache_dir=root / ".cache" / "studio",
    )
    url = f"http://{'127.0.0.1' if args.host in {'0.0.0.0', '::'} else args.host}:{args.port}/"
    print(f"StageCraft{' (demo)' if args.demo else ''} en {url}  ·  Ctrl+C para cerrar")
    if not args.no_browser:
        threading.Timer(1.0, webbrowser.open, args=(url,)).start()
    uvicorn.run(application, host=args.host, port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
