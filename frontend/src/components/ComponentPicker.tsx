import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Check, Plus, X } from "lucide-react";
import { cn } from "../utils";
import type { Component, Kind, PackageKind } from "../types";
import { KindBadge, KINDS, SearchField, TypeFilter } from "./ComponentUI";
import { componentSearchText, displayDescription } from "../lib/componentLocation";
import { repositoryLabel } from "../catalog/catalogItem";
import { ComponentLocation } from "./ComponentLocation";

// From Skills Manager's AddSkillsSheet and SkillPickerRow.
export function ComponentPicker({ items, existing, packageKind, onClose, onAdd, error, loading, onRetry }: {
  items: Component[]; existing: Set<string>; packageKind: PackageKind; onClose: () => void; onAdd: (items: Component[]) => void;
  error?: string; loading?: boolean; onRetry: () => void;
}) {
  const noun = packageKind === "stack" ? "stack" : "preset";
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState<Kind | "all">("all");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const ref = useRef<HTMLDialogElement>(null);
  const pickerId = useId();
  useEffect(() => {
    const dialog = ref.current!;
    dialog.showModal();
    return () => dialog.close();
  }, []);
  const q = query.trim().toLowerCase();
  const visible = items.filter(item => (kind === "all" || item.kind === kind) &&
    componentSearchText(item).includes(q));
  const kinds = KINDS.filter(type => items.some(item => item.kind === type));
  const selected = items.filter(item => selectedIds.has(item.id) && !existing.has(item.id));

  return createPortal(<dialog ref={ref} aria-label="Add components"
    onCancel={e => { e.preventDefault(); onClose(); }}
    onClick={e => { if (e.target === e.currentTarget) onClose(); }}
    className="fixed inset-y-0 right-0 left-auto m-0 h-dvh max-h-none w-full max-w-[520px] overflow-hidden border-l border-border-subtle bg-surface text-primary shadow-2xl backdrop:bg-black/65">
    <div className="flex h-full flex-col">
      <div className="flex shrink-0 items-start justify-between gap-3 border-b border-border-subtle px-5 py-4">
        <h2 className="text-[14px] font-semibold text-primary">Add components</h2>
        <button type="button" onClick={onClose} aria-label="Close picker" className="rounded-md p-1.5 text-muted transition-colors hover:bg-surface-hover hover:text-secondary"><X className="h-4 w-4" /></button>
      </div>
      <div className="shrink-0 space-y-2 border-b border-border-subtle px-5 py-3">
        <SearchField value={query} onChange={setQuery} />
        <TypeFilter kinds={kinds} active={kind} onChange={setKind} />
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto scrollbar-hide">
        {loading ? <p role="status" className="px-5 py-12 text-center text-[13px] text-muted">Loading catalog…</p> :
        error ? <p role="alert" className="px-5 py-12 text-center text-[13px] text-danger">{error} <button className="underline" onClick={onRetry}>Retry</button></p> :
        visible.length ? <div className="divide-y divide-border-subtle">
          {visible.map(item => {
            const included = existing.has(item.id);
            const selected = selectedIds.has(item.id);
            const inputId = pickerId + item.id;
            return <div key={item.id} className={cn("relative flex select-none items-center gap-3 px-5 py-2.5 transition-colors",
              included ? "opacity-60" : "cursor-pointer hover:bg-surface-hover", selected && "bg-accent-bg")}>
              <input id={inputId} type="checkbox" checked={included || selected} disabled={included} className="sr-only peer"
                onChange={() => setSelectedIds(prev => { const next = new Set(prev); if (!next.delete(item.id)) next.add(item.id); return next; })} />
              <span className={cn("flex h-4 w-4 shrink-0 items-center justify-center rounded-[4px] border transition-colors peer-focus-visible:ring-2 peer-focus-visible:ring-accent",
                included || selected ? "border-accent bg-accent text-white" : "border-border")}>
                {(included || selected) && <Check className="h-3 w-3" />}
              </span>
              <div className="min-w-0 flex-1">
                <span className="flex min-w-0 items-center gap-2">
                  <label htmlFor={inputId} className="cursor-[inherit] truncate text-[13px] font-medium text-primary after:absolute after:inset-0">{item.name}</label>
                  <KindBadge kind={item.kind} pluginHost={item.pluginHost} />
                </span>
                {displayDescription(item) && <p className="mt-0.5 truncate text-[12px] text-muted">{displayDescription(item)}</p>}
                {item.source?.repositoryUrl && <p className="break-words text-[12px] text-muted">{repositoryLabel(item.source.repositoryUrl)}</p>}
                <ComponentLocation item={item} compact />
              </div>
              {included && <span className="shrink-0 rounded-full bg-accent-bg px-2 py-0.5 text-[11px] font-medium text-accent">Already listed</span>}
            </div>;
          })}
        </div> : <p className="px-5 py-12 text-center text-[13px] text-muted">No matching components.</p>}
      </div>
      <div className="shrink-0 border-t border-border-subtle bg-bg-secondary px-5 py-3">
        <div className="mb-2 flex items-center justify-between gap-2">
          <span className="truncate text-[12px] text-muted">{selected.length} selected</span>
          <button type="button" onClick={() => setSelectedIds(new Set())} disabled={!selected.length}
            className="rounded-md px-2.5 py-1 text-[12px] font-medium text-muted hover:bg-surface-hover hover:text-secondary disabled:opacity-50">Clear</button>
        </div>
        <button type="button" onClick={() => onAdd(selected)} disabled={!selected.length} className="app-button-primary w-full">
          <Plus className="h-4 w-4" /> Add to {noun}
        </button>
      </div>
    </div>
  </dialog>, document.body);
}
