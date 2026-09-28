"""The page and the catalog must agree: every control kind has a renderer, every file exists."""

import re

from asg_stagecraft import GenerationOptions
from asg_studio import create_app
from asg_studio.app import STATIC_DIR
from asg_studio.catalog import catalog_document
from fastapi.testclient import TestClient
from studio_fakes import settings_loader


def kinds(document) -> set[str]:
    return {option["kind"] for group in document["groups"] for option in group["options"]}


def test_every_catalog_kind_has_a_renderer_in_the_page() -> None:
    source = (STATIC_DIR / "js" / "ui.js").read_text(encoding="utf-8")
    renderers = source.split("export const RENDERERS", 1)[1]
    for kind in kinds(catalog_document(GenerationOptions())):
        assert re.search(rf"\n  {kind}: ", renderers), kind


def test_every_local_file_the_page_refers_to_exists() -> None:
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    for reference in re.findall(r'(?:src|href)="([^"#:]+)"', html):
        assert (STATIC_DIR / reference).is_file(), reference
    for script in (STATIC_DIR / "js").rglob("*.js"):
        text = script.read_text(encoding="utf-8")
        for target in re.findall(r'from "(\.[^"]+)"', text):
            assert (script.parent / target).resolve().is_file(), f"{script.name} -> {target}"


def test_the_page_loads_nothing_from_outside() -> None:
    for path in STATIC_DIR.rglob("*"):
        if path.suffix in {".html", ".css", ".js"}:
            text = path.read_text(encoding="utf-8")
            assert not re.search(r"(?:src|href|url\()\s*=?\s*[\"']?https?://", text), path.name


def test_the_page_is_served_with_the_right_types(tmp_path) -> None:
    app = create_app(stories_root=tmp_path, settings_loader=settings_loader())
    with TestClient(app, base_url="http://127.0.0.1") as client:
        page = client.get("/")
        assert "StageCraft" in page.text
        script = client.get("/js/main.js")
        assert script.headers["content-type"].startswith("text/javascript")
        assert client.get("/css/stagecraft.css").headers["content-type"].startswith("text/css")
