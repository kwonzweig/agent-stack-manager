import { Blocks, FileText, PackageOpen, Plug2, Workflow, Puzzle, CircleEllipsis, Search } from "lucide-react";
import { getTagActiveColor, getTagColor } from "../lib/skillTags";
import { cn } from "../utils";
import type { Kind } from "../types";

export const KIND_LABELS: Record<Kind, string> = {
  instruction: "Instruction", skill: "Skill", mcp: "MCP", hook: "Hook", plugin: "Plugin", package: "Stack", other: "Other",
};
export const KINDS = Object.keys(KIND_LABELS) as Kind[];
const icons = { instruction: FileText, skill: Blocks, mcp: Plug2, hook: Workflow, plugin: Puzzle, package: PackageOpen, other: CircleEllipsis };

export function KindIcon({ kind, className = "h-4 w-4" }: { kind: Kind; className?: string }) {
  const Icon = icons[kind] || CircleEllipsis;
  return <Icon className={className} aria-hidden="true" />;
}

export function KindBadge({ kind }: { kind: Kind }) {
  return <span className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium",
    getTagColor(kind, KINDS))}>{KIND_LABELS[kind]}</span>;
}

export function SearchField({ value, onChange, label = "Search components" }: { value: string; onChange: (value: string) => void; label?: string }) {
  return <label className="relative block w-full min-w-[160px] max-w-[320px]">
    <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted" aria-hidden="true" />
    <input type="search" aria-label={label} value={value} onChange={e => onChange(e.target.value)}
      placeholder={label + "…"} className="app-input w-full pl-8 font-medium" autoCapitalize="none" autoCorrect="off" spellCheck={false} />
  </label>;
}

export function TypeFilter({ kinds, active, onChange }: { kinds: Kind[]; active: Kind | "all"; onChange: (kind: Kind | "all") => void }) {
  return <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Component type">
    <span className="text-[12px] text-muted">Type</span>
    <button type="button" aria-pressed={active === "all"} onClick={() => onChange("all")}
      className={cn("rounded-full px-2.5 py-0.5 text-[12px] font-medium",
        active === "all" ? "bg-accent-dark text-white" : "bg-surface-hover text-muted hover:text-secondary")}>All</button>
    {kinds.map(kind => <button key={kind} type="button" aria-pressed={active === kind} onClick={() => onChange(kind)}
      className={cn("rounded-full px-2.5 py-0.5 text-[12px] font-medium",
        active === kind ? getTagActiveColor(kind, KINDS) : getTagColor(kind, KINDS))}>{KIND_LABELS[kind]}</button>)}
  </div>;
}
