from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from zipfile import ZipFile

import yaml

from asm_app import paperclip


REPO = "https://github.com/example/preset-tools"
PATH = "skills/check/SKILL.md"
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
         "source": {"repositoryUrl": REPO, "path": PATH, "ref": "main"}},
        {"id": "playwright", "name": "Playwright", "kind": "mcp",
         "configuration": {"name": "playwright", "transport": "stdio", "registry": False,
                           "command": "npx", "args": ["@playwright/mcp@latest"]}},
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


def exported(report):
    with ZipFile(BytesIO(paperclip.export_package(report))) as archive:
        return {name: archive.read(name).decode() for name in archive.namelist()}


class PaperclipTests(unittest.TestCase):
    def setUp(self):
        self.package = deepcopy(PACKAGE)

    def test_export_preserves_native_instruction_and_remote_source(self):
        report = paperclip.convert(self.package, root=ROOT)
        files = exported(report)
        front, instruction, extension = parse_agent(files)
        self.assertEqual(instruction, "Check the app.")
        self.assertEqual(front["skills"], [])
        self.assertEqual(extension["adapter"], {"type": "codex_local", "config": {
            "engine": "cli", "extraArgs": ["-c", 'mcp_servers.playwright.command="npx"',
                                           "-c", 'mcp_servers.playwright.args=["@playwright/mcp@latest"]'],
        }})
        self.assertEqual(json.loads(files["remote-import-plan.json"])["remoteSources"],
                         [{"repositoryUrl": REPO, "path": PATH, "ref": "main"}])
        self.assertEqual(report["summary"], {"total": 5, "converted": 3, "unconverted": 2})
        for item_id in ("stop", "design"):
            self.assertEqual(by_id(report)[item_id]["conversion"]["status"], "unconverted")
        self.assertTrue(all("runtime" not in row for row in report["items"]))

    def test_report_holds_the_conversion_alone(self):
        report = paperclip.convert(self.package, root=ROOT)
        self.assertEqual(set(report), {"consumer", "items", "summary", "files"})
        for row in report["items"]:
            self.assertEqual(set(row), {"id", "name", "kind", "source", "target", "conversion"})

    def test_export_carries_no_tracking_marker(self):
        _, _, extension = parse_agent(exported(paperclip.convert(self.package, root=ROOT)))
        self.assertNotIn("metadata", extension)

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

    def test_skill_that_follows_the_default_branch_converts(self):
        for source in ({"repositoryUrl": REPO, "path": PATH, "ref": ""},
                       {"repositoryUrl": REPO, "path": PATH, "ref": "HEAD"},
                       {"repositoryUrl": REPO, "path": PATH},
                       {"repositoryUrl": REPO, "path": PATH, "ref": "main"}):
            with self.subTest(ref=source.get("ref")):
                self.package["components"][1]["source"] = source
                report = paperclip.convert(self.package, root=ROOT)
                check = by_id(report)["check"]
                self.assertEqual(check["conversion"]["status"], "converted")
                plan = json.loads(exported(report)["remote-import-plan.json"])
                expected = {"repositoryUrl": REPO, "path": PATH}
                if source.get("ref") == "main":
                    expected["ref"] = "main"
                self.assertEqual(plan["remoteSources"], [expected])

    def test_hook_and_plugin_name_paperclip_as_the_reason(self):
        items = by_id(paperclip.convert(self.package, root=ROOT))
        for item_id, kind in (("stop", "hook"), ("design", "plugin")):
            conversion = items[item_id]["conversion"]
            self.assertEqual(conversion["cause"], "unsupported")
            self.assertEqual(conversion["reason"], f"Paperclip has no setting for agent {kind}s.")
        self.assertNotIn("cause", items["check"]["conversion"])

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

    def test_additional_apm_instruction_is_reported_unconverted(self):
        self.package["components"].append({"id": "instructions:style", "name": "Style",
                                           "kind": "instruction", "configuration": "Use plain text."})
        items = by_id(paperclip.convert(self.package, root=ROOT))
        self.assertEqual(items["instruction"]["conversion"]["status"], "converted")
        self.assertEqual(items["instructions:style"]["conversion"]["status"], "unconverted")


if __name__ == "__main__":
    unittest.main()
