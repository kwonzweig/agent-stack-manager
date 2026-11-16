"""Convert APM packages into a package Paperclip can import."""

from io import BytesIO
import json
from pathlib import Path
import re
from zipfile import ZIP_DEFLATED, ZipFile

import yaml


REPOSITORY = re.compile(r"https://github\.com/[\w.-]+/[\w.-]+", re.IGNORECASE | re.ASCII)
MCP_NAME = re.compile(r"[a-zA-Z0-9_-]+")
MCP_FIELDS = {"name", "transport", "registry", "command", "args"}
PLAN_PATH = "remote-import-plan.json"


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


class _Reason(str):
    cause = None


def _because(text, cause):
    """A reason that also names why Paperclip leaves the component out."""
    reason = _Reason(text)
    reason.cause = cause
    return reason


def _status(status, reason):
    result = {"status": status, "reason": str(reason)}
    cause = getattr(reason, "cause", None)
    if cause:
        result["cause"] = cause
    return result


def _native_source(component):
    """The remote skill as Paperclip imports it. Without a ref it follows the default branch."""
    source = component.get("source") or {}
    repository = source.get("repositoryUrl")
    path, ref = source.get("path"), source.get("ref") or ""
    if not (isinstance(repository, str) and isinstance(path, str) and isinstance(ref, str)):
        return None
    repository = repository.rstrip("/").removesuffix(".git")
    if not REPOSITORY.fullmatch(repository):
        return None
    path = path.rstrip("/")
    if path.startswith("/") or "\\" in path or any(part in (".", "..") for part in path.split("/")):
        return None
    if path.rsplit("/", 1)[-1].lower() != "skill.md":
        path = f"{path}/SKILL.md" if path else "SKILL.md"
    target = {"repositoryUrl": repository, "path": path}
    if ref and ref != "HEAD":
        target["ref"] = ref
    return target


def _mcp_config(component):
    config = component.get("configuration")
    if (not isinstance(config, dict) or config.get("transport", "stdio") != "stdio"
            or config.get("registry", False) is not False):
        return None, "This exporter maps inline stdio MCP servers."
    unmapped = sorted(set(config) - MCP_FIELDS)
    if unmapped:
        return None, "This exporter has no mapping for " + ", ".join(unmapped) + "."
    name, command, args = config.get("name"), config.get("command"), config.get("args", [])
    if (not isinstance(name, str) or not MCP_NAME.fullmatch(name) or
            not isinstance(command, str) or not command.strip() or
            not isinstance(args, list) or not all(isinstance(arg, str) for arg in args)):
        return None, "A stdio MCP server needs a valid name, command and argument list."
    return {"name": name, "transport": "stdio", "command": command, "args": args}, "Mapped to Codex CLI settings."


def _report(package, root):
    items, mcp = [], {}
    seen = {}
    instruction_path = f"agents/{_agent_slug(package)}/AGENTS.md"

    def add(component, ancestry):
        kind = component["kind"]
        component_id = component["id"]
        signature = (component_id, kind, component.get("source"), component.get("configuration"))
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
        target = None
        if primary_instruction:
            target, reason = instruction_path, "Written to Paperclip AGENTS.md."
        elif kind == "instruction":
            reason = "This exporter maps the preset's instruction to AGENTS.md."
        elif kind == "skill":
            target = _native_source(component)
            reason = ("Included in the remote skill import plan." if target else
                      "Native import needs a GitHub repository and a skill path.")
        elif kind == "mcp":
            target, reason = _mcp_config(component)
            if target:
                previous_mcp = mcp.setdefault(target["name"], target)
                if previous_mcp != target:
                    reason = f"Conflicting settings for MCP server {target['name']}."
                    target = None
        elif kind == "package":
            reason = "Stack membership expanded."
        elif kind in ("hook", "plugin"):
            reason = _because(f"Paperclip has no setting for agent {kind}s.", "unsupported")
        else:
            reason = "The Paperclip exporter has no mapping for this component."
        row = {
            "id": item_id, "name": component["name"], "kind": kind,
            "source": component.get("source") or component.get("sourceUrl"), "target": target,
            "conversion": _status("converted" if target is not None else "unconverted", reason),
        }
        items.append(row)
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
                for member in child["components"]:
                    if member["id"] != "instruction" or child["instruction"].strip():
                        add(member, (*ancestry, package_id))
                row["target"] = {"packageId": package_id}
                row["conversion"] = _status("converted", reason)
                return
        row["conversion"] = _status("unconverted", reason)

    components = package["components"]
    if not any(component["id"] == "instruction" for component in components):
        components = [{"id": "instruction", "name": "Instruction", "kind": "instruction"}, *components]
    for component in components:
        add(component, (package["id"],))
    return {"consumer": "paperclip", "items": items}


def _agent_slug(package):
    return re.sub("[^a-z0-9]+", "-", package["title"].lower()).strip("-") or package["id"]


def _extra_args(items):
    return [argument for config in items for field in ("command", "args") for argument in
            ("-c", f'mcp_servers.{config["name"]}.{field}={json.dumps(config[field], ensure_ascii=False)}')]


def _native_files(package, report):
    slug, title = _agent_slug(package), package["title"]
    sources = [row["target"] for row in report["items"] if row["kind"] == "skill" and row["target"] is not None]
    mcp = {row["target"]["name"]: row["target"] for row in report["items"]
           if row["kind"] == "mcp" and row["target"] is not None}
    args = _extra_args(mcp.values())
    config = {
        "role": "engineer",
        "adapter": {"type": "codex_local", "config": {"engine": "cli", "extraArgs": args} if args else {}},
        "runtime": {"heartbeat": {"enabled": False, "wakeOnDemand": False}},
        "permissions": {"canCreateAgents": False},
        "budgetMonthlyCents": 0,
    }
    return {
        "COMPANY.md": _frontmatter({"name": title, "description": package["description"]}),
        f"agents/{slug}/AGENTS.md": _frontmatter(
            {"kind": "agent", "name": title, "title": title, "slug": slug, "role": config["role"], "skills": []},
            _instruction(package["instruction"]),
        ),
        ".paperclip.yaml": _yaml({"schemaVersion": 7, "agents": {slug: config}}),
        PLAN_PATH: json.dumps({"slug": slug, "sourceFormat": "APM", "remoteSources": sources},
                              ensure_ascii=False, indent=2) + "\n",
    }


def convert(package, *, root: Path):
    """Produce a native Paperclip package and a plan listing the original remote skills."""
    report = _report(package, root)
    items = report["items"]
    converted = sum(row["conversion"]["status"] == "converted" for row in items)
    report["summary"] = {"total": len(items), "converted": converted, "unconverted": len(items) - converted}
    report["files"] = [{"path": path, "content": content} for path, content in _native_files(package, report).items()]
    return report


def export_package(report):
    """Return the Paperclip package as a ZIP, including its remote import plan."""
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for entry in report["files"]:
            archive.writestr(entry["path"], entry["content"])
    return output.getvalue()
