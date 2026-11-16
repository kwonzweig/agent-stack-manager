// Grid and list cards from AITMPL dashboard/src/components/ComponentGrid.tsx (MIT).
import { useState } from 'react';
import { FolderGit2 } from 'lucide-react';
import type { CatalogItem, PackageKind, PackageSummary } from '../types';
import { KIND_STYLES } from '../lib/kinds';
import { KindIcon } from '../components/ComponentUI';
import AddToMenu from './AddToMenu';
import Checkbox from './Checkbox';
import { itemName, itemRepository, repositoryLabel } from './catalogItem';

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
  const isList = viewMode === 'list';
  const selectable = item.type !== 'preset';
  const repository = itemRepository(item);
  const label = item.componentCount === undefined
    ? config.singular
    : item.componentCount + (item.componentCount === 1 ? ' component' : ' components');
  const chips = (
    <>
      <span className="font-mono text-[10px] font-semibold px-2 py-0.5 rounded border border-[var(--color-border)] bg-[var(--color-surface-2)] text-[var(--color-text-tertiary)]">
        {label}
      </span>
      {repository && onRepository && (
        <button type="button" onClick={() => onRepository(repository)}
          className="relative z-[1] inline-flex min-w-0 max-w-full items-center gap-1 rounded px-1.5 py-0.5 font-mono text-[11px] text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-2)] hover:text-[var(--color-accent)]"
          title={'Show everything from ' + repositoryLabel(repository)}>
          <FolderGit2 className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          <span className="truncate">{repositoryLabel(repository)}</span>
        </button>
      )}
    </>
  );

  return (
    <article
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
        <KindIcon kind={item.kind} className={isList ? 'h-[22px] w-[22px]' : 'h-5 w-5'} />
      </div>

      <div className="min-w-0 flex-1">
        <h3 className={'font-mono text-[14px] font-bold text-[var(--color-text-primary)] group-hover:text-[var(--color-accent)] transition-colors ' +
          (isList ? 'mb-1' : 'leading-tight mb-1.5')}>
          <button type="button" className="text-left break-words after:absolute after:inset-0 after:rounded-md focus-visible:outline-none focus-visible:after:outline focus-visible:after:outline-2 focus-visible:after:outline-[var(--color-primary-500)]" onClick={() => onOpen(item)}>
            {name}
          </button>
        </h3>
        {item.description && (
          <p className={'text-[12px] text-[var(--color-text-secondary)] ' + (isList ? 'line-clamp-1 leading-relaxed' : 'line-clamp-2 leading-[1.6]')}>
            {item.description}
          </p>
        )}
        <div className={'flex flex-wrap items-center gap-2 ' + (isList ? 'mt-1.5 sm:hidden' : 'mt-3')}>{chips}</div>
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
