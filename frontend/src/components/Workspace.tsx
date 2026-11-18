import { useState } from "react";
import { CheckSquare, ChevronRight, LayoutGrid, List, MessageSquare, Pencil, Plus, Save, Square, Trash2 } from "lucide-react";
import { sourceLabel, withSourceFacts } from "../catalog/catalogItem";
import { inventoryComponents, isDirty, type Draft } from "../draft";
import type { Component, Kind, SourceFacts } from "../types";
import { cn } from "../utils";
import { CardActionMenu } from "./CardActionMenu";
import { KindBadge, KindIcon, KINDS, SearchField, TypeFilter } from "./ComponentUI";
import { hrefFor, PresetIcon, type Route } from "./Sidebar";
import { PresetIconPicker } from "./PresetIconPicker";
import { inferPresetIconKey } from "../lib/presetIcons";
import "./preset.css";

export type WorkspaceTab = NonNullable<Route["tab"]>;
const tabs: { id: WorkspaceTab; label: string }[] = [
  { id: "components", label: "Components" }, { id: "export", label: "Export" }, { id: "source", label: "Source files" },
];

// Grid layout extracted from Skills Manager's WorkspaceView.
function WorkspaceCard({ item, selected, selectable, onSelect, onOpen, onRemove, canComment }: {
  item: Component; selectable: boolean; selected: boolean; onSelect: () => void;
  onOpen: () => void; onRemove: () => void; canComment: boolean;
}) {
  return <div data-component-id={item.canonicalId ?? item.id} className={cn("app-panel group relative flex h-full flex-col shadow-card transition-all hover:-translate-y-px hover:border-border hover:shadow-card-hover",
    selected && "border-accent-border ring-1 ring-accent-border")}>
    <div className="flex items-center gap-2.5 px-3.5 pb-1.5 pt-3">
      {selectable && item.id !== "instruction"
        ? <CheckItem item={item} selected={selected} onSelect={onSelect} />
        : <span className="flex h-4 w-4 shrink-0 items-center justify-center"><span className="h-2 w-2 rounded-full bg-accent-light shadow-[0_0_0_3px_var(--color-accent-bg)]" /></span>}
      <h3 className="min-w-0 flex-1 text-[14px] font-semibold text-primary group-hover:text-accent-light">
        <button type="button" className="block max-w-full truncate text-left before:absolute before:inset-0" title={item.name}
          onClick={selectable && item.id !== "instruction" ? onSelect : onOpen}>{item.name}</button>
      </h3>
      <KindIcon kind={item.kind} pluginHost={item.pluginHost} className="h-3.5 w-3.5 shrink-0 text-faint" />
    </div>
    <div className="px-3.5 pb-3">
      {item.description && <p className="truncate text-[13px] leading-[18px] text-muted" title={item.description}>{item.description}</p>}
      <div className={cn("flex flex-wrap items-center gap-1", item.description && "mt-2")}><KindBadge kind={item.kind} pluginHost={item.pluginHost} /></div>
    </div>
    <div className="mt-auto flex items-center justify-between gap-2 border-t border-border-faint px-3.5 py-2.5">
      <span className="truncate text-[12px] text-muted">{sourceLabel(item)}</span>
      <div className="relative z-10">
        <CardActionMenu label={`Actions for ${item.name}`} actions={[
          ...(canComment ? [{ key: "comment", label: "Comments", icon: <MessageSquare className="h-3.5 w-3.5" />, onSelect: onOpen }] : []),
          ...(item.inventoryId ? [{ key: "membership", label: "Edit membership", icon: <Pencil className="h-3.5 w-3.5" />, onSelect: onOpen }] :
            item.id === "instruction" ? [] : [{ key: "remove", label: "Remove", icon: <Trash2 className="h-3.5 w-3.5" />, onSelect: onRemove, danger: true }]),
        ]} />
      </div>
    </div>
  </div>;
}

function CheckItem({ item, selected, onSelect }: { item: Component; selected: boolean; onSelect: () => void }) {
  return <button className="relative z-10 flex h-4 w-4 shrink-0 items-center justify-center" type="button" role="checkbox"
    aria-checked={selected} aria-label={`Select ${item.name}`} onClick={onSelect}>
    {selected ? <CheckSquare className="h-3.5 w-3.5 text-accent" /> : <Square className="h-3.5 w-3.5 text-faint" />}
  </button>;
}

export function WorkspaceHeader({ draft, route, onNavigate, onEdit, onIcon, onSave, saving }: {
  draft: Draft; route: Route; onNavigate: (route: Route) => void;
  onEdit: () => void; onIcon: (icon: string) => void; onSave: () => void; saving: boolean;
}) {
  const dirty = isDirty(draft);
  const componentCount = draft.original.appInventory
    ? new Set([...draft.original.appInventory, ...draft.members].map(item => item.canonicalId ?? item.id)).size + Number(Boolean(draft.instruction.trim()))
    : draft.members.length + 1;
  const noun = draft.kind === "stack" ? "stack" : "preset";
  return <header className="app-page-header flex flex-col gap-2.5 pb-3">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2.5">
          <PresetIconPicker label={`Change ${noun} icon`} disabled={saving} onChange={onIcon}
            value={inferPresetIconKey({ name: draft.title, description: draft.description, icon: draft.icon })}>
            <PresetIcon title={draft.title} description={draft.description} icon={draft.icon} active className="h-7 w-7 rounded-lg [&>svg]:h-4 [&>svg]:w-4" />
          </PresetIconPicker>
          <h1 className="app-page-title flex min-w-0 flex-wrap items-center gap-2.5">
            <span className="min-w-0 break-words">{draft.title}</span>
            <span className="app-badge" aria-label={`${componentCount} components`}>{componentCount}</span>
            <button type="button" className="rounded-md p-1.5 text-muted transition-colors hover:bg-surface-hover hover:text-secondary"
              aria-label={`Edit ${noun} details`} title={`Edit ${noun} details`} onClick={onEdit} disabled={saving}><Pencil className="h-3.5 w-3.5" /></button>
          </h1>
        </div>
        {draft.description && <p className="app-page-subtitle break-words">{draft.description}</p>}
        {(draft.workArea.length > 0 || draft.usage.length > 0 || draft.kind === "stack") && <div className="mt-2 flex flex-wrap items-center gap-1.5">
          {draft.kind === "stack" && <KindBadge kind="package" />}
          {draft.workArea.map(value => <span key={value} title="Work area" className="rounded-full bg-surface-hover px-2.5 py-0.5 text-[12px] text-muted">{value}</span>)}
          {draft.usage.map(value => <span key={value} title="Usage" className="rounded-full bg-surface-hover px-2.5 py-0.5 text-[12px] text-muted">{value}</span>)}
        </div>}
      </div>
      {(dirty || saving) && <button type="button" className="app-button-primary" onClick={onSave} disabled={saving}>
        <Save className="h-4 w-4" /> {saving ? "Saving…" : "Save changes"}
      </button>}
    </div>
    <nav className="app-segmented w-fit max-w-full" aria-label={`${noun === "stack" ? "Stack" : "Preset"} sections`}>
      {tabs.map(tab => {
        const active = (route.tab || "components") === tab.id;
        const next = { ...route, tab: tab.id, consumer: undefined };
        return <a key={tab.id} href={hrefFor(next)} aria-current={active ? "page" : undefined}
          onClick={e => { if (!e.metaKey && !e.ctrlKey && !e.shiftKey && !e.altKey) { e.preventDefault(); onNavigate(next); } }}
          className={cn("app-segmented-button", active && "app-segmented-button-active")}>{tab.label}</a>;
      })}
    </nav>
  </header>;
}

export function PresetContents({ draft, facts, onOpen, onAdd, onRemove, busy }: {
  draft: Draft; onOpen: (item: Component) => void; onAdd: () => void;
  /** What each member's source says, from GET /api/catalog/sources. */
  facts: Record<string, SourceFacts>;
  onRemove: (ids: string[]) => void; busy: boolean;
}) {
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState<Kind | "all">("all");
  const [view, setView] = useState<"grid" | "list">(() => localStorage.getItem("asm:component-view") === "list" ? "list" : "grid");
  const [selectMode, setSelectMode] = useState(false);
  const [selection, setSelection] = useState<Set<string>>(new Set());
  const noun = draft.kind === "stack" ? "stack" : "preset";
  const instruction: Component = { ...draft.original.components.find(item => item.id === "instruction"),
    id: "instruction", name: "Instruction", kind: "instruction",
    description: draft.instruction ? draft.instruction.replace(/\s+/g, " ").trim() : `Add instructions for this ${noun}.`,
    configuration: draft.instruction };
  const rows = [
    ...(!draft.original.appInventory || draft.instruction.trim() ? [instruction] : []),
    ...withSourceFacts(inventoryComponents(draft.original.appInventory ?? []), facts),
    ...withSourceFacts(draft.members, facts),
  ];
  const all = [...new Map(rows.map(item => [item.canonicalId ?? item.id, item])).values()];
  const kinds = KINDS.filter(type => all.some(item => item.kind === type));
  const active = kind === "all" || kinds.includes(kind) ? kind : "all";
  const q = query.trim().toLowerCase();
  const visible = all.filter(item => (active === "all" || item.kind === active) &&
    `${item.name} ${item.description ?? ""} ${item.sourceUrl ?? item.source?.repositoryUrl ?? ""}`.toLowerCase().includes(q));
  const updateView = (next: "grid" | "list") => { localStorage.setItem("asm:component-view", next); setView(next); };
  const chosen = draft.members.filter(item => selection.has(item.id));
  const toggleSelection = (id: string) => setSelection(prev => {
    const next = new Set(prev); if (!next.delete(id)) next.add(id); return next;
  });
  const remove = (ids: string[]) => {
    onRemove(ids);
    setSelection(prev => new Set([...prev].filter(id => !ids.includes(id))));
  };

  return <section aria-label={`${noun === "stack" ? "Stack" : "Preset"} components`} className="space-y-3">
    <div className="app-toolbar">
      <SearchField value={query} onChange={setQuery} />
      <div className="flex flex-wrap items-center gap-2">
        <div className="app-segmented app-toolbar-segmented" role="group" aria-label="Component view">
          {([{ id: "grid", title: "Grid view", icon: LayoutGrid }, { id: "list", title: "List view", icon: List }] as const).map(({ id, title, icon: Icon }) =>
            <button key={id} type="button" aria-label={title} title={title} aria-pressed={view === id} onClick={() => updateView(id)}
              className={cn("rounded-md p-2 transition-colors", view === id ? "bg-surface-active text-secondary" : "text-muted hover:bg-surface-hover hover:text-tertiary")}>
              <Icon className="h-4 w-4" />
            </button>
          )}
          <span aria-hidden="true" className="mx-1 h-5 w-px self-center bg-border-subtle" />
          <button type="button" aria-label="Select components" title="Select components" aria-pressed={selectMode}
            onClick={() => { if (selectMode) setSelection(new Set()); setSelectMode(!selectMode); }}
            className={cn("rounded-md p-2 transition-colors", selectMode ? "bg-surface-active text-secondary" : "text-muted hover:bg-surface-hover hover:text-tertiary")}>
            <CheckSquare className="h-4 w-4" />
          </button>
        </div>
        <button type="button" className="app-toolbar-button app-toolbar-button-primary disabled:opacity-50"
          onClick={onAdd} disabled={busy}><Plus className="h-3.5 w-3.5" /> Add components</button>
      </div>
    </div>
    <TypeFilter kinds={kinds} active={active} onChange={setKind} />
    {selectMode && <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border-subtle bg-surface px-3 py-2 text-[13px] text-muted">
      <span>{chosen.length} selected</span>
      <div className="flex items-center gap-3">
        <button type="button" onClick={() => setSelection(prev => new Set([...prev, ...visible.filter(item => item.id !== "instruction" && !item.inventoryId).map(item => item.id)]))}
          className="text-tertiary hover:text-secondary">Select visible</button>
        <button type="button" onClick={() => remove(chosen.map(item => item.id))} disabled={!chosen.length || busy}
          className="flex items-center gap-1.5 rounded-md px-1.5 py-1 text-danger hover:bg-danger-bg disabled:opacity-50">
          <Trash2 className="h-3.5 w-3.5" /> Remove selected
        </button>
      </div>
    </div>}
    {!visible.length ? <p className="asm-preset empty">No matching components.</p> :
      view === "grid" ? <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {visible.map(item => <WorkspaceCard key={item.id} item={item} selectable={selectMode && !item.inventoryId} selected={selection.has(item.id)}
          onOpen={() => onOpen(item)} onSelect={() => toggleSelection(item.id)} onRemove={() => { if (!busy) remove([item.id]); }}
          canComment={draft.original.components.some(value => value.id === item.id)} />)}
      </div> : <div className="asm-preset"><ul className="contents-list">
        {visible.map(item => {
          const selectable = selectMode && item.id !== "instruction" && !item.inventoryId;
          return <li key={item.id} data-component-id={item.canonicalId ?? item.id} className="contents-row">
            <div className="component-label">
              {selectable ? <CheckItem item={item} selected={selection.has(item.id)} onSelect={() => toggleSelection(item.id)} /> :
                <KindIcon kind={item.kind} pluginHost={item.pluginHost} className="h-4 w-4 shrink-0 text-muted" />}
              <button type="button" className="row-action" onClick={selectable ? () => toggleSelection(item.id) : () => onOpen(item)}>{item.name}</button>
            </div>
            <span className="type-badge"><KindBadge kind={item.kind} pluginHost={item.pluginHost} /></span>
            <span className="source-host">{sourceLabel(item)}</span>
            <ChevronRight className="row-arrow h-4 w-4" aria-hidden="true" />
          </li>;
        })}
      </ul></div>}
  </section>;
}

