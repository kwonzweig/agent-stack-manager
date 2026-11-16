import assert from "node:assert/strict";
import test from "node:test";
import { outcome, conversionStatus } from "../src/lib/paperclipOutcome.ts";

const item = conversion => ({
  id: "x", name: "x", kind: "skill", source: null, target: null, conversion: { reason: "", ...conversion },
});

test("a converted component is converted", () => {
  assert.equal(outcome(item({ status: "converted" })), "converted");
});

test("a kind Paperclip has no setting for is left out as expected", () => {
  assert.equal(outcome(item({ status: "unconverted", cause: "unsupported" })), "expected");
});

test("a conversion that failed needs attention", () => {
  assert.equal(outcome(item({ status: "unconverted" })), "attention");
});

test("each conversion result has its own word and tone", () => {
  const shown = result => { const { label, tone } = conversionStatus(result); return [label, tone]; };
  assert.deepEqual(shown({ status: "converted" }), ["Converted", "good"]);
  assert.deepEqual(shown({ status: "unconverted", cause: "unsupported" }), ["Not supported", "neutral"]);
  assert.deepEqual(shown({ status: "unconverted" }), ["Unconverted", "bad"]);
});
