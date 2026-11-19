"""Convert an APM preset into a company package that Paperclip can import."""

from io import BytesIO
import os
from pathlib import Path, PurePosixPath
import re
import tomllib
from zipfile import ZIP_DEFLATED, ZipFile

import yaml

from . import export_graph


GITHUB = re.compile(r"https://github\.com/([\w.-]+)/([\w.-]+)", re.IGNORECASE | re.ASCII)
# Paperclip stores a role outside its own list when a package names none, so every agent names `general`.
# A role or right the company needs is set in Paperclip after the import.
ROLE = "general"
# Every preset's export is committed here, one folder per package id, and Paperclip imports it by URL.
EXPORTS = "exports/paperclip"
# A preset's own skill is read from this repository's main branch once it is committed there.
OWN_BRANCH = "main"


class _PaperclipDumper(yaml.SafeDumper):
    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)


def _yaml(value):
    return yaml.dump(value, Dumper=_PaperclipDumper, sort_keys=False, allow_unicode=True)


def _frontmatter(value, body=""):
    return f"---\n{_yaml(value)}---\n\n{body}\n"


def _instruction(text):
    return text.replace("\r\n", "\n").strip()


def _repository(root):
    """This repository's GitHub URL, from `project.urls.Repository` in its pyproject.toml."""
    try:
        with open(Path(root) / "pyproject.toml", "rb") as file:
            project = tomllib.load(file).get("project", {})
    except (OSError, tomllib.TOMLDecodeError):
        return None
    url = project.get("urls", {}).get("Repository") if isinstance(project.get("urls"), dict) else None
    return url.rstrip("/").removesuffix(".git") if isinstance(url, str) else None


class _Reason(str):
    cause = None


def _because(text, cause):
    """A reason that also names why Paperclip leaves the component out as expected."""
    reason = _Reason(text)
    reason.cause = cause
    return reason


def _status(status, reason):
    result = {"status": status, "reason": str(reason)}
    cause = getattr(reason, "cause", None)
    if cause:
        result["cause"] = cause
    return result


def _folder(path):
    """A skill's folder inside its repository: `.` for the root, never an empty string."""
    path = (path or "").strip("/")
    if PurePosixPath(path).name.lower() == "skill.md":
        path = str(PurePosixPath(path).parent)
    if path in ("", "."):
        return "."
    if "\\" in path or any(part in ("", ".", "..") for part in path.split("/")):
        return None
    return path


def _github_source(repository, path, ref):
    """The stub source of a skill, or the reason it cannot have one."""
    match = GITHUB.fullmatch(repository.rstrip("/").removesuffix(".git")) if isinstance(repository, str) else None
    if not match:
        return None, "Paperclip imports skills from GitHub only."
    folder = _folder(path)
    if folder is None:
        return None, "The skill's path is not a folder inside its repository."
    if not isinstance(ref, str) or not ref or ref == "HEAD":
        return None, "Name the branch this skill follows."
    repo = f"{match[1]}/{match[2]}"
    url = f"https://github.com/{repo}/tree/{ref}" + ("" if folder == "." else f"/{folder}")
    return {"kind": "github-dir", "repo": repo, "path": folder, "trackingRef": ref, "url": url}, None


def _inherited_skill(store, owner, file, snapshots):
    base = store.base_root
    manifest = store._directory(owner, root=base) / "apm.yml"
    if owner not in snapshots:
        snapshots[owner] = (
            (store._snapshot(owner, root=store.root), store._snapshot(owner, root=base))
            if store._checked(manifest, root=base).is_file() else None
        )
    pair = snapshots[owner]
    if pair is None:
        return False
    prefix = PurePosixPath(file).parent.as_posix() + "/"
    private, original = ({name: data for name, data in snapshot.items() if name.startswith(prefix)} for snapshot in pair)
    return file in original and private == original


def _skill_source(component, owner, store, snapshots):
    file = component.get("file")
    if file:
        # The preset's own skill, committed in this repository under packages/<owner>/.
        if PurePosixPath(file).name != "SKILL.md" or len(file.split("/")) < 4:
            return None, "A skill in the package needs its own folder with a SKILL.md."
        root = store._package_root(owner)
        if store.base_root is not None and root == store.root and _inherited_skill(store, owner, file, snapshots):
            root = store.base_root
        repository = _repository(root)
        if not repository:
            return None, "Set project.urls.Repository in pyproject.toml to this repository's GitHub URL."
        return _github_source(repository, f"packages/{owner}/{file}", OWN_BRANCH)
    source = component.get("source") or {}
    return _github_source(source.get("repositoryUrl"), source.get("path"), source.get("ref"))


_MANIFESTS = {".claude-plugin": "claude-code-plugin", ".codex-plugin": "codex-plugin"}


def support_kind(component):
    """The support table row of a component. A plugin's row is that of the manifest folder in its source,
    `.claude-plugin/` or `.codex-plugin/`; a plugin with neither, or both, has none."""
    kind = component["kind"]
    if kind in ("instruction", "skill", "mcp", "hook"):
        return kind
    if kind != "plugin":
        return None
    source = component.get("source") if isinstance(component.get("source"), dict) else {}
    places = [component.get("sourceUrl"), component.get("file"), source.get("path"), source.get("repositoryUrl")]
    found = {_MANIFESTS[part] for place in places if isinstance(place, str)
             for part in re.split(r"[/\\]", place) if part in _MANIFESTS}
    if found:
        return found.pop() if len(found) == 1 else None
    return {"claude": "claude-code-plugin", "codex": "codex-plugin"}.get(component.get("pluginHost"))


def _base_key(stub):
    folder = stub["path"]
    return stub["repo"].split("/")[1] if folder == "." else folder.rsplit("/", 1)[-1]


def _inventory_rows(package, packages):
    for owner, current in packages.items():
        nested = owner != package["id"]
        for item in current.get("appInventory", []):
            for app, state in item["apps"].items():
                name = {"codex": "Codex", "claude": "Claude Code"}[app]
                identifier = f"inventory:{app}:{item['id']}"
                yield {
                    "id": f"{owner}/{identifier}" if nested else identifier,
                    **({"originPackage": export_graph.origin(current)} if nested else {}),
                    "name": item["name"], "kind": item["kind"], "app": app, "supportKind": None,
                    **{field: state[field] for field in ("installed", "enabled", "selected")},
                    "source": item.get("source"), "target": None,
                    "conversion": _status("unconverted", _because(
                        f"Paperclip cannot preserve the {name} inventory state for this item.", "not-in-format")),
                }


def _report(package, store):
    is_preset = package.get("kind", "preset") == "preset"
    packages, members = export_graph.expand(package, store, include_empty_instruction=is_preset)
    items, skills = [], []
    seen, snapshots = {}, {}
    instruction_path = f"agents/{package['id']}/AGENTS.md"

    for member in members:
        component, ancestry = member.component, member.ancestry
        kind = component["kind"]
        component_id = component["id"]
        file = component.get("file")
        signature = (component_id, kind, component.get("source"), component.get("file"),
                     component.get("configuration"), member.owner if file else None)
        previous = seen.setdefault(component_id, [])
        primary_instruction = kind == "instruction" and component_id == "instruction" and len(ancestry) == 1
        if kind not in ("package", "instruction") and any(original == signature for _, original in previous):
            continue
        item_id = component_id
        if previous:
            item_id = "/".join((*ancestry[1:], component_id))
            if any(existing_id == item_id for existing_id, _ in previous):
                item_id = f"{item_id}:{len(previous) + 1}"
        previous.append((item_id, signature))
        target = stub = None
        if primary_instruction:
            target, reason = instruction_path, "Instruction exported as AGENTS.md."
        elif kind == "instruction":
            reason = "Paperclip takes one Instruction per agent; merge it into the Instruction."
        elif kind == "skill":
            stub, reason = _skill_source(component, member.owner, store, snapshots)
        elif kind == "mcp":
            reason = _because("Paperclip's company package has no MCP entry; "
                              "set it in the agent's adapter after import.", "adapter")
        elif kind == "package":
            reason = member.error or "Stack members exported."
            if not member.error:
                target = {"packageId": member.dependency}
        elif kind in ("hook", "plugin"):
            reason = _because(f"Paperclip's company package has no {kind} entry.", "not-in-format")
        else:
            reason = "The Paperclip exporter has no mapping for this component."
        row = {
            "id": item_id, "name": component["name"], "kind": kind, "supportKind": support_kind(component),
            "source": component.get("source") or component.get("sourceUrl") or component.get("file"),
            "target": target,
            "conversion": _status("converted" if target is not None else "unconverted", reason),
        }
        if member.owner != package["id"]:
            row["originPackage"] = export_graph.origin(packages[member.owner])
        items.append(row)
        if kind == "skill" and stub:
            skills.append((row, stub, component))

    items.extend(_inventory_rows(package, packages))
    bundle = {owner: {entry["path"]: entry["content"].encode("utf-8") for entry in saved.get("files", [])}
              for owner, saved in packages.items()}
    return items, _stubs(skills), bundle


def _stubs(skills):
    """Give every distinct skill source one key, in member order, and point its rows at the stub."""
    def identity(stub):
        return stub["repo"].casefold(), stub["path"], stub["trackingRef"]

    sources = {}
    for _, stub, component in skills:
        sources.setdefault(identity(stub), (stub, component))
    counts = {}
    for stub, _ in sources.values():
        key = _base_key(stub).casefold()
        counts[key] = counts.get(key, 0) + 1
    keys, used, stubs = {}, set(), {}
    for source, (stub, component) in sources.items():
        key = _base_key(stub)
        if counts[key.casefold()] > 1:
            key = f"{stub['repo'].split('/')[1]}-{key}"
        unique, number = key, 2
        while unique.casefold() in used:
            unique, number = f"{key}-{number}", number + 1
        used.add(unique.casefold())
        keys[source] = unique
        stubs[unique] = (stub, component)
    for row, stub, _ in skills:
        key = keys[identity(stub)]
        row["target"] = f"skills/{key}/SKILL.md"
        row["conversion"] = _status("converted", f"Skill exported as skills/{key}, following {stub['trackingRef']}.")
    return stubs


def _skill_labels(component, key):
    """A stub's name and description: the catalog row's, or for a preset's own skill its SKILL.md's."""
    name = component["name"]
    description = (component.get("description") or "").strip()
    if component.get("file"):
        front = {}
        text = component.get("configuration")
        lines = text.replace("\r\n", "\n").split("\n") if isinstance(text, str) else []
        if lines and lines[0] == "---" and "---" in lines[1:]:
            try:
                front = yaml.safe_load("\n".join(lines[1:lines.index("---", 1)]))
            except yaml.YAMLError:
                front = {}
            front = front if isinstance(front, dict) else {}
        own = lambda field: front[field].strip() if isinstance(front.get(field), str) else ""
        name = own("name") or PurePosixPath(component["file"]).parent.name or key
        description = description or own("description")
    return name, description


def _files(package, stubs, bundle):
    from .store import _export_digest

    slug, title = package["id"], package["title"]
    config = {
        "role": ROLE,
        "runtime": {"heartbeat": {"enabled": False}},
        "metadata": {"agentStackManagerPackageId": slug, "agentStackManagerRevision": _export_digest(bundle)},
    }
    files = {
        "COMPANY.md": _frontmatter({"schema": "agentcompanies/v1", "kind": "company", "slug": slug,
                                    "name": title, "description": package["description"] or title}),
        f"agents/{slug}/AGENTS.md": _frontmatter(
            {"kind": "agent", "name": title, "title": title, "slug": slug, "role": ROLE, "skills": list(stubs)},
            _instruction(package["instruction"]),
        ),
        ".paperclip.yaml": _yaml({"schemaVersion": 7, "agents": {slug: config}}),
    }
    for key, (stub, component) in stubs.items():
        name, description = _skill_labels(component, key)
        front = {"key": key, "name": name}
        if description:
            front["description"] = description
        front["metadata"] = {"sources": [stub]}
        files[f"skills/{key}/SKILL.md"] = _frontmatter(front, f"Imported from {stub['url']}.")
    return files


def convert(package, *, root: Path, store=None):
    """Produce the Paperclip company package of a preset and the report of every component."""
    from .store import Store

    store = store or Store(root)
    items, stubs, bundle = _report(package, store)
    converted = sum(row["conversion"]["status"] == "converted" for row in items)
    return {
        "consumer": "paperclip", "items": items,
        "summary": {"total": len(items), "converted": converted, "unconverted": len(items) - converted},
        "files": [{"path": path, "content": content}
                  for path, content in _files(package, stubs, bundle).items()],
        "folder": _folder_of(package, store._package_root(package["id"])),
    }


def _folder_of(package, root):
    """Where the preset's export is committed, and its GitHub page; a stack is not one agent, so none."""
    if package.get("kind", "preset") != "preset":
        return None
    path = f"{EXPORTS}/{package['id']}"
    repository = _repository(root)
    return {"path": path, "url": f"{repository}/tree/{OWN_BRANCH}/{path}" if repository else None}


def export_package(report):
    """Return the Paperclip package files as a ZIP."""
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for entry in report["files"]:
            archive.writestr(entry["path"], entry["content"])
    return output.getvalue()


def needs_attention(row):
    """A component left out for a reason somebody can fix, apart from those the format leaves out."""
    return row["conversion"]["status"] == "unconverted" and not row["conversion"].get("cause")


def _exports(root, store=None):
    """The export of every preset: `{id, report}`, or `{id, error}` for a package that cannot be read."""
    from .exporters import EXPORTERS
    from .store import Store

    store = store or Store(root)
    results = []
    for identifier in store._ids():
        try:
            package = store.get(identifier)
            assessment = EXPORTERS["paperclip"].assess(package, store)
            if assessment.artifact is not None:
                results.append({"id": identifier, "report": assessment.artifact})
        except (ValueError, OSError) as error:
            results.append({"id": identifier, "error": str(error)})
    return store, results


def _differences(store, results):
    """Compare exports/paperclip/ on disk with the exports: the folder and its changed, missing, extra files."""
    directory = store._checked(store.root / EXPORTS)
    expected = {f"{result['id']}/{entry['path']}": entry["content"].encode("utf-8")
                for result in results if "report" in result for entry in result["report"]["files"]}
    # A package that cannot be read keeps the folder it had.
    kept = {result["id"] for result in results if "error" in result}
    actual = {}
    for current, dirs, names in os.walk(directory):
        for name in names:
            path = Path(current) / name
            relative = path.relative_to(directory).as_posix()
            if relative.split("/")[0] not in kept:
                actual[relative] = store._checked(path)
    changed = sorted(name for name in expected.keys() & actual.keys() if actual[name].read_bytes() != expected[name])
    return directory, expected, {"changed": changed, "missing": sorted(expected.keys() - actual.keys()),
                                 "extra": sorted(actual.keys() - expected.keys())}


def write_exports(root, *, store=None):
    """Write exports/paperclip/<id>/ for every preset, exactly the converted files, and remove the rest."""
    from .store import _atomic_write

    store, results = _exports(root, store)
    directory, expected, differences = _differences(store, results)
    for name in (*differences["changed"], *differences["missing"]):
        target = store._checked(directory / name)
        target.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(target, expected[name])
    for name in differences["extra"]:
        (directory / name).unlink()
    for current, _, _ in os.walk(directory, topdown=False):
        if Path(current) != directory and not any(Path(current).iterdir()):
            Path(current).rmdir()
    return results


def check_exports(root, *, store=None):
    """The exports and how exports/paperclip/ differs from them, writing nothing."""
    store, results = _exports(root, store)
    return results, _differences(store, results)[2]
