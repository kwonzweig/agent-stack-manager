"""Convert an APM preset into a company package that Paperclip can import."""

from io import BytesIO
import json
import os
from pathlib import Path, PurePosixPath
import re
import tomllib
from zipfile import ZIP_DEFLATED, ZipFile

import yaml


GITHUB = re.compile(r"https://github\.com/([\w.-]+)/([\w.-]+)", re.IGNORECASE | re.ASCII)
DEFAULT_ROLE = "general"
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


def _read_package(root, package_id):
    from .store import Store

    return Store(root).get(package_id)


def _repository(root):
    """This repository's GitHub URL, from `project.urls.Repository` in its pyproject.toml."""
    try:
        with open(Path(root) / "pyproject.toml", "rb") as file:
            project = tomllib.load(file).get("project", {})
    except (OSError, tomllib.TOMLDecodeError):
        return None
    url = project.get("urls", {}).get("Repository") if isinstance(project.get("urls"), dict) else None
    return url.rstrip("/").removesuffix(".git") if isinstance(url, str) else None


def _roles(root):
    """Paperclip's role list from catalog/consumers.json, or None when the file does not hold one."""
    try:
        data = json.loads((Path(root) / "catalog" / "consumers.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    for consumer in data.get("consumers", []):
        if consumer.get("id") == "paperclip":
            values = (consumer.get("roles") or {}).get("values")
            return values if isinstance(values, list) else None
    return None


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


def _skill_source(component, owner, root):
    file = component.get("file")
    if file:
        # The preset's own skill, committed in this repository under packages/<owner>/.
        if PurePosixPath(file).name != "SKILL.md" or len(file.split("/")) < 4:
            return None, "A skill in the package needs its own folder with a SKILL.md."
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
    return found.pop() if len(found) == 1 else None


def _base_key(stub):
    folder = stub["path"]
    return stub["repo"].split("/")[1] if folder == "." else folder.rsplit("/", 1)[-1]


def _report(package, root):
    items, skills, bundle = [], [], {}
    seen = {}
    instruction_path = f"agents/{package['id']}/AGENTS.md"

    def remember(current):
        bundle.setdefault(current["id"], {
            entry["path"]: entry["content"].encode("utf-8") for entry in current.get("files", [])})

    def add(component, ancestry):
        kind = component["kind"]
        component_id = component["id"]
        signature = (component_id, kind, component.get("source"), component.get("file"),
                     component.get("configuration"))
        previous = seen.setdefault(component_id, [])
        primary_instruction = kind == "instruction" and component_id == "instruction" and len(ancestry) == 1
        if kind not in ("package", "instruction"):
            for _, original in previous:
                if original == signature:
                    return
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
            stub, reason = _skill_source(component, ancestry[-1], root)
        elif kind == "mcp":
            reason = _because("Paperclip's company package has no MCP entry; "
                              "set it in the agent's adapter after import.", "adapter")
        elif kind == "package":
            reason = "Stack members exported."
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
        items.append(row)
        if kind == "skill" and stub:
            skills.append((row, stub, component))
        if kind != "package":
            return

        package_id = (component.get("configuration") or {}).get("packageId")
        if not package_id:
            reason = "The APM dependency has no local stack to expand."
        elif package_id in ancestry:
            reason = f"Stack dependency cycle at {package_id}."
        else:
            try:
                child = _read_package(root, package_id)
            except (ValueError, LookupError, FileNotFoundError):
                reason = f"Local stack {package_id} could not be read."
            else:
                remember(child)
                for member in child["components"]:
                    if member["id"] != "instruction" or child["instruction"].strip():
                        add(member, (*ancestry, package_id))
                row["target"] = {"packageId": package_id}
                row["conversion"] = _status("converted", reason)
                return
        row["conversion"] = _status("unconverted", reason)

    remember(package)
    components = package["components"]
    if not any(component["id"] == "instruction" for component in components):
        components = [{"id": "instruction", "name": "Instruction", "kind": "instruction"}, *components]
    for component in components:
        add(component, (package["id"],))
    return items, _stubs(skills), bundle


def _stubs(skills):
    """Give every distinct skill source one key, in member order, and point its rows at the stub."""
    sources = []
    for _, stub, component in skills:
        if stub not in (known for known, _ in sources):
            sources.append((stub, component))
    counts = {}
    for stub, _ in sources:
        counts[_base_key(stub)] = counts.get(_base_key(stub), 0) + 1
    keys, used = [], set()
    for stub, _ in sources:
        key = _base_key(stub)
        if counts[key] > 1:
            key = f"{stub['repo'].split('/')[1]}-{key}"
        unique, number = key, 2
        while unique in used:
            unique, number = f"{key}-{number}", number + 1
        used.add(unique)
        keys.append(unique)
    stubs = {}
    for (stub, component), key in zip(sources, keys):
        stubs[key] = (stub, component)
    for row, stub, _ in skills:
        key = keys[[known for known, _ in sources].index(stub)]
        row["target"] = f"skills/{key}/SKILL.md"
        row["conversion"] = _status("converted", f"Skill exported as skills/{key}, following {stub['trackingRef']}.")
    return stubs


def _role(package, root):
    """The role written to both files, and the report row when the preset's role is not Paperclip's."""
    labels = package.get("paperclip") or {}
    role = labels.get("role") or DEFAULT_ROLE
    roles = _roles(root)
    if roles is None or role in roles:
        return role, None
    row = {"id": "paperclip:role", "name": "Paperclip role", "kind": "other", "supportKind": None, "source": role, "target": None,
           "conversion": _status("unconverted", f"Role {role} is not one of Paperclip's roles, so {DEFAULT_ROLE} "
                                                f"was written; choose one of {', '.join(roles)}.")}
    return DEFAULT_ROLE, row


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


def _files(package, role, stubs, bundle):
    from .store import _export_digest

    slug, title = package["id"], package["title"]
    labels = package.get("paperclip") or {}
    config = {
        "role": role,
        "permissions": {"canCreateAgents": labels.get("canCreateAgents") is True},
        "runtime": {"heartbeat": {"enabled": False}},
        "metadata": {"agentStackManagerPackageId": slug, "agentStackManagerRevision": _export_digest(bundle)},
    }
    files = {
        "COMPANY.md": _frontmatter({"schema": "agentcompanies/v1", "kind": "company", "slug": slug,
                                    "name": title, "description": package["description"] or title}),
        f"agents/{slug}/AGENTS.md": _frontmatter(
            {"kind": "agent", "name": title, "title": title, "slug": slug, "role": role, "skills": list(stubs)},
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


def convert(package, *, root: Path):
    """Produce the Paperclip company package of a preset and the report of every component."""
    items, stubs, bundle = _report(package, root)
    role, role_row = _role(package, root)
    if role_row:
        items.append(role_row)
    converted = sum(row["conversion"]["status"] == "converted" for row in items)
    return {
        "consumer": "paperclip", "items": items,
        "summary": {"total": len(items), "converted": converted, "unconverted": len(items) - converted},
        "files": [{"path": path, "content": content}
                  for path, content in _files(package, role, stubs, bundle).items()],
        "folder": _folder_of(package, root),
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


def _exports(root):
    """The export of every preset: `{id, report}`, or `{id, error}` for a package that cannot be read."""
    from .store import Store

    store = Store(root)
    results = []
    for identifier in store._ids():
        try:
            package = store.get(identifier)
            if package["kind"] == "preset":
                results.append({"id": identifier, "report": convert(package, root=store.root)})
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


def write_exports(root):
    """Write exports/paperclip/<id>/ for every preset, exactly the converted files, and remove the rest."""
    store, results = _exports(root)
    directory, expected, differences = _differences(store, results)
    for name in (*differences["changed"], *differences["missing"]):
        target = directory / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(expected[name])
    for name in differences["extra"]:
        (directory / name).unlink()
    for current, _, _ in os.walk(directory, topdown=False):
        if Path(current) != directory and not any(Path(current).iterdir()):
            Path(current).rmdir()
    return results


def check_exports(root):
    """The exports and how exports/paperclip/ differs from them, writing nothing."""
    store, results = _exports(root)
    return results, _differences(store, results)[2]
