// Grid and list cards from AITMPL dashboard/src/components/ComponentGrid.tsx (MIT).
import { useState } from 'react';
import type { CatalogItem, PackageKind, PackageSummary } from '../types';
import { KIND_STYLES } from '../lib/kinds';
import { KindIcon } from '../components/ComponentUI';
import AddToMenu from './AddToMenu';
import Checkbox from './Checkbox';
import ItemProperties from './ItemProperties';
import { itemName } from './catalogItem';
import { componentLocations, displayDescription } from '../lib/componentLocation';
import { ComponentLocation } from '../components/ComponentLocation';

interface Props {
  item: CatalogItem;
  index: number;
  viewMode: 'grid' | 'list';
  selected: boolean;
  targets: PackageSummary[];
  onOpen: (item: CatalogItem) => void;
  onSelect: (item: CatalogItem, selected: boolean) => void;
  onAdd: (packageId: string, componentIds: string[]) => Promise<void>;
  onCreate: (componentIds: string[], kind: PackageKind) => void;
  /** Unset when the grid already groups entries under their repository. */
  onRepository?: (repository: string) => void;
}

export default function ComponentCard({ item, index, viewMode, selected, targets, onOpen, onSelect, onAdd, onCreate, onRepository }: Props) {
  const [menuOpen, setMenuOpen] = useState(false);
  const config = KIND_STYLES[item.kind];
  const name = itemName(item);
  const description = displayDescription(item);
  const isList = viewMode === 'list';
  const selectable = item.type !== 'preset' && item.addable !== false;
  const chips = <ItemProperties item={item} repository={onRepository} />;

  return (
    <article
      data-component-id={item.canonicalId ?? item.id}
      className={'group relative flex rounded-md bg-[var(--color-card-bg)] border hover:bg-[var(--color-card-hover)] hover:border-[var(--color-accent)] transition-all duration-150 cursor-pointer animate-fade-in-up ' +
        (selected ? 'border-[var(--color-accent)] ring-1 ring-[var(--color-accent)] ' : 'border-[var(--color-border)] ') +
        (menuOpen ? 'z-20 ' : '') +
        (isList ? 'items-center gap-4 p-4' : 'items-start gap-3.5 p-5')}
      style={{ animationDelay: index * (isList ? 30 : 50) + 'ms', animationFillMode: 'both' }}
    >
      <div className={'flex w-4 shrink-0 items-center ' + (isList ? '' : 'h-10')}>
        {selectable && <Checkbox checked={selected} label={'Select ' + name} onChange={(checked) => onSelect(item, checked)} />}
      </div>
      <div
        className={'rounded flex items-center justify-center shrink-0 ' + (isList ? 'w-11 h-11' : 'w-10 h-10')}
        style={{ backgroundColor: config.color + '15', color: config.color, border: '1px solid ' + config.color + '30' }}
      >
        <KindIcon kind={item.kind} pluginHost={item.pluginHost} className={isList ? 'h-[22px] w-[22px]' : 'h-5 w-5'} />
      </div>

      <div className="flex min-w-0 flex-1 flex-col self-stretch">
        <h3 className={'font-mono text-[14px] font-bold text-[var(--color-text-primary)] group-hover:text-[var(--color-accent)] transition-colors ' +
          (isList ? 'mb-1' : 'leading-tight mb-1.5')}>
          <button type="button" className="text-left break-words after:absolute after:inset-0 after:rounded-md focus-visible:outline-none focus-visible:after:outline focus-visible:after:outline-2 focus-visible:after:outline-[var(--color-primary-500)]" onClick={() => onOpen(item)}>
            {name}
          </button>
        </h3>
        {description && (
          <p className={'text-[12px] text-[var(--color-text-secondary)] ' + (isList ? 'line-clamp-1 leading-relaxed' : 'line-clamp-2 leading-[1.6]')}>
            {description}
          </p>
        )}
        {componentLocations(item).length > 0 && <div className="mt-1.5"><ComponentLocation item={item} /></div>}
        {/* In the grid the properties sit at the card's bottom, so cards in one row line up. */}
        <div className={'flex flex-wrap items-center gap-2 ' + (isList ? 'mt-1.5 sm:hidden' : 'mt-auto pt-3')}>{chips}</div>
      </div>

      {isList && <div className="hidden sm:flex min-w-0 max-w-[40%] items-center gap-2 shrink-0">{chips}</div>}
      {selectable && (
        <AddToMenu
          label={'Add ' + name + ' to a preset or stack'}
          targets={targets}
          exclude={item.packageId}
          onAdd={(packageId) => onAdd(packageId, [item.id])}
          onCreate={(kind) => onCreate([item.id], kind)}
          onOpenChange={setMenuOpen}
          triggerClassName={'w-8 h-8 rounded flex items-center justify-center transition-all duration-150 border ' + (menuOpen
            ? 'bg-[var(--color-surface-2)] text-[var(--color-accent)] border-[var(--color-border)]'
            : 'text-[var(--color-text-tertiary)] opacity-75 group-hover:opacity-100 focus-visible:opacity-100 hover:text-[var(--color-accent)] hover:bg-[var(--color-surface-2)] border-transparent hover:border-[var(--color-border)]')}
        >
          <svg aria-hidden="true" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
          </svg>
        </AddToMenu>
      )}
    </article>
  );
}
