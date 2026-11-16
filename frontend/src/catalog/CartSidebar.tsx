// Adapted from AITMPL dashboard/src/components/CartSidebar.tsx (MIT).
import { useRef, useState } from 'react';
import type { CatalogItem, PackageKind, PackageSummary } from '../types';
import { KIND_STYLES } from '../lib/kinds';
import { KindIcon } from '../components/ComponentUI';
import { itemName } from './catalogItem';

interface Props {
  selected: CatalogItem[];
  presets: PackageSummary[];
  onRemove: (item: CatalogItem) => void;
  onClear: () => void;
  onCreate: (componentIds: string[], kind: PackageKind) => void;
  onAdd: (presetId: string, componentIds: string[]) => Promise<void>;
}

export default function CartSidebar({ selected, presets, onRemove, onClear, onCreate, onAdd }: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [presetId, setPresetId] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const cart = new Map<CatalogItem['kind'], CatalogItem[]>();
  for (const item of selected) {
    const items = cart.get(item.kind);
    if (items) items.push(item);
    else cart.set(item.kind, [item]);
  }
  const totalItems = selected.length;
  const itemIds = selected.map((item) => item.id);
  const destination = presets.find((preset) => preset.id === presetId);
  const close = () => dialog.current?.close();

  async function addToPreset() {
    if (!destination || saving || !totalItems) return;
    setSaving(true);
    setError('');
    try {
      await onAdd(destination.id, itemIds);
      close();
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Could not open the selected preset.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      {/* Floating button */}
      {totalItems > 0 && (
        <button
          onClick={() => dialog.current?.showModal()}
          type="button"
          aria-haspopup="dialog"
          className="fixed bottom-6 right-6 z-40 flex items-center gap-2.5 pl-4 pr-3 py-3 aitmpl-stack-accent text-white rounded-full shadow-lg shadow-[0_10px_15px_-3px_var(--color-accent-light)] transition-all duration-200 hover:scale-105 hover:shadow-xl active:scale-95"
        >
          <svg aria-hidden="true" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
            <path strokeLinecap="round" strokeLinejoin="round" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
          </svg>
          <span className="text-[13px] font-semibold">Stack</span>
          <span className="min-w-5 h-5 px-1.5 rounded-full bg-white/25 backdrop-blur-sm text-white text-[11px] font-bold flex items-center justify-center border border-white/20">
            {totalItems}
          </span>
        </button>
      )}

      <dialog
        ref={dialog}
        aria-labelledby="aitmpl-stack-title"
        onClick={(event) => {
          if (event.target === event.currentTarget) close();
        }}
        onClose={() => setError('')}
        className="aitmpl-stack-dialog fixed inset-auto top-0 right-0 m-0 h-dvh max-h-none w-96 max-w-[90vw] border-l border-[var(--color-border)] bg-[var(--color-surface-0)] text-[var(--color-text-primary)] shadow-2xl"
      >
        <div className="flex flex-col h-full">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-4 border-b border-[var(--color-border)] bg-gradient-to-b from-[var(--color-surface-1)] to-[var(--color-surface-0)] shrink-0">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg aitmpl-stack-accent flex items-center justify-center shadow-md shadow-[0_4px_6px_-1px_var(--color-accent-light)]">
                <svg aria-hidden="true" className="w-[18px] h-[18px] text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
                </svg>
              </div>
              <div className="flex flex-col">
                <h2 id="aitmpl-stack-title" className="text-[15px] font-semibold text-[var(--color-text-primary)] leading-none">Stack Builder</h2>
                <span className="text-[11px] text-[var(--color-text-tertiary)] mt-1">
                  {totalItems} {totalItems === 1 ? 'component' : 'components'}
                </span>
              </div>
            </div>
            <div className="flex items-center gap-1.5">
              {totalItems > 0 && (
                <button
                  onClick={onClear} disabled={saving}
                  className="text-xs text-[var(--color-text-tertiary)] hover:text-red-400 hover:bg-red-400/10 px-3 py-1.5 rounded-lg transition-all font-medium"
                >
                  Clear All
                </button>
              )}
              <button
                onClick={close}
                className="p-2 rounded-lg hover:bg-[var(--color-surface-3)] text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] transition-colors"
                aria-label="Close stack"
                title="Close stack"
                autoFocus
              >
                <svg aria-hidden="true" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>
          {/* Content */}
          <div className="flex-1 overflow-y-auto min-h-0">
            {totalItems === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center px-6">
                <div className="relative w-24 h-24 rounded-2xl bg-gradient-to-br from-[var(--color-surface-2)] to-[var(--color-surface-3)] border border-[var(--color-border)] flex items-center justify-center mb-5 shadow-sm">
                  <svg aria-hidden="true" className="w-12 h-12 text-[var(--color-text-tertiary)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
                  </svg>
                  <div className="absolute -top-1.5 -right-1.5 w-7 h-7 rounded-full bg-[var(--color-accent)]/10 border-2 border-[var(--color-accent)]/30 flex items-center justify-center backdrop-blur-sm">
                    <svg aria-hidden="true" className="w-3.5 h-3.5 text-[var(--color-accent)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
                    </svg>
                  </div>
                </div>
                <p className="text-base font-semibold text-[var(--color-text-primary)] mb-2">Your stack is empty</p>
              </div>
            ) : (
              <div className="px-3 py-4">
                {Array.from(cart).map(([type, items], idx, arr) => {
                  const config = KIND_STYLES[type];
                  const isLast = idx === arr.length - 1;
                  return (
                    <div key={type} className={!isLast ? 'mb-4 pb-3 border-b border-[var(--color-border)]' : 'mb-2'}>
                      {/* Folder row */}
                      <div className="flex items-center gap-2.5 py-2 px-3 rounded-lg bg-[var(--color-surface-1)] border border-[var(--color-border)] mb-2 shadow-sm">
                        <KindIcon kind={type} className="w-4 h-4 shrink-0" style={{ color: config?.color ?? 'var(--color-text-tertiary)' }} />
                        <span className="text-[13px] font-semibold text-[var(--color-text-primary)]">
                          {config?.plural ?? type}
                        </span>
                        <span className="ml-auto text-[10px] px-2 py-0.5 rounded-full bg-[var(--color-surface-3)] text-[var(--color-text-tertiary)] font-semibold tabular-nums border border-[var(--color-border)]">
                          {items.length}
                        </span>
                      </div>
                      {/* File rows with tree lines */}
                      {items.map((item, i) => {
                        const isLastItem = i === items.length - 1;
                        return (
                          <div
                            key={item.id}
                            className="flex items-center group pl-2 pr-1.5 py-0.5 hover:bg-[var(--color-surface-1)] rounded-md transition-all duration-150"
                          >
                            {/* Tree connector */}
                            <span aria-hidden="true" className="text-[var(--color-border)] text-[13px] font-mono w-7 shrink-0 select-none">
                              {isLastItem ? '└─' : '├─'}
                            </span>
                            {/* File icon */}
                            <svg aria-hidden="true" className="w-3.5 h-3.5 shrink-0 mr-2.5 text-[var(--color-text-tertiary)] group-hover:text-[var(--color-text-secondary)] transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                              <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
                              <polyline points="14 2 14 8 20 8" />
                            </svg>
                            {/* Name */}
                            <span className="text-[12px] text-[var(--color-text-primary)] flex-1 truncate py-2 font-medium">
                              {itemName(item)}
                            </span>
                            {/* Remove */}
                            <button
                              onClick={() => onRemove(item)}
                              disabled={saving}
                              className="opacity-75 group-hover:opacity-100 focus-visible:opacity-100 p-1.5 rounded-md hover:bg-red-400/10 text-[var(--color-text-tertiary)] hover:text-red-400 transition-all shrink-0"
                              title="Remove from stack"
                              aria-label={`Remove ${itemName(item)}`}
                            >
                              <svg aria-hidden="true" className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                              </svg>
                            </button>
                          </div>
                        );
                      })}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
          {totalItems > 0 && (
            <footer className="border-t border-[var(--color-border)] bg-gradient-to-t from-[var(--color-surface-1)] to-[var(--color-surface-0)] p-4 space-y-3 shadow-[0_-8px_16px_rgba(0,0,0,0.08)] shrink-0">
              <div className="flex gap-2">
                <button
                  type="button"
                  disabled={saving}
                  onClick={() => { close(); onCreate(itemIds, 'preset'); }}
                  className="aitmpl-stack-accent flex-1 flex items-center justify-center gap-2 px-4 py-2.5 text-white rounded-lg text-sm font-semibold transition-all duration-200 shadow-md hover:shadow-lg active:scale-95 disabled:opacity-60"
                >
                  <svg aria-hidden="true" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
                  </svg>
                  Create preset
                </button>
                <button
                  type="button"
                  disabled={saving}
                  onClick={() => { close(); onCreate(itemIds, 'stack'); }}
                  className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 bg-[var(--color-surface-2)] hover:bg-[var(--color-surface-3)] text-[var(--color-text-primary)] rounded-lg text-[13px] font-medium transition-colors border border-[var(--color-border)] disabled:opacity-60"
                >
                  Create stack
                </button>
              </div>
              {presets.length > 0 && (
                <form
                  className="flex gap-2"
                  onSubmit={(event) => { event.preventDefault(); void addToPreset(); }}
                >
                  <select
                    aria-label="Existing preset"
                    value={presetId}
                    onChange={(event) => { setPresetId(event.target.value); setError(''); }}
                    disabled={saving}
                    className="flex-1 min-w-0 px-2 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] text-[13px]"
                  >
                    <option value="">Choose a preset</option>
                    {presets.map((preset) => <option key={preset.id} value={preset.id}>{preset.title}</option>)}
                  </select>
                  <button
                    type="submit"
                    disabled={!destination || saving}
                    className="flex items-center justify-center gap-1.5 px-3 py-2 bg-[var(--color-surface-2)] hover:bg-[var(--color-surface-3)] text-[var(--color-text-primary)] rounded-lg text-[13px] font-medium transition-colors border border-[var(--color-border)] disabled:opacity-60"
                  >
                    {saving ? 'Opening…' : 'Add to preset'}
                  </button>
                </form>
              )}
              {error && <p role="alert" className="text-[13px] text-red-700">{error}</p>}
            </footer>
          )}
        </div>
      </dialog>
    </>
  );
}
