import json
import re
import unittest
from pathlib import Path

import yaml

from asm_app.store import _git

ROOT = Path(__file__).resolve().parents[1]
# A 40-hex commit, an npm version after a package name, or a version tag used as a ref.
PINNED = re.compile(r"""\b[0-9a-f]{40}\b|@\d+\.\d+\.\d+|"?ref"?: "?v?\d+\.\d+[\w.-]*""")
BRANCH = "main"


def apm_dependencies(text):
    return ((yaml.safe_load(text) or {}).get("dependencies") or {}).get("apm") or []


def pinned_dependencies(text):
    """The APM dependencies of one apm.yml that carry a version or name a ref other than the branch.

    A string entry is read as the store reads it, `owner/repo/path#ref`, so `#<commit>` or `#v1.0` counts.
    """
    found = []
    for entry in apm_dependencies(text):
        git = _git(entry)
        if isinstance(entry, dict):
            pinned = "version" in entry or bool(git) and entry.get("ref", BRANCH) != BRANCH
        else:
            pinned = bool(git) and (git["ref"] or BRANCH) != BRANCH
        if pinned:
            found.append(entry)
    return found


class RemoteFirstTests(unittest.TestCase):
    def test_presets_and_catalog_follow_their_remotes(self):
        # A consumer's own update can only follow a branch. A pinned commit or version never moves.
        files = [*sorted(ROOT.glob("packages/*/apm.yml")), ROOT / "catalog" / "components.json"]
        pinned = {path.relative_to(ROOT).as_posix(): sorted(set(PINNED.findall(path.read_text(encoding="utf-8"))))
                  for path in files}
        self.assertEqual({path: found for path, found in pinned.items() if found}, {})

    def test_preset_dependencies_name_a_branch_and_no_version(self):
        for manifest in sorted(ROOT.glob("packages/*/apm.yml")):
            with self.subTest(manifest=manifest.parent.name):
                self.assertEqual(pinned_dependencies(manifest.read_text(encoding="utf-8")), [])

    def test_a_string_dependency_with_a_ref_other_than_the_branch_is_caught(self):
        # APM's string form `owner/repo/path#ref` is read by the store too, and its ref reaches the export.
        text = (ROOT / "packages" / "ar" / "apm.yml").read_text(encoding="utf-8")
        for ref, caught in (("#af86024", True), ("#v1.0", True), ("#" + "0" * 40, True), ("#main", False), ("", False)):
            line = f"kwonzweig/there-is-a-tool-for-that/skills/find-tools{ref}"
            with self.subTest(entry=line):
                found = pinned_dependencies(text.replace("  apm:\n", f"  apm:\n  - {line}\n", 1))
                self.assertEqual(found, [line] if caught else [])

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


def members_outside_the_catalog(text, rows):
    """The repository and plugin members of one apm.yml that no catalog item names; string entries included."""
    known = {(repository(value["git"]), value.get("path", ""), value.get("ref", ""))
             for row in rows if (value := git_value(row))}
    plugins = {(row["apm"]["value"].get("marketplace"), row["apm"]["value"].get("name"))
               for row in rows if row["kind"] == "plugin"}
    found = []
    for entry in apm_dependencies(text):
        if git := _git(entry):
            if (repository(git["git"]), git.get("path", ""), git.get("ref", "")) not in known:
                found.append(entry)
        elif isinstance(entry, dict) and "marketplace" in entry:
            if (entry["marketplace"], entry.get("name")) not in plugins:
                found.append(entry)
    return found


class CatalogRepositoryTests(unittest.TestCase):
    def test_every_repository_member_of_a_preset_is_a_catalog_item(self):
        for manifest in sorted(ROOT.glob("packages/*/apm.yml")):
            with self.subTest(manifest=manifest.parent.name):
                self.assertEqual(members_outside_the_catalog(manifest.read_text(encoding="utf-8"), catalog()["items"]), [])

    def test_a_string_member_outside_the_catalog_is_caught(self):
        text = (ROOT / "packages" / "ar" / "apm.yml").read_text(encoding="utf-8")
        for line, caught in (("kwonzweig/there-is-a-tool-for-that/skills/find-tools#main", False),
                             ("kwonzweig/there-is-a-tool-for-that/skills/not-in-the-catalog#main", True)):
            with self.subTest(entry=line):
                found = members_outside_the_catalog(text.replace("  apm:\n", f"  apm:\n  - {line}\n", 1), catalog()["items"])
                self.assertEqual(found, [line] if caught else [])

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
