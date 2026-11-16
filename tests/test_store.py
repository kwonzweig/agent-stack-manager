import io
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

import yaml

from asm_app.store import Store, StoreError


ROOT = Path(__file__).resolve().parents[1]


class StoreTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        catalog = self.root / "catalog"
        catalog.mkdir()
        (catalog / "components.json").write_bytes((ROOT / "catalog/components.json").read_bytes())
        self.store = Store(self.root)
        self.catalog = {row["name"]: row for row in self.store.catalog()["items"]}

    def create(self, title="Checkout engineer", names=(), **changes):
        return self.store.create({
            "title": title, "description": "Build checkout.", "workArea": ["Product"],
            "usage": ["Build"], "instruction": "Verify payment totals.",
            "componentIds": [self.catalog[name]["id"] for name in names], **changes,
        })

    def test_native_package_survives_reopening_and_zip_preserves_bytes(self):
        package = self.create(names=["brainstorming", "playwright", "web-session-start", "frontend-design"])
        self.assertEqual(Store(self.root).get("checkout-engineer"), package)
        self.assertEqual(package["workArea"], ["Product"])
        self.assertEqual(package["instruction"], "Verify payment totals.")
        self.assertEqual({row["kind"] for row in package["components"]},
                         {"instruction", "skill", "mcp", "hook", "plugin"})
        with ZipFile(io.BytesIO(self.store.export(package["id"]))) as archive:
            self.assertEqual(set(archive.namelist()), {
                "apm.yml", ".apm/agents/checkout-engineer.agent.md", ".apm/hooks/web-session-start.json"})
            for name in archive.namelist():
                self.assertEqual(archive.read(name), (self.root / "packages/checkout-engineer" / name).read_bytes())

    def test_patch_keeps_unknown_native_fields_and_dependency_fields(self):
        first = self.create(names=["brainstorming"])
        base = self.root / "packages/checkout-engineer"
        manifest = base / "apm.yml"
        data = yaml.safe_load(manifest.read_text())
        data["x-unfamiliar"] = {"features": ["editing", {"size": 7}]}
        data["x-preset-labels"]["project"] = "Checkout"
        data["dependencies"]["apm"][0]["x-vendor"] = "keep me"
        data["dependencies"]["apm"][0]["x-published"] = date(2026, 11, 14)
        data["dependencies"]["vendor"] = ["unfamiliar"]
        manifest.write_text(yaml.safe_dump(data), encoding="utf-8")
        agent = base / ".apm/agents/checkout-engineer.agent.md"
        agent.write_text("---\nname: checkout-engineer\nmodel: unusual\n---\n\nOld instructions.\n", encoding="utf-8")
        current = self.store.get(first["id"])
        saved = self.store.save(first["id"], {
            "revision": current["revision"], "title": "Checkout specialist", "instruction": "Review refunds.",
            "componentIds": [self.catalog["brainstorming"]["id"]],
        })
        updated = yaml.safe_load(manifest.read_text())
        self.assertEqual(updated["x-unfamiliar"], {"features": ["editing", {"size": 7}]})
        self.assertEqual(updated["x-preset-labels"]["project"], "Checkout")
        self.assertEqual(updated["dependencies"]["vendor"], ["unfamiliar"])
        self.assertEqual(updated["dependencies"]["apm"][0]["x-vendor"], "keep me")
        self.assertEqual(updated["dependencies"]["apm"][0]["x-published"], date(2026, 11, 14))
        json.dumps(saved)
        self.assertIn("model: unusual", agent.read_text(encoding="utf-8"))
        self.assertEqual((saved["title"], saved["instruction"]), ("Checkout specialist", "Review refunds."))

    def test_preset_icon_is_saved_in_preset_labels_and_listed(self):
        package = self.create()
        self.assertEqual(package["icon"], "")
        manifest = self.root / "packages/checkout-engineer/apm.yml"
        saved = self.store.save(package["id"], {"revision": package["revision"], "icon": "rocket"})
        self.assertEqual(saved["icon"], "rocket")
        self.assertEqual(yaml.safe_load(manifest.read_text())["x-preset-labels"]["icon"], "rocket")
        self.assertEqual(self.store.list_packages()[0]["icon"], "rocket")
        cleared = self.store.save(package["id"], {"revision": saved["revision"], "icon": ""})
        self.assertEqual(cleared["icon"], "")
        self.assertNotIn("icon", yaml.safe_load(manifest.read_text())["x-preset-labels"])
        for value in ("<svg/>", "Rocket", 7):
            with self.assertRaises(StoreError):
                self.store.save(package["id"], {"revision": cleared["revision"], "icon": value})

    def test_source_url_names_the_same_case_sensitive_path_as_the_source(self):
        item = next(row for row in self.create(names=["react-start"])["components"] if row["kind"] == "skill")
        self.assertEqual(item["source"], {
            "repositoryUrl": "https://github.com/TanStack/router",
            "path": "packages/react-start/skills/react-start/SKILL.md",
            "ref": "main",
        })
        self.assertEqual(item["sourceUrl"], "https://github.com/TanStack/router/blob/main/packages/react-start/skills/react-start/SKILL.md")

    def test_source_without_a_ref_links_the_default_branch(self):
        from asm_app.store import _source_url
        source = {"repositoryUrl": "https://github.com/obra/superpowers", "path": "skills/brainstorming/SKILL.md", "ref": ""}
        self.assertEqual(_source_url(source), "https://github.com/obra/superpowers/blob/HEAD/skills/brainstorming/SKILL.md")

    def test_stale_revision_includes_native_changes_outside_yaml(self):
        original = self.create(names=["web-session-start"])
        hook = self.root / "packages/checkout-engineer/.apm/hooks/web-session-start.json"
        hook.write_text('{"hooks": {"SessionStart": []}}', encoding="utf-8")
        with self.assertRaises(StoreError) as error:
            self.store.save(original["id"], {"revision": original["revision"], "description": "stale"})
        self.assertEqual(error.exception.status, 409)
        self.assertEqual(self.store.get(original["id"])["description"], "Build checkout.")

    def test_create_collision_preserves_existing_package(self):
        original = self.create()
        with self.assertRaises(StoreError) as error:
            self.create("Checkout engineer!", description="Overwrite the package.")
        self.assertEqual(error.exception.status, 409)
        self.assertEqual(self.store.get(original["id"]), original)

    def test_component_removal_changes_native_dependency_lists_and_files(self):
        first = self.create(names=["brainstorming", "playwright", "web-session-start", "frontend-design"])
        updated = self.store.save(first["id"], {"revision": first["revision"], "componentIds": []})
        base = self.root / "packages" / first["id"]
        manifest = yaml.safe_load((base / "apm.yml").read_text())
        self.assertEqual(manifest["dependencies"], {"apm": [], "mcp": []})
        self.assertFalse((base / ".apm/hooks/web-session-start.json").exists())
        self.assertEqual([row["id"] for row in updated["components"]], ["instruction"])

    def test_nested_stack_reference_is_live_and_cycles_are_rejected(self):
        alpha = self.create("Alpha", kind="stack")
        beta = self.create("Beta", kind="stack", componentIds=["package:alpha"])
        self.assertEqual(beta["components"][-1]["configuration"], {"packageId": "alpha"})
        rows = {row["id"]: row for row in self.store.catalog()["items"]}
        self.assertEqual(rows["package:alpha"]["type"], "stack")
        self.assertEqual(rows["package:alpha"]["packageId"], "alpha")
        native = yaml.safe_load((self.root / "packages/beta/apm.yml").read_text())
        self.assertEqual(native["dependencies"]["apm"], ["../alpha"])
        with self.assertRaisesRegex(StoreError, "cycle"):
            self.store.save("alpha", {"revision": alpha["revision"], "componentIds": ["package:beta"]})
        self.assertEqual(self.store.get("alpha")["revision"], alpha["revision"])
        with ZipFile(io.BytesIO(self.store.export("beta"))) as archive:
            self.assertIn("alpha/apm.yml", archive.namelist())
            self.assertIn("beta/apm.yml", archive.namelist())

    def test_component_comments_are_local_and_survive_reopening(self):
        package = self.create()
        comment = self.store.add_comment(package["id"], "instruction", {"body": "Confirmed on test data.", "author": "Casey"})
        self.assertEqual(Store(self.root).comments(package["id"], "instruction"), [comment])
        self.assertEqual(comment["body"], "Confirmed on test data.")
        self.assertEqual(self.store.get(package["id"])["revision"], package["revision"])

    def test_rejects_unsafe_ids_and_catalog_file_paths(self):
        with self.assertRaises(StoreError) as error:
            self.store.get("../catalog")
        self.assertEqual(error.exception.status, 400)
        with self.assertRaises(StoreError):
            self.create("COM1")
        manifest = self.root / "catalog/components.json"
        data = json.loads(manifest.read_text(encoding="utf-8"))
        hook = next(row for row in data["items"] if row["name"] == "web-session-start")
        hook["apm"]["path"] = ".apm/hooks/../../../escape.json"
        manifest.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(StoreError):
            self.create(names=["web-session-start"])
        self.assertFalse((self.root / "packages/checkout-engineer").exists())

    def test_lock_refuses_external_local_dependency_without_running_apm(self):
        self.create()
        manifest = self.root / "packages/checkout-engineer/apm.yml"
        data = yaml.safe_load(manifest.read_text())
        data["dependencies"]["apm"] = [{"path": "../../external"}]
        manifest.write_text(yaml.safe_dump(data), encoding="utf-8")
        with patch("asm_app.store.subprocess.run") as run:
            with self.assertRaisesRegex(StoreError, "Local dependency"):
                self.store.lock("checkout-engineer")
        run.assert_not_called()

    def test_lock_reports_missing_cli_without_creating_output(self):
        package = self.create()
        with patch("asm_app.store.Store._apm_command", return_value=[]):
            self.assertEqual(self.store.lock(package["id"]), {
                "ok": False, "output": "Microsoft APM CLI was not found on this machine."})
        self.assertEqual(self.store.get(package["id"])["revision"], package["revision"])

    def test_selecting_native_manifest_hook_keeps_its_original_mapping(self):
        self.create()
        manifest = self.root / "packages/checkout-engineer/apm.yml"
        data = yaml.safe_load(manifest.read_text())
        data["hooks"] = {"Stop": [{"command": "echo detected"}]}
        manifest.write_text(yaml.safe_dump(data), encoding="utf-8")
        package = self.store.get("checkout-engineer")
        hook = next(row for row in package["components"] if row["kind"] == "hook")
        saved = self.store.save(package["id"], {
            "revision": package["revision"], "componentIds": [hook["id"]],
        })
        self.assertEqual(yaml.safe_load(manifest.read_text())["hooks"], {"Stop": [{"command": "echo detected"}]})
        self.store.save(package["id"], {"revision": saved["revision"], "componentIds": []})
        self.assertNotIn("hooks", yaml.safe_load(manifest.read_text()))

    def test_paperclip_labels_are_read_from_preset_labels(self):
        store = Store(ROOT)
        self.assertEqual(store.get("cao")["paperclip"], {"role": "general", "canCreateAgents": False})
        self.assertEqual(store.get("web-app-engineer")["paperclip"], {"role": None, "canCreateAgents": False})

    def test_save_keeps_the_paperclip_labels(self):
        package = self.create()
        manifest = self.root / "packages/checkout-engineer/apm.yml"
        data = yaml.safe_load(manifest.read_text())
        data["x-preset-labels"]["paperclip"] = {"role": "researcher", "canCreateAgents": True}
        manifest.write_text(yaml.safe_dump(data), encoding="utf-8")
        package = self.store.get(package["id"])
        self.assertEqual(package["paperclip"], {"role": "researcher", "canCreateAgents": True})
        saved = self.store.save(package["id"], {"revision": package["revision"], "title": "Checkout lead"})
        self.assertEqual(saved["paperclip"], {"role": "researcher", "canCreateAgents": True})
        self.assertEqual(yaml.safe_load(manifest.read_text())["x-preset-labels"]["paperclip"],
                         {"role": "researcher", "canCreateAgents": True})

    def test_a_component_stored_in_the_package_names_its_file(self):
        package = self.create(names=["brainstorming", "web-session-start"])
        rows = {row["name"]: row for row in package["components"]}
        self.assertEqual(rows["web-session-start"]["file"], ".apm/hooks/web-session-start.json")
        self.assertNotIn("file", rows["brainstorming"])

    def test_migrated_fixtures_keep_instructions_and_component_types(self):
        store = Store(ROOT)
        expected = {"web-app-engineer": {"instruction": 1, "skill": 31, "mcp": 1, "hook": 1, "plugin": 1},
                    "cao": {"instruction": 1, "skill": 4, "hook": 1, "plugin": 1}}
        for package_id, counts in expected.items():
            with self.subTest(package_id=package_id):
                package = store.get(package_id)
                self.assertTrue(package["instruction"])
                actual = {}
                for item in package["components"]:
                    actual[item["kind"]] = actual.get(item["kind"], 0) + 1
                self.assertEqual(actual, counts)


if __name__ == "__main__":
    unittest.main()
