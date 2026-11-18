import assert from "node:assert/strict";
import test from "node:test";
import { createDraft, inventoryComponents, makePayload, rebaseDraft, withInventorySelection, withMembers } from "../src/draft.ts";

const component = (id) => ({ id, name: id, kind: "skill" });
const saved = (revision, fields = {}, members = ["a", "b"]) => ({
  id: "example", title: "Example", kind: "preset", icon: "", version: "1.0.0", description: "",
  workArea: [], usage: [], instruction: "", revision, componentCount: members.length + 1,
  files: [], components: [{ id: "instruction", name: "Instruction", kind: "instruction" }, ...members.map(component)], ...fields,
});

test("reviewing a newer revision preserves unrelated external and local changes", () => {
  const starting = saved("old");
  const draft = { ...createDraft(starting), instruction: "Write clear reports.", members: ["a", "local"].map(component) };
  const latest = saved("new", { description: "Added by teammate." }, ["a", "b", "external"]);
  const rebased = rebaseDraft(draft, latest);
  assert.deepEqual(makePayload(rebased), {
    revision: "new", title: "Example", description: "Added by teammate.", kind: "preset", icon: "",
    workArea: [], usage: [], instruction: "Write clear reports.", componentIds: ["a", "external", "local"],
  });
});

test("a chosen preset icon is saved and survives a rebase", () => {
  const draft = { ...createDraft(saved("old")), icon: "rocket" };
  assert.equal(makePayload(draft).icon, "rocket");
  assert.equal(rebaseDraft(draft, saved("new", { description: "Changed elsewhere." })).icon, "rocket");
});

test("a draft's edited value applies over overlapping saved metadata only after rebase", () => {
  const draft = { ...createDraft(saved("old")), title: "My title" };
  const latest = saved("new", { title: "Their title" });
  assert.equal(makePayload(draft).revision, "old");
  assert.equal(rebaseDraft(draft, latest).title, "My title");
});

test("a metadata edit keeps additional native instruction members", () => {
  const pkg = saved("old");
  pkg.components.push({ id: "instruction:shared/AGENTS.md", kind: "instruction", name: "Shared instructions" });
  const draft = { ...createDraft(pkg), title: "Updated" };
  assert.deepEqual(makePayload(draft).componentIds, ["a", "b", "instruction:shared/AGENTS.md"]);
});

test("edits made during a save rebase against the submitted snapshot", () => {
  const baseline = createDraft(saved("old"));
  const submitting = { ...baseline, instruction: "Text being saved" };
  const editedDuringSave = { ...submitting, instruction: "" };
  const latest = saved("new", { instruction: "Text being saved" });
  assert.equal(rebaseDraft(editedDuringSave, latest, submitting).instruction, "");
});

test("adding from Catalog saves only new members onto the saved version", () => {
  const { added, draft } = withMembers(saved("current"), ["b", "c", "c"].map(component).concat({ id: "package:example", name: "Example", kind: "package" }));
  assert.deepEqual(added.map(item => item.id), ["c"]);
  assert.deepEqual(makePayload(draft), {
    revision: "current", title: "Example", description: "", kind: "preset", icon: "",
    workArea: [], usage: [], instruction: "", componentIds: ["a", "b", "c"],
  });
});

test("an open draft keeps its unsaved edits after a Catalog add is saved", () => {
  const open = { ...createDraft(saved("old")), instruction: "Unsaved text", members: ["a"].map(component) };
  const rebased = rebaseDraft(open, saved("new", {}, ["a", "b", "c"]));
  assert.equal(rebased.instruction, "Unsaved text");
  assert.deepEqual(makePayload(rebased).componentIds, ["a", "c"]);
});

test("a selection changed back while saving survives alongside other app observations", () => {
  const state = { installed: true, enabled: false, selected: true };
  const item = { id: "example", name: "Example", kind: "skill", description: "", apps: { codex: state, claude: state } };
  const starting = createDraft(saved("old", { appInventory: [item] }));
  const submitting = withInventorySelection(starting, item, "codex", false);
  const editedWhileSaving = withInventorySelection(submitting, item, "codex", true);
  const latest = saved("new", { appInventory: [{ ...item, apps: {
    codex: { ...state, selected: false }, claude: { ...state, enabled: true },
  } }] });
  const rebased = rebaseDraft(editedWhileSaving, latest, submitting);
  assert.deepEqual(makePayload(rebased).appInventorySelections, { example: { codex: true } });
  assert.equal(rebased.original.appInventory[0].apps.claude.enabled, true);
});

test("inventory rows retain their own identity and original repository coordinates in the workspace", () => {
  const rows = inventoryComponents([
    { id: "instruction", name: "Local instructions", kind: "instruction", description: "Project rules.", apps: {} },
    { id: "git-skill", name: "Skill", kind: "skill", description: "Reviews code.", apps: {},
      source: "https://github.com/example/skills", sourcePath: "skills/review/SKILL.md", sourceRef: "stable" },
  ]);
  assert.equal(rows[0].inventoryId, "instruction");
  assert.notEqual(rows[0].id, "instruction");
  assert.deepEqual(rows[1].source, {
    repositoryUrl: "https://github.com/example/skills", path: "skills/review/SKILL.md", ref: "stable",
  });
  assert.equal(rows[1].description, "Reviews code.");
});

test("adding from the Catalog leaves an inventory-managed skill under its per-app selections", () => {
  const appInventory = [{ id: "skill", name: "Skill", kind: "skill", apps: {},
    apm: { git: "https://github.com/example/skills", ref: "main", path: "skills/code" } }];
  const pkg = saved("current", { appInventory });
  const managed = { id: "catalog-different-id", kind: "skill", name: "Skill",
    source: { repositoryUrl: "https://github.com/Example/Skills.git", ref: "main", path: "skills/code/SKILL.md" } };
  const differentRef = { ...managed, id: "another-ref", source: { ...managed.source, ref: "preview" } };
  assert.deepEqual(withMembers(pkg, [managed, differentRef]).added, [differentRef]);
});
