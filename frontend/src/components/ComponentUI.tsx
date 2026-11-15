import type { CSSProperties } from "react";
import { Search } from "lucide-react";
import { KIND_STYLES } from "../lib/kinds";
import { cn } from "../utils";
import type { Kind, PackageKind } from "../types";

export const KINDS: Kind[] = ["instruction", "skill", "mcp", "hook", "plugin", "package", "other"];
export const KIND_LABELS = Object.fromEntries(KINDS.map(kind => [kind, KIND_STYLES[kind].singular])) as Record<Kind, string>;

export function KindIcon({ kind, className = "h-4 w-4", style }: { kind: Kind | PackageKind; className?: string; style?: CSSProperties }) {
  const Icon = (KIND_STYLES[kind] ?? KIND_STYLES.other).icon;
  return <Icon className={className} style={style} aria-hidden="true" />;
}

export function KindBadge({ kind }: { kind: Kind }) {
  return <span className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium",
    KIND_STYLES[kind].chip)}>{KIND_LABELS[kind]}</span>;
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
      className={cn("inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[12px] font-medium",
        active === kind ? KIND_STYLES[kind].chipActive : KIND_STYLES[kind].chip)}>
      <KindIcon kind={kind} className="h-3 w-3" />{KIND_LABELS[kind]}
    </button>)}
  </div>;
}
