"""catalog/consumers.json: what each app supports, per component kind, each cell with the page that says so."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlsplit

from asm_app.store import SUPPORT_KINDS, Store, StoreError

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "catalog/consumers.json").read_text(encoding="utf-8"))


class ConsumerDataTests(unittest.TestCase):
    def test_every_consumer_has_a_filled_cell_for_every_kind(self):
        self.assertEqual(DATA["kinds"], list(SUPPORT_KINDS))
        self.assertEqual([row["id"] for row in DATA["consumers"]], ["paperclip", "claude-code", "codex", "ccswitch"])
        for consumer in DATA["consumers"]:
            self.assertEqual(list(consumer["support"]), list(SUPPORT_KINDS), consumer["id"])
            for kind, cell in consumer["support"].items():
                with self.subTest(consumer=consumer["id"], kind=kind):
                    self.assertIn(cell["value"], ("yes", "no", "not-documented"))
                    self.assertEqual(urlsplit(cell["doc"]).scheme, "https")
                    if cell["value"] == "yes":
                        self.assertTrue(cell["name"].strip())

    def test_only_paperclip_is_exported_to(self):
        self.assertEqual([row["id"] for row in DATA["consumers"] if row["export"]], ["paperclip"])

    def test_cc_switch_names_the_tools_its_column_covers(self):
        ccswitch = next(row for row in DATA["consumers"] if row["id"] == "ccswitch")
        self.assertEqual(ccswitch["tools"], ["Claude Code", "Codex"])

    def test_the_store_serves_the_file(self):
        self.assertEqual(Store(ROOT).consumers(), DATA)


class ConsumerValidationTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        (self.root / "catalog").mkdir()

    def write(self, data):
        (self.root / "catalog/consumers.json").write_text(json.dumps(data), encoding="utf-8")

    def refused(self, change):
        data = copy.deepcopy(DATA)
        change(data)
        self.write(data)
        with self.assertRaises(StoreError):
            Store(self.root).consumers()

    def test_no_file_means_no_consumers(self):
        self.assertEqual(Store(self.root).consumers(), {"kinds": list(SUPPORT_KINDS), "consumers": []})

    def test_a_copy_of_the_file_is_accepted(self):
        self.write(DATA)
        self.assertEqual(Store(self.root).consumers(), DATA)

    def test_incomplete_or_unsourced_cells_are_refused(self):
        cell = lambda data, consumer=1, kind="hook": data["consumers"][consumer]["support"][kind]
        self.refused(lambda data: data["consumers"][1]["support"].pop("hook"))
        self.refused(lambda data: cell(data).update(value="not-checked"))
        self.refused(lambda data: cell(data).update(value=None))
        self.refused(lambda data: cell(data).pop("doc"))
        self.refused(lambda data: cell(data).update(doc="docs/hooks.md"))
        self.refused(lambda data: cell(data).pop("name"))
        self.refused(lambda data: cell(data).update(note=7))
        self.refused(lambda data: data["consumers"][1]["support"].update(lsp=cell(data)))
        self.refused(lambda data: data.update(kinds=["skill"]))
        self.refused(lambda data: data["consumers"][0].update(export="yes"))
        self.refused(lambda data: data["consumers"][0]["roles"].update(values=["general", 3]))
        self.refused(lambda data: data["consumers"].append(copy.deepcopy(data["consumers"][0])))


if __name__ == "__main__":
    unittest.main()
