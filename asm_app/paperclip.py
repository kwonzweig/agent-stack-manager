"""Convert APM packages and verify their saved Paperclip configuration."""

from collections import defaultdict
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
import tomllib
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen
from zipfile import ZIP_DEFLATED, ZipFile

import yaml


REPOSITORY = re.compile(r"https://github\.com/[\w.-]+/[\w.-]+", re.IGNORECASE | re.ASCII)
COMMIT = re.compile(r"[0-9a-f]{40}", re.IGNORECASE)
MCP_NAME = re.compile(r"[a-zA-Z0-9_-]+")
MCP_FIELDS = {"name", "transport", "registry", "command", "args"}
PACKAGE_MARKER = "agentStackManagerPackageId"
MCP_MARKER = "agentStackManagerMcpServers"
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
    """A reason that also names why Paperclip left the component out."""
    reason = _Reason(text)
    reason.cause = cause
    return reason


def _status(status, reason):
    result = {"status": status, "reason": str(reason)}
    cause = getattr(reason, "cause", None)
    if cause:
        result["cause"] = cause
    return result


def _repo_key(repository):
    return repository.rstrip("/").casefold().removesuffix(".git")


def _ref_key(ref):
    return ref.lower() if COMMIT.fullmatch(ref) else ref


def _source_id(source):
    return _repo_key(source["repositoryUrl"]), source["path"], _ref_key(source["ref"])


def _native_source(component):
    source = component.get("source") or {}
    repository = source.get("repositoryUrl")
    path, ref = source.get("path"), source.get("ref")
    if not (isinstance(repository, str) and isinstance(path, str) and isinstance(ref, str)):
        return None
    repository = repository.rstrip("/").removesuffix(".git")
    if not REPOSITORY.fullmatch(repository) or not ref or ref == "HEAD":
        return None
    path = path.rstrip("/")
    if path.startswith("/") or "\\" in path or any(part in (".", "..") for part in path.split("/")):
        return None
    if path.rsplit("/", 1)[-1].lower() != "skill.md":
        path = f"{path}/SKILL.md" if path else "SKILL.md"
    return {"repositoryUrl": repository, "path": path, "ref": ref}


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
    items, members, mcp = [], {}, {}
    revisions = {package["id"]: package.get("revision")}
    seen = {}
    instruction_path = f"agents/{_agent_slug(package)}/AGENTS.md"

    def add(component, ancestry):
        kind = component["kind"]
        component_id = component["id"]
        signature = (component_id, kind, component.get("source"), component.get("configuration"))
        previous = seen.setdefault(component_id, [])
        primary_instruction = kind == "instruction" and component_id == "instruction" and len(ancestry) == 1
        if kind not in ("package", "instruction"):
            for item_id, original in previous:
                if original == signature:
                    return item_id
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
                      "Native import needs a GitHub repository, a skill path and an explicit branch or commit.")
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
            "import": _status("not_checked", "Paperclip has not been checked."),
        }
        items.append(row)
        if kind != "package":
            return item_id

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
                revisions[package_id] = child["revision"]
                child_ancestry = (*ancestry, package_id)
                members[item_id] = [
                    add(member, child_ancestry) for member in child["components"]
                    if member["id"] != "instruction" or child["instruction"].strip()
                ]
                row["target"] = {"packageId": package_id}
                row["conversion"] = _status("converted", reason)
                return item_id
        row["conversion"] = _status("unconverted", reason)
        return item_id

    components = package["components"]
    if not any(component["id"] == "instruction" for component in components):
        components = [{"id": "instruction", "name": "Instruction", "kind": "instruction"}, *components]
    for component in components:
        add(component, (package["id"],))
    for item in items:
        if item["conversion"]["status"] == "unconverted":
            item["import"] = _status("not_checked", "This component was not exported.")
    source_revision = sha256(json.dumps(revisions, sort_keys=True).encode("utf-8")).hexdigest()
    return {"consumer": "paperclip", "items": items, "sourceRevision": source_revision}, revisions, members


def _agent_slug(package):
    return re.sub("[^a-z0-9]+", "-", package["title"].lower()).strip("-") or package["id"]


def _extra_args(items):
    return [argument for config in items for field in ("command", "args") for argument in
            ("-c", f'mcp_servers.{config["name"]}.{field}={json.dumps(config[field], ensure_ascii=False)}')]


def _sources(report):
    return [row for row in report["items"] if row["kind"] == "skill" and row["target"] is not None]


def _mcps(report):
    return [row["target"] for row in report["items"] if row["kind"] == "mcp" and row["target"] is not None]


def _native_files(package, report):
    slug, title = _agent_slug(package), package["title"]
    sources = [row["target"] for row in _sources(report)]
    keys = list(dict.fromkeys(source["key"] for source in sources if source.get("key")))
    mcp = {target["name"]: target for target in _mcps(report)}
    args = _extra_args(mcp.values())
    config = {
        "role": "engineer",
        "adapter": {"type": "codex_local", "config": {"engine": "cli", "extraArgs": args} if args else {}},
        "runtime": {"heartbeat": {"enabled": False, "wakeOnDemand": False}},
        "permissions": {"canCreateAgents": False},
        "budgetMonthlyCents": 0,
        "metadata": {PACKAGE_MARKER: package["id"], MCP_MARKER: list(mcp)},
    }
    return {
        "COMPANY.md": _frontmatter({"name": title, "description": package["description"]}),
        f"agents/{slug}/AGENTS.md": _frontmatter(
            {"kind": "agent", "name": title, "title": title, "slug": slug, "role": config["role"], "skills": keys},
            _instruction(package["instruction"]),
        ),
        ".paperclip.yaml": _yaml({"schemaVersion": 7, "agents": {slug: config}}),
        PLAN_PATH: json.dumps({"slug": slug, "sourceFormat": "APM", "remoteSources": sources},
                              ensure_ascii=False, indent=2) + "\n",
    }


def _finish(package, report, members, agent=None):
    statuses = {row["id"]: row["import"] for row in report["items"]}
    for item_id, children in reversed(list(members.items())):
        if agent and all(statuses[child_id]["status"] == "saved" for child_id in children):
            statuses[item_id].update(_status("saved", "Stack members match in Paperclip."))
        else:
            statuses[item_id].update(_status("missing", "Some stack members are missing or unconverted."))
    items = report["items"]
    converted = sum(row["conversion"]["status"] == "converted" for row in items)
    saved = sum(row["import"]["status"] == "saved" for row in items)
    report["summary"] = {"total": len(items), "converted": converted, "unconverted": len(items) - converted,
                         "imported": saved, "notImported": len(items) - saved}
    report["files"] = [{"path": path, "content": content} for path, content in _native_files(package, report).items()]
    return report


def convert(package, *, root: Path):
    """Produce a native bundle and a plan containing the original remote skills."""
    report, _, _ = _report(package, root)
    return _finish(package, report, {})


def export_package(report):
    """Return the Paperclip bundle as a ZIP, including its remote import plan."""
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for entry in report["files"]:
            archive.writestr(entry["path"], entry["content"])
    return output.getvalue()


class _PaperclipError(RuntimeError):
    def __init__(self, message, code=None, cause=None):
        super().__init__(message)
        self.code = code
        self.cause = cause

    def reason(self):
        return _because(str(self), self.cause)


class _Paperclip:
    def __init__(self, base_url, company_id):
        url = urlsplit(base_url)
        if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError("An HTTP or HTTPS Paperclip API URL is required.")
        if not isinstance(company_id, str) or not company_id.strip():
            raise ValueError("A Paperclip company ID is required.")
        self.base_url = base_url.rstrip("/")
        if not self.base_url.endswith("/api"):
            self.base_url += "/api"
        self.company = "/companies/" + quote(company_id, safe="")
        self.company_id = company_id

    def request(self, path, body=None, method="GET"):
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = Request(self.base_url + path, data=data, method=method,
                          headers={"Accept": "application/json", "Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=30 if method == "GET" else 90) as response:
                return json.load(response)
        except HTTPError as error:
            message = f"Paperclip returned HTTP {error.code}."
            cause = None
            try:
                payload = json.loads(error.read(4096))
                if isinstance(payload, dict) and isinstance(payload.get("error"), str):
                    message = f"{message} {payload['error'][:700]}"
                    details = payload.get("details")
                    if (payload.get("code") == "skill_source_github_read_failed" and isinstance(details, dict)
                            and details.get("status") in (401, 403, 404)):
                        cause = "access"
            except (ValueError, OSError):
                pass
            raise _PaperclipError(message, error.code, cause) from error
        except (URLError, TimeoutError, OSError, ValueError) as error:
            raise _PaperclipError("Paperclip could not be reached or returned invalid data.") from error

    def agent(self, package):
        agents = self.request(self.company + "/agents")
        matches = [agent for agent in agents if (agent.get("metadata") or {}).get(PACKAGE_MARKER) == package["id"]]
        if len(matches) > 1:
            raise _PaperclipError("Several Paperclip agents identify as this preset.")
        return matches[0] if matches else None


def _matching_source(sources, repository, ref):
    return next((source for source in sources
                 if _repo_key(source.get("repositoryUrl") or "") == _repo_key(repository)
                 and _ref_key(source.get("trackingRef") or "") == _ref_key(ref)), None)


def _resolve_skills(api, report):
    rows = _sources(report)
    if not rows:
        return {}
    for row in rows:
        row["target"].pop("key", None)
    sources = api.request(api.company + "/skill-sources")
    library = {skill["id"]: skill for skill in api.request(api.company + "/skills")}
    found = {}
    for row in rows:
        target = row["target"]
        identity = _source_id(target)
        source = _matching_source(sources, target["repositoryUrl"], target["ref"])
        if not source:
            found[identity] = (None, "The remote skill source is not registered in Paperclip.")
            continue
        entry = next((entry for entry in source["entries"] if entry["path"] == target["path"]), {})
        skill = library.get(entry.get("skillId"))
        refusal = entry.get("error")
        error = refusal
        if not skill:
            error = error or source.get("lastError")
        if refusal:
            found[identity] = (None, _because(f"Paperclip refused the skill. {refusal[:700]}", "refused"))
            continue
        if error:
            found[identity] = (None, f"Paperclip could not import the skill. {error[:700]}")
            continue
        if not skill or entry.get("selection") == "excluded" or entry.get("present") is False:
            found[identity] = (None, "The exact skill path is not imported from the registered source.")
            continue
        locator = skill.get("sourceLocator")
        skill_path = skill.get("sourcePath")
        if ((locator and _repo_key(locator) != _repo_key(target["repositoryUrl"])) or
                (skill_path and skill_path != target["path"])):
            found[identity] = (None, "The saved skill repository or path differs from the package reference.")
            continue
        ref = target["ref"]
        expected_commit = ref if COMMIT.fullmatch(ref) else source.get("lastScanCommit")
        if (not expected_commit or _ref_key(skill.get("sourceRef") or "") != _ref_key(expected_commit)
                or not skill.get("key")):
            found[identity] = (None, "The imported skill revision differs from the package reference.")
            continue
        target["key"] = skill["key"]
        found[identity] = (skill, None)
    return found


def _agent_path(agent):
    return "/agents/" + quote(agent["id"], safe="")


def _read_instruction(api, agent):
    try:
        return api.request(_agent_path(agent) + "/instructions-bundle/file?path=AGENTS.md")
    except _PaperclipError as error:
        if error.code == 404:
            return {}
        raise


def _assignments(api, agent):
    result = api.request(_agent_path(agent) + "/skills")
    entries = result.get("desiredSkillEntries")
    if entries is None:
        raise _PaperclipError("Paperclip did not return saved skill assignments.")
    return {entry["key"]: entry.get("versionId") for entry in entries}


def _assigned(skill, assignments):
    return (skill["key"] in assignments and
            assignments[skill["key"]] in (None, skill.get("currentVersionId")))


def _override_args(args):
    """Yield the option and parsed key for each Codex -c/--config setting."""
    if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
        return
    index = 0
    while index < len(args):
        option = args[index]
        if option in ("-c", "--config") and index + 1 < len(args):
            override = args[index + 1]
            yield args[index:index + 2], *override.partition("=")[::2]
            index += 2
        elif option.startswith(("-c=", "--config=")):
            _, _, override = option.partition("=")
            yield [option], *override.partition("=")[::2]
            index += 1
        else:
            yield [option], "", ""
            index += 1


def _mcp_values(config, name):
    values = {}
    prefix = f"mcp_servers.{name}"
    for _, key, raw in _override_args(config.get("extraArgs") or []):
        if not (key == prefix or key == "mcp_servers" or key.startswith(prefix + ".")):
            continue
        try:
            value = tomllib.loads(f"value = {raw}")["value"]
        except (tomllib.TOMLDecodeError, KeyError):
            value = raw
        if key == "mcp_servers":
            values = value.get(name, {}) if isinstance(value, dict) else {"invalid": value}
        elif key == prefix:
            values = value if isinstance(value, dict) else {"invalid": value}
        else:
            values[key[len(prefix) + 1:]] = value
    return values


def _mcp_status(agent, target):
    config = agent.get("adapterConfig") or {}
    if agent.get("adapterType") != "codex_local" or config.get("engine") != "cli":
        return _status("missing", "Paperclip is not configured to use the Codex CLI engine.")
    actual = _mcp_values(config, target["name"])
    if actual == {field: target[field] for field in ("command", "args")}:
        return _status("saved", "Saved Codex CLI command and arguments match.")
    return _status("missing", "Saved MCP settings differ from the package.")


def _observe(api, package, report, members, errors=None):
    errors = errors or {}
    agent = None
    agent_error = instruction_error = assignments_error = source_error = None
    source_skills, instructions, assignments = {}, {}, {}
    try:
        agent = api.agent(package)
    except _PaperclipError as error:
        agent_error = str(error)
    try:
        source_skills = _resolve_skills(api, report)
    except _PaperclipError as error:
        source_error = str(error)
    if agent:
        try:
            instructions = _read_instruction(api, agent)
        except _PaperclipError as error:
            instruction_error = str(error)
        if source_skills:
            try:
                assignments = _assignments(api, agent)
            except _PaperclipError as error:
                assignments_error = str(error)

    for row in report["items"]:
        if row["conversion"]["status"] == "unconverted":
            continue
        kind, target = row["kind"], row["target"]
        if kind == "package":
            continue
        reason = errors.get(row["id"]) or errors.get("agent") or agent_error
        if kind == "skill":
            identity = _source_id(target)
            skill, mismatch = source_skills.get(identity, (None, source_error))
            reason = errors.get(identity) or reason or mismatch
            if not reason and skill and _assigned(skill, assignments):
                row["import"] = _status("saved", "The assigned repository, path and revision match.")
                continue
            reason = reason or assignments_error or "The exact skill revision is not assigned to this agent."
        elif not reason and agent and kind == "instruction":
            content = instructions.get("content")
            if isinstance(content, str) and _instruction(content) == _instruction(package["instruction"]):
                row["import"] = _status("saved", "Saved AGENTS.md matches the package.")
                continue
            reason = instruction_error or "Saved AGENTS.md differs from the package."
        elif not reason and agent and kind == "mcp":
            row["import"] = _mcp_status(agent, target)
            continue
        row["import"] = _status("missing", reason or "No matching Paperclip agent was found.")
    return _finish(package, report, members, agent)


def observe(package, *, root: Path, base_url: str, company_id: str):
    """Check actual saved instructions, skill sources, and MCP settings."""
    report, _, members = _report(package, root)
    return _observe(_Paperclip(base_url, company_id), package, report, members)


def _register_sources(api, report, errors, recheck=False):
    targets = defaultdict(dict)
    for row in _sources(report):
        target = row["target"]
        targets[(target["repositoryUrl"].casefold(), target["ref"])][target["path"]] = target
    if not targets:
        return
    path = api.company + "/skill-sources"
    try:
        sources = api.request(path)
    except _PaperclipError as error:
        errors.update({_source_id(row["target"]): error.reason() for row in _sources(report)})
        return
    for (_, ref), paths in targets.items():
        repository = next(iter(paths.values()))["repositoryUrl"]
        source = _matching_source(sources, repository, ref)
        pending = set(paths)
        try:
            if source:
                # A stored refusal may date from an older Paperclip. A new scan costs GitHub requests, so only on request.
                if recheck and any(entry.get("error") and entry["path"] in paths for entry in source["entries"]):
                    try:
                        refresh = path + "/" + quote(source["id"], safe="") + "/refresh"
                        source = api.request(refresh, {}, "POST").get("source") or source
                    except _PaperclipError:
                        pass
                selected = {entry["path"] for entry in source["entries"]
                            if entry.get("selection") in ("selected", "included") or
                            (entry.get("skillId") and entry.get("selection") != "excluded")}
                known_failures = {entry["path"] for entry in source["entries"] if entry.get("error")}
                pending -= selected | known_failures
                if pending:
                    payload = {"revision": source["revision"], "selectedPaths": sorted(selected | pending),
                               "excludedFolders": source.get("excludedFolders", [])}
                    api.request(path + "/" + quote(source["id"], safe=""), payload, "PATCH")
            else:
                payload = {"repositoryUrl": repository, "trackingRef": ref}
                commit = ref
                if not COMMIT.fullmatch(ref):
                    commit = api.request(path + "/discover", payload, "POST").get("commitSha")
                    if not commit or not COMMIT.fullmatch(commit):
                        raise _PaperclipError("Paperclip did not resolve the skill source to a commit.")
                api.request(path, {**payload, "commitSha": commit, "selectedPaths": sorted(paths),
                                   "excludedFolders": []}, "POST")
        except _PaperclipError as error:
            for skill_path in pending:
                errors[_source_id(paths[skill_path])] = error.reason()


def _create_agent(api, package, report):
    files = _native_files(package, report)
    del files[PLAN_PATH]
    payload = {
        "source": {"type": "inline", "files": files},
        "target": {"mode": "existing_company", "companyId": api.company_id},
        "include": {"company": False, "agents": True, "skills": False, "projects": False, "issues": False},
        "pauseAutomations": True, "collisionStrategy": "skip",
    }
    preview = api.request("/companies/import/preview", payload, "POST")
    if preview.get("errors"):
        raise _PaperclipError("Paperclip import preview failed. " + " ".join(preview["errors"])[:700])
    agents = preview.get("manifest", {}).get("agents", [])
    keys = {row["target"]["key"] for row in _sources(report) if row["target"].get("key")}
    if (len(agents) != 1 or agents[0]["slug"] != _agent_slug(package)
            or set(agents[0]["skills"]) != keys):
        raise _PaperclipError("The Paperclip import preview changed the agent or its skill references.")
    plans = preview.get("plan", {}).get("agentPlans", [])
    if plans and plans[0].get("action") != "create":
        agent = api.agent(package)
        if agent:
            return agent
        raise _PaperclipError("The Paperclip import preview found an unrelated agent with this name.")
    result = api.request("/companies/import", payload, "POST")
    agent = api.agent(package)
    if not agent:
        warnings = " ".join(result.get("warnings", []))[:700]
        raise _PaperclipError("Paperclip did not create the requested agent. " + warnings)
    return agent


def _update_agent(api, package, agent, report, source_skills, errors):
    path = _agent_path(agent)
    if agent.get("status") != "paused":
        api.request(path + "/pause", method="POST")
    if agent.get("adapterType") != "codex_local":
        raise _PaperclipError("The existing Paperclip agent has a different adapter.")
    try:
        instruction = _read_instruction(api, agent)
        text = _instruction(package["instruction"])
        if not isinstance(instruction.get("content"), str) or _instruction(instruction["content"]) != text:
            api.request(path + "/instructions-bundle/file", {
                "path": "AGENTS.md", "content": text,
                "baseRevisionId": (instruction.get("revision") or {}).get("id"),
                "clearLegacyPromptTemplate": True,
            }, "PUT")
    except _PaperclipError as error:
        errors["instruction"] = str(error)

    mcp = {value["name"]: value for value in _mcps(report)}
    metadata = dict(agent.get("metadata") or {})
    managed_names = set(metadata.get(MCP_MARKER, [])) | mcp.keys()
    metadata[MCP_MARKER] = list(mcp)
    config = dict(agent.get("adapterConfig") or {})
    if managed_names:
        args = [arg for tokens, key, _ in _override_args(config.get("extraArgs") or [])
                if not any(key == f"mcp_servers.{name}" or key.startswith(f"mcp_servers.{name}.")
                           for name in managed_names) for arg in tokens]
        config["extraArgs"] = args + _extra_args(mcp.values())
        if mcp:
            config["engine"] = "cli"
    if config != agent.get("adapterConfig") or metadata != agent.get("metadata"):
        try:
            api.request(path, {"adapterConfig": config, "metadata": metadata}, "PATCH")
        except _PaperclipError as error:
            for row in report["items"]:
                if row["kind"] == "mcp" and row["target"]:
                    errors[row["id"]] = str(error)

    if source_skills:
        missing = []
        try:
            assignments = _assignments(api, agent)
            missing = [skill["key"] for skill, _ in source_skills.values()
                       if skill and not _assigned(skill, assignments)]
            if missing:
                api.request(path + "/skills/sync", {"mode": "add", "desiredSkills": list(dict.fromkeys(missing))}, "POST")
        except _PaperclipError as error:
            for identity, (skill, _) in source_skills.items():
                if skill and (not missing or skill["key"] in missing):
                    errors[identity] = str(error)


def _require_current(root, revisions):
    for package_id, expected in revisions.items():
        try:
            actual = _read_package(root, package_id)["revision"]
        except (ValueError, LookupError, FileNotFoundError):
            actual = None
        if expected is None or actual != expected:
            raise ValueError(f"Package {package_id} changed before Paperclip import. Reload it and try again.")


def import_package(package, *, root: Path, base_url: str, company_id: str, recheck: bool = False):
    """Import into the explicit company, then read back the saved configuration."""
    report, revisions, members = _report(package, root)
    _require_current(root, revisions)
    api = _Paperclip(base_url, company_id)
    errors = {}
    try:
        api.request(api.company)
        agent = api.agent(package)
        _register_sources(api, report, errors, recheck)
        try:
            source_skills = _resolve_skills(api, report)
        except _PaperclipError as error:
            source_skills = {}
            for row in _sources(report):
                errors.setdefault(_source_id(row["target"]), str(error))
        _require_current(root, revisions)
        if agent:
            _update_agent(api, package, agent, report, source_skills, errors)
        else:
            created = _create_agent(api, package, report)
            # Another request may have won the native import or the legacy
            # importer may have left the previous canonical instruction.
            _update_agent(api, package, created, report, source_skills, errors)
    except _PaperclipError as error:
        errors["agent"] = str(error)
    return _observe(api, package, report, members, errors)
