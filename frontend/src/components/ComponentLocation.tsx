import { componentLocations } from '../lib/componentLocation';
import type { CatalogItem, Component } from '../types';

export function ComponentLocation({ item }: { item: Component | CatalogItem }) {
  const locations = componentLocations(item);
  if (!locations.length) return null;
  return <div className="space-y-2 text-[12px] leading-[1.5] text-muted" aria-label="Observed origin">
    {locations.map((location, index) => <dl key={index} className="grid min-w-0 grid-cols-[3rem_minmax(0,1fr)] gap-x-2 gap-y-0.5">
      {location.owner && <><dt>App</dt><dd className="min-w-0 break-words text-secondary">{location.owner}</dd></>}
      {location.scope && <><dt>Scope</dt><dd className="min-w-0 break-words">{location.scope}</dd></>}
      <dt>Source</dt><dd className="min-w-0 [overflow-wrap:anywhere]">{location.location ?? 'Not recorded'}</dd>
      {location.parent && <><dt>Container</dt><dd className="min-w-0 [overflow-wrap:anywhere]">{location.parent}</dd></>}
    </dl>)}
  </div>;
}
