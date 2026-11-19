import { compactLocationGroups, componentLocations } from '../lib/componentLocation';
import type { CatalogItem, Component } from '../types';

export function ComponentLocation({ item, compact = false }: { item: Component | CatalogItem; compact?: boolean }) {
  const locations = componentLocations(item);
  if (!locations.length) return null;
  if (compact) {
    const groups = compactLocationGroups(item);
    return <div className="space-y-1.5 text-[12px] leading-[1.5] text-muted" aria-label="Observed origin">
      {groups.map((group, index) => <dl key={index} className="flex min-w-0 flex-wrap gap-x-4 gap-y-0.5">
        {group.owner && <div className="flex min-w-0 gap-2"><dt>App</dt><dd className="min-w-0 break-words text-secondary">{group.owner}</dd></div>}
        {group.scope && <div className="flex min-w-0 gap-2"><dt>Scope</dt><dd className="min-w-0 break-words">{group.scope}</dd></div>}
        {group.parent && <div className="flex min-w-0 gap-2"><dt>Container</dt><dd className="min-w-0 break-words">{group.parent}</dd></div>}
        {group.files.length > 0 && <div className="grid min-w-0 basis-full grid-cols-[3rem_minmax(0,1fr)] gap-x-2"><dt>Source</dt><dd className="min-w-0 space-y-0.5 [overflow-wrap:anywhere]">{group.files.map(location => <div key={location}>{location}</div>)}</dd></div>}
      </dl>)}
    </div>;
  }
  return <div className="space-y-2 text-[12px] leading-[1.5] text-muted" aria-label="Observed origin">
    {locations.map((location, index) => <dl key={index} className="grid min-w-0 grid-cols-[4rem_minmax(0,1fr)] gap-x-2 gap-y-0.5">
      {location.owner && <><dt>App</dt><dd className="min-w-0 break-words text-secondary">{location.owner}</dd></>}
      {location.scope && <><dt>Scope</dt><dd className="min-w-0 break-words">{location.scope}</dd></>}
      {location.location && <><dt>Source</dt><dd className="min-w-0 [overflow-wrap:anywhere]">{location.location}</dd></>}
      {location.parent && <><dt>Container</dt><dd className="min-w-0 [overflow-wrap:anywhere]">{location.parent}</dd></>}
    </dl>)}
  </div>;
}
