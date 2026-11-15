import assert from "node:assert/strict";
import test from "node:test";
import { createDraft, makePayload, rebaseDraft } from "../src/draft.ts";

const component = (id) => ({ id, name: id, kind: "skill" });
const saved = (revision, fields = {}, members = ["a", "b"]) => ({
  id: "example", title: "Example", kind: "preset", version: "1.0.0", description: "",
  workArea: [], usage: [], instruction: "", revision, componentCount: members.length + 1,
  files: [], components: [{ id: "instruction", name: "Instruction", kind: "instruction" }, ...members.map(component)], ...fields,
});

test("reviewing a newer revision preserves unrelated external and local changes", () => {
  const starting = saved("old");
  const draft = { ...createDraft(starting), instruction: "Write clear reports.", members: ["a", "local"].map(component) };
  const latest = saved("new", { description: "Added by teammate." }, ["a", "b", "external"]);
  const rebased = rebaseDraft(draft, latest);
  assert.deepEqual(makePayload(rebased), {
    revision: "new", title: "Example", description: "Added by teammate.", kind: "preset",
    workArea: [], usage: [], instruction: "Write clear reports.", componentIds: ["a", "external", "local"],
  });
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
