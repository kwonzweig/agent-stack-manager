import type { CatalogItem } from '../types';

export function itemName(item: CatalogItem) {
  return item.title || item.name || item.kind;
}
