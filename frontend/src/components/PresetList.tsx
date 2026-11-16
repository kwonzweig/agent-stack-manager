import { useState } from "react";
import { ChevronRight, Plus } from "lucide-react";
import type { PackageSummary } from "../types";
import { KIND_STYLES } from "../lib/kinds";
import { SearchField } from "./ComponentUI";
import { hrefFor, PresetIcon, type Route } from "./Sidebar";

// Management list of saved packages: row dividers, a page-level create action and aligned row ends.
export function PresetList({ presets, loading, onNavigate, onCreate }: {
  presets: PackageSummary[]; loading: boolean; onNavigate: (route: Route) => void; onCreate: () => void;
}) {
  const [search, setSearch] = useState("");
  const query = search.trim().toLowerCase();
  const visible = query ? presets.filter(preset => [preset.title, preset.description, ...preset.workArea, ...preset.usage]
    .some(value => value.toLowerCase().includes(query))) : presets;
  return <section className="app-page" aria-labelledby="presets-title">
    <header className="app-page-header flex flex-wrap items-center justify-between gap-3">
      <h1 id="presets-title" className="app-page-title">Presets</h1>
      <button type="button" className="app-button-primary" onClick={onCreate}><Plus className="h-4 w-4" /> New preset</button>
    </header>
    {loading && !presets.length ? <p role="status" className="text-[13px] text-muted">Loading presets…</p> : !presets.length ?
      <p className="text-[13px] text-muted">No presets yet.</p> : <>
      <SearchField value={search} onChange={setSearch} label="Search presets" />
      {visible.length ? <ul className="app-panel divide-y divide-border-subtle">
        {visible.map(preset => {
          const next: Route = { view: "presets", id: preset.id };
          return <li key={preset.id}>
            <a href={hrefFor(next)} className="flex items-center gap-3 px-3.5 py-3 transition-colors hover:bg-surface-hover"
              onClick={e => { if (!e.metaKey && !e.ctrlKey && !e.shiftKey && !e.altKey) { e.preventDefault(); onNavigate(next); } }}>
              <PresetIcon title={preset.title} description={preset.description} icon={preset.icon} active className="h-8 w-8 rounded-lg [&>svg]:h-4 [&>svg]:w-4" />
              <span className="min-w-0 flex-1">
                <span className="flex flex-wrap items-center gap-2 text-[14px] font-semibold text-primary">
                  {preset.title}
                  {preset.kind === "stack" && <span className={"rounded-full px-2 py-0.5 text-[11px] font-medium " + KIND_STYLES.stack.chip}>Stack</span>}
                </span>
                {preset.description && <span className="mt-0.5 block truncate text-[13px] text-muted">{preset.description}</span>}
              </span>
              <span className="shrink-0 text-[12px] tabular-nums text-muted">
                {preset.componentCount} {preset.componentCount === 1 ? "component" : "components"}
              </span>
              <ChevronRight className="h-4 w-4 shrink-0 text-faint" aria-hidden="true" />
            </a>
          </li>;
        })}
      </ul> : <p className="text-[13px] text-muted">No presets match “{search.trim()}”.</p>}
    </>}
  </section>;
}
