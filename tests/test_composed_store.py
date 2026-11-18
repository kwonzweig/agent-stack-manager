"""Exercise a private package overlay against an independent canonical checkout."""

import io
import json
from pathlib import Path
import shutil
import tempfile
from threading import Thread
import unittest
from unittest.mock import Mock, patch
from urllib.request import urlopen
from zipfile import ZipFile

import yaml

from asm_app.paperclip import convert
from asm_app.server import create_server
from asm_app.store import Store, StoreError


ROOT = Path(__file__).resolve().parents[1]


class ComposedStoreTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        workspace = Path(temporary.name)
        self.base = workspace / "canonical"
        self.private = workspace / "private"
        shutil.copytree(ROOT / "catalog", self.base / "catalog")
        shutil.copyfile(ROOT / "pyproject.toml", self.base / "pyproject.toml")
        self.shared = self.package(self.base, "shared", {"title": "Shared"})
        self.stack = self.package(self.base, "common", {"title": "Common", "kind": "stack"})
        self.personal = self.package(self.private, "personal-kit", {"title": "Personal Kit"}, ["../common"])

    def package(self, root, name, labels, dependencies=()):
        path = root / "packages" / name / "apm.yml"
        path.parent.mkdir(parents=True)
        path.write_text(yaml.safe_dump({"name": name, "version": "1.0",
                                        "dependencies": {"apm": list(dependencies)},
                                        "x-preset-labels": labels}), encoding="utf-8")
        return path

    def test_packages_and_catalog_are_composed_by_live_read_through(self):
        store = Store(self.private, base_root=self.base)
        self.assertEqual([row["id"] for row in store.list_packages()], ["common", "personal-kit", "shared"])
        self.assertTrue(any(row["type"] == "component" for row in store.catalog()["items"]))
        self.assertTrue(store.consumers()["consumers"])
        self.assertFalse((self.private / "packages" / "shared").exists())
        old = store.get("shared")
        model = yaml.safe_load(self.shared.read_bytes())
        model["description"] = "Updated in the canonical repo."
        self.shared.write_text(yaml.safe_dump(model), encoding="utf-8")
        self.assertEqual(store.get("shared")["description"], "Updated in the canonical repo.")
        with self.assertRaisesRegex(StoreError, "changed"):
            store.save("shared", {"revision": old["revision"], "title": "Stale title"})

    def test_saves_copy_only_the_edited_package_and_write_exports_privately(self):
        skill = self.shared.parent / ".apm/skills/example/SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("---\nname: example\n---\nExample skill.\n", encoding="utf-8")
        before = self.shared.read_bytes()
        store = Store(self.private, base_root=self.base)
        initial = store.get("shared")
        store.save("shared", {"revision": initial["revision"], "title": "Private title"})
        self.assertEqual(self.shared.read_bytes(), before)
        self.assertFalse((self.base / "exports").exists())
        self.assertTrue((self.private / "exports/paperclip/shared").is_dir())
        self.assertFalse((self.private / "packages/common").exists())
        current = Store(self.private, base_root=self.base).get("shared")
        self.assertEqual(current["title"], "Private title")
        self.assertIn(".apm/skills/example/SKILL.md", [row["path"] for row in current["files"]])
        with self.assertRaisesRegex(StoreError, "already exists"):
            store.create({"title": "Common"})

    def test_exports_expand_a_base_stack_inside_a_private_preset(self):
        store = Store(self.private, base_root=self.base)
        with ZipFile(io.BytesIO(store.export("personal-kit"))) as archive:
            self.assertEqual(set(archive.namelist()), {"personal-kit/apm.yml", "common/apm.yml"})
        report = convert(store.get("personal-kit"), root=store.root, store=store)
        stack = next(item for item in report["items"] if item["kind"] == "package")
        self.assertEqual(stack["conversion"]["status"], "converted")
        self.assertEqual(stack["target"], {"packageId": "common"})
        shared = convert(store.get("shared"), root=store.root, store=store)
        self.assertIn("/exports/paperclip/shared", shared["folder"]["url"])

    def test_lock_resolves_shared_siblings_from_private_scratch(self):
        store = Store(self.private, base_root=self.base)

        def run(command, *, cwd, **kwargs):
            self.assertTrue(cwd.is_relative_to(self.private))
            self.assertTrue((cwd.parent / "common/apm.yml").is_file())
            (cwd / "apm.lock.yaml").write_bytes(b"test lock")
            return type("Result", (), {"returncode": 0, "stdout": "locked"})()

        with patch.object(store, "_apm_command", return_value=["apm.exe"]), patch("asm_app.store.subprocess.run", side_effect=run):
            self.assertTrue(store.lock("personal-kit")["ok"])
        self.assertFalse((self.base / "packages/common/apm.lock.yaml").exists())
        self.assertFalse((self.private / "packages/common").exists())
        private_lock = self.private / "packages/personal-kit/apm.lock.yaml"
        self.assertEqual(private_lock.read_bytes(), b"test lock")

    def test_api_catalog_enriches_only_the_canonical_components(self):
        catalog = self.private / "catalog"
        catalog.mkdir()
        (catalog / "components.json").write_text('{"items":[{"id":"private-catalog-item"}]}', encoding="utf-8")
        with create_server(self.private, port=0, base_root=self.base) as server:
            server._sources = Mock()
            server._sources.read.return_value = {"items": {}, "errors": []}
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                url = f"http://127.0.0.1:{server.server_port}/api"
                with urlopen(f"{url}/presets", timeout=3) as response:
                    ids = {row["id"] for row in json.load(response)["presets"]}
                    self.assertEqual(ids, {"common", "personal-kit", "shared"})
                with urlopen(f"{url}/catalog/sources", timeout=3) as response:
                    self.assertEqual(json.load(response), {"items": {}, "errors": []})
                rows = server._sources.read.call_args.args[0]
                self.assertTrue(rows)
                self.assertTrue(all(row["type"] == "component" and row["id"] != "private-catalog-item" for row in rows))
            finally:
                server.shutdown()
                thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
