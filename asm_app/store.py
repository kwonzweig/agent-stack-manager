"""Read and edit native APM packages for the dashboard."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from urllib.parse import quote, urlsplit
from zipfile import ZIP_DEFLATED, ZipFile

import yaml


_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_SIBLING = re.compile(r"\.\./([^/]+)")
_PRIMARY = ".apm/agents/{}.agent.md"
_KINDS = {"skill", "mcp", "hook", "plugin", "instruction", "package", "other"}
_LISTS = (("dependencies", "apm"), ("dependencies", "mcp"), ("dependencies", "lsp"),
          ("dependencies", "hooks"), ("dependencies", "plugins"), ("hooks",), ("plugins",))
# apm.lock.yaml is written by `lock`: it records resolved commits and is not part of the preset.
_SKIPPED = {".git", ".asm", "apm_modules", "apm.lock.yaml", "__pycache__", ".venv", ".env"}
# Resolving a preset of many skills takes APM several minutes.
_LOCK_SECONDS = 600
_ICON = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_MUTEX = threading.RLock()
_APM_RUN = threading.Lock()


class StoreError(ValueError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


@dataclass
class _Entry:
    item: dict
    location: tuple[str, ...] = ()
    value: object = None
    files: tuple[str, ...] = ()


def _package_id(value):
    if (not isinstance(value, str) or len(value) > 100 or not _ID.fullmatch(value)
            or PureWindowsPath(value).is_reserved()):
        raise StoreError("Invalid package ID.")
    return value


def _relative(value):
    if not isinstance(value, str) or "\\" in value:
        raise StoreError("Invalid relative path.")
    parts = value.split("/")
    if any(not part or part in {".", ".."} or part.endswith((".", " "))
           or PureWindowsPath(part).is_reserved() or re.search(r'[<>:"|?*\x00-\x1f]', part)
           for part in parts):
        raise StoreError(f"Invalid relative path: {value}")
    return value


def _mapping(value):
    return value if isinstance(value, dict) else {}


def _text(value):
    return value if isinstance(value, str) else ""


def _json_value(value):
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    return str(value)


def _file_content(path, data):
    if path.endswith(".json"):
        try:
            return json.loads(data)
        except ValueError:
            pass
    return data.decode("utf-8", errors="replace")


def _load_manifest(data):
    try:
        value = yaml.safe_load(data)
    except yaml.YAMLError as exc:
        raise StoreError(f"Invalid apm.yml: {exc}") from exc
    if not isinstance(value, dict):
        raise StoreError("apm.yml must contain a mapping.")
    return value


def _yaml(value):
    return yaml.safe_dump(value, allow_unicode=True, sort_keys=False).encode("utf-8")


def _read_json(data, label):
    try:
        return json.loads(data)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise StoreError(f"Invalid {label}: {exc}") from exc


def _revision(files):
    digest = hashlib.sha256()
    for name, data in sorted(files.items()):
        digest.update(name.encode("utf-8") + b"\0")
        digest.update(hashlib.sha256(data).digest())
    return digest.hexdigest()


def _export_digest(bundle):
    """SHA-256 over every file of a preset's bundle, keyed by package id and path, with LF line endings.

    It names the preset content an export came from. Unlike `_revision`, which is one package's save
    token, it covers the nested stacks too and gives the same value on Windows and Linux checkouts.
    """
    digest = hashlib.sha256()
    for package_id, files in sorted(bundle.items()):
        for name, data in sorted(files.items()):
            digest.update(package_id.encode("utf-8") + b"\0" + name.encode("utf-8") + b"\0")
            digest.update(hashlib.sha256(data.replace(b"\r\n", b"\n")).digest())
    return digest.hexdigest()


def _atomic_write(path, data):
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix="_asm-tmp-", delete=False) as tmp:
        name = tmp.name
        try:
            tmp.write(data)
            tmp.close()
            os.replace(name, path)
        finally:
            Path(name).unlink(missing_ok=True)


def _instruction(data):
    lines = data.decode("utf-8").splitlines(keepends=True)
    if lines and lines[0].rstrip("\r\n") == "---":
        for index, line in enumerate(lines[1:], 1):
            if line.rstrip("\r\n") == "---":
                return "".join(lines[:index + 1]), "".join(lines[index + 1:]).strip("\r\n")
    return "", "".join(lines).strip("\r\n")


def _skill_labels(path, data):
    """A native skill's name and description from its SKILL.md front matter; the name falls back to its folder."""
    front = {}
    head, _ = _instruction(data)
    if head:
        try:
            front = yaml.safe_load("\n".join(head.splitlines()[1:-1]))
        except yaml.YAMLError:
            front = {}
        front = front if isinstance(front, dict) else {}
    own = lambda field: front[field].strip() if isinstance(front.get(field), str) else ""
    return own("name") or PurePosixPath(path).parent.name, own("description")


def _sibling(value):
    value = _mapping(value).get("path") if isinstance(value, dict) and "git" not in value else value
    found = _SIBLING.fullmatch(value) if isinstance(value, str) else None
    return _package_id(found[1]) if found else None


def _git(value):
    if isinstance(value, str):
        locator, _, ref = value.partition("#")
        if re.fullmatch(r"[\w.-]+/[\w.-]+(?:/[\w./-]+)?", locator) and not locator.startswith("."):
            owner, repo, *path = locator.split("/")
            value = {"git": f"https://github.com/{owner}/{repo}", "path": "/".join(path), "ref": ref}
        else:
            return None
    if isinstance(value, dict) and isinstance(value.get("git"), str):
        return value
    return None


def _source(kind, value):
    git = _git(value)
    if not git:
        return None
    repository = git["git"].rstrip("/").removesuffix(".git")
    if repository == "parent":
        return None
    if re.fullmatch(r"[\w.-]+/[\w.-]+", repository):
        repository = f"https://github.com/{repository}"
    path = _text(git.get("path"))
    if path:
        _relative(path)
    if kind == "skill" and PurePosixPath(path).name != "SKILL.md":
        path = f"{path}/SKILL.md" if path else "SKILL.md"
    return {"repositoryUrl": repository, "path": path, "ref": _text(git.get("ref"))}


def _source_url(source):
    if not source:
        return None
    repo, path, ref = (source[field] for field in ("repositoryUrl", "path", "ref"))
    location = urlsplit(repo)
    if location.scheme not in {"https", "http"}:
        return None
    if path and location.hostname in {"github.com", "gitlab.com"}:
        # Without a ref the source follows the default branch, which HEAD names on both hosts.
        prefix = "/-/blob/" if location.hostname == "gitlab.com" else "/blob/"
        return f"{repo}{prefix}{quote(ref or 'HEAD', safe='')}/{quote(path)}"
    return repo


def _repository_key(url):
    return url.rstrip("/").removesuffix(".git").casefold()


# The rows of the support table: the component kinds, with Plugin split by the manifest each app reads.
SUPPORT_KINDS = ("instruction", "skill", "mcp", "hook", "claude-code-plugin", "codex-plugin")
# `not-documented`: the app's page on that format says nothing, kept apart from `no`.
_SUPPORT_VALUES = ("yes", "no", "not-documented")


def _https(value):
    return isinstance(value, str) and urlsplit(value).scheme == "https" and bool(urlsplit(value).hostname)


def _consumers(data):
    """catalog/consumers.json, refused unless every cell is filled and names the page that says so."""
    data = _mapping(data)
    if data.get("kinds") != list(SUPPORT_KINDS):
        raise StoreError(f"catalog/consumers.json kinds must be {', '.join(SUPPORT_KINDS)}.")
    consumers = data.get("consumers")
    if not isinstance(consumers, list):
        raise StoreError("catalog/consumers.json consumers must be a list.")
    seen = set()
    for consumer in consumers:
        consumer = _mapping(consumer)
        identifier = consumer.get("id")
        if not isinstance(identifier, str) or not _ID.fullmatch(identifier) or identifier in seen:
            raise StoreError("Every consumer needs a unique lowercase id.")
        seen.add(identifier)
        if not _text(consumer.get("name")).strip() or not isinstance(consumer.get("export"), bool):
            raise StoreError(f"Consumer {identifier} needs a name and export true or false.")
        tools = consumer.get("tools", [])
        if not isinstance(tools, list) or any(not _text(tool).strip() for tool in tools):
            raise StoreError(f"Consumer {identifier} tools must be a list of names.")
        if "roles" in consumer:
            roles = _mapping(consumer["roles"])
            values = roles.get("values")
            if (not isinstance(values, list) or not values or any(not isinstance(v, str) or not v for v in values)
                    or not _https(roles.get("doc"))):
                raise StoreError(f"Consumer {identifier} roles need values and the doc that lists them.")
        support = consumer.get("support")
        if not isinstance(support, dict) or list(support) != list(SUPPORT_KINDS):
            raise StoreError(f"Consumer {identifier} needs one support cell per kind, in the order of kinds.")
        for kind, cell in support.items():
            cell = _mapping(cell)
            where = f"Support of {kind} by {identifier}"
            if cell.get("value") not in _SUPPORT_VALUES:
                raise StoreError(f"{where} must be {', '.join(_SUPPORT_VALUES)}.")
            if not _https(cell.get("doc")):
                raise StoreError(f"{where} needs doc, the page that says so.")
            if cell["value"] == "yes" and not _text(cell.get("name")).strip():
                raise StoreError(f"{where} needs name, the app's own term.")
            for field in ("name", "note"):
                if field in cell and not _text(cell[field]).strip():
                    raise StoreError(f"{where}: {field} must be text.")
            if set(cell) - {"value", "name", "note", "doc"}:
                raise StoreError(f"{where} has fields other than value, name, note and doc.")
    return data


def _repository_stars(rows):
    """Each catalog repository's stars and the day they were read, keyed by URL. Both are must-fill."""
    if not isinstance(rows, list):
        raise StoreError("Catalog repositories must be a list.")
    found = {}
    for row in rows:
        row = _mapping(row)
        url = row.get("url")
        if not isinstance(url, str) or not url:
            raise StoreError("Every catalog repository needs its url.")
        stars, checked = row.get("stars"), row.get("starsCheckedOn")
        if type(stars) is not int or stars < 0:
            raise StoreError(f"Catalog repository {url} needs stars, a count read from its page.")
        try:
            valid = isinstance(checked, str) and date.fromisoformat(checked).isoformat() == checked
        except ValueError:
            valid = False
        if not valid:
            raise StoreError(f"Catalog repository {url} needs starsCheckedOn, the day its stars were read (YYYY-MM-DD).")
        found[_repository_key(url)] = {"stars": stars, "starsCheckedOn": checked}
    return found


def _item_source(row):
    """A catalog item's source: derived from its APM git value, or stored for an item without one."""
    spec = row["apm"]
    if "value" in spec and isinstance(_mapping(spec["value"]).get("git"), str):
        return _source(row["kind"], spec["value"])
    return row.get("source")


def _dependency_kind(section, value):
    kind = {"mcp": "mcp", "hooks": "hook", "plugins": "plugin", "lsp": "other"}.get(section)
    if kind:
        return kind
    native = _mapping(value)
    if native.get("marketplace") and native.get("name"):
        return "plugin"
    if _sibling(value):
        return "package"
    git = _git(value)
    if git:
        declared = git.get("kind", git.get("type"))
        if isinstance(declared, str) and declared in _KINDS - {"package"}:
            return declared
        path = _text(git.get("path"))
        if "/instructions/" in f"/{path}/" or path.endswith(".instructions.md"):
            return "instruction"
        if path.endswith((".prompt.md", ".agent.md")):
            return "other"
        if "/skills/" in f"/{path}/" or PurePosixPath(path).name == "SKILL.md":
            return "skill"
    return "other"


def _identity(kind, value):
    if kind in {"skill", "instruction", "other"} and (source := _source(kind, value)):
        repo = source["repositoryUrl"]
        if repo.casefold().startswith("https://github.com/"):
            repo = repo.casefold()
        return kind, repo, source["path"], source["ref"]
    native = _mapping(value)
    if kind == "plugin":
        return kind, native.get("marketplace"), native.get("name"), native.get("version")
    if kind == "mcp":
        return kind, native.get("name", value if isinstance(value, str) else "")
    return None


def _name(kind, value, source):
    if kind == "package":
        return _sibling(value)
    if kind == "skill" and source:
        path = PurePosixPath(source["path"])
        return path.parent.name or PurePosixPath(source["repositoryUrl"]).name
    return _text(_mapping(value).get("name")) or _text(value) or kind.title()


def _component(identifier, name, kind, config, *, source=None, description="", source_url=None, file=None):
    component = {"id": identifier, "name": name, "kind": kind, "description": description,
                 "sourceUrl": source_url, "source": source, "configuration": _json_value(config)}
    if file:
        component["file"] = file
    return component


def _native_file_kind(path):
    parts = path.split("/")
    if parts[0] != ".apm" or len(parts) < 3:
        return None
    return {"hooks": "hook", "skills": "skill", "instructions": "instruction",
            "plugins": "plugin", "mcp": "mcp"}.get(parts[1], "other")


class Store:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()

    def _checked(self, path):
        cursor = self.root
        for part in path.relative_to(self.root).parts:
            cursor /= part
            if cursor.is_symlink() or (hasattr(cursor, "is_junction") and cursor.is_junction()):
                raise StoreError(f"Linked paths are not supported: {cursor.relative_to(self.root).as_posix()}")
        return path

    def _directory(self, identifier):
        return self._checked(self.root / "packages" / _package_id(identifier))

    def _snapshot(self, identifier):
        directory = self._directory(identifier)
        if not self._checked(directory / "apm.yml").is_file():
            raise StoreError(f"Package {identifier} was not found.", 404)
        files = {}
        for current, dirs, names in os.walk(directory):
            current = Path(current)
            dirs[:] = [name for name in dirs if name not in _SKIPPED]
            for name in (*dirs, *names):
                if name in _SKIPPED or name.startswith("_asm-tmp-"):
                    continue
                path = self._checked(current / name)
                relative = _relative(path.relative_to(directory).as_posix())
                if name in names and path.is_file():
                    files[relative] = path.read_bytes()
        return files

    def _catalog(self):
        path = self._checked(self.root / "catalog" / "components.json")
        if not path.is_file():
            return {"items": [], "repositories": []}
        catalog = _read_json(path.read_bytes(), "component catalog")
        catalog.setdefault("repositories", [])
        stars = _repository_stars(catalog["repositories"])
        for row in catalog["items"]:
            repository = _item_source(row)
            if repository and _repository_key(repository["repositoryUrl"]) not in stars:
                raise StoreError(f"Catalog item {row['id']} comes from {repository['repositoryUrl']}, "
                                 "which has no repositories row with its stars.")
        return catalog

    def consumers(self):
        """What each app supports per component kind, from catalog/consumers.json; none without the file."""
        path = self._checked(self.root / "catalog" / "consumers.json")
        if not path.is_file():
            return {"kinds": list(SUPPORT_KINDS), "consumers": []}
        return _consumers(_read_json(path.read_bytes(), "consumer support data"))

    def _paperclip_roles(self):
        for consumer in self.consumers()["consumers"]:
            if consumer["id"] == "paperclip" and "roles" in consumer:
                return consumer["roles"]["values"]
        raise StoreError("catalog/consumers.json lists no Paperclip roles to check the role against.")

    def _entries(self, identifier, model, files, catalog):
        entries = []
        seen = set()
        by_path, by_identity = {}, {}
        for row in catalog:
            spec = row["apm"]
            if "path" in spec:
                by_path[spec["path"]] = row
            elif (identity := _identity(row["kind"], spec["value"])):
                by_identity[identity] = row

        def add(item, **kwargs):
            base = item["id"]
            number = 2
            while item["id"] in seen:
                item["id"] = f"{base}:{number}"
                number += 1
            seen.add(item["id"])
            entries.append(_Entry(item, **kwargs))

        for location in _LISTS:
            parent = model if len(location) == 1 else _mapping(model.get(location[0]))
            section = location[-1]
            values = parent.get(section)
            if section in {"hooks", "plugins"} and values and not isinstance(values, list):
                values = [values]
            elif not isinstance(values, list):
                continue
            for value in values:
                kind = _dependency_kind(section, value)
                entry = by_identity.get(_identity(kind, value))
                if entry is None and kind == "other" and section == "apm":
                    entry = by_identity.get(_identity("skill", value))
                    if entry:
                        kind = "skill"
                source = _source(kind, value) if section == "apm" else None
                name = entry["name"] if entry else _name(kind, value, source)
                config = value
                if kind == "package":
                    target = self._directory(name) / "apm.yml"
                    stored = _load_manifest(self._checked(target).read_bytes()) if target.is_file() else {}
                    item = _component(f"package:{name}",
                                      _mapping(stored.get("x-preset-labels")).get("title", name),
                                      kind, {"packageId": name}, description=_text(stored.get("description")))
                elif entry:
                    item = _component(entry["id"], name, kind, config, source=entry.get("source") or source,
                                      description=entry["description"], source_url=entry.get("sourceUrl") or _source_url(source))
                else:
                    digest = hashlib.sha256(_yaml(value)).hexdigest()[:16]
                    item = _component(f"{kind}:{digest}", name, kind, config,
                                      source=source, source_url=_source_url(source))
                add(item, location=location, value=value)

        primary = _PRIMARY.format(identifier)
        for path, data in sorted(files.items()):
            kind = _native_file_kind(path)
            if not kind or path == primary:
                continue
            parts = path.split("/")
            names = (path,)
            if kind == "skill" and len(parts) >= 4:
                skill_root = "/".join(parts[:3])
                skill_file = f"{skill_root}/SKILL.md"
                if path != skill_file and skill_file in files:
                    continue
                if path == skill_file:
                    names = tuple(name for name in files if name.startswith(f"{skill_root}/"))
            entry = by_path.get(path)
            name, description = PurePosixPath(path).stem, ""
            if entry:
                name, description = entry["name"], entry["description"]
            elif kind == "skill" and PurePosixPath(path).name == "SKILL.md":
                name, description = _skill_labels(path, data)
            config = _file_content(path, data)
            item = _component(entry["id"] if entry else f"{kind}:{path}", name, kind, config,
                              description=description,
                              source=entry.get("source") if entry else None,
                              source_url=entry.get("sourceUrl") if entry else None, file=path)
            add(item, files=names)
        return entries

    def _package(self, identifier, files, catalog):
        model = _load_manifest(files["apm.yml"])
        labels = _mapping(model.get("x-preset-labels"))
        entries = self._entries(identifier, model, files, catalog)
        _, instruction = _instruction(files.get(_PRIMARY.format(identifier), b""))
        kind = labels.get("kind")
        paperclip = _mapping(labels.get("paperclip"))
        package = {
            "id": identifier, "title": _text(labels.get("title")) or _text(model.get("name")) or identifier,
            "description": _text(model.get("description")), "kind": "stack" if kind == "stack" else "preset",
            "icon": _text(labels.get("icon")),
            "version": str(model.get("version", "")), "componentCount": 1 + len(entries),
            **{key: [value for value in labels[key] if isinstance(value, str)]
               if isinstance(labels.get(key), list) else [] for key in ("workArea", "usage")},
            "paperclip": {"role": _text(paperclip.get("role")) or None,
                          "canCreateAgents": paperclip.get("canCreateAgents") is True},
            "revision": _revision(files), "instruction": instruction,
            "components": [_component("instruction", "Instruction", "instruction", instruction),
                           *(entry.item for entry in entries)],
            "files": [{"path": path, "content": data.decode("utf-8", errors="replace")}
                      for path, data in sorted(files.items())],
        }
        return package, model, entries

    def _ids(self):
        directory = self._checked(self.root / "packages")
        if directory.is_dir():
            for path in sorted(directory.iterdir()):
                if _ID.fullmatch(path.name) and self._checked(path / "apm.yml").is_file():
                    yield path.name

    def get(self, identifier):
        with _MUTEX:
            return self._package(identifier, self._snapshot(identifier), self._catalog()["items"])[0]

    def list_packages(self):
        with _MUTEX:
            summaries = []
            for identifier in self._ids():
                package = self.get(identifier)
                summaries.append({key: package[key] for key in (
                    "id", "title", "description", "kind", "icon", "version", "workArea", "usage", "componentCount")})
            return summaries

    def catalog(self):
        with _MUTEX:
            catalog = self._catalog()
            stars = _repository_stars(catalog["repositories"])
            items = []
            for row in catalog["items"]:
                spec = row["apm"]
                config = _file_content(spec["path"], spec["content"].encode("utf-8")) if "path" in spec else spec["value"]
                source = _item_source(row)
                item = {**row, "type": "component", "configuration": config,
                        "source": source, "sourceUrl": row.get("sourceUrl") or _source_url(source)}
                if source:
                    item.update(stars[_repository_key(source["repositoryUrl"])])
                items.append(item)
            return {"items": [
                *items, *({**row, "id": f"package:{row['id']}", "packageId": row["id"],
                           "type": row["kind"]} for row in self.list_packages()),
            ]}

    def create(self, payload):
        title = _text(payload.get("title")).strip()
        if not title:
            raise StoreError("A title is required.")
        normalized = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
        slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
        identifier = _package_id(slug or f"package-{hashlib.sha256(title.encode('utf-8')).hexdigest()[:12]}")
        with _MUTEX:
            directory = self._directory(identifier)
            if directory.exists():
                raise StoreError(f"Package {identifier} already exists.", 409)
            model = {"name": identifier, "version": "0.1.0", "description": "",
                     "dependencies": {"apm": [], "mcp": []}, "x-preset-labels": {"title": title, "kind": "preset",
                                                                              "workArea": [], "usage": []}}
            files = {_PRIMARY.format(identifier): b"---\n" + _yaml({"name": identifier}) + b"---\n"}
            return self._save(identifier, payload, model, [], files, previous=None)

    def save(self, identifier, payload):
        with _MUTEX:
            previous = self._snapshot(identifier)
            if not isinstance(payload.get("revision"), str):
                raise StoreError(f"revision is required: send the revision from GET /api/presets/{identifier}.")
            if payload.get("revision") != _revision(previous):
                raise StoreError("This package changed. Reload it before saving.", 409)
            _, model, entries = self._package(identifier, previous, self._catalog()["items"])
            return self._save(identifier, payload, model, entries, previous.copy(), previous=previous)

    def _save(self, identifier, payload, model, entries, files, *, previous):
        labels = model.setdefault("x-preset-labels", {})
        if not isinstance(labels, dict):
            raise StoreError("x-preset-labels must contain a mapping.")
        for field in ("title", "description", "instruction"):
            if field in payload and not isinstance(payload[field], str):
                raise StoreError(f"{field} must be text.")
        if "title" in payload:
            if not payload["title"].strip():
                raise StoreError("A title is required.")
            labels["title"] = payload["title"].strip()
        if "description" in payload:
            model["description"] = payload["description"]
        if "kind" in payload:
            if payload["kind"] not in ("stack", "preset"):
                raise StoreError("Kind must be stack or preset.")
            labels["kind"] = payload["kind"]
        if "icon" in payload:
            icon = payload["icon"]
            if not isinstance(icon, str) or icon and not _ICON.fullmatch(icon) or len(icon) > 40:
                raise StoreError("icon must be an icon name such as rocket or folder-git-2.")
            if icon:
                labels["icon"] = icon
            else:
                labels.pop("icon", None)
        for field in ("workArea", "usage"):
            if field in payload:
                labels[field] = self._strings(payload[field], field)
        if "paperclip" in payload:
            self._paperclip(labels, payload["paperclip"])
        if "instruction" in payload:
            path = _PRIMARY.format(identifier)
            old = files.get(path, b"")
            front, body = _instruction(old)
            new = payload["instruction"].strip("\r\n")
            if new != body:
                files[path] = (front + ("\n" if front and new else "") + new + ("\n" if new else "")).encode("utf-8")

        catalog = self._catalog()["items"]
        if "componentIds" in payload:
            selected = self._strings(payload["componentIds"], "componentIds")
            self._select(identifier, model, entries, files, selected, catalog)

        if previous is None or _load_manifest(previous["apm.yml"]) != model:
            files["apm.yml"] = _yaml(model)
        self._bundle(identifier, files)
        result = self._package(identifier, files, catalog)[0]
        directory = self._directory(identifier)
        if previous is None:
            try:
                directory.mkdir(parents=True)
            except FileExistsError as exc:
                raise StoreError(f"Package {identifier} already exists.", 409) from exc
        elif previous != self._snapshot(identifier):
            raise StoreError("This package changed. Reload it before saving.", 409)
        for path, data in files.items():
            if previous is None or previous.get(path) != data:
                target = self._checked(directory / _relative(path))
                target.parent.mkdir(parents=True, exist_ok=True)
                _atomic_write(target, data)
        for path in (previous or {}).keys() - files.keys():
            self._checked(directory / path).unlink()
        # A saved stack changes the export of every preset that includes it, so every preset is rewritten.
        from .paperclip import write_exports
        write_exports(self.root)
        return result

    def _paperclip(self, labels, value):
        """Write x-preset-labels.paperclip from the payload; an empty role or false removes its key."""
        if not isinstance(value, dict) or set(value) - {"role", "canCreateAgents"}:
            raise StoreError("paperclip must be an object with role and canCreateAgents.")
        role = value.get("role")
        if role is not None and not isinstance(role, str):
            raise StoreError("paperclip.role must be text.")
        allowed = value.get("canCreateAgents", False)
        if not isinstance(allowed, bool):
            raise StoreError("paperclip.canCreateAgents must be true or false.")
        stored = labels.get("paperclip")
        block = dict(stored) if isinstance(stored, dict) else {}
        # A role already in apm.yml is kept even when it is not Paperclip's, so other edits still save;
        # the export reports it as needing attention.
        if role and role != block.get("role") and role not in (roles := self._paperclip_roles()):
            raise StoreError(f"Role {role} is not one of Paperclip's roles: {', '.join(roles)}.")
        block.pop("role", None)
        block.pop("canCreateAgents", None)
        if role:
            block["role"] = role
        if allowed:
            block["canCreateAgents"] = True
        if block:
            labels["paperclip"] = block
        else:
            labels.pop("paperclip", None)

    @staticmethod
    def _strings(values, field):
        if not isinstance(values, list) or any(not isinstance(value, str) or not value.strip() for value in values):
            raise StoreError(f"{field} must be a list of nonempty strings.")
        return list(dict.fromkeys(values))

    def _select(self, identifier, model, entries, files, selected, catalog):
        recognized = {entry.item["id"]: entry for entry in entries}
        selected_set = set(selected)
        available = {row["id"]: row["apm"] for row in catalog}
        manifest_entries = {}
        for entry in entries:
            if entry.location:
                manifest_entries.setdefault(entry.location, [])
            if entry.item["id"] not in selected_set:
                for path in entry.files:
                    del files[path]
        for item_id in selected:
            if item_id == "instruction":
                continue
            if item_id in recognized:
                entry = recognized[item_id]
                if entry.location:
                    manifest_entries[entry.location].append(entry.value)
            elif item_id.startswith("package:"):
                target = _package_id(item_id.removeprefix("package:"))
                if target != identifier:
                    manifest = _load_manifest(self._snapshot(target)["apm.yml"])
                    if _mapping(manifest.get("x-preset-labels")).get("kind") != "stack":
                        raise StoreError("Only stacks can be added as package dependencies.")
                manifest_entries.setdefault(("dependencies", "apm"), []).append(f"../{target}")
            elif item_id in available:
                spec = available[item_id]
                if "path" in spec:
                    path = _relative(spec["path"])
                    if not _native_file_kind(path) or any(name.casefold() == path.casefold() for name in files):
                        raise StoreError(f"Component file path is unavailable: {path}")
                    files[path] = spec["content"].encode("utf-8")
                elif spec["section"] in ("apm", "mcp"):
                    manifest_entries.setdefault(("dependencies", spec["section"]), []).append(spec["value"])
                else:
                    raise StoreError(f"Unsupported catalog component: {item_id}")
            else:
                raise StoreError(f"Unknown component: {item_id}")
        for location, values in manifest_entries.items():
            parent = model if len(location) == 1 else model.setdefault(location[0], {})
            section = location[-1]
            if isinstance(parent, dict) and isinstance(parent.get(section, []), list):
                parent[section] = values
            elif isinstance(parent, dict) and section in {"hooks", "plugins"}:
                if not values:
                    del parent[section]
            else:
                raise StoreError(f"Cannot edit {'.'.join(location)} because it is not a list.")

    def _bundle(self, identifier, files):
        bundle = {}

        def visit(current, snapshot, lineage):
            if current in lineage:
                raise StoreError(f"Package dependency cycle: {' -> '.join((*lineage, current))}.")
            if current in bundle:
                return
            bundle[current] = snapshot
            model = _load_manifest(snapshot["apm.yml"])
            values = _mapping(model.get("dependencies")).get("apm", [])
            for value in values if isinstance(values, list) else ():
                if target := _sibling(value):
                    visit(target, files if target == identifier else self._snapshot(target), (*lineage, current))

        visit(identifier, files, ())
        return bundle

    def export(self, identifier):
        with _MUTEX:
            packages = self._bundle(identifier, self._snapshot(identifier))
            buffer = io.BytesIO()
            with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
                for package_id, files in packages.items():
                    for path, data in sorted(files.items()):
                        archive.writestr(f"{package_id}/{path}" if len(packages) > 1 else path, data)
            return buffer.getvalue()

    def _comment_file(self, identifier, component_id):
        if not any(item["id"] == component_id for item in self.get(identifier)["components"]):
            raise StoreError("Component was not found.", 404)
        key = hashlib.sha256(component_id.encode("utf-8")).hexdigest()
        return self._checked(self.root / ".asm" / "comments" / identifier / f"{key}.json")

    def comments(self, identifier, component_id):
        with _MUTEX:
            path = self._comment_file(identifier, component_id)
            return _read_json(path.read_bytes(), "comments") if path.is_file() else []

    def add_comment(self, identifier, component_id, payload):
        body = _text(payload.get("body")).strip()
        if not body:
            raise StoreError("Comment body is required.")
        comment = {"id": uuid.uuid4().hex, "body": body, "author": _text(payload.get("author")).strip() or "Local user",
                   "createdAt": datetime.now(timezone.utc).isoformat()}
        with _MUTEX:
            path = self._comment_file(identifier, component_id)
            comments = self.comments(identifier, component_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write(path, json.dumps([*comments, comment], ensure_ascii=False, indent=2).encode("utf-8"))
        return comment

    def lock(self, identifier, update=False):
        # APM can run for minutes, so only the check holds _MUTEX; reads and saves go on meanwhile.
        # apm.lock.yaml is not part of a save, and _APM_RUN keeps two locks from writing it at once.
        with _MUTEX:
            files = self._snapshot(identifier)
            bundle = self._bundle(identifier, files)
            for snapshot in bundle.values():
                self._check_lock_paths(snapshot, bundle)
            directory = self._directory(identifier)
        command = self._apm_command()
        if not command:
            return {"ok": False, "output": "Microsoft APM CLI was not found on this machine."}
        with _APM_RUN:
            try:
                result = subprocess.run([*command, "lock", *(["--update"] if update else [])],
                                        cwd=directory, stdin=subprocess.DEVNULL,
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False,
                                        timeout=_LOCK_SECONDS, encoding="utf-8", errors="replace")
            except subprocess.TimeoutExpired:
                return {"ok": False, "output": f"APM lock timed out after {_LOCK_SECONDS} seconds."}
            except OSError as exc:
                return {"ok": False, "output": f"Could not start Microsoft APM CLI: {exc}"}
            return {"ok": result.returncode == 0, "output": result.stdout.strip()}

    @staticmethod
    def _check_lock_paths(files, bundle):
        model = _load_manifest(files["apm.yml"])
        deps = _mapping(model.get("dependencies")).get("apm")
        replacements = model.get("replace")
        candidates = list(deps) if isinstance(deps, list) else []
        if isinstance(replacements, list):
            candidates.extend(_mapping(rule).get("with") for rule in replacements)
        for entry in candidates:
            if git := _git(entry):
                if git["git"].lower().startswith("file:"):
                    raise StoreError("Local dependency must stay inside this package or reference a saved package.")
                _source("other", entry)
                continue
            path = _mapping(entry).get("path")
            if isinstance(entry, str) and re.match(r"^(?:[.~][/\\]|\.\.[/\\]|[/\\]|[a-zA-Z]:|file:)", entry, re.I):
                path = entry
            if path is None or _sibling(entry) in bundle:
                continue
            if isinstance(path, str) and path.startswith("./"):
                relative = _relative(path.removeprefix("./"))
                if relative in files or any(name.startswith(f"{relative}/") for name in files):
                    continue
            raise StoreError("Local dependency must stay inside this package or reference a saved package.")

    @staticmethod
    def _apm_command():
        # Atom's legacy apm.cmd is not Microsoft APM. Use an executable or the Python entry point.
        if executable := shutil.which("apm.exe" if os.name == "nt" else "apm"):
            return [executable]
        if importlib.util.find_spec("apm_cli"):
            return [sys.executable, "-P", "-m", "apm_cli.entrypoint"]
        return []
