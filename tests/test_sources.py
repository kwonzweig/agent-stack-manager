import json
import tempfile
import unittest
import threading
from pathlib import Path

from asm_app.sources import MAX_AGE, SourceReader

SKILL = {"id": "brainstorming-1", "name": "brainstorming", "kind": "skill",
         "source": {"repositoryUrl": "https://github.com/obra/superpowers", "path": "skills/brainstorming/SKILL.md", "ref": "main"}}
PLUGIN = {"id": "frontend-design", "name": "frontend-design", "kind": "plugin",
          "source": {"repositoryUrl": "https://github.com/anthropics/claude-plugins-official", "path": "plugins/frontend-design", "ref": "main"}}
MCP = {"id": "playwright", "name": "playwright", "kind": "mcp",
       "source": {"repositoryUrl": "https://github.com/microsoft/playwright-mcp", "path": "README.md", "ref": "main"}}
HOOK = {"id": "web-session-start", "name": "web-session-start", "kind": "hook", "source": None}

REPLIES = {
    "https://api.github.com/repos/obra/superpowers": {"stargazers_count": 318722, "description": "Agentic skills"},
    "https://api.github.com/repos/anthropics/claude-plugins-official": {"stargazers_count": 47483, "description": "Plugins"},
    "https://api.github.com/repos/microsoft/playwright-mcp": {"stargazers_count": 30000, "description": "Playwright MCP server"},
    "https://raw.githubusercontent.com/obra/superpowers/main/skills/brainstorming/SKILL.md":
        "---\nname: brainstorming\ndescription: You MUST use this before any creative work.\n---\n# Brainstorming\n",
    "https://raw.githubusercontent.com/anthropics/claude-plugins-official/main/plugins/frontend-design/.claude-plugin/plugin.json":
        {"name": "frontend-design", "description": "Frontend design skill for UI/UX implementation"},
    "https://skills.sh/api/search?q=obra/superpowers&limit=100":
        {"skills": [{"source": "obra/superpowers", "skillId": "brainstorming", "name": "brainstorming", "installs": 432022},
                    {"source": "someone/else", "skillId": "brainstorming", "name": "brainstorming", "installs": 5}]},
}


class SourceReaderTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.cache = Path(directory.name) / ".asm" / "sources.json"
        self.asked = []
        self.now = 1_000_000.0

    def fetch(self, url):
        self.asked.append(url)
        if url not in REPLIES:
            raise OSError("unreachable")
        reply = REPLIES[url]
        return (reply if isinstance(reply, str) else json.dumps(reply)).encode("utf-8")

    def reader(self):
        return SourceReader(self.cache, fetch=self.fetch, clock=lambda: self.now)

    def test_each_item_shows_what_its_own_source_says(self):
        found = self.reader().read([SKILL, PLUGIN, MCP, HOOK])["items"]
        skill = found["brainstorming-1"]
        self.assertEqual(skill["description"], "You MUST use this before any creative work.")
        self.assertEqual(skill["descriptionUrl"], "https://github.com/obra/superpowers/blob/main/skills/brainstorming/SKILL.md")
        self.assertEqual((skill["stars"], skill["installs"]), (318722, 432022))
        self.assertEqual(found["frontend-design"]["description"], "Frontend design skill for UI/UX implementation")
        self.assertEqual(found["playwright"]["description"], "Playwright MCP server")
        self.assertEqual(found["playwright"]["descriptionUrl"], "https://github.com/microsoft/playwright-mcp")
        self.assertNotIn("installs", found["playwright"])
        # A hook defined in the catalog has no source to ask.
        self.assertNotIn("web-session-start", found)

    def test_answers_are_reused_for_an_hour_and_kept_out_of_the_repo(self):
        self.reader().read([SKILL])
        first = len(self.asked)
        self.reader().read([SKILL])
        self.assertEqual(len(self.asked), first, "asked again within the hour")
        self.now += MAX_AGE
        self.reader().read([SKILL])
        self.assertEqual(len(self.asked), 2 * first)
        self.assertEqual(self.cache.parent.name, ".asm")

    def test_an_unreachable_source_is_reported_and_keeps_its_last_answer(self):
        self.reader().read([SKILL])
        self.now += MAX_AGE
        saved = dict(REPLIES)
        REPLIES.clear()
        try:
            result = self.reader().read([SKILL])
        finally:
            REPLIES.update(saved)
        self.assertEqual(result["items"]["brainstorming-1"]["stars"], 318722)
        self.assertTrue(any("api.github.com/repos/obra/superpowers" in error for error in result["errors"]))

    def test_unverified_and_private_inventory_never_reach_third_party_hosts(self):
        for access, reply in ((None, None), ("private", None), ("verify", {"private": True})):
            self.asked.clear()
            item = {**SKILL, "id": "private-observation", "remoteApproved": False,
                    "sourceAccess": access}
            def lookup(url):
                self.asked.append(url)
                self.assertEqual(url, "https://api.github.com/repos/obra/superpowers")
                return json.dumps({"stargazers_count": 0, "description": "", **reply}).encode()
            reader = SourceReader(self.cache.with_name(str(access) + ".json"), fetch=lookup, clock=lambda: self.now)
            result = reader.read([item])
            self.assertEqual(len(self.asked), 1 if access == "verify" else 0)
            self.assertFalse(any("skills.sh" in url or "raw.githubusercontent.com" in url for url in self.asked))
            self.assertNotIn("content", result["items"].get(item["id"], {}))

    def test_a_new_explicit_remote_is_verified_then_reads_its_default_branch_without_rewriting_observation(self):
        # Real installations have fresh cache records from before visibility/body support.
        self.cache.parent.mkdir(parents=True)
        self.cache.write_text(json.dumps({"repository:obra/superpowers": {
            "stars": 11, "description": "Legacy metadata", "readAt": self.now,
        }}))
        item = {**SKILL, "id": "new-observation", "sourceAccess": "verify", "remoteApproved": False,
                "source": {**SKILL["source"], "ref": ""}}
        def lookup(url):
            self.asked.append(url)
            if url == "https://api.github.com/repos/obra/superpowers":
                return json.dumps({"private": False, "stargazers_count": 42, "description": "Skills", "default_branch": "stable"}).encode()
            if url == "https://raw.githubusercontent.com/obra/superpowers/stable/skills/brainstorming/SKILL.md":
                return b"---\nname: brainstorming\ndescription: Current purpose.\n---\n# Full body\n"
            if url.startswith("https://skills.sh/"):
                return b'{"skills":[]}'
            raise AssertionError(url)
        result = SourceReader(self.cache, fetch=lookup, clock=lambda: self.now).read([item])["items"][item["id"]]
        self.assertEqual(result["stars"], 42)
        self.assertEqual(result["sourceResolvedRef"], "stable")
        self.assertIn("# Full body", result["content"])
        self.assertEqual(item["source"]["ref"], "")
        self.assertEqual(self.asked[0], "https://api.github.com/repos/obra/superpowers")
        refreshed = json.loads(self.cache.read_text())["repository:obra/superpowers"]
        self.assertEqual(refreshed["visibility"], "public")
        self.assertEqual(refreshed["defaultRef"], "stable")

    def test_an_explicitly_private_source_does_not_upgrade_or_consume_legacy_public_cache(self):
        self.cache.parent.mkdir(parents=True)
        self.cache.write_text(json.dumps({"repository:obra/superpowers": {
            "stars": 11, "description": "Legacy metadata", "readAt": self.now,
        }}))
        item = {**SKILL, "sourceAccess": "private", "remoteApproved": False}
        result = self.reader().read([item])
        self.assertEqual(result["items"], {})
        self.assertEqual(self.asked, [])

    def test_negative_cache_preserves_network_cause_without_calling_it_private(self):
        item = {**SKILL, "sourceAccess": "verify", "remoteApproved": False}
        def failing(url):
            self.asked.append(url)
            raise OSError("Network unavailable")
        reader = SourceReader(self.cache, fetch=failing, clock=lambda: self.now)
        initial = reader.read([item])
        retry = reader.read([item])
        self.assertEqual(len(self.asked), 1)
        self.assertEqual(initial["errors"], retry["errors"])
        self.assertIn("Network unavailable", retry["errors"][0])
        self.assertIn("visibility check failed", retry["items"][item["id"]]["sourceUnavailable"])
        self.assertNotIn("repository as private", retry["items"][item["id"]]["sourceUnavailable"])

    def test_an_unlocated_skill_does_not_use_the_repository_description_as_its_purpose(self):
        for kind in ("skill", "plugin"):
            item = {**SKILL, "kind": kind, "source": {"repositoryUrl": SKILL["source"]["repositoryUrl"], "ref": "main"}}
            facts = self.reader().read([item])["items"][item["id"]]
            self.assertEqual(facts["stars"], 318722)
            self.assertNotIn("description", facts)
            self.assertNotIn("content", facts)

    def test_cold_bulk_read_does_not_hold_the_cache_lock_while_fetching(self):
        started, release = threading.Event(), threading.Event()
        def lookup(url):
            if "slow/project" in url:
                started.set()
                release.wait(3)
            return b'{"stargazers_count":1,"description":"Source"}'
        reader = SourceReader(self.cache, fetch=lookup, clock=lambda: self.now)
        slow = {**MCP, "source": {"repositoryUrl": "https://github.com/slow/project"}}
        worker = threading.Thread(target=lambda: reader.read([slow]))
        worker.start()
        try:
            self.assertTrue(started.wait(1))
            fast = {**MCP, "id": "fast", "source": {"repositoryUrl": "https://github.com/fast/project"}}
            result = reader.read([fast])
            self.assertEqual(result["items"]["fast"]["stars"], 1)
            self.assertFalse(release.is_set())
        finally:
            release.set()
            worker.join(3)


if __name__ == "__main__":
    unittest.main()
