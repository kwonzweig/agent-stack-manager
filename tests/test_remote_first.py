import json
import re
import unittest
from datetime import date
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


def repository(url):
    return url.rstrip("/").removesuffix(".git").casefold()


def catalog():
    return json.loads((ROOT / "catalog" / "components.json").read_text(encoding="utf-8"))


def git_value(row):
    value = row["apm"].get("value")
    return value if isinstance(value, dict) and isinstance(value.get("git"), str) else None


def item_repository(row):
    """The repository a catalog item comes from: its APM git value, or the source stored for an item without one."""
    if value := git_value(row):
        return repository(value["git"])
    source = row.get("source") or {}
    return repository(source["repositoryUrl"]) if source.get("repositoryUrl") else None


class CatalogRepositoryTests(unittest.TestCase):
    def test_every_repository_member_of_a_preset_is_a_catalog_item(self):
        rows = catalog()["items"]
        known = {(repository(value["git"]), value.get("path", ""), value.get("ref", ""))
                 for row in rows if (value := git_value(row))}
        plugins = {(row["apm"]["value"].get("marketplace"), row["apm"]["value"].get("name"))
                   for row in rows if row["kind"] == "plugin"}
        for manifest in sorted(ROOT.glob("packages/*/apm.yml")):
            dependencies = yaml.safe_load(manifest.read_text(encoding="utf-8")).get("dependencies") or {}
            for entry in dependencies.get("apm") or []:
                if not isinstance(entry, dict):
                    continue
                with self.subTest(manifest=manifest.parent.name, entry=entry.get("path") or entry.get("git") or entry.get("name")):
                    if "git" in entry:
                        self.assertIn((repository(entry["git"]), entry.get("path", ""), entry.get("ref", "")), known)
                    elif "marketplace" in entry:
                        self.assertIn((entry["marketplace"], entry.get("name")), plugins)

    def test_every_item_repository_has_one_row_and_every_row_is_used(self):
        data = catalog()
        rows = [repository(row["url"]) for row in data["repositories"]]
        self.assertEqual(len(rows), len(set(rows)), "a repository is listed twice")
        used = {found for row in data["items"] if (found := item_repository(row))}
        self.assertEqual(sorted(used - set(rows)), [], "items whose repository has no row")
        self.assertEqual(sorted(set(rows) - used), [], "rows no item uses")

    def test_every_repository_row_holds_a_star_count_and_the_day_it_was_read(self):
        for row in catalog()["repositories"]:
            with self.subTest(repository=row.get("url")):
                self.assertEqual(set(row), {"url", "stars", "starsCheckedOn"})
                self.assertRegex(row["url"], r"^https://github\.com/[\w.-]+/[\w.-]+$")
                self.assertIs(type(row["stars"]), int)
                self.assertGreaterEqual(row["stars"], 0)
                self.assertEqual(date.fromisoformat(row["starsCheckedOn"]).isoformat(), row["starsCheckedOn"])

    def test_source_is_stored_only_for_items_without_git(self):
        # A git item's source and link are derived from its APM value, so it has one location.
        for row in catalog()["items"]:
            with self.subTest(component=row["id"]):
                if git_value(row):
                    self.assertNotIn("source", row)
                    self.assertNotIn("sourceUrl", row)
                else:
                    self.assertIn("source", row)


if __name__ == "__main__":
    unittest.main()
