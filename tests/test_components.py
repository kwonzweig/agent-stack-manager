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

    def test_distinct_git_plugins_do_not_inherit_the_last_catalog_plugin_source(self):
        refs = [{"git": f"https://github.com/example/{name}", "ref": "main", "path": "plugins/tool", "kind": "plugin"}
                for name in ("first", "second")]
        (self.root / "catalog/components.json").write_text(json.dumps({"items": [
            {"id": name, "name": name, "kind": "plugin", "apm": {"section": "apm", "value": ref}}
            for name, ref in zip(("first", "second"), refs)]}))
        (self.folder / "apm.yml").write_text(yaml.safe_dump({"name": "a-preset", "dependencies": {"apm": refs}}))
        rows = [row for row in self.store.get("a-preset")["components"] if row["kind"] == "plugin"]
        self.assertEqual([row["name"] for row in rows], ["first", "second"])
        self.assertEqual([row["source"]["repositoryUrl"] for row in rows], [ref["git"] for ref in refs])
        self.assertEqual(len({row["canonicalId"] for row in rows}), 2)

    def test_modified_native_catalog_file_is_a_local_fork_instead_of_overwriting_shared_detail(self):
        path = ".apm/hooks/start.json"
        original = '{"command":"shared-start"}'
        changed = '{"command":"custom-start"}'
        (self.root / "catalog/components.json").write_text(json.dumps({"items": [
            {"id": "shared-start", "name": "Shared startup", "kind": "hook", "apm": {"path": path, "content": original}}]}))
        target = self.folder / path
        target.parent.mkdir(parents=True)
        target.write_text(changed)
        local = next(row for row in self.store.get("a-preset")["components"] if row.get("file") == path)
        shared = next(row for row in self.store.catalog()["items"] if row["id"] == "shared-start")
        self.assertNotEqual(local["canonicalId"], shared["canonicalId"])
        self.assertEqual(self.store.component(shared["canonicalId"])["details"]["content"], original)
        self.assertEqual(json.loads(self.store.component(local["canonicalId"])["details"]["content"]), json.loads(changed))

    def test_native_source_url_cannot_override_its_proven_coordinates(self):
        row = {"id": "review", "kind": "skill", "sourceUrl": "https://github.com/other/project/blob/old/WRONG.md",
               "source": {"repositoryUrl": "https://github.com/example/tools", "path": "skills/review/SKILL.md", "ref": "stable"}}
        self.assertEqual(identify(row, "preset")["sourceUrl"],
                         "https://github.com/example/tools/blob/stable/skills/review/SKILL.md")

    def test_reuse_carries_complementary_apps_and_unselected_parent_provenance(self):
        other = self.root / "packages/z-other"
        other.mkdir()
        parent = {"id": "tools", "kind": "plugin", "name": "Tools", "description": "", "apps": {
            "claude": {"installed": True, "enabled": True, "selected": True, "scope": "user"}}}
        child = {**self.item, "id": "other-review", "apps": {"claude": {
            "installed": True, "enabled": True, "selected": True, "scope": "plugin", "parentId": "tools"}}}
        (other / "apm.yml").write_text(yaml.safe_dump({"name": "z-other", "x-app-inventory": {"items": [parent, child]}}))
        identity = self.store.get("a-preset")["appInventory"][0]["canonicalId"]
        saved = self.store.create({"title": "Combined", "componentIds": [identity]})
        copied = next(row for row in saved["appInventory"] if row["canonicalId"] == identity)
        self.assertEqual(set(copied["apps"]), {"codex", "claude"})
        self.assertIs(copied["apps"]["codex"]["selected"], False)
        copied_parent = next(row for row in saved["appInventory"] if row["id"] == copied["apps"]["claude"]["parentId"])
        self.assertEqual(copied_parent["name"], "Tools")
        self.assertIs(copied_parent["apps"]["claude"]["selected"], False)
        self.assertTrue(any(origin.get("parentName") == "Tools" for origin in self.store.component(identity)["origins"]
                            if origin.get("presetId") == saved["id"]))

    def test_reuse_reviews_conflicting_choices_but_keeps_distinct_origins_and_existing_destination_choices(self):
        for identifier, locator, selection in (("b-source", "~/.agents/skills/review/SKILL.md", True),
                                               ("c-source", "~/project/review/SKILL.md", True)):
            directory = self.root / "packages" / identifier
            directory.mkdir()
            row = {**self.item, "id": identifier, "apps": {"codex": {
                "installed": True, "enabled": False, "selected": selection, "locator": locator}}}
            (directory / "apm.yml").write_text(yaml.safe_dump({"name": identifier, "x-app-inventory": {"items": [row]}}))
        identity = self.store.get("a-preset")["appInventory"][0]["canonicalId"]
        saved = self.store.create({"title": "Combined", "componentIds": [identity]})
        rows = [row for row in saved["appInventory"] if row["canonicalId"] == identity]
        self.assertEqual(len(rows), 2)
        shared = next(row for row in rows if row["apps"]["codex"]["locator"] == "~/.agents/skills/review/SKILL.md")
        separate = next(row for row in rows if row["apps"]["codex"]["locator"] == "~/project/review/SKILL.md")
        self.assertIsNone(shared["apps"]["codex"]["selected"])
        self.assertIs(separate["apps"]["codex"]["selected"], True)
        chosen = self.store.save(saved["id"], {"revision": saved["revision"], "appInventorySelections": {shared["id"]: {"codex": False}}})
        again = self.store.save(saved["id"], {"revision": chosen["revision"], "componentIds": [identity]})
        self.assertIs(next(row for row in again["appInventory"] if row["id"] == shared["id"])["apps"]["codex"]["selected"], False)
        self.assertEqual(len(again["appInventory"]), 2)

    def test_reuse_reviews_new_app_conflicts_without_resetting_an_existing_app_choice(self):
        identity = self.store.get("a-preset")["appInventory"][0]["canonicalId"]
        saved = self.store.create({"title": "Destination", "componentIds": [identity]})
        saved = self.store.save(saved["id"], {"revision": saved["revision"],
                                            "appInventorySelections": {self.item["id"]: {"codex": True}}})
        for name, selected in (("b-source", False), ("c-source", True)):
            directory = self.root / "packages" / name
            directory.mkdir()
            row = {**self.item, "id": name, "apps": {"claude": {
                "installed": True, "enabled": True, "selected": selected, "locator": "~/.agents/skills/review/SKILL.md"}}}
            (directory / "apm.yml").write_text(yaml.safe_dump({"name": name, "x-app-inventory": {"items": [row]}}))
        saved = self.store.save(saved["id"], {"revision": saved["revision"], "componentIds": [identity]})
        self.assertEqual(len(saved["appInventory"]), 1)
        self.assertIs(saved["appInventory"][0]["apps"]["codex"]["selected"], True)
        self.assertIsNone(saved["appInventory"][0]["apps"]["claude"]["selected"])

    def test_github_http_aliases_cannot_bypass_a_private_repository_declaration(self):
        self.item.update(source="http://github.com/example/skills.git", sourceAccess="private")
        self.write()
        native = next(row for row in self.store.get("a-preset")["components"] if row["kind"] == "skill")
        self.assertFalse(self.store.component(native["canonicalId"])["remoteApproved"])
        self.assertEqual(self.store.source_components(), [])

    def test_native_ssh_and_https_github_references_match_the_catalog_entity(self):
        ref = {**self.ref, "git": "git@github.com:example/skills.git"}
        (self.folder / "apm.yml").write_text(yaml.safe_dump({"name": "a-preset", "dependencies": {"apm": [ref]}}))
        native = next(row for row in self.store.get("a-preset")["components"] if row["kind"] == "skill")
        shared = self.store.component("old-catalog-id")
        self.assertEqual(native["canonicalId"], shared["canonicalId"])
        self.assertEqual(native["sourceUrl"], "https://github.com/example/skills/blob/main/skills/review/SKILL.md")

    def test_container_cycles_fail_without_creating_a_destination(self):
        self.item["apps"]["codex"]["parentId"] = "old-observation-id"
        self.write()
        identity = self.store.get("a-preset")["appInventory"][0]["canonicalId"]
        with self.assertRaisesRegex(ValueError, "cycle"):
            self.store.create({"title": "Cycle copy", "componentIds": [identity]})
        self.assertFalse((self.root / "packages/cycle-copy").exists())

    def test_dangling_parent_provenance_cannot_bind_to_an_unrelated_destination_item(self):
        self.item["apps"]["codex"]["parentId"] = "missing-parent"
        self.write()
        directory = self.root / "packages/destination"
        directory.mkdir()
        unrelated = {"id": "missing-parent", "name": "Unrelated container", "kind": "plugin", "description": "",
                     "apps": {"codex": {"installed": True, "enabled": True, "selected": True}}}
        (directory / "apm.yml").write_text(yaml.safe_dump({"name": "destination", "x-app-inventory": {"items": [unrelated]}}))
        identity = self.store.get("a-preset")["appInventory"][0]["canonicalId"]
        before = self.store.get("destination")
        saved = self.store.save("destination", {"revision": before["revision"], "componentIds": [identity]})
        copied = next(row for row in saved["appInventory"] if row["canonicalId"] == identity)
        self.assertNotIn("parentId", copied["apps"]["codex"])
        self.assertEqual(copied["apps"]["codex"]["provenance"]["parentId"], "missing-parent")
        self.assertFalse(any(origin.get("parentName") for origin in self.store.component(identity)["origins"]
                             if origin.get("presetId") == "destination"))

    def test_catalog_alias_and_canonical_add_preserve_the_same_native_reference_and_app_choices(self):
        self.item["apps"]["codex"]["selected"] = True
        self.write()
        identity = self.store.component("old-catalog-id")["canonicalId"]
        packages = [self.store.create({"title": title, "componentIds": [selected]})
                    for title, selected in (("Alias route", "old-catalog-id"), ("Canonical route", identity))]
        for package in packages:
            self.assertEqual(len(package.get("appInventory", [])), 1)
            row = package["appInventory"][0]
            self.assertEqual(row["canonicalId"], identity)
            self.assertIs(row["apps"]["codex"]["selected"], True)
            native = next(row for row in package["components"] if row["kind"] == "skill")
            self.assertEqual(native["canonicalId"], identity)
            self.assertTrue(native["managedByInventory"])


if __name__ == "__main__":
    unittest.main()
