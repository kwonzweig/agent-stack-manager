import base64
import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import yaml

from asm_app.store import Store, StoreError


class InventoryTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.manifest = self.root / "packages" / "example" / "apm.yml"
        self.manifest.parent.mkdir(parents=True)
        self.items = [
            {"id": "example-skill", "name": "Example skill", "kind": "skill", "description": "Read files.",
             "skillRepository": {"owner": "example", "repo": "skills", "branch": "main"},
             "apps": {"codex": {"installed": True, "enabled": False, "selected": True, "scope": "user"},
                      "claude": {"installed": True, "enabled": None, "selected": True}}},
            {"id": "start-hook", "name": "Start hook", "kind": "hook", "description": "Runs at startup.",
             "apps": {"claude": {"installed": True, "enabled": True, "selected": True}}},
            {"id": "server", "name": "Example MCP", "kind": "mcp", "description": "Look up records.",
             "apps": {"codex": {"installed": True, "enabled": None, "selected": True}}},
        ]
        self.manifest.write_text(yaml.safe_dump({"name": "example", "version": "0.1.0",
                                                 "x-app-inventory": {"items": self.items}}))
        self.store = Store(self.root)

    def test_excluding_one_app_preserves_installed_state_and_other_apps(self):
        package = self.store.get("example")
        self.assertEqual([{key: value for key, value in row.items() if key in expected}
                          for row, expected in zip(package["appInventory"], self.items)], self.items)
        self.assertTrue(all(row["canonicalId"].startswith("component-") for row in package["appInventory"]))
        saved = self.store.save("example", {"revision": package["revision"],
                                           "appInventorySelections": {"example-skill": {"codex": False}}})
        expected = self.items[0]["apps"]["codex"] | {"selected": False}
        self.assertEqual(saved["appInventory"][0]["apps"]["codex"], expected)
        self.assertEqual(saved["appInventory"][0]["apps"]["claude"], self.items[0]["apps"]["claude"])
        self.assertEqual(Store(self.root).get("example"), saved)
        restored = self.store.save("example", {"revision": saved["revision"],
                                              "appInventorySelections": {"example-skill": {"codex": True}}})
        self.assertEqual([{key: value for key, value in row.items() if key in expected}
                          for row, expected in zip(restored["appInventory"], self.items)], self.items)

    def test_unknown_app_selection_fails_without_writing_other_changes(self):
        package = self.store.get("example")
        with self.assertRaisesRegex(StoreError, "not installed"):
            self.store.save("example", {"revision": package["revision"], "description": "Changed",
                                       "appInventorySelections": {"start-hook": {"codex": False}}})
        self.assertEqual(self.store.get("example"), package)

    def test_native_skill_tracks_selection_across_apps(self):
        ref = {"git": "https://github.com/example/skills", "ref": "main", "path": "skills/example"}
        manifest = yaml.safe_load(self.manifest.read_text())
        manifest["x-app-inventory"]["items"][0]["apm"] = ref
        stored = {**ref, "alias": "preserve-existing-alias"}
        unrelated = {"git": "https://github.com/example/other", "ref": "main", "path": "skills/other"}
        manifest["dependencies"] = {"apm": [unrelated, stored]}
        self.manifest.write_text(yaml.safe_dump(manifest))
        starting = self.store.get("example")
        managed = next(row for row in starting["components"] if row.get("managedByInventory"))
        unmanaged = next(row for row in starting["components"] if row["kind"] == "skill" and not row.get("managedByInventory"))
        self.assertEqual(managed["configuration"], stored)
        saved = self.store.save("example", {"revision": starting["revision"], "componentIds": [unmanaged["id"]],
                                           "appInventorySelections": {"example-skill": {"codex": False}}})
        self.assertEqual(yaml.safe_load(self.manifest.read_text())["dependencies"]["apm"], [unrelated, stored])
        saved = self.store.save("example", {"revision": saved["revision"],
                                           "appInventorySelections": {"example-skill": {"claude": False}}})
        self.assertEqual(yaml.safe_load(self.manifest.read_text())["dependencies"]["apm"], [unrelated])
        self.assertEqual(saved["appInventory"][0]["apm"], ref)
        self.store.save("example", {"revision": saved["revision"],
                                   "appInventorySelections": {"example-skill": {"codex": True}}})
        self.assertEqual(yaml.safe_load(self.manifest.read_text())["dependencies"]["apm"], [unrelated, ref])

    def test_a_verified_native_skill_may_live_at_the_root_of_its_repo(self):
        ref = {"git": "https://github.com/example/skill", "ref": "main"}
        manifest = yaml.safe_load(self.manifest.read_text())
        manifest["x-app-inventory"]["items"][0]["apm"] = ref
        manifest["dependencies"] = {"apm": [ref]}
        self.manifest.write_text(yaml.safe_dump(manifest))
        package = self.store.get("example")
        self.assertEqual([row["kind"] for row in package["components"] if row.get("managedByInventory")],
                         ["skill"])

    def test_cc_switch_accounts_for_each_app_and_only_registers_the_repo(self):
        from asm_app.cc_switch import convert

        package = self.store.get("example")
        package = self.store.save("example", {"revision": package["revision"],
                                             "appInventorySelections": {"example-skill": {"claude": False}}})
        report = convert(package)
        statuses = {(row["id"], row["app"]): row["status"] for row in report["items"]}
        self.assertEqual(statuses, {("example-skill", "codex"): "registration-only",
                                    ("example-skill", "claude"): "excluded",
                                    ("start-hook", "claude"): "unsupported",
                                    ("server", "codex"): "manual"})
        self.assertEqual(report["skillRepositories"], [
            {"owner": "example", "repo": "skills", "branch": "main",
             "url": "ccswitch://v1/import?resource=skill&repo=example%2Fskills&branch=main"}])
        codex = next(row for row in report["items"] if (row["id"], row["app"]) == ("example-skill", "codex"))
        self.assertIs(codex["enabled"], False)
        self.assertIs(codex["selected"], True)
        self.assertTrue(codex["installed"])

    def test_only_explicit_prompts_and_enabled_credential_free_mcp_are_importable(self):
        from asm_app.cc_switch import convert

        def row(identifier, kind, enabled, portable):
            return {"id": identifier, "name": identifier, "kind": kind,
                    "apps": {"codex": {"installed": True, "enabled": enabled,
                                       "selected": True, "portable": portable}}}

        items = [
            row("prompt", "instruction", False, {"prompt": "Explain café."}),
            row("remote", "mcp", True, {"mcp": {"name": "remote", "url": "https://mcp.example.com/v1"}}),
            row("disabled", "mcp", False, {"mcp": {"name": "disabled", "url": "https://mcp.example.com/v1"}}),
            row("protected", "mcp", True, {"mcp": {"name": "protected", "url": "https://mcp.example.com/?key=secret"}}),
        ]
        prompt, mcp, disabled, protected = convert({"id": "portable", "appInventory": items})["items"]
        self.assertEqual([prompt["status"], mcp["status"], disabled["status"], protected["status"]],
                         ["import-ready", "import-ready", "manual", "manual"])
        spec = parse_qs(urlsplit(prompt["url"]).query)
        self.assertEqual(spec["enabled"], ["false"])
        self.assertEqual(base64.b64decode(spec["content"][0]).decode(), "Explain café.")
        spec = parse_qs(urlsplit(mcp["url"]).query)
        self.assertEqual(json.loads(base64.b64decode(spec["config"][0])),
                         {"mcpServers": {"remote": {"url": "https://mcp.example.com/v1"}}})
        self.assertNotIn("secret", json.dumps(protected))


if __name__ == "__main__":
    unittest.main()
