import { useState } from "react";
import { ChevronDown, ChevronRight, Layers, Menu, Moon, Plus, Plug2, Sun } from "lucide-react";
import { getPresetIconOption } from "../lib/presetIcons";
import { cn } from "../utils";
import type { PackageSummary } from "../types";

export type Route = { view: "catalog" | "consumers" | "presets"; id?: string; tab?: "contents" | "paperclip" | "source" };
export function hrefFor({ view, id, tab }: Route) {
  const params = new URLSearchParams({ view });
  if (id) params.set("preset", id);
  if (tab && tab !== "contents") params.set("tab", tab);
  return "#" + params;
}

export function PresetIcon({ title, description, active, className }: {
  title: string; description?: string; active?: boolean; className?: string;
}) {
  const option = getPresetIconOption({ name: title, description });
  const Icon = option.icon;
  return <span className={cn("flex h-[20px] w-[20px] shrink-0 items-center justify-center rounded-[4px] border",
    active ? option.activeClass + " " + option.colorClass : "border-border bg-surface text-muted",
    className)}>
    <Icon className="h-3 w-3" aria-hidden="true" />
  </span>;
}

// Browser adaptation of the Skills Manager navigation and preset rows.
export function Sidebar({ route, presets, onNavigate, onCreate, theme, onTheme }: {
  route: Route; presets: PackageSummary[]; onNavigate: (route: Route) => void;
  onCreate: () => void; theme: "light" | "dark"; onTheme: () => void;
}) {
  const [presetsOpen, setPresetsOpen] = useState(true);
  const [mobileOpen, setMobileOpen] = useState(false);
  const navItems = [
    { view: "catalog", name: "Catalog", icon: Layers },
    { view: "consumers", name: "Consumers", icon: Plug2 },
  ] as const;
  return <aside className="relative z-10 flex min-h-0 w-full shrink-0 select-none flex-col border-b border-border-subtle bg-bg-secondary md:h-full md:w-[220px] md:border-b-0 md:border-r">
    <div className="h-2.5 shrink-0" />
    <div className="flex shrink-0 items-center gap-3 px-3 pb-2.5">
      <Layers className="h-5 w-5 shrink-0 text-accent" aria-hidden="true" />
      <span className="text-[15px] font-semibold leading-[22px] tracking-tight text-secondary">Agent Stack Manager</span>
      <button type="button" aria-label="Toggle navigation" aria-expanded={mobileOpen} onClick={() => setMobileOpen(open => !open)} className="ml-auto rounded-md p-1.5 text-muted hover:bg-surface-hover md:hidden"><Menu className="h-4 w-4" /></button>
    </div>
    <div className={cn("min-h-0 flex-1 flex-col", mobileOpen ? "flex" : "hidden", "md:flex")}>
    <nav aria-label="Main" className="flex shrink-0 gap-0.5 px-2.5 md:block md:space-y-0.5">
      {navItems.map(({ view, name, icon: Icon }) => {
        const active = route.view === view;
        return <a key={view} href={hrefFor({ view })} aria-current={active ? "page" : undefined}
          onClick={e => { if (!e.metaKey && !e.ctrlKey && !e.shiftKey && !e.altKey) { e.preventDefault(); setMobileOpen(false); onNavigate({ view }); } }}
          className={cn("flex items-center gap-2.5 rounded-md px-2.5 py-[7px] text-[14px] font-medium leading-5 transition-colors",
            active ? "bg-surface-active text-primary" : "text-tertiary hover:bg-surface-hover hover:text-secondary")}>
          <Icon aria-hidden="true" className={cn("h-4 w-4 shrink-0", active ? "text-accent" : "text-muted")} />{name}
        </a>;
      })}
    </nav>
    <div className="mx-3 mb-2.5 mt-3.5 border-t border-border-subtle" />
    <nav aria-label="Presets" className="min-h-0 flex-1 overflow-y-auto px-2.5 scrollbar-hide">
      <div className="mb-1.5 flex items-center gap-1 px-2.5">
        <button onClick={() => setPresetsOpen(v => !v)} aria-expanded={presetsOpen}
          className="flex min-w-0 flex-1 items-center gap-1 text-left">
          {presetsOpen ? <ChevronDown className="h-3 w-3 shrink-0 text-faint" /> : <ChevronRight className="h-3 w-3 shrink-0 text-faint" />}
          <span className="truncate whitespace-nowrap text-[12px] font-semibold tracking-[0.01em] text-muted">Presets</span>
        </button>
      </div>
      {presetsOpen && <div className="flex max-h-[126px] flex-wrap gap-0.5 overflow-auto pb-2 md:block md:max-h-none md:space-y-0.5">
        {presets.map(preset => {
          const active = route.view === "presets" && route.id === preset.id;
          const next = { view: "presets", id: preset.id } as const;
          return <a key={preset.id} href={hrefFor(next)} aria-current={active ? "page" : undefined}
            onClick={e => { if (!e.metaKey && !e.ctrlKey && !e.shiftKey && !e.altKey) { e.preventDefault(); setMobileOpen(false); onNavigate(next); } }}
            title={preset.description || preset.title}
            className={cn("group flex min-w-0 items-center gap-2 rounded-md px-2.5 py-[7px] text-left text-[14px] leading-5 transition-colors",
              active ? "bg-surface-active font-medium text-primary" : "text-tertiary hover:bg-surface-hover hover:text-secondary")}>
            <PresetIcon title={preset.title} description={preset.description} active={active} />
            <span className="flex-1 truncate">{preset.title}</span>
            <span className={cn("ml-auto min-w-[18px] rounded-full px-1.5 text-center text-[12px] font-medium leading-[18px] tabular-nums",
              active ? "bg-accent-bg text-accent" : "bg-surface-hover text-muted")}>{preset.componentCount}</span>
          </a>;
        })}
      </div>}
      <button onClick={() => { setMobileOpen(false); onCreate(); }} className="mb-2.5 mt-1 flex w-full items-center gap-2 rounded-md px-2.5 py-[7px] text-left text-[14px] leading-5 text-muted transition-colors hover:bg-surface-hover hover:text-secondary">
        <Plus className="h-4 w-4 shrink-0" aria-hidden="true" /> New preset
      </button>
    </nav>
    <div className="shrink-0 border-t border-border-subtle px-2.5 py-2.5">
      <button type="button" onClick={onTheme} className="flex w-full items-center gap-2.5 rounded-md px-2.5 py-[7px] text-left text-[14px] font-medium leading-5 text-tertiary hover:bg-surface-hover hover:text-secondary">
        {theme === "light" ? <Moon className="h-4 w-4 shrink-0 text-muted" /> : <Sun className="h-4 w-4 shrink-0 text-muted" />}
        {theme === "light" ? "Dark appearance" : "Light appearance"}
      </button>
    </div>
    </div>
  </aside>;
}


