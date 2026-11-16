"""The committed Paperclip exports under exports/paperclip/<id>/: the command, its check mode and saves."""
from contextlib import redirect_stdout
import io
from pathlib import Path
import shutil
import tempfile
import unittest

import yaml

from asm_app import cli
from asm_app.store import Store

ROOT = Path(__file__).resolve().parents[1]
SKILL = ("  - git: https://github.com/example/kit.git\n"
         "    ref: main\n"
         "    path: skills/check\n")


def run(root, *args):
    output = io.StringIO()
    with redirect_stdout(output):
        code = cli.main(["--root", str(root), "export", *args])
    return code, output.getvalue()


def files_under(directory):
    return sorted(path.relative_to(directory).as_posix() for path in directory.rglob("*") if path.is_file())


class ExportFolderTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        (self.root / "catalog").mkdir()
        for name in ("components.json", "consumers.json"):
            shutil.copy(ROOT / "catalog" / name, self.root / "catalog" / name)
        self.package("base", "name: base\nx-preset-labels:\n  kind: stack\n  title: Base\n"
                             "dependencies:\n  apm:\n" + SKILL)
        self.package("demo", "name: demo\nx-preset-labels:\n  title: Demo\n"
                             "dependencies:\n  apm:\n  - ../base\n  hooks:\n  - name: stop\n",
                     {".apm/agents/demo.agent.md": "Check the app.\n"})
        self.exports = self.root / "exports" / "paperclip"

    def package(self, identifier, manifest, files=None):
        directory = self.root / "packages" / identifier
        for path, text in {"apm.yml": manifest, **(files or {})}.items():
            (directory / path).parent.mkdir(parents=True, exist_ok=True)
            (directory / path).write_text(text, encoding="utf-8")

    def revision(self, identifier="demo"):
        settings = yaml.safe_load((self.exports / identifier / ".paperclip.yaml").read_text(encoding="utf-8"))
        return settings["agents"][identifier]["metadata"]["agentStackManagerRevision"]

    def test_export_writes_only_the_package_files_of_each_preset(self):
        code, output = run(self.root)
        self.assertEqual(code, 0, output)
        self.assertEqual([path.name for path in self.exports.iterdir()], ["demo"])
        self.assertEqual(files_under(self.exports / "demo"),
                         [".paperclip.yaml", "COMPANY.md", "agents/demo/AGENTS.md", "skills/check/SKILL.md"])
        self.assertIn("exports/paperclip/demo", output)
        self.assertIn("stop (hook): Paperclip's company package has no hook entry.", output)

    def test_written_files_are_the_conversion_with_lf_line_endings(self):
        run(self.root)
        from asm_app.paperclip import convert
        report = convert(Store(self.root).get("demo"), root=self.root)
        for entry in report["files"]:
            self.assertEqual((self.exports / "demo" / entry["path"]).read_bytes(), entry["content"].encode("utf-8"))

    def test_export_fails_when_a_component_needs_attention(self):
        self.package("loose", "name: loose\ndependencies:\n  apm:\n"
                              "  - git: https://gitlab.com/example/kit.git\n    ref: main\n    path: skills/x\n")
        code, output = run(self.root)
        self.assertEqual(code, 1)
        self.assertIn("needs attention: x (skill): Paperclip imports skills from GitHub only.", output)
        self.assertTrue((self.exports / "loose" / "COMPANY.md").is_file())

    def test_check_passes_on_a_current_export(self):
        run(self.root)
        code, output = run(self.root, "--check")
        self.assertEqual(code, 0, output)

    def test_check_fails_on_a_changed_missing_or_extra_file(self):
        for change, word in (
                (lambda: (self.exports / "demo/COMPANY.md").write_text("edited\n", encoding="utf-8"), "changed"),
                (lambda: (self.exports / "demo/skills/check/SKILL.md").unlink(), "missing"),
                (lambda: (self.exports / "demo/notes.md").write_text("x\n", encoding="utf-8"), "extra"),
                (lambda: (self.exports / "gone").mkdir() or (self.exports / "gone/COMPANY.md").write_text(
                    "x\n", encoding="utf-8"), "extra")):
            with self.subTest(word=word):
                run(self.root)
                before = {name: (self.exports / name).read_bytes() for name in files_under(self.exports)}
                change()
                code, output = run(self.root, "--check")
                self.assertEqual(code, 1, output)
                self.assertIn(word, output)
                self.assertIn("python -m asm_app export", output)
                after = {name: (self.exports / name).read_bytes() for name in files_under(self.exports)}
                self.assertNotEqual(before, after, "--check writes nothing")

    def test_check_fails_when_no_export_was_written(self):
        code, output = run(self.root, "--check")
        self.assertEqual(code, 1)
        self.assertIn("missing: exports/paperclip/demo/COMPANY.md", output)

    def test_saving_a_preset_rewrites_its_export(self):
        store = Store(self.root)
        store.save("demo", {"revision": store.get("demo")["revision"], "instruction": "Review refunds."})
        agents = (self.exports / "demo/agents/demo/AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("Review refunds.", agents)
        self.assertEqual(run(self.root, "--check")[0], 0)

    def test_saving_a_stack_rewrites_the_export_of_the_preset_that_includes_it(self):
        run(self.root)
        first = self.revision()
        store = Store(self.root)
        store.save("base", {"revision": store.get("base")["revision"], "description": "Changed."})
        self.assertNotEqual(first, self.revision())
        self.assertFalse((self.exports / "base").exists())
        self.assertEqual(run(self.root, "--check")[0], 0)

    def test_creating_a_preset_writes_its_export(self):
        Store(self.root).create({"title": "New role", "instruction": "Start here."})
        self.assertTrue((self.exports / "new-role/agents/new-role/AGENTS.md").is_file())

    def test_a_removed_preset_loses_its_export_and_a_removed_skill_its_stub(self):
        run(self.root)
        self.package("base", "name: base\nx-preset-labels:\n  kind: stack\n")
        shutil.rmtree(self.root / "packages" / "demo")
        self.package("other", "name: other\n")
        run(self.root)
        self.assertEqual([path.name for path in self.exports.iterdir()], ["other"])
        self.package("other", "name: other\ndependencies:\n  apm:\n" + SKILL)
        run(self.root)
        self.assertTrue((self.exports / "other/skills/check/SKILL.md").is_file())
        self.package("other", "name: other\n")
        run(self.root)
        self.assertFalse((self.exports / "other/skills").exists())

    def test_a_preset_that_cannot_be_read_keeps_its_folder_and_fails_the_command(self):
        run(self.root)
        (self.root / "packages/demo/apm.yml").write_text("[not a mapping]\n", encoding="utf-8")
        code, output = run(self.root)
        self.assertEqual(code, 1)
        self.assertIn("demo", output)
        self.assertTrue((self.exports / "demo/COMPANY.md").is_file())


class CommittedExportTests(unittest.TestCase):
    def test_every_preset_in_this_repository_has_its_export_folder(self):
        presets = sorted(row["id"] for row in Store(ROOT).list_packages() if row["kind"] == "preset")
        folders = sorted(path.name for path in (ROOT / "exports" / "paperclip").iterdir())
        self.assertEqual(folders, presets)


if __name__ == "__main__":
    unittest.main()
