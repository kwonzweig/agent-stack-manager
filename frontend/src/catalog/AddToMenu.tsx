import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Plus } from 'lucide-react';
import type { PackageKind, PackageSummary } from '../types';
import { KIND_STYLES } from '../lib/kinds';
import { PresetIcon } from '../components/Sidebar';

interface Props {
  label: string;
  targets: PackageSummary[];
  /** A saved stack is never offered as a destination for itself. */
  exclude?: string;
  placement?: 'below' | 'above';
  triggerClassName: string;
  children: ReactNode;
  onAdd: (id: string) => Promise<void>;
  onCreate: (kind: PackageKind) => void;
  onOpenChange?: (open: boolean) => void;
}

// Destination menu: pick a saved preset or stack and the selection is saved into it at once.
export default function AddToMenu({
  label, targets, exclude, placement = 'below', triggerClassName, children, onAdd, onCreate, onOpenChange,
}: Props) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const openChange = useRef(onOpenChange);
  openChange.current = onOpenChange;
  const groups = (['preset', 'stack'] as const)
    .map((kind) => [kind, targets.filter((target) => target.kind === kind && target.id !== exclude)] as const)
    .filter(([, rows]) => rows.length);

  function toggle(next: boolean) {
    setOpen(next);
    setError('');
    openChange.current?.(next);
  }

  useEffect(() => {
    if (!open) return;
    panel.current?.querySelector('button')?.focus();
    const outside = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) toggle(false);
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      event.stopPropagation();
      toggle(false);
      trigger.current?.focus();
    };
    document.addEventListener('pointerdown', outside);
    document.addEventListener('keydown', escape);
    return () => {
      document.removeEventListener('pointerdown', outside);
      document.removeEventListener('keydown', escape);
    };
  }, [open]);

  useEffect(() => () => openChange.current?.(false), []);

  async function add(id: string) {
    setBusy(id);
    setError('');
    try {
      await onAdd(id);
      toggle(false);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not add to this preset.');
    } finally {
      setBusy('');
    }
  }

  const row = 'flex w-full items-center gap-2.5 rounded-md px-2 py-1.5 text-left text-[13px] text-[var(--color-text-primary)] transition-colors hover:bg-[var(--color-surface-2)] disabled:opacity-60';
  return (
    <div ref={root} className="relative z-[1] shrink-0">
      <button ref={trigger} type="button" className={triggerClassName} aria-label={label} title={label}
        aria-haspopup="true" aria-expanded={open} onClick={() => toggle(!open)}>
        {children}
      </button>
      {open && (
        <div ref={panel} role="group" aria-label={label}
          className={'absolute right-0 z-30 w-64 max-w-[calc(100vw-2rem)] rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-0)] p-1.5 shadow-lg ' +
            (placement === 'above' ? 'bottom-full mb-2' : 'top-full mt-1')}>
          <div className="max-h-64 overflow-y-auto">
            {groups.map(([kind, rows]) => (
              <div key={kind} className="mb-1">
                <p className="px-2 pb-1 pt-1.5 text-[11px] font-semibold text-[var(--color-text-tertiary)]">{KIND_STYLES[kind].plural}</p>
                {rows.map((target) => (
                  <button key={target.id} type="button" className={row} disabled={Boolean(busy)} onClick={() => void add(target.id)}>
                    <PresetIcon title={target.title} description={target.description} icon={target.icon} />
                    <span className="min-w-0 flex-1 truncate">{busy === target.id ? 'Adding…' : target.title}</span>
                    <span className="text-[11px] tabular-nums text-[var(--color-text-tertiary)]">{target.componentCount}</span>
                  </button>
                ))}
              </div>
            ))}
          </div>
          <div className={groups.length ? 'mt-1 border-t border-[var(--color-border)] pt-1' : ''}>
            {(['preset', 'stack'] as const).map((kind) => (
              <button key={kind} type="button" className={row} disabled={Boolean(busy)} onClick={() => { toggle(false); onCreate(kind); }}>
                <Plus className="h-4 w-4 shrink-0 text-[var(--color-text-tertiary)]" aria-hidden="true" />
                New {KIND_STYLES[kind].singular.toLowerCase()}…
              </button>
            ))}
          </div>
          {error && <p role="alert" className="px-2 pb-1 pt-1.5 text-[12px] text-red-600 dark:text-red-400">{error}</p>}
        </div>
      )}
    </div>
  );
}
