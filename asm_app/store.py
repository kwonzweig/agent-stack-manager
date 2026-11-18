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
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from urllib.parse import quote, urlsplit
from zipfile import ZIP_DEFLATED, ZipFile

import yaml


_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_SIBLING = re.compile(r"\.\./([^/]+)")
_PRIMARY = ".apm/agents/{}.agent.md"
_KINDS = {"skill", "mcp", "hook", "plugin", "instruction", "package", "other"}
_INVENTORY = "x-app-inventory"
_INVENTORY_APPS = {"codex", "claude"}
_INVENTORY_REPO = re.compile(r"https://github\.com/[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+")
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
        if not _text(consumer.get("name")).strip():
            raise StoreError(f"Consumer {identifier} needs a name.")
        if "export" in consumer and not isinstance(consumer["export"], bool):
            raise StoreError(f"Consumer {identifier} export must be true or false.")
        tools = consumer.get("tools", [])
        if not isinstance(tools, list) or any(not _text(tool).strip() for tool in tools):
            raise StoreError(f"Consumer {identifier} tools must be a list of names.")
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


# What a repository owns. ASM reads these from the source when it shows them (asm_app/sources.py).
_READ_FROM_SOURCE = ("description", "stars", "starsCheckedOn", "installs", "installsCheckedOn",
                     "descriptionUrl", "descriptionCheckedOn")


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


def _app_inventory(model):
    if _INVENTORY not in model:
        return None
    inventory = model[_INVENTORY]
    if not isinstance(inventory, dict) or not isinstance(inventory.get("items"), list):
        raise StoreError(f"{_INVENTORY} must contain an items list.")
    seen = set()
    for item in inventory["items"]:
        if not isinstance(item, dict) or any(not _text(item.get(key)).strip() for key in ("id", "name", "kind")):
            raise StoreError("Each inventory item needs a text id, name and kind.")
        identifier = item["id"]
        if identifier in seen:
            raise StoreError(f"Duplicate inventory item: {identifier}")
        seen.add(identifier)
        if not isinstance(item.get("description"), str):
            raise StoreError(f"Inventory item {identifier} needs a text description.")
        apps = item.get("apps")
        if not isinstance(apps, dict) or not apps or set(apps) - _INVENTORY_APPS:
            raise StoreError(f"Inventory item {identifier} needs Codex or Claude Code app states.")
        for state in apps.values():
            if (not isinstance(state, dict) or not isinstance(state.get("installed"), bool)
                    or any(key not in state or (state[key] is not None and not isinstance(state[key], bool))
                           for key in ("enabled", "selected"))):
                raise StoreError(f"Inventory item {identifier} needs installed, enabled and selected states.")
    return inventory


def _select_inventory(model, changes):
    inventory = _app_inventory(model)
    if inventory is None or not isinstance(changes, dict):
        raise StoreError("appInventorySelections requires a preset inventory and an object of item selections.")
    items = {item["id"]: item["apps"] for item in inventory["items"]}
    for identifier, apps in changes.items():
        if identifier not in items or not isinstance(apps, dict):
            raise StoreError(f"Invalid inventory selection: {identifier}")
        for app, selected in apps.items():
            if app not in items[identifier]:
                raise StoreError(f"{identifier} is not installed in {app}.")
            if selected is not None and not isinstance(selected, bool):
                raise StoreError("An inventory selection must be true, false or null.")
            items[identifier][app]["selected"] = selected


def _managed_inventory_skills(inventory):
    result = {}
    for item in inventory["items"]:
        spec = item.get("apm")
        if spec is None:
            continue
        if (item["kind"] != "skill" or not isinstance(spec, dict)
                or set(spec) - {"git", "ref", "path"}
                or not _text(spec.get("ref")).strip()
                or ("path" in spec and not _text(spec["path"]).strip())
                or not _INVENTORY_REPO.fullmatch(_text(spec.get("git")))
                or not (identity := _identity("skill", spec))):
            raise StoreError(f"Inventory item {item['id']} needs a GitHub APM skill reference with a ref and optional path.")
        result.setdefault(identity, {"spec": spec, "selected": False})
        if any(state["selected"] is True for state in item["apps"].values()):
            result[identity]["selected"] = True
    return result


def _sync_inventory_skills(model):
    inventory = _app_inventory(model)
    managed = _managed_inventory_skills(inventory) if inventory is not None else {}
    if not managed:
        return
    dependencies = model.setdefault("dependencies", {})
    if not isinstance(dependencies, dict) or not isinstance(dependencies.get("apm", []), list):
        raise StoreError("Managed inventory skills need a dependencies.apm list.")
    kept = []
    seen = set()
    for spec in dependencies.get("apm", []):
        identity = _identity("skill", spec)
        if identity not in managed or managed[identity]["selected"]:
            kept.append(spec)
            seen.add(identity)
    kept.extend(ref["spec"] for identity, ref in managed.items() if ref["selected"] and identity not in seen)
    dependencies["apm"] = kept


def _native_file_kind(path):
    parts = path.split("/")
    if parts[0] != ".apm" or len(parts) < 3:
        return None
    return {"hooks": "hook", "skills": "skill", "instructions": "instruction",
            "plugins": "plugin", "mcp": "mcp"}.get(parts[1], "other")


class Store:
    def __init__(self, root: Path, *, base_root: Path | None = None):
        self.root = Path(root).resolve()
        self.base_root = Path(base_root).resolve() if base_root is not None else None
        if self.base_root is not None:
            if self.root.is_relative_to(self.base_root) or self.base_root.is_relative_to(self.root):
                raise StoreError("The private root and read-only base must be separate folders.")
            if not self._checked(self.base_root / "packages", root=self.base_root).is_dir():
                raise StoreError("The read-only base must contain a packages folder.")

    def _checked(self, path, *, root=None):
        root = self.root if root is None else root
        cursor = root
        for part in path.relative_to(root).parts:
            cursor /= part
            if cursor.is_symlink() or (hasattr(cursor, "is_junction") and cursor.is_junction()):
                raise StoreError(f"Linked paths are not supported: {cursor.relative_to(root).as_posix()}")
        return path

    def _directory(self, identifier, *, root=None):
        root = self.root if root is None else root
        return self._checked(root / "packages" / _package_id(identifier), root=root)

    def _package_root(self, identifier):
        local = self._directory(identifier)
        if self.base_root is not None and not self._checked(local / "apm.yml").is_file():
            directory = self._directory(identifier, root=self.base_root)
            if self._checked(directory / "apm.yml", root=self.base_root).is_file():
                return self.base_root
        return self.root

    def _snapshot(self, identifier):
        root = self._package_root(identifier)
        directory = self._directory(identifier, root=root)
        if not self._checked(directory / "apm.yml", root=root).is_file():
            raise StoreError(f"Package {identifier} was not found.", 404)
        files = {}
        for current, dirs, names in os.walk(directory):
            current = Path(current)
            dirs[:] = [name for name in dirs if name not in _SKIPPED]
            for name in (*dirs, *names):
                if name in _SKIPPED or name.startswith("_asm-tmp-"):
                    continue
                path = self._checked(current / name, root=root)
                relative = _relative(path.relative_to(directory).as_posix())
                if name in names and path.is_file():
                    files[relative] = path.read_bytes()
        return files

    def _catalog(self):
        root = self.base_root if self.base_root is not None else self.root
        path = self._checked(root / "catalog" / "components.json", root=root)
        if not path.is_file():
            return {"items": []}
        catalog = _read_json(path.read_bytes(), "component catalog")
        for row in catalog["items"]:
            stored = [field for field in _READ_FROM_SOURCE if field in row]
            if _item_source(row) and stored:
                raise StoreError(f"Catalog item {row['id']} stores {', '.join(stored)}, which its repository owns. "
                                 "Remove them: ASM reads them from the source.")
        return catalog

    def consumers(self):
        """Documented app support plus the exporters installed in this process."""
        from .exporters import EXPORTERS

        root = self.base_root if self.base_root is not None else self.root
        path = self._checked(root / "catalog" / "consumers.json", root=root)
        if not path.is_file():
            return {"kinds": list(SUPPORT_KINDS), "consumers": []}
        data = _consumers(_read_json(path.read_bytes(), "consumer support data"))
        for consumer in data["consumers"]:
            consumer["export"] = consumer["id"] in EXPORTERS
        return data

    def _entries(self, identifier, model, files, catalog, inventory_skills=None):
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
                managed = (location == ("dependencies", "apm") and
                           _identity("skill", value) in (inventory_skills or {}))
                if managed:
                    kind = "skill"
                entry = by_identity.get(_identity(kind, value))
                if entry is None and kind == "other" and section == "apm":
                    entry = by_identity.get(_identity("skill", value))
                    if entry:
                        kind = "skill"
                source = _source(kind, value) if section == "apm" else None
                name = entry["name"] if entry else _name(kind, value, source)
                config = value
                if kind == "package":
                    root = self._package_root(name)
                    target = self._checked(self._directory(name, root=root) / "apm.yml", root=root)
                    stored = _load_manifest(target.read_bytes()) if target.is_file() else {}
                    item = _component(f"package:{name}",
                                      _mapping(stored.get("x-preset-labels")).get("title", name),
                                      kind, {"packageId": name}, description=_text(stored.get("description")))
                elif entry:
                    item = _component(entry["id"], name, kind, config, source=entry.get("source") or source,
                                      description=entry.get("description", ""), source_url=entry.get("sourceUrl") or _source_url(source))
                else:
                    digest = hashlib.sha256(_yaml(value)).hexdigest()[:16]
                    item = _component(f"{kind}:{digest}", name, kind, config,
                                      source=source, source_url=_source_url(source))
                if managed:
                    item["managedByInventory"] = True
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
                name, description = entry["name"], entry.get("description", "")
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
        inventory = _app_inventory(model)
        inventory_skills = _managed_inventory_skills(inventory) if inventory is not None else None
        entries = self._entries(identifier, model, files, catalog, inventory_skills)
        _, instruction = _instruction(files.get(_PRIMARY.format(identifier), b""))
        kind = labels.get("kind")
        package = {
            "id": identifier, "title": _text(labels.get("title")) or _text(model.get("name")) or identifier,
            "description": _text(model.get("description")), "kind": "stack" if kind == "stack" else "preset",
            "icon": _text(labels.get("icon")),
            "version": str(model.get("version", "")), "componentCount": 1 + len(entries),
            **{key: [value for value in labels[key] if isinstance(value, str)]
               if isinstance(labels.get(key), list) else [] for key in ("workArea", "usage")},
            "revision": _revision(files), "instruction": instruction,
            "components": [_component("instruction", "Instruction", "instruction", instruction),
                           *(entry.item for entry in entries)],
            "files": [{"path": path, "content": data.decode("utf-8", errors="replace")}
                      for path, data in sorted(files.items())],
        }
        if inventory is not None:
            package["appInventory"] = _json_value(inventory["items"])
            package["componentCount"] = (len(inventory["items"]) +
                                         sum(not entry.item.get("managedByInventory") for entry in entries) +
                                         bool(instruction.strip()))
            if "coverage" in inventory:
                package["appInventoryCoverage"] = _json_value(inventory["coverage"])
        return package, model, entries

    def _ids(self):
        packages = set()
        for root in dict.fromkeys((self.root, self.base_root)):
            if root is None:
                continue
            directory = self._checked(root / "packages", root=root)
            if directory.is_dir():
                for path in directory.iterdir():
                    if _ID.fullmatch(path.name) and self._checked(path / "apm.yml", root=root).is_file():
                        packages.add(path.name)
        yield from sorted(packages)

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
            items = []
            for row in catalog["items"]:
                spec = row["apm"]
                config = _file_content(spec["path"], spec["content"].encode("utf-8")) if "path" in spec else spec["value"]
                source = _item_source(row)
                items.append({**row, "type": "component", "configuration": config,
                              "source": source, "sourceUrl": row.get("sourceUrl") or _source_url(source)})
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
            if directory.exists() or self._package_root(identifier) != self.root:
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
        if "instruction" in payload:
            path = _PRIMARY.format(identifier)
            old = files.get(path, b"")
            front, body = _instruction(old)
            new = payload["instruction"].strip("\r\n")
            if new != body:
                files[path] = (front + ("\n" if front and new else "") + new + ("\n" if new else "")).encode("utf-8")

        catalog = self._catalog()["items"]
        if "appInventorySelections" in payload:
            _select_inventory(model, payload["appInventorySelections"])
        if "componentIds" in payload:
            selected = self._strings(payload["componentIds"], "componentIds")
            self._select(identifier, model, entries, files, selected, catalog)
        _sync_inventory_skills(model)

        if previous is None or _load_manifest(previous["apm.yml"]) != model:
            files["apm.yml"] = _yaml(model)
        self._bundle(identifier, files)
        result = self._package(identifier, files, catalog)[0]
        directory = self._directory(identifier)
        inherited = self._package_root(identifier) != self.root
        if previous is None:
            try:
                directory.mkdir(parents=True)
            except FileExistsError as exc:
                raise StoreError(f"Package {identifier} already exists.", 409) from exc
        elif previous != self._snapshot(identifier):
            raise StoreError("This package changed. Reload it before saving.", 409)
        if inherited:
            if previous == files:
                return result
            directory.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="_asm-tmp-", dir=directory.parent) as temporary:
                staged = Path(temporary) / "package"
                for path, data in files.items():
                    target = staged / _relative(path)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
                if previous != self._snapshot(identifier) or directory.exists():
                    raise StoreError("This package changed. Reload it before saving.", 409)
                staged.rename(directory)
        else:
            for path, data in files.items():
                if previous is None or previous.get(path) != data:
                    target = self._checked(directory / _relative(path))
                    target.parent.mkdir(parents=True, exist_ok=True)
                    _atomic_write(target, data)
            for path in (previous or {}).keys() - files.keys():
                self._checked(directory / path).unlink()
        # A saved stack changes the export of every preset that includes it, so every preset is rewritten.
        from .paperclip import write_exports
        write_exports(self.root, store=self)
        return result

    @staticmethod
    def _strings(values, field):
        if not isinstance(values, list) or any(not isinstance(value, str) or not value.strip() for value in values):
            raise StoreError(f"{field} must be a list of nonempty strings.")
        return list(dict.fromkeys(values))

    def _select(self, identifier, model, entries, files, selected, catalog):
        recognized = {entry.item["id"]: entry for entry in entries}
        selected_set = set(selected)
        for entry in entries:
            if entry.item.get("managedByInventory") and entry.item["id"] not in selected_set:
                selected.append(entry.item["id"])
                selected_set.add(entry.item["id"])
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
            if self.base_root is None:
                return self._run_lock(command, directory, update)
            return self._lock_overlay(identifier, bundle, command, update)

    @staticmethod
    def _run_lock(command, directory, update):
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

    def _lock_overlay(self, identifier, bundle, command, update):
        scratch = self._checked(self.root / ".asm")
        scratch.mkdir(parents=True, exist_ok=True)
        cache = self._checked(scratch / "locks" / identifier / "apm.lock.yaml")
        with tempfile.TemporaryDirectory(prefix="lock-", dir=scratch) as temporary:
            staged = Path(temporary)
            for package, files in bundle.items():
                for path, data in files.items():
                    target = staged / package / path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
            directory = staged / identifier
            staged_lock = directory / "apm.lock.yaml"
            origin = self._package_root(identifier)
            source = self._checked(self._directory(identifier, root=origin) / staged_lock.name, root=origin)
            output = source if origin == self.root else cache
            previous = next((path for path in (output, cache, source) if path.is_file()), None)
            if previous is not None:
                staged_lock.write_bytes(previous.read_bytes())
            result = self._run_lock(command, directory, update)
            if result["ok"] and staged_lock.is_file():
                with _MUTEX:
                    if self._bundle(identifier, self._snapshot(identifier)) != bundle:
                        return {"ok": False, "output": "This package or a dependency changed during APM lock. Run it again."}
                    self._checked(output).parent.mkdir(parents=True, exist_ok=True)
                    _atomic_write(output, staged_lock.read_bytes())
            return result

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
