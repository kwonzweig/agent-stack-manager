import json
import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
# A 40-hex commit, an npm version after a package name, or a version tag used as a ref.
PINNED = re.compile(r"""\b[0-9a-f]{40}\b|@\d+\.\d+\.\d+|"?ref"?: "?v?\d+\.\d+[\w.-]*""")
BRANCH = "main"


class RemoteFirstTests(unittest.TestCase):
    def test_presets_and_catalog_follow_their_remotes(self):
        # A consumer's own update can only follow a branch. A pinned commit or version never moves.
        files = [*sorted(ROOT.glob("packages/*/apm.yml")), ROOT / "catalog" / "components.json"]
        pinned = {path.relative_to(ROOT).as_posix(): sorted(set(PINNED.findall(path.read_text(encoding="utf-8"))))
                  for path in files}
        self.assertEqual({path: found for path, found in pinned.items() if found}, {})

    def test_preset_dependencies_name_a_branch_and_no_version(self):
        for manifest in sorted(ROOT.glob("packages/*/apm.yml")):
            dependencies = yaml.safe_load(manifest.read_text(encoding="utf-8")).get("dependencies") or {}
            for entry in dependencies.get("apm") or []:
                if not isinstance(entry, dict):
                    continue
                with self.subTest(manifest=manifest.parent.name, entry=entry.get("git") or entry.get("name")):
                    self.assertNotIn("version", entry)
                    if "git" in entry:
                        self.assertIn(entry.get("ref", BRANCH), (BRANCH,))

    def test_catalog_sources_and_links_follow_the_default_branch(self):
        catalog = json.loads((ROOT / "catalog" / "components.json").read_text(encoding="utf-8"))
        for row in catalog["items"]:
            with self.subTest(component=row["id"]):
                value = row["apm"].get("value")
                if isinstance(value, dict):
                    self.assertNotIn("version", value)
                    self.assertIn(value.get("ref", BRANCH), (BRANCH,))
                if row.get("source"):
                    self.assertEqual(row["source"]["ref"], BRANCH)
                if row.get("sourceUrl") and "/blob/" in row["sourceUrl"]:
                    self.assertEqual(row["sourceUrl"].split("/blob/", 1)[1].split("/", 1)[0], BRANCH)


if __name__ == "__main__":
    unittest.main()
