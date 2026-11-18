import json
import tempfile
import unittest
from pathlib import Path

import yaml

from asm_app.store import Store
from asm_app.components import identify


class ComponentIdentityTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        (self.root / "catalog").mkdir()
        self.ref = {"git": "https://github.com/Example/Skills.git", "ref": "main", "path": "skills/review"}
        catalog = {"items": [{"id": "old-catalog-id", "name": "Review", "kind": "skill",
                              "apm": {"section": "apm", "value": self.ref}}]}
        (self.root / "catalog/components.json").write_text(json.dumps(catalog))
        self.folder = self.root / "packages/a-preset"
        self.folder.mkdir(parents=True)
        self.item = {"id": "old-observation-id", "kind": "skill", "name": "Review", "description": "Observed purpose.",
                     "source": "https://github.com/example/skills", "sourcePath": "skills/review/SKILL.md",
                     "sourceRef": "main", "apps": {"codex": {"installed": True, "enabled": False, "selected": False,
                                                            "locator": "~/.agents/skills/review/SKILL.md"}}}
        self.write()
        self.store = Store(self.root)

    def write(self):
        (self.folder / "apm.yml").write_text(yaml.safe_dump({
            "name": "a-preset", "dependencies": {"apm": [self.ref]},
            "x-app-inventory": {"items": [self.item]},
        }))

    def test_catalog_native_dependency_and_observation_resolve_to_one_entity(self):
        package = self.store.get("a-preset")
        catalog = next(row for row in self.store.catalog()["items"] if row["id"] == "old-catalog-id")
        native = next(row for row in package["components"] if row["kind"] == "skill")
        observed = package["appInventory"][0]
        self.assertEqual(catalog["canonicalId"], native["canonicalId"])
        self.assertEqual(catalog["canonicalId"], observed["canonicalId"])
        detail = self.store.component(catalog["canonicalId"])
        self.assertEqual(len(detail["memberships"]), 2)
        self.assertEqual(detail["memberships"][1]["inventoryId"], "old-observation-id")
        self.assertIs(detail["memberships"][1]["apps"]["codex"]["enabled"], False)
        self.assertTrue(detail["remoteApproved"])
        self.assertEqual(detail["source"]["path"], "skills/review/SKILL.md")
        self.assertEqual(self.store.component("old-catalog-id")["canonicalId"], detail["canonicalId"])

    def test_unknown_refs_private_sources_and_same_named_local_items_stay_distinct(self):
        self.item.pop("sourceRef")
        self.write()
        package = self.store.get("a-preset")
        native = next(row for row in package["components"] if row["kind"] == "skill")
        observed = package["appInventory"][0]
        self.assertNotEqual(native["canonicalId"], observed["canonicalId"])
        self.assertFalse(self.store.component(observed["canonicalId"])["remoteApproved"])
        self.item.pop("source")
        self.write()
        local = self.store.get("a-preset")["appInventory"][0]
        self.assertFalse(self.store.component(local["canonicalId"])["remoteApproved"])
        self.assertEqual(self.store.component(local["canonicalId"])["details"]["availability"], "metadata-only")

    def test_plugin_host_is_part_of_identity_and_old_inventory_choices_are_preserved(self):
        self.item.update(kind="codex-plugin", sourcePath="plugins/review", sourceRef="main")
        self.write()
        old = (self.folder / "apm.yml").read_bytes()
        first = self.store.get("a-preset")["appInventory"][0]
        self.item["kind"] = "claude-code-plugin"
        self.write()
        second = self.store.get("a-preset")["appInventory"][0]
        self.assertNotEqual(first["canonicalId"], second["canonicalId"])
        self.assertEqual(first["pluginHost"], "codex")
        self.assertEqual(second["pluginHost"], "claude")
        self.item["kind"] = "codex-plugin"
        self.write()
        self.store.catalog()
        self.assertEqual((self.folder / "apm.yml").read_bytes(), old)

    def test_observed_component_can_be_reused_without_losing_legacy_id_or_choices(self):
        self.item.pop("source")
        self.write()
        observed = self.store.get("a-preset")["appInventory"][0]
        saved = self.store.create({"title": "Another environment", "componentIds": [observed["canonicalId"]]})
        self.assertEqual(saved["appInventory"][0]["id"], self.item["id"])
        self.assertIs(saved["appInventory"][0]["apps"]["codex"]["selected"], False)
        self.assertEqual(saved["appInventory"][0]["canonicalId"], observed["canonicalId"])
        detail = self.store.component(observed["canonicalId"])
        self.assertEqual({membership["presetId"] for membership in detail["memberships"]}, {"a-preset", "another-environment"})

    def test_local_aliases_follow_provenance_and_unproven_ids_stay_scoped(self):
        local = {"id": "legacy-id", "name": "Same name", "kind": "skill", "apps": {}}
        self.assertNotEqual(identify(local, "first")["canonicalId"], identify(local, "second")["canonicalId"])
        local["apps"] = {"codex": {"locator": "~/.agents/skills/review/SKILL.md"}}
        renamed = {**local, "id": "different-import-id"}
        self.assertEqual(identify(local, "first")["canonicalId"], identify(renamed, "second")["canonicalId"])
        elsewhere = {**local, "apps": {"codex": {"locator": "~/.agents/skills/other/SKILL.md"}}}
        self.assertNotEqual(identify(local, "first")["canonicalId"], identify(elsewhere, "first")["canonicalId"])
        second_app = {**local, "apps": {"codex": {"locator": "~/.agents/skills/review/SKILL.md", "targetId": "first-alias"},
                                       "claude": {"locator": "~/.agents/skills/review/SKILL.md", "targetId": "second-alias"}}}
        self.assertEqual(identify(local, "first")["canonicalId"], identify(second_app, "first")["canonicalId"])

    def test_missing_monorepo_paths_do_not_become_root_skills(self):
        first = {"id": "one", "name": "One", "kind": "skill", "source": "https://github.com/example/monorepo"}
        second = {**first, "id": "two", "name": "Two"}
        self.assertNotEqual(identify(first, "preset")["canonicalId"], identify(second, "preset")["canonicalId"])
        self.assertNotIn("path", identify(first, "preset")["source"])
        explicit_root = {**first, "apm": {"git": first["source"], "ref": "main"}}
        self.assertEqual(identify(explicit_root, "preset")["source"]["path"], "SKILL.md")
        child = {**explicit_root, "pluginHost": "codex"}
        self.assertEqual(identify(child, "preset")["canonicalId"], identify(explicit_root, "preset")["canonicalId"])

    def test_private_origin_prevents_remote_enrichment_of_matching_catalog_source(self):
        self.item["sourceAccess"] = "private"
        self.write()
        identity = self.store.get("a-preset")["appInventory"][0]["canonicalId"]
        self.assertFalse(self.store.component(identity)["remoteApproved"])
        self.assertFalse(any(row["canonicalId"] == identity for row in self.store.source_components()))

    def test_tree_and_blob_receipts_normalize_to_the_same_repository_ref_and_path(self):
        native = {"id": "native", "kind": "skill", "source": {"repositoryUrl": "https://github.com/example/tools",
                  "ref": "main", "path": "skills/review/SKILL.md"}}
        receipt = {"id": "receipt", "kind": "skill",
                   "source": "https://github.com/example/tools/tree/main/skills/review",
                   "sourceRef": "main", "sourcePath": "skills/review/SKILL.md"}
        blob = {**receipt, "source": "https://github.com/example/tools/blob/main/skills/review/SKILL.md"}
        self.assertEqual(identify(native, "a")["canonicalId"], identify(receipt, "b")["canonicalId"])
        self.assertEqual(identify(native, "a")["canonicalId"], identify(blob, "b")["canonicalId"])
        self.assertEqual(identify(receipt, "b")["sourceUrl"],
                         "https://github.com/example/tools/blob/main/skills/review/SKILL.md")

    def test_reuse_handles_a_legacy_id_collision_without_dropping_the_requested_component(self):
        self.item.pop("source")
        self.write()
        source = self.store.get("a-preset")["appInventory"][0]
        destination = self.root / "packages/destination"
        destination.mkdir()
        conflict = {**self.item, "apps": {"codex": {"installed": True, "enabled": True, "selected": True,
                                                   "locator": "~/.agents/skills/different/SKILL.md"}}}
        (destination / "apm.yml").write_text(yaml.safe_dump({"name": "destination", "x-app-inventory": {"items": [conflict]}}))
        before = self.store.get("destination")
        saved = self.store.save("destination", {"revision": before["revision"], "componentIds": [source["canonicalId"]]})
        self.assertEqual(len(saved["appInventory"]), 2)
        copied = next(row for row in saved["appInventory"] if row["canonicalId"] == source["canonicalId"])
        self.assertNotEqual(copied["id"], conflict["id"])
        self.assertIs(copied["apps"]["codex"]["selected"], False)
        self.assertEqual(saved, Store(self.root).get("destination"))

    def test_known_native_dependency_without_catalog_record_can_be_reused(self):
        ref = {"git": "https://github.com/example/new-tools", "ref": "stable", "path": "skills/different"}
        (self.folder / "apm.yml").write_text(yaml.safe_dump({"name": "a-preset", "dependencies": {"apm": [ref]}}))
        native = next(row for row in self.store.get("a-preset")["components"] if row["kind"] == "skill")
        detail = self.store.component(native["canonicalId"])
        self.assertTrue(detail["addable"])
        copied = self.store.create({"title": "Native copy", "componentIds": [detail["canonicalId"]]})
        reused = next(row for row in copied["components"] if row["kind"] == "skill")
        self.assertEqual(reused["canonicalId"], native["canonicalId"])
        self.assertEqual(reused["configuration"], ref)

    def test_unlisted_marketplace_plugin_has_host_identity_without_a_source_url(self):
        plugin = {"name": "another-plugin", "marketplace": "configured-marketplace"}
        (self.folder / "apm.yml").write_text(yaml.safe_dump({"name": "a-preset", "dependencies": {"apm": [plugin]}}))
        item = next(row for row in self.store.get("a-preset")["components"] if row["kind"] == "plugin")
        self.assertEqual(item["pluginHost"], "claude")
        detail = self.store.component(item["canonicalId"])
        self.assertTrue(detail["addable"])
        self.assertFalse(detail["remoteApproved"])


if __name__ == "__main__":
    unittest.main()
