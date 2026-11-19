import type { ComponentOrigin, ComponentMembership, InventoryApp, InventoryAppState, Source } from '../types';

type LocatedItem = {
  kind: string; name?: string; title?: string; description?: string;
  source?: Source | null; sourceUrl?: string | null; file?: string;
  origins?: ComponentOrigin[]; memberships?: ComponentMembership[];
  apps?: Partial<Record<InventoryApp, InventoryAppState>>;
};

export function observationAppName(app: InventoryApp, observation: { scope?: string; locator?: string; path?: string; provenance?: { location?: string } } = {}) {
  if (app === 'codex') return 'Codex';
  return /^desktop\b/i.test(observation.scope?.trim() ?? '')
    ? 'Claude Desktop' : 'Claude Code';
}

export function inventoryOrigins(apps: LocatedItem['apps'], parents?: ReadonlyMap<string, { name: string }>): ComponentOrigin[] {
  return Object.entries(apps ?? {}).map(([app, state]) => ({
    type: 'observation', app: app as InventoryApp, scope: state.scope,
    locator: state.locator ?? state.provenance?.location ?? state.path,
    ...(state.parentId ? { parentId: state.parentId,
      ...(parents?.get(state.parentId) ? { parentName: parents.get(state.parentId)!.name } : {}) } : {}),
  }));
}

export function componentLocations(item: LocatedItem): { owner?: string; scope?: string; location?: string; parent?: string }[] {
  const observations = [...(item.origins ?? []), ...inventoryOrigins(item.apps),
    ...(item.memberships ?? []).flatMap(member => inventoryOrigins(member.apps).map(origin => ({
      ...origin, presetId: member.presetId, inventoryId: member.inventoryId,
    })))];
  const compatible = (a: ComponentOrigin, b: ComponentOrigin) => a.app === b.app && a.scope === b.scope && a.parentId === b.parentId
    && (!a.presetId || !b.presetId || a.presetId === b.presetId)
    && (!a.inventoryId || !b.inventoryId || a.inventoryId === b.inventoryId);
  const origins = observations.map(origin => {
    if (!origin.parentId || origin.parentName) return origin;
    const names = new Set(observations.filter(other => compatible(origin, other)).map(other => other.parentName).filter(Boolean));
    return names.size === 1 ? { ...origin, parentName: [...names][0] } : origin;
  }).filter(origin => (origin.locator || origin.file || origin.path || origin.parentName)
    || !observations.some(other => compatible(origin, other) && (other.locator || other.file || other.path || other.parentName)));
  const locations = origins.filter(origin => origin.app || origin.scope || origin.parentName || origin.locator || origin.file || origin.path).map(origin => ({
    ...(origin.app ? { owner: observationAppName(origin.app, origin) } : {}),
    ...(origin.scope ? { scope: origin.scope } : {}),
    ...(origin.parentName ? { parent: origin.parentName } : {}),
    ...((origin.locator ?? origin.file ?? origin.path) ? { location: (origin.locator ?? origin.file ?? origin.path)!.replaceAll('\\', '/') } : {}),
  }));
  if (!locations.some(location => location.location)) {
    const local = (!item.source?.repositoryUrl || !/^https?:/i.test(item.source.repositoryUrl) ? item.source?.path : undefined)
      ?? item.file ?? (item.sourceUrl && !/^https?:/i.test(item.sourceUrl) ? item.sourceUrl : undefined)
      ?? (item.source?.repositoryUrl && !/^https?:/i.test(item.source.repositoryUrl) ? item.source.repositoryUrl : undefined);
    if (local) locations.push({ location: local.replaceAll('\\', '/') });
  }
  const unique = new Map<string, (typeof locations)[number]>();
  for (const location of locations) {
    const key = JSON.stringify([location.owner, location.scope, location.parent, location.location]);
    unique.set(key, { ...unique.get(key), ...location });
  }
  return [...unique.values()];
}

export function compactLocationGroups(item: LocatedItem) {
  const groups = new Map<string, { owner?: string; scope?: string; parent?: string; files: string[] }>();
  for (const location of componentLocations(item)) {
    const key = JSON.stringify([location.owner, location.scope, location.parent]);
    const group = groups.get(key) ?? { owner: location.owner, scope: location.scope, parent: location.parent, files: [] };
    if (location.location) group.files.push(location.location);
    groups.set(key, group);
  }
  const combined = new Map<string, { owners: Set<string>; scope?: string; parent?: string; files: string[] }>();
  for (const group of groups.values()) {
    const key = JSON.stringify([Boolean(group.owner), group.scope, group.parent, [...group.files].sort()]);
    const existing = combined.get(key) ?? { owners: new Set<string>(), scope: group.scope, parent: group.parent, files: group.files };
    if (group.owner) existing.owners.add(group.owner);
    combined.set(key, existing);
  }
  return [...combined.values()].map(({ owners, ...group }) => ({ owner: owners.size ? [...owners].join(', ') : undefined, ...group }));
}

export function displayDescription(item: LocatedItem) {
  // Older captures supplied this stock sentence even for Claude Desktop files.
  return item.kind === 'setting' && /^(?:Claude Code|Codex) configuration file\. Field types and choices are recorded for review\.$/.test(item.description ?? '')
    ? undefined : item.description;
}

export function componentSearchText(item: LocatedItem) {
  return [item.name, item.title, displayDescription(item), item.source?.repositoryUrl, item.source?.path, item.sourceUrl,
    ...componentLocations(item).flatMap(location => [location.owner, location.scope, location.parent, location.location])].filter(Boolean).join(' ').toLowerCase();
}
