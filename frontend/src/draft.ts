import type { Component, InventoryApp, InventoryItem, InventorySelection, Package, PackageKind } from "./types";

export interface Draft {
  original: Package;
  title: string;
  description: string;
  kind: PackageKind;
  icon: string;
  workArea: string[];
  usage: string[];
  instruction: string;
  members: Component[];
  appInventorySelections: Record<string, Partial<Record<InventoryApp, InventorySelection>>>;
}

const fields = ["title", "description", "kind", "icon", "workArea", "usage", "instruction"] as const;
type Field = (typeof fields)[number];
const equal = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);

export function createDraft(pkg: Package): Draft {
  const { title, description, kind, icon, workArea, usage, instruction, components } = pkg;
  return { original: pkg, title, description, kind, icon, workArea, usage, instruction,
    members: components.filter(item => item.id !== "instruction" && !item.managedByInventory), appInventorySelections: {} };
}

export function inventorySelection(draft: Draft, item: InventoryItem, app: InventoryApp) {
  const changes = Object.hasOwn(draft.appInventorySelections, item.id) ? draft.appInventorySelections[item.id] : {};
  return changes[app] === undefined ? item.apps[app]?.selected : changes[app];
}

export function withInventorySelection(draft: Draft, item: InventoryItem, app: InventoryApp, selected: InventorySelection): Draft {
  const selections = { ...draft.appInventorySelections };
  const itemChanges = Object.hasOwn(selections, item.id) ? { ...selections[item.id] } : {};
  if (item.apps[app]?.selected === selected) delete itemChanges[app];
  else itemChanges[app] = selected;
  if (!Object.keys(itemChanges).length) delete selections[item.id];
  else return { ...draft, appInventorySelections: { ...selections, [item.id]: itemChanges } };
  return { ...draft, appInventorySelections: selections };
}

// The saved package plus the given components it lacks; a package never contains itself.
export function withMembers(pkg: Package, items: Component[]) {
  const base = createDraft(pkg);
  const ids = new Set([...base.members.map(item => item.id), "package:" + pkg.id]);
  const added = items.filter(item => !ids.has(item.id) && ids.add(item.id));
  return { added, draft: { ...base, members: [...base.members, ...added] } };
}

export function makePayload({ original, members, title, description, kind, icon, workArea, usage, instruction, appInventorySelections }: Draft) {
  return { revision: original.revision, title, description, kind, icon, workArea, usage, instruction,
    componentIds: members.map(item => item.id),
    ...(Object.keys(appInventorySelections).length ? { appInventorySelections } : {}) };
}

export function isDirty(draft: Draft) {
  return !equal(makePayload(draft), makePayload(createDraft(draft.original)));
}

export function overlappingChanges(draft: Draft, latest: Package): Field[] {
  return fields.filter(field => !equal(draft[field], draft.original[field]) &&
    !equal(latest[field], draft.original[field]) && !equal(draft[field], latest[field]));
}

export function rebaseDraft(draft: Draft, latest: Package, baseline = createDraft(draft.original)): Draft {
  let rebased = createDraft(latest);
  for (const field of fields) {
    if (!equal(draft[field], baseline[field])) Object.assign(rebased, { [field]: draft[field] });
  }
  const originalIds = new Set(baseline.members.map(item => item.id));
  const draftIds = new Set(draft.members.map(item => item.id));
  rebased.members = rebased.members.filter(item => !originalIds.has(item.id) || draftIds.has(item.id));
  const rebasedIds = new Set(rebased.members.map(item => item.id));
  rebased.members.push(...draft.members.filter(item => !originalIds.has(item.id) && !rebasedIds.has(item.id)));
  const oldItems = new Map(draft.original.appInventory?.map(item => [item.id, item]));
  for (const item of latest.appInventory ?? []) {
    const old = oldItems.get(item.id);
    if (!old) continue;
    for (const app of ["codex", "claude"] as const) {
      if (!item.apps[app]) continue;
      const chosen = inventorySelection(draft, old, app);
      if (chosen !== undefined && chosen !== inventorySelection(baseline, old, app))
        rebased = withInventorySelection(rebased, item, app, chosen);
    }
  }
  return rebased;
}


