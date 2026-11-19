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

export function inventoryOrigins(apps: LocatedItem['apps']): ComponentOrigin[] {
  return Object.entries(apps ?? {}).map(([app, state]) => ({
    type: 'observation', app: app as InventoryApp, scope: state.scope,
    locator: state.locator ?? state.provenance?.location ?? state.path,
  }));
}

export function componentLocations(item: LocatedItem): { owner?: string; scope?: string; location?: string; parent?: string }[] {
  const origins = [...(item.origins ?? []), ...inventoryOrigins(item.apps),
    ...(item.memberships ?? []).flatMap(member => inventoryOrigins(member.apps))];
  const locations = origins.filter(origin => origin.locator || origin.file || origin.path).map(origin => ({
    ...(origin.app ? { owner: observationAppName(origin.app, origin) } : {}),
    ...(origin.scope ? { scope: origin.scope } : {}),
    ...(origin.parentName ? { parent: origin.parentName } : {}),
    ...((origin.locator ?? origin.file ?? origin.path) ? { location: (origin.locator ?? origin.file ?? origin.path)!.replaceAll('\\', '/') } : {}),
  }));
  if (!locations.length) {
    const local = (!item.source?.repositoryUrl || !/^https?:/i.test(item.source.repositoryUrl) ? item.source?.path : undefined)
      ?? item.file ?? (item.sourceUrl && !/^https?:/i.test(item.sourceUrl) ? item.sourceUrl : undefined)
      ?? (item.source?.repositoryUrl && !/^https?:/i.test(item.source.repositoryUrl) ? item.source.repositoryUrl : undefined);
    if (local) locations.push({ location: local.replaceAll('\\', '/') });
  }
  const unique = new Map<string, (typeof locations)[number]>();
  for (const location of locations) {
    const key = JSON.stringify([location.owner, location.location]);
    unique.set(key, { ...unique.get(key), ...location });
  }
  return [...unique.values()];
}

export function displayDescription(item: LocatedItem) {
  // Older captures supplied this stock sentence even for Claude Desktop files.
  return item.kind === 'setting' && /^(?:Claude Code|Codex) configuration file\. Field types and choices are recorded for review\.$/.test(item.description ?? '')
    ? undefined : item.description;
}

export function componentSearchText(item: LocatedItem) {
  return [item.name, item.title, displayDescription(item), item.source?.repositoryUrl, item.source?.path, item.sourceUrl,
    ...componentLocations(item).flatMap(location => [location.owner, location.scope, location.location])].filter(Boolean).join(' ').toLowerCase();
}
