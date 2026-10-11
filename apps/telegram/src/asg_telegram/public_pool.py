"""Atomic GitHub publication of approved anonymous story texts."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
from datetime import UTC, datetime
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

LOGGER = logging.getLogger(__name__)


class GitHubPool:
    """Publish a manifest and texts together in a non-forced Git commit."""

    def __init__(self, repository: str, token: str, branch: str = "main") -> None:
        """Restrict requests to the explicitly configured GitHub repository."""
        if not re.fullmatch(r"[\w.-]+/[\w.-]+", repository):
            raise ValueError("STORY_POOL_REPOSITORY debe ser propietario/repositorio.")
        self.base = f"https://api.github.com/repos/{repository}"
        self.token = token
        self.branch = quote(branch, safe="/")

    def request(self, path: str, data=None, *, method: str | None = None):
        """Perform a bounded API request without logging credentials or error bodies."""
        request = Request(
            self.base + path,
            data=json.dumps(data).encode() if data is not None else None,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
                "User-Agent": "ASG-story-pool",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        with urlopen(request, timeout=30) as response:
            return json.load(response)

    def publish(self, stories: list[dict]) -> None:
        """Merge the public manifest and atomically advance the configured branch."""
        head = self.request(f"/git/ref/heads/{self.branch}")["object"]["sha"]
        commit = self.request(f"/git/commits/{head}")
        try:
            remote = self.request(f"/contents/story-pool/manifest.json?ref={head}")
            manifest = json.loads(base64.b64decode(remote["content"]))
        except HTTPError as error:
            if error.code != 404:
                raise
            manifest = {"schema_version": 1, "stories": []}
        indexed = {story["id"]: story for story in manifest["stories"]}
        entries = []
        for story in stories:
            item = {"id": story["id"], "text_hash": story["text_hash"]}
            old = indexed.get(story["id"])
            if old and old != item:
                raise ValueError("Una historia pública tiene otra huella; no se sobrescribió.")
            if old:
                continue
            indexed[story["id"]] = item
            entries.append(
                {
                    "path": f"story-pool/{story['id']}.md",
                    "mode": "100644",
                    "type": "blob",
                    "content": story["text"],
                }
            )
        if not entries:
            return
        manifest = {"schema_version": 1, "stories": sorted(indexed.values(), key=lambda s: s["id"])}
        entries.append(
            {
                "path": "story-pool/manifest.json",
                "mode": "100644",
                "type": "blob",
                "content": json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            }
        )
        tree = self.request("/git/trees", {"base_tree": commit["tree"]["sha"], "tree": entries})
        new = self.request(
            "/git/commits",
            {"message": "Publicar historias autorizadas", "tree": tree["sha"], "parents": [head]},
        )
        self.request(
            f"/git/refs/heads/{self.branch}", {"sha": new["sha"], "force": False}, method="PATCH"
        )


class PoolPublisher:
    """Retry the persistent publication outbox independently from generation."""

    def __init__(self, repository, github: GitHubPool) -> None:
        """Attach local approval state and the configured remote transport."""
        self.repository = repository
        self.github = github

    def sync(self) -> int:
        """Publish due approved texts and record success or bounded retry backoff."""
        now = datetime.now(UTC).isoformat()
        due = [
            s
            for s in self.repository.publication_batch()
            if not s["synced_at"] and (not s["next_attempt"] or s["next_attempt"] <= now)
        ]
        if not due:
            return 0
        try:
            self.github.publish(due)
        except Exception as exc:
            # Error bodies can contain request headers or remote user data.
            reason = type(exc).__name__
            for story in due:
                self.repository.publication_result(story["id"], success=False, error=reason)
            LOGGER.warning("Publicación pendiente de reintento: %s", reason)
            return 0
        for story in due:
            self.repository.publication_result(story["id"], success=True)
        return len(due)

    async def run(self) -> None:
        """Drain the outbox every minute without blocking the Telegram event loop."""
        while True:
            try:
                await asyncio.to_thread(self.sync)
            except Exception:
                LOGGER.exception("No se pudo revisar la cola de publicación")
            await asyncio.sleep(60)
