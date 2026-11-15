import { useEffect, useRef, useState } from 'react';
import type { CatalogItem, PackageKind, PackageSummary } from '../types';
import CartSidebar from './CartSidebar';
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
  onAddToPreset: (id: string, componentIds: string[]) => Promise<void>;
}

const STORAGE_KEY = 'asm.catalog.stack';

function readSelection(value: string | null): Set<string> {
  try {
    const ids: unknown = JSON.parse(value ?? '[]');
    return new Set(Array.isArray(ids) ? ids.filter((id): id is string => typeof id === 'string') : []);
  } catch {
    return new Set();
  }
}

function getSavedSelection() {
  try {
    return readSelection(localStorage.getItem(STORAGE_KEY));
  } catch {
    return new Set<string>();
  }
}

export default function CatalogPage({
  items, presets, sources, isLoading, error, onRetry, onOpenItem, onOpenPreset, onCreatePreset, onAddToPreset,
}: CatalogPageProps) {
  const [selection, setSelection] = useState(getSavedSelection);
  const remoteSelection = useRef<ReadonlySet<string> | null>(null);
  const byId = new Map(items.map((item) => [item.id, item]));
  const selected = [...selection].flatMap((id) => {
    const item = byId.get(id);
    return item && item.type !== 'preset' ? [item] : [];
  });

  useEffect(() => {
    if (selection === remoteSelection.current) return;
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify([...selection]));
    } catch {
      // The current stack stays available when browser storage is disabled.
    }
  }, [selection]);

  useEffect(() => {
    const sync = (event: StorageEvent) => {
      if (event.key !== STORAGE_KEY && event.key !== null) return;
      const next = readSelection(event.newValue);
      remoteSelection.current = next;
      setSelection(next);
    };
    window.addEventListener('storage', sync);
    return () => window.removeEventListener('storage', sync);
  }, []);

  function toggleItem(item: CatalogItem) {
    if (item.type === 'preset') return;
    setSelection((previous) => {
      const next = new Set(previous);
      if (!next.delete(item.id)) next.add(item.id);
      return next;
    });
  }

  function setMany(visibleItems: CatalogItem[], add: boolean) {
    setSelection((previous) => {
      const next = new Set(previous);
      for (const item of visibleItems) {
        if (add) next.add(item.id);
        else next.delete(item.id);
      }
      return next;
    });
  }

  function openItem(item: CatalogItem) {
    if (item.packageId) onOpenPreset(item.packageId);
    else onOpenItem(item);
  }

  const presetOptions = presets.filter((preset) => preset.kind === 'preset');

  return (
    <section className="aitmpl-catalog min-h-full pb-16" aria-label="Catalog">
      <ComponentGrid
        items={items}
        selection={selection}
        isLoading={isLoading}
        error={error}
        onRetry={onRetry}
        onOpen={openItem}
        onToggle={toggleItem}
        onSetMany={setMany}
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
      <CartSidebar
        selected={selected}
        presets={presetOptions}
        onRemove={toggleItem}
        onClear={() => setSelection(new Set())}
        onCreate={onCreatePreset}
        onAdd={onAddToPreset}
      />
    </section>
  );
}
