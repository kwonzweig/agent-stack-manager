import type { CatalogItem } from '../types';

export function itemName(item: CatalogItem) {
  return item.title || item.name || item.kind;
}

export function itemRepository(item: CatalogItem) {
  return item.source?.repositoryUrl || '';
}

// Most stars first; entries without a repository go last, and catalog order holds among equal counts.
export function byStars(items: CatalogItem[]) {
  return [...items].sort((a, b) => (b.stars ?? -1) - (a.stars ?? -1));
}

export function starsLabel(stars: number) {
  return new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 }).format(stars);
}

export function starsTitle(item: CatalogItem) {
  return (item.stars ?? 0).toLocaleString('en') + ' GitHub stars, read on ' + item.starsCheckedOn;
}

// "obra/superpowers" for a GitHub URL, otherwise the host and path.
export function repositoryLabel(url: string) {
  return url.replace(/^https?:\/\/(www\.)?github\.com\//i, '').replace(/^https?:\/\//i, '').replace(/(\.git)?\/?$/, '');
}
