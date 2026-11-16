"""The README's support table is catalog/consumers.json written out, so the two cannot drift apart."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABELS = {"instruction": "Instruction", "skill": "Skill", "mcp": "MCP", "hook": "Hook",
          "claude-code-plugin": "Claude Code plugin", "codex-plugin": "Codex plugin"}
# The words a cell shows when the app gives no term of its own, as on the dashboard.
SHOWN = {"yes": "Supported", "no": "No", "not-documented": "Not documented"}


def column(consumer):
    tools = consumer.get("tools")
    return f"{consumer['name']} ({' · '.join(tools)})" if tools else consumer["name"]


def expected_table(data):
    consumers = data["consumers"]
    lines = ["| Component | " + " | ".join(column(consumer) for consumer in consumers) + " |",
             "| --- |" + " --- |" * len(consumers)]
    for kind in data["kinds"]:
        cells = []
        for consumer in consumers:
            cell = consumer["support"][kind]
            cells.append(f"[{cell.get('name') or SHOWN[cell['value']]}]({cell['doc']})")
        lines.append(f"| {LABELS[kind]} | " + " | ".join(cells) + " |")
    return lines


def readme_table(text):
    lines = text.splitlines()
    start = next((index for index, line in enumerate(lines) if line.startswith("| Component |")), None)
    if start is None:
        return []
    table = []
    for line in lines[start:]:
        if not line.startswith("|"):
            break
        table.append(line)
    return table


class ReadmeTableTests(unittest.TestCase):
    maxDiff = None

    def test_the_support_table_equals_consumers_json(self):
        data = json.loads((ROOT / "catalog/consumers.json").read_text(encoding="utf-8"))
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertEqual(readme_table(readme), expected_table(data))

    def test_every_kind_has_a_label(self):
        data = json.loads((ROOT / "catalog/consumers.json").read_text(encoding="utf-8"))
        self.assertEqual(list(LABELS), data["kinds"])


if __name__ == "__main__":
    unittest.main()
