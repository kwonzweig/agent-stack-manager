import type { Component, Package, PackageKind } from "./types";

export interface Draft {
  original: Package;
  title: string;
  description: string;
  kind: PackageKind;
  workArea: string[];
  usage: string[];
  instruction: string;
  members: Component[];
}

const fields = ["title", "description", "kind", "workArea", "usage", "instruction"] as const;
type Field = (typeof fields)[number];
const equal = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);

export function createDraft(pkg: Package): Draft {
  const { title, description, kind, workArea, usage, instruction, components } = pkg;
  return { original: pkg, title, description, kind, workArea, usage, instruction,
    members: components.filter(item => item.id !== "instruction") };
}

export function makePayload({ original, members, title, description, kind, workArea, usage, instruction }: Draft) {
  return { revision: original.revision, title, description, kind, workArea, usage, instruction,
    componentIds: members.map(item => item.id) };
}

export function isDirty(draft: Draft) {
  return !equal(makePayload(draft), makePayload(createDraft(draft.original)));
}

export function overlappingChanges(draft: Draft, latest: Package): Field[] {
  return fields.filter(field => !equal(draft[field], draft.original[field]) &&
    !equal(latest[field], draft.original[field]) && !equal(draft[field], latest[field]));
}

export function rebaseDraft(draft: Draft, latest: Package, baseline = createDraft(draft.original)): Draft {
  const rebased = createDraft(latest);
  for (const field of fields) {
    if (!equal(draft[field], baseline[field])) Object.assign(rebased, { [field]: draft[field] });
  }
  const originalIds = new Set(baseline.members.map(item => item.id));
  const draftIds = new Set(draft.members.map(item => item.id));
  rebased.members = rebased.members.filter(item => !originalIds.has(item.id) || draftIds.has(item.id));
  const rebasedIds = new Set(rebased.members.map(item => item.id));
  rebased.members.push(...draft.members.filter(item => !originalIds.has(item.id) && !rebasedIds.has(item.id)));
  return rebased;
}


