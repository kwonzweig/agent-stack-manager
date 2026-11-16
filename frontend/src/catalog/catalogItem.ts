import type { CatalogItem } from '../types';

export function itemName(item: CatalogItem) {
  return item.title || item.name || item.kind;
}

export function itemRepository(item: CatalogItem) {
  return item.source?.repositoryUrl || '';
}

// "obra/superpowers" for a GitHub URL, otherwise the host and path.
export function repositoryLabel(url: string) {
  return url.replace(/^https?:\/\/(www\.)?github\.com\//i, '').replace(/^https?:\/\//i, '').replace(/(\.git)?\/?$/, '');
}
