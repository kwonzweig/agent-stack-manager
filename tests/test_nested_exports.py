"""Export the same saved stack graph through the preview, downloads and local folder."""

import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen
from zipfile import ZipFile

import yaml

from asm_app.server import create_server


def observed(identifier, name, kind, apps, **fields):
    return {"id": identifier, "name": name, "kind": kind, "description": "", "apps": apps, **fields}


def selection(selected):
    return {"selected": selected, "installed": True, "enabled": True}


class NestedExportTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "pyproject.toml").write_text(
            '[project.urls]\nRepository = "https://github.com/example/fixtures"\n', encoding="utf-8")
        remote = {"git": "https://github.com/example/tools", "ref": "main", "path": "skills/review"}
        self.package("common", "stack", [remote], [
            observed("shared", "Review skill", "skill", {"codex": selection(True), "claude": selection(False)},
                     apm=remote, skillRepository={"owner": "example", "repo": "tools", "branch": "main", "directory": "skills/review"}),
            observed("stop", "Observed stop hook", "hook", {"claude": selection(True)}),
        ], hooks=[{"name": "Native stop hook"}])
        for side in ("alpha", "bravo"):
            self.package(side, "stack", ["../common"], [
                observed("local", f"{side} prompt", "prompt", {"codex": selection(None)}),
            ], files={".apm/skills/local/SKILL.md": "---\nname: Same name\n---\nLocal skill.\n"})
        self.package("carrier", "preset", ["../alpha", "../bravo"],
                     files={".apm/agents/carrier.agent.md": "Inspect the deployment.\n"})

        self.server = create_server(self.root, port=0)
        worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        worker.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def package(self, identifier, kind, members, inventory=(), hooks=(), files=None):
        name = self.root / "packages" / identifier
        manifest = {"name": identifier, "x-preset-labels": {"kind": kind},
                    "dependencies": {"apm": members, "hooks": list(hooks)}}
        if inventory:
            manifest["x-app-inventory"] = {"items": list(inventory)}
        for path, content in {"apm.yml": yaml.safe_dump(manifest), **(files or {})}.items():
            target = name / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

    def get(self, preset, suffix="", status=200, data=None):
        url = f"http://127.0.0.1:{self.server.server_port}/api/presets/{preset}{suffix}"
        request = Request(url) if data is None else Request(
            url, json.dumps(data).encode(), {"Content-Type": "application/json"}, method="PATCH")
        try:
            with urlopen(request, timeout=5) as response:
                self.assertEqual(response.status, status)
                return response.read()
        except HTTPError as error:
            self.assertEqual(error.code, status, error.read().decode())

    def choices(self, preset="carrier"):
        return {row["id"]: row for row in json.loads(self.get(preset, "/exports"))["targets"]}

    def test_shared_stack_observations_appear_once_in_both_reports_and_in_the_review(self):
        for preset in ("carrier", "alpha"):
            with self.subTest(preset=preset):
                choices = self.choices(preset)
                switch = choices["ccswitch"]
                self.assertTrue(switch["available"])
                report = json.loads(self.get(preset, switch["download"]))
                self.assertEqual(switch["preview"]["items"], report["items"] + report["unassignedItems"])
                expected = {(name, app, state) for name, app, state in (
                    ("Review skill", "codex", "registration-only"), ("Review skill", "claude", "excluded"),
                    ("Observed stop hook", "claude", "unsupported"), ("alpha prompt", "codex", "manual"))}
                if preset == "carrier":
                    expected.add(("bravo prompt", "codex", "manual"))
                observed_rows = [(row["name"], row["app"], row["status"]) for row in report["items"]]
                self.assertCountEqual(observed_rows, expected)
                self.assertEqual(len({(row["id"], row["app"]) for row in report["items"]}), len(observed_rows))
                self.assertEqual([row["name"] for row in report["unassignedItems"] if row["status"] == "unsupported"],
                                 ["Native stop hook"])
                self.assertEqual(len(report["skillRepositories"]), 1)
                self.assertEqual(parse_qs(urlsplit(report["skillRepositories"][0]["url"]).query),
                                 {"resource": ["skill"], "repo": ["example/tools"], "branch": ["main"],
                                  "directory": ["skills/review"]})
                paperclip = choices["paperclip"]
                self.assertEqual(paperclip["available"], preset == "carrier")
                rows = [row for row in paperclip["preview"]["items"] if row.get("app")]
                self.assertCountEqual([(row["name"], row["app"]) for row in rows],
                                      [(name, app) for name, app, _ in expected])
                self.assertTrue(all(row["conversion"]["status"] == "unconverted" and row["target"] is None for row in rows))
                for row in rows:
                    self.assertIn("inventory state", row["conversion"]["reason"])
                    owner = row["name"].split()[0] if "prompt" in row["name"] else "common"
                    self.assertEqual(row.get("originPackage"), {"id": owner, "title": owner} if owner != preset else None)

    def test_stack_preview_explains_missing_and_cyclic_members(self):
        self.package("loop", "stack", ["../missing", "../loop"])
        expectations = ("Local stack missing could not be read.", "Stack dependency cycle at loop.")
        for target in self.choices("loop").values():
            self.assertEqual(target["available"], target["id"] == "ccswitch")
            rows = target["preview"]["items"]
            self.assertCountEqual([row.get("conversion", row)["reason"] for row in rows], expectations)

    def test_nested_cc_switch_parent_reference_uses_the_exported_parent_id_even_after_collision(self):
        self.package("nested-parent", "stack", [], [
            observed("child", "Nested child", "skill", {"codex": {**selection(True), "parentId": "tools", "scope": "plugin"}}),
            observed("tools", "Nested parent", "plugin", {"codex": selection(False)}),
            observed("unresolved", "Unresolved child", "skill", {"codex": {**selection(True), "parentId": "root-only"}}),
        ])
        self.package("with-parent", "preset", ["../nested-parent"], [
            observed("tools", "Root parent", "plugin", {"codex": selection(True)}),
            observed("nested-parent/tools", "Root collision", "plugin", {"codex": selection(True)}),
            observed("root-only", "Unrelated parent", "plugin", {"codex": selection(True)}),
        ])
        switch = self.choices("with-parent")["ccswitch"]
        report = json.loads(self.get("with-parent", switch["download"]))
        rows = {row["name"]: row for row in report["items"]}
        self.assertEqual(rows["Nested child"]["parentId"], rows["Nested parent"]["id"])
        self.assertEqual(rows["Nested parent"]["status"], "excluded")
        self.assertEqual(rows["Root parent"]["id"], "tools")
        self.assertEqual(rows["Root collision"]["id"], "nested-parent/tools")
        self.assertNotIn("parentId", rows["Unresolved child"])
        self.assertEqual(len({row["id"] for row in rows.values()}), len(rows))

    def test_zip_preserves_distinct_local_skills_with_identical_paths_and_shared_remote_once(self):
        paperclip = self.choices()["paperclip"]
        with ZipFile(io.BytesIO(self.get("carrier", paperclip["download"]))) as archive:
            files = {name: archive.read(name) for name in archive.namelist()}
        stubs = [yaml.safe_load(data.decode().split("---", 2)[1])["metadata"]["sources"][0]["path"]
                 for name, data in files.items() if name.startswith("skills/")]
        self.assertCountEqual(stubs, ["packages/alpha/.apm/skills/local", "packages/bravo/.apm/skills/local", "skills/review"])
        skill_rows = [row for row in paperclip["preview"]["items"]
                      if row["kind"] == "skill" and row["conversion"]["status"] == "converted"]
        self.assertCountEqual([row["target"] for row in skill_rows], [name for name in files if name.startswith("skills/")])

    def test_remote_aliases_share_one_stub_without_colliding_case_sensitive_source_paths(self):
        def skill(repository, path):
            return {"git": f"https://github.com/{repository}", "ref": "main", "path": f"skills/{path}"}

        self.package("aliases", "preset", [skill("EXAMPLE/TOOLS", "review"),
                                             skill("example/tools", "Review"), "../common"])
        paperclip = self.choices("aliases")["paperclip"]
        with ZipFile(io.BytesIO(self.get("aliases", paperclip["download"]))) as archive:
            paths = [name for name in archive.namelist() if name.startswith("skills/")]
            source_paths = [yaml.safe_load(archive.read(name).decode().split("---", 2)[1])
                            ["metadata"]["sources"][0]["path"] for name in paths]
        self.assertCountEqual(source_paths, ["skills/review", "skills/Review"])
        self.assertEqual(len({path.casefold() for path in paths}), 2)
        rows = [row for row in paperclip["preview"]["items"] if row["kind"] == "skill" and row["target"]]
        self.assertEqual({row["target"] for row in rows}, set(paths))

    def test_nested_save_expires_previews_and_updates_real_artifacts(self):
        previous = self.choices()
        self.assertTrue(previous["ccswitch"]["available"])
        common = json.loads(self.get("common"))
        self.get("common", data={"revision": common["revision"], "appInventorySelections": {"shared": {"codex": False}}})
        for target in previous.values():
            self.get("carrier", target["download"], status=409)
        current = self.choices()
        report = json.loads(self.get("carrier", current["ccswitch"]["download"]))
        self.assertEqual(report["skillRepositories"], [])
        rows = [row for row in report["items"] if row["name"] == "Review skill"]
        self.assertEqual({(row["app"], row["status"], row["enabled"]) for row in rows},
                         {("codex", "excluded", True), ("claude", "excluded", True)})
        with ZipFile(io.BytesIO(self.get("carrier", current["paperclip"]["download"]))) as archive:
            files = {name: archive.read(name) for name in archive.namelist()}
        self.assertNotIn("skills/review/SKILL.md", files)
        output = self.root / "exports" / "paperclip" / "carrier"
        self.assertEqual(files, {file.relative_to(output).as_posix(): file.read_bytes()
                                 for file in output.rglob("*") if file.is_file()})
