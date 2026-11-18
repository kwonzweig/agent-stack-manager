"""What each Catalog item's source says now: its description, its repository's GitHub stars and its skills.sh installs.

ASM queries these when it shows them and writes none of them into the repo. Answers are kept for an hour in
.asm/sources.json, which Git ignores, so a page load asks each host once.
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

MAX_AGE = 3600  # seconds an answer is reused before the source is asked again
# skills.sh refuses quick bursts; the others take a few requests at once.
_LIMITS = {"api.github.com": threading.BoundedSemaphore(4), "raw.githubusercontent.com": threading.BoundedSemaphore(8),
           "skills.sh": threading.BoundedSemaphore(1)}
_OTHER_HOST = threading.BoundedSemaphore(4)


def fetch(url):
    host = urlsplit(url).hostname
    headers = {"User-Agent": "agent-stack-manager"}
    if host == "api.github.com":
        headers["Accept"] = "application/vnd.github+json"
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if token:
            headers["Authorization"] = "Bearer " + token
    with _LIMITS.get(host, _OTHER_HOST):
        for attempt in range(3):
            try:
                with urlopen(Request(url, headers=headers), timeout=20) as response:
                    return response.read()
            except HTTPError as error:
                if error.code != 429 or attempt == 2:
                    raise
                time.sleep(min(10, int(error.headers.get("Retry-After") or 0) or 2 * (attempt + 1)))


def _github(url):
    """owner/repo for a github.com repository URL, else None."""
    location = urlsplit(url or "")
    parts = location.path.strip("/").removesuffix(".git").split("/")
    return "/".join(parts[:2]) if location.hostname == "github.com" and len(parts) >= 2 else None


def _plan(item):
    """The questions an item needs answered, as cache keys with the URL that answers each."""
    if item.get("sourceAccess") == "private" or (item.get("remoteApproved") is False and item.get("sourceAccess") != "verify"):
        return None
    source = item.get("source") or {}
    repository = _github(source.get("repositoryUrl"))
    if not repository:
        return None
    ref, path = source.get("ref") or "HEAD", source.get("path") or ""
    raw = f"https://raw.githubusercontent.com/{repository}/{quote(ref, safe='')}/"
    page = f"https://github.com/{repository}/blob/{quote(ref, safe='')}/"
    plan = {"repository": (f"repository:{repository}", f"https://api.github.com/repos/{repository}")}
    if item["kind"] == "skill" and path and item.get("bodyAllowed", bool(source.get("ref"))):
        file = path if PurePosixPath(path).name == "SKILL.md" else str(PurePosixPath(path, "SKILL.md"))
        plan["file"] = (f"file:{repository}@{ref}:{file}", raw + quote(file), page + quote(file))
        plan["installs"] = (f"skills.sh:{repository}", f"https://skills.sh/api/search?q={quote(repository)}&limit=100")
    elif item["kind"] == "plugin" and path and item.get("bodyAllowed", bool(source.get("ref"))):
        manifest = ".codex-plugin" if item.get("pluginHost") == "codex" else ".claude-plugin"
        file = path if PurePosixPath(path).name == "plugin.json" else str(PurePosixPath(path, manifest, "plugin.json"))
        plan["file"] = (f"file:{repository}@{ref}:{file}", raw + quote(file), page + quote(file))
    return plan


def _answer(key, data):
    """The part of a host's reply ASM shows."""
    if key.startswith("repository:"):
        reply = json.loads(data)
        return {"stars": reply["stargazers_count"], "description": (reply.get("description") or "").strip(),
                "visibility": "public" if reply.get("private") is False else "private" if reply.get("private") is True else "unknown",
                "defaultRef": reply.get("default_branch")}
    if key.startswith("skills.sh:"):
        repository = key.removeprefix("skills.sh:").casefold()
        installs = {}
        for entry in json.loads(data).get("skills", []):
            if entry.get("source", "").casefold() == repository:
                for name in {entry.get("skillId"), entry.get("name")} - {None}:
                    installs[name] = entry["installs"]
        return {"installs": installs}
    if key.endswith("plugin.json"):
        return {"description": (json.loads(data).get("description") or "").strip(),
                "content": data.decode("utf-8"), "contentFormat": "json"}
    return {"description": _skill_labels(key.rsplit(":", 1)[1], data)[1],
            "content": data.decode("utf-8"), "contentFormat": "markdown"}


class SourceReader:
    def __init__(self, cache_path: Path, fetch=fetch, clock=time.time):
        self.cache_path, self.fetch, self.clock = cache_path, fetch, clock
        self._lock = threading.Lock()
        self._failures = {}
        self._failure_messages = {}

    def _load(self):
        try:
            return json.loads(self.cache_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def read(self, items):
        """{"items": {id: what its source says}, "errors": [why a source could not be read]}."""
        plans = {item["id"]: plan for item in items if (plan := _plan(item))}
        with self._lock:
            cache = self._load()
        now = self.clock()
        errors = {}
        attempted = set()

        def refresh(urls):
            for key in urls:
                if now - self._failures.get(key, float("-inf")) < 30:
                    errors[key] = self._failure_messages.get(key, "The source request failed. Retry shortly.")
            stale = [key for key in urls if key not in attempted and
                     now - self._failures.get(key, float("-inf")) >= 30 and
                     (now - cache.get(key, {}).get("readAt", 0) >= MAX_AGE
                      or (key.startswith("file:") and "content" not in cache.get(key, {}))
                      or (key.startswith("repository:") and
                          ("visibility" not in cache.get(key, {}) or
                           (cache.get(key, {}).get("visibility") == "public" and "defaultRef" not in cache.get(key, {})))))]
            attempted.update(stale)
            def ask(key):
                try:
                    answer = {**_answer(key, self.fetch(urls[key])), "readAt": now}
                    self._failures.pop(key, None)
                    self._failure_messages.pop(key, None)
                    return key, answer
                except Exception as error:
                    errors[key] = f"{urls[key]}: {error}"
                    self._failures[key] = now
                    self._failure_messages[key] = errors[key]
                    return key, None
            with ThreadPoolExecutor(max_workers=8) as pool:
                for key, answer in pool.map(ask, stale):
                    if answer:
                        cache[key] = answer
            return bool(stale)

        candidates = {item["id"] for item in items if item.get("sourceAccess") == "verify" and not item.get("remoteApproved")}
        native_ids = candidates | {item["id"] for item in items if item.get("sourceAccess") == "public"}
        native_urls = {plans[key]["repository"][0]: plans[key]["repository"][1] for key in native_ids if key in plans}
        changed = refresh(native_urls)
        for key in candidates & plans.keys():
            if cache.get(plans[key]["repository"][0], {}).get("visibility") != "public":
                plans[key] = {"repository": plans[key]["repository"]}
        resolved_refs = {}
        by_id = {item["id"]: item for item in items}
        for key in native_ids & plans.keys():
            item = by_id[key]
            repository = cache.get(plans[key]["repository"][0], {})
            if (repository.get("visibility") == "public" and repository.get("defaultRef")
                    and not item["source"].get("ref") and item["source"].get("path")):
                resolved = {**item, "source": {**item["source"], "ref": repository["defaultRef"]}, "bodyAllowed": True}
                plans[key] = _plan(resolved)
                resolved_refs[key] = repository["defaultRef"]
        urls = {entry[0]: entry[1] for plan in plans.values() for entry in plan.values()}
        changed = refresh(urls) or changed
        if changed:
            with self._lock:
                current = self._load()
                for key, answer in cache.items():
                    if answer.get("readAt", 0) >= current.get(key, {}).get("readAt", 0):
                        current[key] = answer
                self.cache_path.parent.mkdir(parents=True, exist_ok=True)
                self.cache_path.write_text(json.dumps(current), encoding="utf-8")

        def stamp(entry):
            return datetime.fromtimestamp(entry["readAt"], timezone.utc).isoformat(timespec="seconds")

        found = {}
        for item in items:
            plan = plans.get(item["id"])
            if not plan:
                continue
            facts = {}
            if item["id"] in resolved_refs:
                facts["sourceResolvedRef"] = resolved_refs[item["id"]]
            repository = cache.get(plan["repository"][0])
            if item["id"] in candidates and (not repository or repository.get("visibility") != "public"):
                reason = ("GitHub identifies this repository as private. Its source and metrics were not requested."
                          if repository and repository.get("visibility") == "private" else
                          "The repository visibility check failed. Its source and metrics are unavailable."
                          if plan["repository"][0] in errors else
                          "The repository's public visibility is unverified. Its source and metrics are unavailable.")
                found[item["id"]] = {"sourceUnavailable": reason}
                continue
            if repository:
                facts.update(stars=repository["stars"], starsReadAt=stamp(repository))
            file = cache.get(plan["file"][0]) if "file" in plan else None
            described = file if "file" in plan else None if item["kind"] in {"skill", "plugin"} else repository
            if described and described["description"]:
                facts.update(description=described["description"], descriptionReadAt=stamp(described),
                             descriptionUrl=plan["file"][2] if "file" in plan else item["source"]["repositoryUrl"])
            if file and "content" in file:
                facts.update(content=file["content"], contentFormat=file.get("contentFormat", "markdown"),
                             contentUrl=plan["file"][2], contentReadAt=stamp(file))
            elif file and "content" not in file:
                # Old cache records predate source-body support and refresh at normal expiry.
                facts["contentUnavailable"] = "The cached source has metadata only; its next refresh will include the body."
            listed = cache.get(plan["installs"][0]) if "installs" in plan else None
            folder = PurePosixPath(plan["file"][0].rsplit(":", 1)[1]).parent.name if "file" in plan else ""
            names = [name for name in (item.get("name"), folder) if name]
            count = next((listed["installs"][name] for name in names if listed and name in listed["installs"]), None)
            if count is not None:
                facts.update(installs=count, installsReadAt=stamp(listed))
            found[item["id"]] = facts
        return {"items": found, "errors": sorted(errors.values())}
