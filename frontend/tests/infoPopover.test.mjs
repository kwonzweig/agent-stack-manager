import assert from "node:assert/strict";
import test from "node:test";
import { CLOSED, escapeKey, nextPopover, sourceLinkText } from "../src/lib/infoPopover.ts";

const run = (...events) => events.reduce(nextPopover, CLOSED);

test("the source link names the page's host and path", () => {
  assert.equal(sourceLinkText("https://code.claude.com/docs/en/hooks"), "code.claude.com/docs/en/hooks");
  assert.equal(sourceLinkText("https://github.com/farion1231/cc-switch#supported-features-by-tool"),
    "github.com/farion1231/cc-switch");
  assert.equal(sourceLinkText("https://github.com/farion1231/cc-switch/"), "github.com/farion1231/cc-switch");
  assert.equal(sourceLinkText("not a url"), "not a url");
});

test("hover opens the popover and leaving the icon and the popover closes it", () => {
  assert.equal(run("pointer-enter").open, true);
  assert.equal(run("pointer-enter", "pointer-leave").open, false);
});

test("a click keeps the popover open after the pointer leaves only until it leaves", () => {
  assert.equal(run("pointer-enter", "click").open, true);
  assert.equal(run("pointer-enter", "click", "pointer-leave").open, false);
});

test("a second click or tap closes what a click opened", () => {
  assert.equal(run("click").open, true);
  assert.equal(run("click", "click").open, false);
  assert.equal(run("pointer-enter", "click", "click").open, false);
});

test("a tap opens it even when the tap also focused the button", () => {
  assert.equal(run("focus-in", "click").open, true);
  assert.equal(run("focus-in", "click", "click").open, false);
});

test("keyboard focus opens it and the pointer passing over does not close it", () => {
  assert.equal(run("focus-in").open, true);
  assert.equal(run("focus-in", "pointer-enter", "pointer-leave").open, true);
  assert.equal(run("focus-in", "focus-out").open, false);
});

test("Escape and a click elsewhere close it however it opened", () => {
  for (const opening of ["pointer-enter", "focus-in", "click"]) {
    assert.equal(run(opening, "escape").open, false, opening);
    assert.equal(run(opening, "outside").open, false, opening);
  }
});

test("after it closes, hover opens it again", () => {
  assert.deepEqual(run("click", "click", "pointer-enter"), { open: true, by: "hover" });
});

test("Escape anywhere on the page closes an open popover; focus goes back only from inside it", () => {
  assert.equal(escapeKey("Enter", true, true), null);
  assert.equal(escapeKey("Escape", false, true), null);
  // Opened by hover, with focus elsewhere on the page: it closes and focus stays where it is.
  assert.deepEqual(escapeKey("Escape", true, false), { close: true, refocus: false });
  assert.deepEqual(escapeKey("Escape", true, true), { close: true, refocus: true });
});
