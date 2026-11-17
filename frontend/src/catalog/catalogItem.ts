import type { CatalogItem, Source, SourceFacts } from '../types';

export function itemName(item: CatalogItem) {
  return item.title || item.name || item.kind;
}

export function itemRepository(item: CatalogItem) {
  return item.source?.repositoryUrl || '';
}

export type CatalogKind = 'all' | CatalogItem['kind'];

export function filterCatalogFacets(
  items: CatalogItem[],
  kind: CatalogKind,
  repositories: readonly string[],
  minimumStars: number | null,
) {
  if (kind === 'all' && !repositories.length && minimumStars === null) return items;

  const selected = new Set(repositories);
  return items.filter((item) =>
    (kind === 'all' || item.kind === kind)
    && (!selected.size || selected.has(itemRepository(item)))
    && (minimumStars === null || (item.stars != null && item.stars >= minimumStars)),
  );
}

// Most stars first; entries without a repository go last, and catalog order holds among equal counts.
export function byStars(items: CatalogItem[]) {
  return [...items].sort((a, b) => (b.stars ?? -1) - (a.stars ?? -1));
}

// "318.3K" for stars or installs.
export function countLabel(count: number) {
  return new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 }).format(count);
}

// When a value was read from its source, in the viewer's time: "Nov 16, 2026, 10:42 AM".
export function readAtLabel(iso?: string) {
  const time = iso ? new Date(iso) : undefined;
  return time && !Number.isNaN(time.getTime())
    ? time.toLocaleString('en', { dateStyle: 'medium', timeStyle: 'short' }) : 'unknown';
}

export function starsTitle(item: SourceFacts) {
  return (item.stars ?? 0).toLocaleString('en') + ' GitHub stars, read ' + readAtLabel(item.starsReadAt);
}

export function installsTitle(item: SourceFacts) {
  return (item.installs ?? 0).toLocaleString('en') + ' skills.sh installs, read ' + readAtLabel(item.installsReadAt);
}

// Each Catalog item with what its source says, once GET /api/catalog/sources has answered.
export function withSourceFacts<T extends { id: string }>(items: T[], facts: Record<string, SourceFacts>): T[] {
  return items.map((item) => (facts[item.id] ? { ...item, ...facts[item.id] } : item));
}

// "obra/superpowers" for a GitHub URL, otherwise the host and path.
export function repositoryLabel(url: string) {
  return url.replace(/^https?:\/\/(www\.)?github\.com\//i, '').replace(/^https?:\/\//i, '').replace(/(\.git)?\/?$/, '');
}

// Where a component comes from: its repository as the Catalog card names it, else the host of its page.
export function sourceLabel(item: { kind: string; sourceUrl?: string | null; source?: Source | null }) {
  if (item.source?.repositoryUrl) return repositoryLabel(item.source.repositoryUrl);
  if (item.sourceUrl && /^https?:\/\//i.test(item.sourceUrl)) {
    try { return new URL(item.sourceUrl).hostname; } catch { /* not a URL */ }
  }
  return item.kind === 'package' ? 'Local stack' : 'Local';
}
