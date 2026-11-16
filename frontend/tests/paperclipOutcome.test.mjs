import assert from "node:assert/strict";
import test from "node:test";
import { outcome, stageStatus } from "../src/lib/paperclipOutcome.ts";

const item = (conversion, imported) => ({
  id: "x", name: "x", kind: "skill", source: null, target: null,
  conversion: { reason: "", ...conversion }, import: { reason: "", ...imported },
});
const converted = { status: "converted" };
const notExported = { status: "not_checked" };

test("a kind Paperclip has no setting for is left out as expected", () => {
  assert.equal(outcome(item({ status: "unconverted", cause: "unsupported" }, notExported)), "expected");
});

test("a skill Paperclip's scan refused is left out as expected", () => {
  assert.equal(outcome(item(converted, { status: "missing", cause: "refused" })), "expected");
});

test("a source Paperclip cannot read needs attention", () => {
  assert.equal(outcome(item(converted, { status: "missing", cause: "access" })), "attention");
});

test("a component left out with no known cause needs attention", () => {
  assert.equal(outcome(item(converted, { status: "missing" })), "attention");
  assert.equal(outcome(item({ status: "unconverted" }, notExported)), "attention");
});

test("a saved component is saved, and one not checked yet is pending", () => {
  assert.equal(outcome(item(converted, { status: "saved" })), "saved");
  assert.equal(outcome(item(converted, { status: "not_checked" })), "pending");
});

test("each stage result has its own word and tone", () => {
  const shown = result => { const { label, tone } = stageStatus(result); return [label, tone]; };
  assert.deepEqual(shown({ status: "converted" }), ["Converted", "good"]);
  assert.deepEqual(shown({ status: "unconverted", cause: "unsupported" }), ["Not supported", "neutral"]);
  assert.deepEqual(shown({ status: "unconverted" }), ["Unconverted", "bad"]);
  assert.deepEqual(shown({ status: "saved" }), ["Saved", "good"]);
  assert.deepEqual(shown({ status: "missing", cause: "refused" }), ["Refused", "neutral"]);
  assert.deepEqual(shown({ status: "missing", cause: "access" }), ["No access", "bad"]);
  assert.deepEqual(shown({ status: "missing" }), ["Missing", "bad"]);
  assert.deepEqual(shown({ status: "not_checked" }), ["Not checked", "neutral"]);
});
