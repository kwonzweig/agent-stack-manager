import { useState } from 'react';
import { X } from 'lucide-react';
import type { CatalogItem, PackageKind, PackageSummary } from '../types';
import AddToMenu from './AddToMenu';
import ComponentGrid from './ComponentGrid';
import './catalog.css';

export interface CatalogPageProps {
  items: CatalogItem[];
  presets: PackageSummary[];
  sources: { name: string; url: string }[];
  isLoading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  onOpenItem: (item: CatalogItem) => void;
  onOpenPreset: (id: string) => void;
  onCreatePreset: (componentIds: string[], kind?: PackageKind) => void;
  onAdd: (packageId: string, componentIds: string[]) => Promise<void>;
}

export default function CatalogPage({
  items, presets, sources, isLoading, error, onRetry, onOpenItem, onOpenPreset, onCreatePreset, onAdd,
}: CatalogPageProps) {
  const [selection, setSelection] = useState<ReadonlySet<string>>(() => new Set());
  const [onlySelected, setOnlySelected] = useState(false);
  const selectedIds = items.filter((item) => selection.has(item.id) && item.type !== 'preset').map((item) => item.id);

  function select(changed: CatalogItem[], selected: boolean) {
    setSelection((previous) => {
      const next = new Set(previous);
      for (const item of changed) {
        if (item.type === 'preset') continue;
        if (selected) next.add(item.id);
        else next.delete(item.id);
      }
      return next;
    });
  }

  function clear() {
    setSelection(new Set());
    setOnlySelected(false);
  }

  function openItem(item: CatalogItem) {
    if (item.packageId) onOpenPreset(item.packageId);
    else onOpenItem(item);
  }

  return (
    <section className="aitmpl-catalog min-h-full pb-24" aria-label="Catalog">
      <ComponentGrid
        items={items}
        selection={selection}
        onlySelected={onlySelected && selectedIds.length > 0}
        targets={presets}
        isLoading={isLoading}
        error={error}
        onRetry={onRetry}
        onOpen={openItem}
        onSelect={select}
        onAdd={onAdd}
        onCreate={onCreatePreset}
      />
      {sources.length > 0 && (
        <details className="mx-4 sm:mx-6 text-[12px] text-[var(--color-text-secondary)]">
          <summary className="w-fit cursor-pointer">Catalog sources</summary>
          <ul className="flex flex-wrap gap-3 pt-2">
            {sources.map((source) => (
              <li key={source.url}>
                {/^https?:\/\//i.test(source.url)
                  ? <a className="underline underline-offset-2" href={source.url} rel="noreferrer" target="_blank">{source.name}</a>
                  : source.name}
              </li>
            ))}
          </ul>
        </details>
      )}
      {selectedIds.length > 0 && (
        <div className="pointer-events-none fixed inset-x-0 bottom-4 z-40 flex justify-center px-4 md:left-[220px]">
          <div role="region" aria-label="Selected components"
            className="pointer-events-auto flex flex-wrap items-center gap-2 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-0)] py-2 pl-3.5 pr-1.5 shadow-lg">
            <span className="text-[13px] font-semibold tabular-nums text-[var(--color-text-primary)]">{selectedIds.length} selected</span>
            <button type="button" aria-pressed={onlySelected} onClick={() => setOnlySelected((value) => !value)}
              className={'rounded-lg border px-3 py-1.5 text-[12px] font-medium transition-colors ' + (onlySelected
                ? 'border-[var(--color-accent)] bg-[var(--color-accent-light)] text-[var(--color-accent)]'
                : 'border-[var(--color-border)] text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-2)]')}>
              Show selected
            </button>
            <AddToMenu
              label={'Add ' + selectedIds.length + ' selected to a preset or stack'}
              targets={presets}
              placement="above"
              onAdd={async (packageId) => { await onAdd(packageId, selectedIds); clear(); }}
              onCreate={(kind) => onCreatePreset(selectedIds, kind)}
              triggerClassName="aitmpl-stack-accent flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[12px] font-semibold text-white"
            >
              Add to…
            </AddToMenu>
            <button type="button" onClick={clear} aria-label="Clear selection" title="Clear selection"
              className="rounded-lg p-1.5 text-[var(--color-text-tertiary)] hover:bg-[var(--color-surface-2)] hover:text-[var(--color-text-primary)]">
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
