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

    def test_an_apm_lockfile_leaves_the_package_and_its_export_unchanged(self):
        # `apm lock` writes apm.lock.yaml beside apm.yml; it records commits and is not part of the preset.
        from asm_app.store import _export_digest
        package = self.create(names=["brainstorming"])
        before = self.store._snapshot(package["id"])
        digest = _export_digest(self.store._bundle(package["id"], before))
        (self.root / "packages/checkout-engineer/apm.lock.yaml").write_text("lockfile_version: '1'\n", encoding="utf-8")
        after = self.store._snapshot(package["id"])
        self.assertEqual(after, before)
        self.assertEqual(self.store.get(package["id"])["revision"], package["revision"])
        self.assertEqual(_export_digest(self.store._bundle(package["id"], after)), digest)

    def test_a_save_without_a_revision_asks_for_one(self):
        package = self.create()
        for payload in ({"description": "x"}, {"revision": None, "description": "x"}, {"revision": 1, "description": "x"}):
            with self.subTest(payload=payload), self.assertRaises(StoreError) as error:
                self.store.save(package["id"], payload)
            self.assertEqual(error.exception.status, 400)
            self.assertIn("revision is required", str(error.exception))
        self.assertEqual(self.store.get(package["id"])["description"], "Build checkout.")

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

    def test_lock_gives_apm_ten_minutes(self):
        # Resolving a preset of 31 skills takes APM minutes, so a one-minute limit stopped it every time.
        import subprocess
        package = self.create()
        with patch("asm_app.store.Store._apm_command", return_value=["apm"]), \
                patch("asm_app.store.subprocess.run", side_effect=subprocess.TimeoutExpired("apm", 600)) as run:
            self.assertEqual(self.store.lock(package["id"]), {
                "ok": False, "output": "APM lock timed out after 600 seconds."})
        self.assertEqual(run.call_args.kwargs["timeout"], 600)

    def test_presets_open_and_save_while_apm_lock_runs(self):
        # APM can take minutes; the dashboard must not wait for it to read or save a preset.
        import threading
        package = self.create()
        started, release = threading.Event(), threading.Event()

        def slow_run(*args, **kwargs):
            started.set()
            release.wait(10)
            return type("Result", (), {"returncode": 0, "stdout": "locked"})()

        with patch("asm_app.store.Store._apm_command", return_value=["apm"]), \
                patch("asm_app.store.subprocess.run", side_effect=slow_run):
            locking = threading.Thread(target=self.store.lock, args=(package["id"],))
            locking.start()
            self.addCleanup(locking.join)
            self.addCleanup(release.set)
            self.assertTrue(started.wait(5))
            done = []
            reader = threading.Thread(target=lambda: done.append(self.store.save(package["id"], {
                "revision": self.store.get(package["id"])["revision"], "description": "Saved during lock."})))
            reader.start()
            reader.join(2)
            self.assertEqual([row["description"] for row in done], ["Saved during lock."])
            release.set()

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
        self.assertEqual(store.get("cao")["paperclip"], {"role": "ceo", "canCreateAgents": False})
        self.assertEqual(store.get("web-app-engineer")["paperclip"], {"role": None, "canCreateAgents": False})
        self.assertEqual(store.get("ar")["paperclip"], {"role": "general", "canCreateAgents": True})

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

    def use_consumers(self):
        (self.root / "catalog/consumers.json").write_bytes((ROOT / "catalog/consumers.json").read_bytes())

    def test_save_writes_the_paperclip_fields_from_the_payload(self):
        self.use_consumers()
        package = self.create()
        manifest = self.root / "packages/checkout-engineer/apm.yml"
        saved = self.store.save(package["id"], {"revision": package["revision"],
                                                "paperclip": {"role": "engineer", "canCreateAgents": True}})
        self.assertEqual(saved["paperclip"], {"role": "engineer", "canCreateAgents": True})
        self.assertEqual(yaml.safe_load(manifest.read_text())["x-preset-labels"]["paperclip"],
                         {"role": "engineer", "canCreateAgents": True})
        saved = self.store.save(package["id"], {"revision": saved["revision"],
                                                "paperclip": {"role": "engineer", "canCreateAgents": False}})
        self.assertEqual(yaml.safe_load(manifest.read_text())["x-preset-labels"]["paperclip"], {"role": "engineer"})
        saved = self.store.save(package["id"], {"revision": saved["revision"],
                                                "paperclip": {"role": "", "canCreateAgents": False}})
        self.assertEqual(saved["paperclip"], {"role": None, "canCreateAgents": False})
        self.assertNotIn("paperclip", yaml.safe_load(manifest.read_text())["x-preset-labels"])

    def test_an_unchanged_empty_paperclip_payload_writes_no_block(self):
        self.use_consumers()
        package = self.create()
        manifest = self.root / "packages/checkout-engineer/apm.yml"
        before = manifest.read_bytes()
        self.store.save(package["id"], {"revision": package["revision"],
                                        "paperclip": {"role": None, "canCreateAgents": False}})
        self.assertEqual(manifest.read_bytes(), before)

    def test_save_refuses_a_paperclip_payload_outside_the_role_list(self):
        self.use_consumers()
        package = self.create()
        for value in ({"role": "agent", "canCreateAgents": False}, {"role": "general", "canCreateAgents": "yes"},
                      {"role": 3}, {"role": "general", "adapter": "codex_local"}, ["general"]):
            with self.subTest(value=value):
                # The current revision, so a payload wrongly accepted earlier cannot fail this one with 409.
                revision = self.store.get(package["id"])["revision"]
                with self.assertRaises(StoreError) as caught:
                    self.store.save(package["id"], {"revision": revision, "paperclip": value})
                self.assertEqual(caught.exception.status, 400)
        self.assertEqual(self.store.get(package["id"])["paperclip"], {"role": None, "canCreateAgents": False})

    def test_a_hand_written_role_outside_the_list_does_not_block_other_edits(self):
        self.use_consumers()
        package = self.create()
        manifest = self.root / "packages/checkout-engineer/apm.yml"
        data = yaml.safe_load(manifest.read_text())
        data["x-preset-labels"]["paperclip"] = {"role": "wizard"}
        manifest.write_text(yaml.safe_dump(data), encoding="utf-8")
        package = self.store.get(package["id"])
        saved = self.store.save(package["id"], {"revision": package["revision"], "title": "Checkout lead",
                                                "paperclip": package["paperclip"]})
        self.assertEqual(saved["paperclip"], {"role": "wizard", "canCreateAgents": False})

    def test_a_paperclip_role_needs_the_role_list(self):
        package = self.create()
        with self.assertRaises(StoreError):
            self.store.save(package["id"], {"revision": package["revision"], "paperclip": {"role": "general"}})

    def test_a_component_stored_in_the_package_names_its_file(self):
        package = self.create(names=["brainstorming", "web-session-start"])
        rows = {row["name"]: row for row in package["components"]}
        self.assertEqual(rows["web-session-start"]["file"], ".apm/hooks/web-session-start.json")
        self.assertNotIn("file", rows["brainstorming"])

    def test_a_presets_own_skill_is_named_from_its_skill_md(self):
        package = Store(ROOT).get("ar")
        skill = next(item for item in package["components"]
                     if item.get("file") == ".apm/skills/technology-research/SKILL.md")
        front = yaml.safe_load((ROOT / "packages/ar/.apm/skills/technology-research/SKILL.md")
                               .read_text(encoding="utf-8").split("---")[1])
        self.assertEqual((skill["name"], skill["description"]), ("technology-research", front["description"]))
        from asm_app import paperclip
        row = next(row for row in paperclip.convert(package, root=ROOT)["items"] if row["id"] == skill["id"])
        self.assertEqual(row["name"], "technology-research")

    def test_a_presets_own_skill_without_a_name_takes_its_folder_name(self):
        package = self.create()
        skill_file = self.root / "packages" / package["id"] / ".apm/skills/plain-notes/SKILL.md"
        skill_file.parent.mkdir(parents=True)
        skill_file.write_text("No front matter.\n", encoding="utf-8")
        skill = next(item for item in self.store.get(package["id"])["components"]
                     if item.get("file") == ".apm/skills/plain-notes/SKILL.md")
        self.assertEqual((skill["name"], skill["description"]), ("plain-notes", ""))

    def write_catalog(self, change):
        manifest = self.root / "catalog/components.json"
        data = json.loads(manifest.read_text(encoding="utf-8"))
        change(data)
        manifest.write_text(json.dumps(data), encoding="utf-8")

    def test_catalog_derives_source_and_link_of_a_git_component(self):
        stored = json.loads((ROOT / "catalog/components.json").read_text(encoding="utf-8"))
        row = next(row for row in stored["items"] if row["name"] == "react-start")
        self.assertNotIn("source", row)
        self.assertNotIn("sourceUrl", row)
        item = self.catalog["react-start"]
        self.assertEqual(item["source"], {
            "repositoryUrl": "https://github.com/TanStack/router",
            "path": "packages/react-start/skills/react-start/SKILL.md",
            "ref": "main",
        })
        self.assertEqual(item["sourceUrl"],
                         "https://github.com/TanStack/router/blob/main/packages/react-start/skills/react-start/SKILL.md")

    def test_catalog_keeps_the_stored_source_of_a_component_without_git(self):
        item = self.catalog["frontend-design"]
        self.assertEqual(item["source"]["repositoryUrl"], "https://github.com/anthropics/claude-plugins-official")
        self.assertTrue(item["sourceUrl"].startswith("https://github.com/anthropics/claude-plugins-official/"))

    def test_catalog_items_carry_their_repositorys_stars(self):
        stored = json.loads((ROOT / "catalog/components.json").read_text(encoding="utf-8"))
        row = next(row for row in stored["repositories"] if row["url"] == "https://github.com/obra/superpowers")
        item = self.catalog["brainstorming"]
        self.assertEqual((item["stars"], item["starsCheckedOn"]), (row["stars"], row["starsCheckedOn"]))
        self.assertNotIn("stars", self.catalog["web-session-start"])

    def test_catalog_refuses_a_repository_without_a_star_count(self):
        bad_rows = ({"stars": None}, {"stars": -1}, {"stars": True}, {"stars": "318k"}, {"stars": 1.5},
                    {"starsCheckedOn": None}, {"starsCheckedOn": "yesterday"}, {"starsCheckedOn": "2026-13-01"})
        for bad in bad_rows:
            with self.subTest(row=bad):
                self.write_catalog(lambda data: data["repositories"][0].update(bad))
                with self.assertRaisesRegex(StoreError, "stars|starsCheckedOn"):
                    self.store.catalog()
                self.setUp()
        self.write_catalog(lambda data: data["repositories"][0].pop("stars"))
        with self.assertRaisesRegex(StoreError, "stars"):
            self.store.catalog()

    def test_catalog_refuses_a_component_whose_repository_has_no_row(self):
        self.write_catalog(lambda data: data.update(repositories=[
            row for row in data["repositories"] if row["url"] != "https://github.com/obra/superpowers"]))
        with self.assertRaisesRegex(StoreError, "https://github.com/obra/superpowers"):
            self.store.catalog()

    def test_catalog_descriptions_are_one_line(self):
        # A card shows the description on one line and an export stub writes it as one YAML value.
        for item in Store(ROOT).catalog()["items"]:
            description = item.get("description") or ""
            with self.subTest(item=item["id"]):
                self.assertEqual(description, " ".join(description.split()))

    def test_committed_presets_hold_their_instruction_and_members(self):
        store = Store(ROOT)
        expected = {"web-app-engineer": {"instruction": 1, "skill": 31, "mcp": 1, "hook": 1, "plugin": 1},
                    "cao": {"instruction": 1, "skill": 4, "hook": 1, "plugin": 1},
                    "ar": {"instruction": 1, "skill": 4}}
        for package_id, counts in expected.items():
            with self.subTest(package_id=package_id):
                package = store.get(package_id)
                self.assertTrue(package["instruction"])
                actual = {}
                for item in package["components"]:
                    actual[item["kind"]] = actual.get(item["kind"], 0) + 1
                self.assertEqual(actual, counts)


class CommittedPackageTests(unittest.TestCase):
    def test_a_save_of_a_committed_package_changes_only_the_edited_line_of_its_apm_yml(self):
        # A save rewrites the whole apm.yml in the store's own layout; a committed file in another
        # layout would show lines in the Git diff that the user never edited.
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        for path in [*ROOT.glob("packages/**/*"), *ROOT.glob("catalog/*")]:
            if path.is_file():
                target = root / path.relative_to(ROOT)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(path.read_bytes())
        store = Store(root)
        for manifest in sorted(ROOT.glob("packages/*/apm.yml")):
            package_id = manifest.parent.name
            with self.subTest(package_id):
                package = store.get(package_id)
                store.save(package_id, {"revision": package["revision"], "title": "Edited title"})
                original = manifest.read_text(encoding="utf-8").splitlines()
                saved = (root / "packages" / package_id / "apm.yml").read_text(encoding="utf-8").splitlines()
                self.assertEqual(len(saved), len(original))
                changed = [line for old, line in zip(original, saved) if old != line]
                self.assertEqual(changed, ["  title: Edited title"])


if __name__ == "__main__":
    unittest.main()
