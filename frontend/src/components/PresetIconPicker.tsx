import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { PRESET_ICON_OPTIONS } from "../lib/presetIcons";
import { cn } from "../utils";

// Interaction from Paperclip's AgentIconPicker (ui/src/components/AgentIconPicker.tsx, MIT):
// the icon opens a searchable grid, and choosing an icon closes it.
export function PresetIconPicker({ value, onChange, label, disabled, children }: {
  value: string; onChange: (icon: string) => void; label: string; disabled?: boolean; children: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const root = useRef<HTMLDivElement>(null);
  const panelId = useId();
  useEffect(() => {
    if (!open) return;
    const outside = (event: PointerEvent) => { if (!root.current?.contains(event.target as Node)) setOpen(false); };
    // Escape closes only the picker, not a dialog around it.
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape") { event.preventDefault(); setOpen(false); } };
    document.addEventListener("pointerdown", outside);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("pointerdown", outside);
      document.removeEventListener("keydown", escape);
    };
  }, [open]);
  const query = search.trim().toLowerCase();
  const options = PRESET_ICON_OPTIONS.filter(option =>
    !query || option.key.includes(query) || option.label.toLowerCase().includes(query));
  const choose = (icon: string) => { onChange(icon); setOpen(false); setSearch(""); };

  return <div ref={root} className="relative shrink-0">
    <button type="button" aria-label={label} title={label} aria-expanded={open} aria-controls={open ? panelId : undefined}
      disabled={disabled} onClick={() => setOpen(value => !value)}
      className="block rounded-lg transition-opacity hover:opacity-80 focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent">
      {children}
    </button>
    {open && <div id={panelId} role="dialog" aria-label={label}
      className="absolute left-0 top-full z-30 mt-2 w-[18rem] rounded-lg border border-border-subtle bg-surface p-3 shadow-lg">
      <input type="search" autoFocus value={search} onChange={e => setSearch(e.target.value)}
        placeholder="Search icons…" aria-label="Search icons" className="app-input mb-2 w-full"
        autoCapitalize="none" autoCorrect="off" spellCheck={false} />
      <div className="grid max-h-48 grid-cols-7 gap-1 overflow-y-auto">
        {options.map(option => {
          const Icon = option.icon;
          const selected = option.key === value;
          return <button key={option.key} type="button" title={option.label} aria-label={option.label} aria-pressed={selected}
            onClick={() => choose(option.key)}
            className={cn("flex h-8 w-8 items-center justify-center rounded-md border transition-colors hover:bg-surface-hover",
              option.colorClass, selected ? option.activeClass : "border-transparent")}>
            <Icon className="h-4 w-4" aria-hidden="true" />
          </button>;
        })}
        {!options.length && <p className="col-span-7 py-2 text-center text-[12px] text-muted">No icons match.</p>}
      </div>
    </div>}
  </div>;
}
