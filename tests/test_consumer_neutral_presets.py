"""A preset is an APM package that every consumer reads alike, so it holds nothing for one consumer.

What a consumer needs beyond the package, such as a Paperclip agent's role or rights, is set in that
consumer after the import.
"""
import json
import unittest
from pathlib import Path

import yaml

from asm_app.store import Store

ROOT = Path(__file__).resolve().parents[1]


def consumers():
    return json.loads((ROOT / "catalog/consumers.json").read_text(encoding="utf-8"))["consumers"]


class ConsumerNeutralPresetTests(unittest.TestCase):
    def test_no_preset_label_is_named_after_a_consumer(self):
        names = {consumer["id"] for consumer in consumers()}
        found = {}
        for manifest in sorted((ROOT / "packages").glob("*/apm.yml")):
            labels = yaml.safe_load(manifest.read_text(encoding="utf-8")).get("x-preset-labels") or {}
            keys = sorted(names & set(labels))
            if keys:
                found[manifest.parent.name] = keys
        self.assertEqual(found, {})

    def test_no_package_from_the_store_has_a_paperclip_field(self):
        store = Store(ROOT)
        self.assertEqual([identifier for identifier in store._ids() if "paperclip" in store.get(identifier)], [])

    def test_no_consumer_lists_roles(self):
        self.assertEqual([consumer["id"] for consumer in consumers() if "roles" in consumer], [])


if __name__ == "__main__":
    unittest.main()
