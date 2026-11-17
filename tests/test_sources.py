import json
import tempfile
import unittest
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


if __name__ == "__main__":
    unittest.main()
