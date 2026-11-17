import assert from "node:assert/strict";
import test from "node:test";
import { byStars, countLabel, filterCatalogFacets, installsTitle, sourceLabel, starsTitle } from "../src/catalog/catalogItem.ts";

const item = (id, stars) => ({ id, type: "component", kind: "skill", name: id, ...(stars === undefined ? {} : { stars, starsCheckedOn: "2026-11-16" }) });

test("the Stars order puts the most-starred repository first", () => {
  const items = [item("a", 10), item("b", 300), item("c", 0)];
  assert.deepEqual(byStars(items).map((entry) => entry.id), ["b", "a", "c"]);
});

test("entries without stars go last and catalog order holds among equal counts", () => {
  const items = [item("preset"), item("first", 5), item("second", 5), item("hook")];
  assert.deepEqual(byStars(items).map((entry) => entry.id), ["first", "second", "preset", "hook"]);
});

test("the Stars order leaves the given list as it was", () => {
  const items = [item("a", 1), item("b", 2)];
  byStars(items);
  assert.deepEqual(items.map((entry) => entry.id), ["a", "b"]);
});

test("a card shows the count short and names the exact count and the day it was read", () => {
  assert.equal(countLabel(318282), "318.3K");
  assert.equal(countLabel(0), "0");
  assert.equal(starsTitle(item("a", 318282)), "318,282 GitHub stars, read on 2026-11-16");
  assert.equal(installsTitle({ installs: 432022, installsCheckedOn: "2026-11-16" }), "432,022 skills.sh installs, read on 2026-11-16");
});

test("a preset's component names its repository as the Catalog card does", () => {
  const superpowers = { source: { repositoryUrl: "https://github.com/obra/superpowers", path: "skills/brainstorming" },
    sourceUrl: "https://github.com/obra/superpowers/blob/HEAD/skills/brainstorming" };
  assert.equal(sourceLabel({ kind: "skill", ...superpowers }), "obra/superpowers");
  assert.equal(sourceLabel({ kind: "skill", sourceUrl: "https://example.com/docs/skill" }), "example.com");
  assert.equal(sourceLabel({ kind: "skill" }), "Local");
  assert.equal(sourceLabel({ kind: "package", source: null }), "Local stack");
});

test("kind and minimum stars narrow the results across all selected repositories", () => {
  const firstRepo = "https://github.com/example/first";
  const secondRepo = "https://github.com/example/second";
  const thirdRepo = "https://github.com/example/third";
  const items = [
    { ...item("at-threshold", 500), source: { repositoryUrl: firstRepo } },
    { ...item("other-selected-repo", 700), source: { repositoryUrl: secondRepo } },
    { ...item("low-stars", 499), source: { repositoryUrl: firstRepo } },
    { ...item("wrong-kind", 900), kind: "hook", source: { repositoryUrl: firstRepo } },
    { ...item("unselected-repo", 900), source: { repositoryUrl: thirdRepo } },
  ];
  const results = filterCatalogFacets(items, "skill", [firstRepo, secondRepo], 500);
  assert.deepEqual(results.map((entry) => entry.id), ["at-threshold", "other-selected-repo"]);
});

test("a zero-star minimum includes known zero counts and excludes missing counts", () => {
  const items = [item("zero", 0), item("unknown"), item("popular", 100)];
  const results = filterCatalogFacets(items, "all", [], 0);
  assert.deepEqual(results.map((entry) => entry.id), ["zero", "popular"]);
  assert.deepEqual(filterCatalogFacets(items, "all", [], null).map((entry) => entry.id), ["zero", "unknown", "popular"]);
});
