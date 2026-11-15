from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import json
from pathlib import Path
from threading import Thread
import unittest
from unittest.mock import patch
from zipfile import ZipFile

import yaml

from asm_app import paperclip


REPO = "https://github.com/example/preset-tools"
REF = "0123456789abcdef0123456789abcdef01234567"
PATH = "skills/check/SKILL.md"
KEY = "github/123/selected/check"
COMPANY = "preset-test"
COMPANY_PATH = f"/api/companies/{COMPANY}"
ROOT = Path(".")

PACKAGE = {
    "id": "test-preset",
    "title": "Test Preset",
    "description": "Exercise the Paperclip adapter.",
    "instruction": "Check the app.",
    "revision": "rev-1",
    "components": [
        {"id": "instruction", "name": "Instruction", "kind": "instruction"},
        {"id": "check", "name": "Check", "kind": "skill",
         "source": {"repositoryUrl": REPO, "path": PATH, "ref": REF}},
        {"id": "playwright", "name": "Playwright", "kind": "mcp",
         "configuration": {"name": "playwright", "transport": "stdio", "registry": False,
                           "command": "npx", "args": ["@playwright/mcp@0.0.85"]}},
        {"id": "stop", "name": "Stop", "kind": "hook"},
        {"id": "design", "name": "Design", "kind": "plugin"},
    ],
}


def by_id(report):
    return {item["id"]: item for item in report["items"]}


def parse_agent(files):
    # Paperclip's portable parser locates AGENTS.md, reads its frontmatter and
    # looks up the corresponding extension entry by slug.
    company = yaml.safe_load(files["COMPANY.md"].split("---", 2)[1])
    assert company["name"]
    paths = [path for path in files if path.startswith("agents/") and path.endswith("/AGENTS.md")]
    assert len(paths) == 1
    _, header, body = files[paths[0]].split("---", 2)
    frontmatter = yaml.safe_load(header)
    extension = yaml.safe_load(files[".paperclip.yaml"])
    assert extension["schemaVersion"] == 7
    return frontmatter, body.strip(), extension["agents"][frontmatter["slug"]]


class PaperclipFixture:
    def __init__(self):
        self.agents = []
        self.library = []
        self.sources = []
        self.saved_instruction = None
        self.assignments = []
        self.requests = []
        self.source_rejected = False
        self.sources_unavailable = False
        self.preview_error = None
        self.ignore_instruction_update = False

    def respond(self, method, url, body):
        self.requests.append((method, url, body))
        if method == "GET":
            if url == COMPANY_PATH:
                return 200, {"id": COMPANY, "name": "Test Company"}
            if url == COMPANY_PATH + "/agents":
                return 200, self.agents
            if url == COMPANY_PATH + "/skills":
                return 200, self.library
            if url == COMPANY_PATH + "/skill-sources":
                if self.sources_unavailable:
                    return 503, {"error": "Skill sources unavailable"}
                return 200, self.sources
            if url == "/api/agents/agent-1/instructions-bundle/file?path=AGENTS.md":
                return 200, {"content": self.saved_instruction, "revision": {"id": "revision-1"}}
            if url == "/api/agents/agent-1/skills":
                return 200, {"desiredSkillEntries": self.assignments}
        if method == "POST" and url == COMPANY_PATH + "/skill-sources":
            query = {"repositoryUrl": REPO, "trackingRef": REF, "commitSha": REF,
                     "selectedPaths": [PATH], "excludedFolders": []}
            if body != query:
                return 422, {"error": "Wrong repository source, commit or path"}
            if self.source_rejected:
                return 422, {"error": "Check failed verification"}
            self.add_source(with_check=True)
            return 201, {"source": self.sources[0]}
        if method == "PATCH" and url == COMPANY_PATH + "/skill-sources/source-1":
            if set(body["selectedPaths"]) != {"skills/other/SKILL.md", PATH}:
                return 422, {"error": "The previous source selection was lost"}
            if body.get("revision") != 2 or body["excludedFolders"] != ["archived"]:
                return 422, {"error": "Source revision or excluded folders were lost"}
            self.add_source(with_check=True)
            return 200, {"source": self.sources[0]}
        if method == "POST" and url in ("/api/companies/import/preview", "/api/companies/import"):
            try:
                front, instructions, ext = parse_agent(body["source"]["files"])
                assert body["target"] == {"mode": "existing_company", "companyId": COMPANY}
                assert body["pauseAutomations"] is True
                assert body["collisionStrategy"] == "skip"
                assert body["include"] == {"company": False, "agents": True, "skills": False,
                                           "projects": False, "issues": False}
                assert "remote-import-plan.json" not in body["source"]["files"]
                assert all(any(s["key"] == key for s in self.library) for key in front["skills"])
            except (AssertionError, KeyError):
                return 422, {"error": "Invalid native Paperclip package"}
            if url.endswith("/preview"):
                return 200, {"manifest": {"agents": [{"slug": front["slug"], "skills": front["skills"]}]},
                             "errors": [self.preview_error] if self.preview_error else []}
            agent = {"id": "agent-1", "urlKey": front["slug"], "name": front["name"],
                     "metadata": ext["metadata"], "adapterType": ext["adapter"]["type"],
                     "adapterConfig": ext["adapter"]["config"], "status": "paused"}
            self.agents.append(agent)
            self.saved_instruction = instructions
            self.assignments = [{"key": key, "versionId": None} for key in front["skills"]]
            return 200, {"agents": [{"id": agent["id"], "action": "created"}], "warnings": []}
        if method == "PUT" and url == "/api/agents/agent-1/instructions-bundle/file":
            if body["path"] != "AGENTS.md" or body["baseRevisionId"] != "revision-1":
                return 409, {"error": "Instruction revision is stale"}
            if not self.ignore_instruction_update:
                self.saved_instruction = body["content"]
            return 200, {"content": self.saved_instruction}
        if method == "PATCH" and url == "/api/agents/agent-1":
            self.agents[0].update(body)
            return 200, self.agents[0]
        if method == "POST" and url == "/api/agents/agent-1/skills/sync":
            if body["mode"] != "add":
                return 422, {"error": "Existing skills must be preserved"}
            for key in body["desiredSkills"]:
                self.assignments = [entry for entry in self.assignments if entry["key"] != key]
                self.assignments.append({"key": key, "versionId": None})
            return 200, {"desiredSkillEntries": self.assignments}
        return 404, {"error": "Unexpected fixture endpoint"}

    def add_source(self, *, with_check):
        other = {"path": "skills/other/SKILL.md", "selection": "selected", "skillId": "other"}
        check = {"path": PATH, "selection": "selected", "skillId": "check-id", "error": None}
        self.sources[:] = [{"id": "source-1", "repositoryUrl": REPO, "trackingRef": REF,
                            "lastScanCommit": REF, "revision": 2, "excludedFolders": ["archived"],
                            "entries": [other, check] if with_check else [other]}]
        self.library[:] = [{"id": "check-id", "key": KEY, "sourceRef": REF,
                            "sourceLocator": REPO, "sourcePath": None,
                            "currentVersionId": "version-1"}] if with_check else []


class PaperclipTests(unittest.TestCase):
    def setUp(self):
        self.package = deepcopy(PACKAGE)
        self.fixture = PaperclipFixture()
        fixture = self.fixture

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def handle_request(self):
                size = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(size)) if size else None
                status, result = fixture.respond(self.command, self.path, body)
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(result).encode())

            do_GET = do_POST = do_PUT = do_PATCH = handle_request

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.url = f"http://127.0.0.1:{self.server.server_port}/api"

    def readback(self):
        return paperclip.observe(self.package, root=ROOT, base_url=self.url, company_id=COMPANY)

    def apply(self, current=None):
        current = self.package if current is None else current
        with patch.object(paperclip, "_read_package", return_value=current):
            return paperclip.import_package(self.package, root=ROOT, base_url=self.url, company_id=COMPANY)

    def test_export_preserves_native_instruction_and_remote_source(self):
        report = paperclip.convert(self.package, root=ROOT)
        with ZipFile(BytesIO(paperclip.export_package(report))) as archive:
            files = {name: archive.read(name).decode() for name in archive.namelist()}
        front, instruction, extension = parse_agent(files)
        self.assertEqual(instruction, "Check the app.")
        self.assertEqual(front["skills"], [])
        self.assertEqual(extension["adapter"], {"type": "codex_local", "config": {
            "engine": "cli", "extraArgs": ["-c", 'mcp_servers.playwright.command="npx"',
                                           "-c", 'mcp_servers.playwright.args=["@playwright/mcp@0.0.85"]'],
        }})
        self.assertEqual(json.loads(files["remote-import-plan.json"])["remoteSources"],
                         [{"repositoryUrl": REPO, "path": PATH, "ref": REF}])
        self.assertEqual(report["summary"], {"total": 5, "converted": 3, "unconverted": 2,
                                             "imported": 0, "notImported": 5})
        for item_id in ("stop", "design"):
            self.assertEqual(by_id(report)[item_id]["conversion"]["status"], "unconverted")
        self.assertTrue(all("runtime" not in row for row in report["items"]))

    def test_stack_members_expand_and_cycles_are_reported(self):
        self.package["components"] = [{"id": "instruction", "name": "Instruction", "kind": "instruction"},
                                      {"id": "package:web", "name": "Web", "kind": "package",
                                       "configuration": {"packageId": "web"}}]
        child = {"id": "web", "revision": "nested-1", "instruction": "", "components": [
            {"id": "instruction", "name": "Instruction", "kind": "instruction"},
            deepcopy(PACKAGE["components"][1]),
            deepcopy(self.package["components"][1]),
        ]}
        with patch.object(paperclip, "_read_package", return_value=child):
            report = paperclip.convert(self.package, root=ROOT)
        self.assertEqual(by_id(report)["check"]["conversion"]["status"], "converted")
        self.assertEqual(sum("cycle" in row["conversion"]["reason"].lower() for row in report["items"]), 1)
        self.assertEqual(len({row["id"] for row in report["items"]}), len(report["items"]))

    def test_register_before_import_and_verify_saved_components(self):
        report = self.apply()
        self.assertEqual(report["summary"]["imported"], 3)
        self.assertEqual(self.fixture.agents[0]["status"], "paused")
        self.assertEqual(self.fixture.assignments, [{"key": KEY, "versionId": None}])
        writes = [(method, path) for method, path, _ in self.fixture.requests if method != "GET"]
        self.assertEqual(writes, [("POST", COMPANY_PATH + "/skill-sources"),
                                  ("POST", "/api/companies/import/preview"),
                                  ("POST", "/api/companies/import")])

    def test_import_keeps_unrelated_skill_selections_and_assignments(self):
        self.fixture.add_source(with_check=False)
        first = self.apply()
        self.assertEqual(first["summary"]["imported"], 3)
        self.fixture.assignments[:] = [{"key": "unrelated", "versionId": "pinned"}]
        second = self.apply()
        self.assertEqual(second["summary"]["imported"], 3)
        self.assertEqual(self.fixture.assignments, [{"key": "unrelated", "versionId": "pinned"},
                                                   {"key": KEY, "versionId": None}])
        self.fixture.requests.clear()
        self.assertEqual(self.apply()["summary"]["imported"], 3)
        self.assertTrue(all(method == "GET" for method, _, _ in self.fixture.requests))

    def test_readback_matches_instruction_ref_and_effective_mcp_arguments(self):
        self.apply()
        self.package["instruction"] = "Check the changed app."
        self.fixture.library[0]["sourceRef"] = "wrong-commit"
        config = self.fixture.agents[0]["adapterConfig"]
        config["extraArgs"] += ["-c", 'mcp_servers.playwright.command="different"']
        items = by_id(self.readback())
        for item_id in ("instruction", "check", "playwright"):
            self.assertEqual(items[item_id]["import"]["status"], "missing")
        self.fixture.library[0]["sourceRef"] = REF
        self.fixture.assignments[0]["versionId"] = "different-saved-version"
        config["extraArgs"] = config["extraArgs"][:-2]
        config["engine"] = "acp"
        items = by_id(self.readback())
        self.assertEqual(items["check"]["import"]["status"], "missing")
        self.assertEqual(items["playwright"]["import"]["status"], "missing")
        self.assertIn("CLI", items["playwright"]["import"]["reason"])

    def test_source_failure_survives_partial_success(self):
        self.fixture.source_rejected = True
        report = self.apply()
        items = by_id(report)
        self.assertEqual(report["summary"]["imported"], 2)
        self.assertEqual(items["check"]["import"]["status"], "missing")
        self.assertIn("Check failed verification", items["check"]["import"]["reason"])
        self.assertIsNone(items["check"]["target"].get("key"))
        self.assertEqual(self.fixture.assignments, [])

    def test_unavailable_sources_do_not_block_instruction_and_mcp(self):
        self.fixture.sources_unavailable = True
        result = self.apply()
        self.assertEqual(result["summary"]["imported"], 2)
        self.assertIn("Skill sources unavailable", by_id(result)["check"]["import"]["reason"])

    def test_wrong_saved_skill_repository_cannot_pass_readback(self):
        self.apply()
        self.fixture.library[0]["sourceLocator"] = "https://github.com/example/same-name"
        skill = by_id(self.readback())["check"]
        self.assertEqual(skill["import"]["status"], "missing")
        self.assertIsNone(skill["target"].get("key"))

    def test_changed_instruction_is_saved_with_a_revision(self):
        self.apply()
        self.package["instruction"] = "Check the updated app."
        self.fixture.ignore_instruction_update = True
        result = by_id(self.apply())
        self.assertEqual(result["instruction"]["import"]["status"], "missing")
        self.assertEqual(result["check"]["import"]["status"], "saved")
        self.fixture.ignore_instruction_update = False
        self.assertEqual(by_id(self.apply())["instruction"]["import"]["status"], "saved")
        self.assertEqual(self.fixture.saved_instruction, "Check the updated app.")

    def test_preview_rejection_survives_readback(self):
        self.fixture.preview_error = "Agent package policy rejected"
        report = self.apply()
        self.assertEqual(report["summary"]["imported"], 0)
        self.assertIn("Agent package policy rejected", by_id(report)["instruction"]["import"]["reason"])
        self.assertEqual(self.fixture.agents, [])

    def test_apply_rejects_stale_preset_before_any_mutation(self):
        current = {**self.package, "revision": "rev-2"}
        with self.assertRaisesRegex(ValueError, "changed"):
            self.apply(current)
        self.assertFalse(any(method != "GET" for method, _, _ in self.fixture.requests))

    def test_unmapped_mcp_options_are_disclosed(self):
        config = self.package["components"][2]["configuration"]
        config["env"] = {"SETTING": "${SETTING}"}
        report = paperclip.convert(self.package, root=ROOT)
        self.assertEqual(by_id(report)["playwright"]["conversion"]["status"], "unconverted")
        self.assertIn("env", by_id(report)["playwright"]["conversion"]["reason"])

    def test_apm_registry_mcp_reference_is_unconverted(self):
        self.package["components"][2]["configuration"] = "playwright"
        report = paperclip.convert(self.package, root=ROOT)
        self.assertEqual(by_id(report)["playwright"]["conversion"]["status"], "unconverted")

    def test_additional_apm_instruction_is_not_claimed_as_saved(self):
        self.package["components"].append({"id": "instructions:style", "name": "Style",
                                           "kind": "instruction", "configuration": "Use plain text."})
        items = by_id(self.apply())
        self.assertEqual(items["instruction"]["import"]["status"], "saved")
        self.assertEqual(items["instructions:style"]["conversion"]["status"], "unconverted")

    def test_source_revision_tracks_preset_and_stack_edits_across_operations(self):
        stack = {"id": "web", "revision": "stack-1", "instruction": "",
                 "components": [self.package["components"].pop(1)]}
        self.package["components"].append({"id": "package:web", "name": "Web", "kind": "package",
                                           "configuration": {"packageId": "web"}})
        packages = {self.package["id"]: self.package, stack["id"]: stack}
        with patch.object(paperclip, "_read_package", side_effect=lambda _, identifier: packages[identifier]):
            original = paperclip.convert(self.package, root=ROOT)["sourceRevision"]
            applied = paperclip.import_package(self.package, root=ROOT, base_url=self.url, company_id=COMPANY)
            self.assertEqual(applied["sourceRevision"], original)
            self.assertEqual(self.readback()["sourceRevision"], original)
            self.package.update({"instruction": "Update the app.", "revision": "rev-2"})
            edited = paperclip.convert(self.package, root=ROOT)["sourceRevision"]
            self.assertNotEqual(edited, original)
            stack["revision"] = "stack-2"
            self.assertNotEqual(paperclip.convert(self.package, root=ROOT)["sourceRevision"], edited)

if __name__ == "__main__":
    unittest.main()
