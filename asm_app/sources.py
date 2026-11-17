"""What each Catalog item's source says now: its description, its repository's GitHub stars and its skills.sh installs.

ASM queries these when it shows them and writes none of them into the repo. Answers are kept for an hour in
.asm/sources.json, which Git ignores, so a page load asks each host once. This module is the one place ASM
reaches the network, and only the hosts in HOSTS; it never contacts a consumer.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path, PurePosixPath
import threading
import time
from urllib.error import HTTPError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

from .store import _skill_labels

HOSTS = {"api.github.com", "raw.githubusercontent.com", "skills.sh"}
MAX_AGE = 3600  # seconds an answer is reused before the source is asked again
# skills.sh refuses quick bursts; the others take a few requests at once.
_LIMITS = {"api.github.com": threading.BoundedSemaphore(4), "raw.githubusercontent.com": threading.BoundedSemaphore(8),
           "skills.sh": threading.BoundedSemaphore(1)}


def fetch(url):
    host = urlsplit(url).hostname
    if host not in HOSTS:
        raise ValueError(f"ASM reads sources only from {', '.join(sorted(HOSTS))}, not {host}.")
    headers = {"User-Agent": "agent-stack-manager"}
    if host == "api.github.com":
        headers["Accept"] = "application/vnd.github+json"
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if token:
            headers["Authorization"] = "Bearer " + token
    with _LIMITS[host]:
        for attempt in range(3):
            try:
                with urlopen(Request(url, headers=headers), timeout=20) as response:
                    return response.read()
            except HTTPError as error:
                if error.code != 429 or attempt == 2:
                    raise
                time.sleep(int(error.headers.get("Retry-After") or 0) or 2 * (attempt + 1))


def _github(url):
    """owner/repo for a github.com repository URL, else None."""
    location = urlsplit(url or "")
    parts = location.path.strip("/").removesuffix(".git").split("/")
    return "/".join(parts[:2]) if location.hostname == "github.com" and len(parts) >= 2 else None


def _plan(item):
    """The questions an item needs answered, as cache keys with the URL that answers each."""
    source = item.get("source") or {}
    repository = _github(source.get("repositoryUrl"))
    if not repository:
        return None
    ref, path = source.get("ref") or "HEAD", source.get("path") or ""
    raw = f"https://raw.githubusercontent.com/{repository}/{quote(ref, safe='')}/"
    page = f"https://github.com/{repository}/blob/{quote(ref, safe='')}/"
    plan = {"repository": (f"repository:{repository}", f"https://api.github.com/repos/{repository}")}
    if item["kind"] == "skill":
        file = path if PurePosixPath(path).name == "SKILL.md" else str(PurePosixPath(path, "SKILL.md"))
        plan["file"] = (f"file:{repository}@{ref}:{file}", raw + quote(file), page + quote(file))
        plan["installs"] = (f"skills.sh:{repository}", f"https://skills.sh/api/search?q={quote(repository)}&limit=100")
    elif item["kind"] == "plugin":
        file = str(PurePosixPath(path, ".claude-plugin", "plugin.json"))
        plan["file"] = (f"file:{repository}@{ref}:{file}", raw + quote(file), page + quote(file))
    return plan


def _answer(key, data):
    """The part of a host's reply ASM shows."""
    if key.startswith("repository:"):
        reply = json.loads(data)
        return {"stars": reply["stargazers_count"], "description": (reply.get("description") or "").strip()}
    if key.startswith("skills.sh:"):
        repository = key.removeprefix("skills.sh:").casefold()
        installs = {}
        for entry in json.loads(data).get("skills", []):
            if entry.get("source", "").casefold() == repository:
                for name in {entry.get("skillId"), entry.get("name")} - {None}:
                    installs[name] = entry["installs"]
        return {"installs": installs}
    if key.endswith("plugin.json"):
        return {"description": (json.loads(data).get("description") or "").strip()}
    return {"description": _skill_labels(key.rsplit(":", 1)[1], data)[1]}


class SourceReader:
    def __init__(self, cache_path: Path, fetch=fetch, clock=time.time):
        self.cache_path, self.fetch, self.clock = cache_path, fetch, clock
        self._lock = threading.Lock()

    def _load(self):
        try:
            return json.loads(self.cache_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def read(self, items):
        """{"items": {id: what its source says}, "errors": [why a source could not be read]}."""
        plans = {item["id"]: plan for item in items if (plan := _plan(item))}
        urls = {entry[0]: entry[1] for plan in plans.values() for entry in plan.values()}
        with self._lock:
            cache = self._load()
            now = self.clock()
            stale = [key for key in urls if now - cache.get(key, {}).get("readAt", 0) >= MAX_AGE]
            errors = {}

            def ask(key):
                try:
                    return key, {**_answer(key, self.fetch(urls[key])), "readAt": now}
                except Exception as error:  # a source that cannot be read leaves its last answer in place
                    errors[key] = f"{urls[key]}: {error}"
                    return key, None

            with ThreadPoolExecutor(max_workers=8) as pool:
                for key, answer in pool.map(ask, stale):
                    if answer:
                        cache[key] = answer
            if stale:
                self.cache_path.parent.mkdir(parents=True, exist_ok=True)
                self.cache_path.write_text(json.dumps(cache), encoding="utf-8")

        def stamp(entry):
            return datetime.fromtimestamp(entry["readAt"], timezone.utc).isoformat(timespec="seconds")

        found = {}
        for item in items:
            plan = plans.get(item["id"])
            if not plan:
                continue
            facts = {}
            repository = cache.get(plan["repository"][0])
            if repository:
                facts.update(stars=repository["stars"], starsReadAt=stamp(repository))
            file = cache.get(plan["file"][0]) if "file" in plan else None
            described = file if "file" in plan else repository
            if described and described["description"]:
                facts.update(description=described["description"], descriptionReadAt=stamp(described),
                             descriptionUrl=plan["file"][2] if "file" in plan else item["source"]["repositoryUrl"])
            listed = cache.get(plan["installs"][0]) if "installs" in plan else None
            folder = PurePosixPath(plan["file"][0].rsplit(":", 1)[1]).parent.name if "file" in plan else ""
            names = [name for name in (item.get("name"), folder) if name]
            count = next((listed["installs"][name] for name in names if listed and name in listed["installs"]), None)
            if count is not None:
                facts.update(installs=count, installsReadAt=stamp(listed))
            found[item["id"]] = facts
        return {"items": found, "errors": sorted(errors.values())}
