"""Build a CC Switch review report from saved inventory without touching any app."""
import base64
import json
import re
from urllib.parse import quote, urlencode, urlsplit


UNSUPPORTED_KINDS = {"hook", "plugin", "claude-code-plugin", "codex-plugin", "connector"}
UNSUPPORTED_REASON = "CC Switch does not manage this component."
_REPO_PART = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9._-]*")


def _link(**parameters):
    return "ccswitch://v1/import?" + urlencode(parameters, quote_via=quote)


def _encoded(text):
    return base64.b64encode(text.encode()).decode()


def _safe_path(value):
    return (isinstance(value, str) and ".." not in value and
            all(_REPO_PART.fullmatch(part) for part in value.split("/")))


def _registration(item):
    repo = item.get("skillRepository")
    if not isinstance(repo, dict):
        return None
    owner, name, branch = (repo.get(key) for key in ("owner", "repo", "branch"))
    if not all(isinstance(value, str) and _REPO_PART.fullmatch(value) for value in (owner, name)):
        return None
    directory = repo.get("directory")
    if not _safe_path(branch) or (directory is not None and not _safe_path(directory)):
        return None
    url = _link(
        resource="skill", repo=f"{owner}/{name}", branch=branch,
        **({"directory": directory} if directory else {}),
    )
    return {"owner": owner, "repo": name, "branch": branch,
            **({"directory": directory} if directory else {}), "url": url}


def _portable_link(item, app, state):
    # Only explicit payloads are portable. Observed configuration never becomes a payload.
    portable = state.get("portable")
    if not isinstance(portable, dict):
        return None
    if item["kind"] in {"instruction", "prompt"} and set(portable) == {"prompt"}:
        prompt = portable["prompt"]
        if isinstance(prompt, str) and prompt.strip():
            return _link(resource="prompt", app=app, name=item["name"], content=_encoded(prompt), enabled="false")
    if item["kind"] != "mcp" or state["enabled"] is not True or set(portable) != {"mcp"}:
        return None
    mcp = portable["mcp"]
    if not isinstance(mcp, dict) or set(mcp) != {"name", "url"}:
        return None
    name, url = mcp["name"], mcp["url"]
    if not isinstance(name, str) or not _REPO_PART.fullmatch(name) or not isinstance(url, str):
        return None
    try:
        endpoint = urlsplit(url)
        # The converter accepts a remote URL only, without auth, headers, commands, or parameters.
        if (endpoint.scheme != "https" or not endpoint.hostname or endpoint.port == 0 or
                "%" in endpoint.hostname or
                endpoint.username is not None or any(ch in url for ch in "?#\\") or
                any(ch.isspace() or ord(ch) < 32 for ch in url)):
            return None
    except ValueError:
        return None
    return _link(resource="mcp", apps=app, config=_encoded(json.dumps({"mcpServers": {name: {"url": url}}})))


def convert(package):
    if "appInventory" not in package:
        raise ValueError("This preset has no app inventory.")
    items, registrations, mcp_imports = [], {}, {}
    for item in package["appInventory"]:
        kind = item["kind"]
        registration = _registration(item) if kind == "skill" else None
        for app, state in item["apps"].items():
            row = {"id": item["id"], "name": item["name"], "kind": kind, "app": app,
                   **{field: state[field] for field in ("installed", "enabled", "selected")}}
            if "originPackage" in item:
                row["originPackage"] = item["originPackage"]
            source, path = item.get("source"), state.get("path")
            if isinstance(source, str):
                row["source"] = source
            if _safe_path(path):
                row["path"] = path
            for field in ("sourcePath", "sourceRef"):
                if _safe_path(item.get(field)):
                    row[field] = item[field]
            for field in ("scope", "parentId"):
                if isinstance(state.get(field), str):
                    row[field] = state[field]
            target_id = state.get("targetId")
            if isinstance(target_id, str) and _REPO_PART.fullmatch(target_id):
                row["targetId"] = target_id
            if registration:
                row["skillRepository"] = registration
            if state["selected"] is False:
                status, reason = "excluded", "Excluded from the preset for this app."
            elif kind in UNSUPPORTED_KINDS:
                status, reason = "unsupported", UNSUPPORTED_REASON
            elif state["selected"] is None:
                status, reason = "manual", "The selection for this app has not been set."
            elif registration:
                status, reason = "registration-only", "The link adds the skill repository. Install or enable the skill separately."
                registrations[registration["url"]] = registration
            elif (kind in {"instruction", "prompt", "mcp"} and state.get("portable") and
                  state.get("scope") not in (None, "user", "global", "user-global")):
                status, reason = "manual", "CC Switch imports into the app's global configuration. Apply this item at its recorded scope."
            elif url := _portable_link(item, app, state):
                status, reason = "import-ready", "Review and import this configuration in CC Switch."
                row["url"] = url
                if kind == "mcp":
                    mcp = state["portable"]["mcp"]
                    row["targetId"] = mcp["name"]
                    mcp_imports.setdefault(mcp["name"], []).append((row, mcp["url"]))
            else:
                status, reason = "manual", "The inventory identifies this item. It does not contain an importable configuration."
            row.update(status=status, reason=reason)
            items.append(row)

    # CC Switch stores one configuration per MCP ID. A second import only enables more apps.
    for entries in mcp_imports.values():
        if len({url for _, url in entries}) > 1:
            for row, _ in entries:
                row.pop("url")
                row.update(status="manual", reason="This MCP ID has conflicting endpoints. Choose one configuration in CC Switch.")
    return {"presetId": package["id"], "consumer": "cc-switch", "items": items,
            "skillRepositories": list(registrations.values())}
