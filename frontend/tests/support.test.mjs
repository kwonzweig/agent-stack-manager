import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { columnName, reportText, supportRows, unplacedPlugins } from "../src/lib/support.ts";

const data = JSON.parse(readFileSync(new URL("../../catalog/consumers.json", import.meta.url), "utf8"));
const row = (id, supportKind, conversion, kind = supportKind) => ({
  id, name: id, kind, supportKind, source: null, target: null, conversion: { reason: "", ...conversion },
});
const report = {
  consumer: "paperclip", items: [
    row("instruction", "instruction", { status: "converted" }),
    row("a", "skill", { status: "converted" }),
    row("b", "skill", { status: "unconverted" }),
    row("playwright", "mcp", { status: "unconverted", cause: "adapter" }),
    row("stack", null, { status: "converted" }, "package"),
  ],
};
const byKind = rows => Object.fromEntries(rows.map(entry => [entry.kind, entry]));
const column = id => data.consumers.findIndex(consumer => consumer.id === id);

test("there is one row per kind, with the plugin kinds split by manifest", () => {
  assert.deepEqual(supportRows(data, report).map(entry => entry.kind),
    ["instruction", "skill", "mcp", "hook", "claude-code-plugin", "codex-plugin"]);
});

test("each row counts this preset's components of that kind, stacks apart", () => {
  const counts = supportRows(data, report).map(entry => entry.count);
  assert.deepEqual(counts, [1, 2, 1, 0, 0, 0]);
  assert.deepEqual(supportRows(data).map(entry => entry.count), [null, null, null, null, null, null]);
});

test("the Paperclip column uses the report for kinds the preset has, in its words", () => {
  const rows = byKind(supportRows(data, report));
  const paperclip = column("paperclip");
  assert.equal(rows.instruction.cells[paperclip].text, "1 exported");
  assert.equal(rows.skill.cells[paperclip].text, "1 exported · 1 needs attention");
  assert.equal(rows.skill.cells[paperclip].tone, "bad");
  assert.equal(rows.mcp.cells[paperclip].text, "1 set in the adapter");
  assert.equal(rows.hook.cells[paperclip].text, "Not documented");
});

test("other apps show their own term from the data file, with the page that says so", () => {
  const rows = byKind(supportRows(data, report));
  assert.equal(rows.instruction.cells[column("claude-code")].text, "CLAUDE.md");
  assert.equal(rows.instruction.cells[column("codex")].text, "AGENTS.md");
  assert.equal(rows.hook.cells[column("ccswitch")].text, "Not managed");
  for (const entry of Object.values(rows)) for (const cell of entry.cells) assert.match(cell.doc, /^https:\/\//);
});

test("a plain report text has every outcome once", () => {
  assert.deepEqual(reportText([row("x", "hook", { status: "unconverted", cause: "not-in-format" }),
    row("y", "hook", { status: "unconverted", cause: "not-in-format" })]),
  { text: "2 not in Paperclip's format", tone: "neutral" });
});

test("CC Switch's heading names the tools its column covers", () => {
  assert.equal(columnName(data.consumers[column("ccswitch")]), "CC Switch (Claude Code · Codex)");
  assert.equal(columnName(data.consumers[column("codex")]), "Codex");
});

test("a plugin with no known manifest is listed apart", () => {
  const items = [row("p", null, { status: "unconverted", cause: "not-in-format" }, "plugin"),
    row("q", "claude-code-plugin", { status: "unconverted", cause: "not-in-format" }, "plugin")];
  assert.deepEqual(unplacedPlugins(items).map(entry => entry.id), ["p"]);
});
