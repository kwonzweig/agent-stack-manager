"""Component identity and source coordinates, shared by every dashboard entry point."""
import hashlib
import json
import re
from pathlib import PurePosixPath
from urllib.parse import quote, urlsplit


def kind_and_host(row):
    kind = row["kind"]
    host = row.get("pluginHost")
    if kind in {"codex-plugin", "claude-code-plugin"}:
        return "plugin", "codex" if kind == "codex-plugin" else "claude"
    source = row.get("source")
    places = [row.get("sourceUrl") or "", row.get("file") or "",
              (source.get("path") or "") if isinstance(source, dict) else (row.get("sourcePath") or "")]
    if kind == "plugin" and not host:
        if any(".codex-plugin" in part for part in places):
            host = "codex"
        elif any(".claude-plugin" in part for part in places):
            host = "claude"
        elif isinstance(row.get("configuration"), dict) and row["configuration"].get("marketplace"):
            host = "claude"
    return kind, host


def source_coordinates(row):
    source = row.get("source")
    spec = row.get("apm") or {}
    if "value" in spec:
        spec = spec["value"] if isinstance(spec["value"], dict) else {}
    if isinstance(source, str):
        source = {"repositoryUrl": source, "path": row.get("sourcePath"), "ref": row.get("sourceRef")}
    source = source.copy() if isinstance(source, dict) else {}
    source = {key: value for key, value in source.items() if isinstance(value, str) and value}
    for field, fallback in (("repositoryUrl", "git"), ("path", "path"), ("ref", "ref")):
        if field not in source and isinstance(spec.get(fallback), str):
            source[field] = spec[fallback]
    repository = source.get("repositoryUrl")
    if not repository:
        return None
    repository = re.sub(r"^git@github\.com:", "https://github.com/", repository, flags=re.IGNORECASE)
    parsed = urlsplit(repository)
    if parsed.scheme == "ssh" and parsed.hostname == "github.com" and parsed.username == "git" and not parsed.password:
        repository = f"https://github.com{parsed.path}"
        parsed = urlsplit(repository)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password:
        return None
    if parsed.query or parsed.fragment:
        return None
    repository = repository.rstrip("/").removesuffix(".git")
    if parsed.hostname.casefold() == "github.com":
        parts = parsed.path.strip("/").split("/")
        if len(parts) < 2:
            return None
        repository = f"https://github.com/{parts[0]}/{parts[1].removesuffix('.git')}"
        if len(parts) > 3 and parts[2] in {"tree", "blob"}:
            tail = "/".join(parts[3:])
            ref = source.get("ref")
            if ref and (tail == ref or tail.startswith(ref + "/")) and not source.get("path"):
                source["path"] = tail[len(ref):].lstrip("/")
    source["repositoryUrl"] = repository
    path = source.get("path", "").strip("/")
    kind, host = kind_and_host(row)
    declared_root = isinstance(row.get("apm"), dict) and ("git" in row["apm"] or "value" in row["apm"])
    if kind == "skill" and (path or declared_root) and PurePosixPath(path).name != "SKILL.md":
        path = str(PurePosixPath(path, "SKILL.md"))
    if kind == "plugin" and PurePosixPath(path).name == "plugin.json":
        path = str(PurePosixPath(path).parent.parent)
    if path:
        source["path"] = path
    else:
        source.pop("path", None)
    return source


def source_url(source):
    if not source:
        return None
    repository, path, ref = (source.get(key) for key in ("repositoryUrl", "path", "ref"))
    host = urlsplit(repository).hostname
    if path and ref and host in {"github.com", "gitlab.com"}:
        prefix = "/-/blob/" if host == "gitlab.com" else "/blob/"
        return f"{repository}{prefix}{quote(ref, safe='')}/{quote(path)}"
    return repository


def identify(row, namespace):
    kind, host = kind_and_host(row)
    identity_host = host if kind == "plugin" else None
    source = source_coordinates(row)
    if source:
        repository = source["repositoryUrl"]
        if urlsplit(repository).hostname == "github.com":
            repository = repository.lower()
        coordinates = (kind, identity_host, repository, source.get("ref"), source.get("path"))
        if kind in {"skill", "plugin"} and not source.get("path"):
            source_key = hashlib.sha256(json.dumps(coordinates).encode()).hexdigest()
            if (row.get("definitionSourceKey") == source_key and isinstance(row.get("definitionId"), str)
                    and re.fullmatch(r"component-[a-f0-9]{64}", row["definitionId"])):
                return {"canonicalId": row["definitionId"], "source": source, "pluginHost": host,
                        "sourceUrl": source_url(source)}
            coordinates += (namespace, row["id"])
    else:
        locators = []
        for app, state in row.get("apps", {}).items():
            provenance = state.get("provenance") or {}
            locator = state.get("locator") or provenance.get("location")
            field = None if kind in {"skill", "instruction", "setting"} else provenance.get("field") or state.get("targetId")
            if locator and (kind in {"skill", "instruction", "setting"} or field):
                normalized = locator.replace("\\", "/")
                locators.append((normalized, field))
        definition_id = row.get("definitionId")
        if not locators and isinstance(definition_id, str) and re.fullmatch(r"component-[a-f0-9]{64}", definition_id):
            return {"canonicalId": row["definitionId"], "source": None, "pluginHost": host, "sourceUrl": None}
        coordinates = ((kind, identity_host, "local-source", sorted(set(locators), key=str))
                       if locators else (kind, identity_host, namespace, row["id"]))
    digest = hashlib.sha256(json.dumps(coordinates, ensure_ascii=True).encode()).hexdigest()
    return {"canonicalId": "component-" + digest, "source": source, "pluginHost": host,
            "sourceUrl": source_url(source) if source else row.get("sourceUrl")}
