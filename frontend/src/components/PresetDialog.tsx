import { useEffect, useId, useRef, useState, type FormEvent, type ReactNode } from "react";
import { X } from "lucide-react";
import type { PackageKind } from "../types";
import { errorMessage } from "../api";

export function Modal({ title, onClose, children, busy = false }: {
  title: string; onClose: () => void; children: ReactNode; busy?: boolean;
}) {
  const titleId = useId();
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current!;
    dialog.showModal();
    return () => dialog.close();
  }, []);
  return <dialog
    ref={ref} aria-labelledby={titleId}
    onCancel={e => { e.preventDefault(); if (!busy) onClose(); }}
    onClick={e => { if (e.target === e.currentTarget && !busy) onClose(); }}
    className="w-[calc(100%-2rem)] max-w-[400px] max-h-[calc(100%-2rem)] overflow-y-auto rounded-xl border border-border bg-surface text-primary shadow-2xl backdrop:bg-black/70 backdrop:backdrop-blur-sm"
  >
    <div className="p-5">
      <div className="mb-4 flex items-center justify-between">
        <h2 id={titleId} className="text-[13px] font-semibold text-primary">{title}</h2>
        <button type="button" onClick={onClose} aria-label="Close" disabled={busy}
          className="rounded-md p-1 text-muted transition-colors hover:text-secondary"><X className="h-4 w-4" /></button>
      </div>
      {children}
    </div>
  </dialog>;
}

const inputClass = "w-full bg-background border border-border-subtle rounded-lg px-3 py-2 text-[13px] text-secondary focus:outline-none focus:border-border transition-all placeholder:text-faint";
const labelClass = "mb-1 block text-[13px] font-medium text-tertiary";
const footerClass = "flex flex-wrap justify-end gap-2 pt-1";

interface PresetFields {
  title: string;
  description: string;
  kind: PackageKind;
  workArea: string[];
  usage: string[];
  paperclip?: { role: string | null; canCreateAgents: boolean };
}

// Form body and controls from Skills Manager's CreatePresetDialog and RenamePresetDialog.
export function PresetDialog({ initial, defaultKind = "preset", roles = [], onClose, onSave }: {
  initial?: PresetFields; defaultKind?: PackageKind; onClose: () => void;
  /** Paperclip's agent roles, from catalog/consumers.json. */
  roles?: string[];
  onSave: (fields: PresetFields) => Promise<void> | void;
}) {
  const [name, setName] = useState(initial?.title || "");
  const [description, setDescription] = useState(initial?.description || "");
  const [kind, setKind] = useState(initial?.kind ?? defaultKind);
  const [workArea, setWorkArea] = useState(initial?.workArea.join("\n") || "");
  const [usage, setUsage] = useState(initial?.usage.join("\n") || "");
  const [role, setRole] = useState(initial?.paperclip?.role ?? "");
  const [canCreateAgents, setCanCreateAgents] = useState(initial?.paperclip?.canCreateAgents ?? false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!name.trim() || loading) return;
    const split = (value: string) => value.split("\n").map(entry => entry.trim()).filter(Boolean);
    setLoading(true);
    setError("");
    try {
      const fields: PresetFields = { title: name.trim(), description, kind, workArea: split(workArea), usage: split(usage) };
      if (initial?.paperclip) fields.paperclip = { role: role || null, canCreateAgents };
      await onSave(fields);
      onClose();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  const noun = kind === "stack" ? "stack" : "preset";
  return <Modal title={initial ? `Edit ${noun} details` : `New ${noun}`} onClose={onClose} busy={loading}>
    <form className="space-y-3" onSubmit={submit}>
      <label className="block"><span className={labelClass}>Name</span>
        <input required autoFocus value={name} onChange={e => setName(e.target.value)}
          placeholder={kind === "stack" ? "Stack name" : "Preset name"} className={inputClass} />
      </label>
      <label className="block"><span className={labelClass}>Description</span>
        <textarea rows={2} value={description} onChange={e => setDescription(e.target.value)}
          placeholder="Optional description" className={inputClass} />
      </label>
      {!initial && <label className="block"><span className={labelClass}>Type</span>
        <select value={kind} onChange={e => setKind(e.target.value as PackageKind)} className={inputClass}>
          <option value="preset">Preset</option><option value="stack">Stack</option>
        </select>
      </label>}
      {initial && <>
        <label className="block"><span className={labelClass}>Work area <small className="font-normal text-muted">(one per line)</small></span>
          <textarea rows={2} value={workArea} onChange={e => setWorkArea(e.target.value)} className={inputClass} />
        </label>
        <label className="block"><span className={labelClass}>Usage <small className="font-normal text-muted">(one per line)</small></span>
          <textarea rows={2} value={usage} onChange={e => setUsage(e.target.value)} className={inputClass} />
        </label>
        {initial.paperclip && initial.kind === "preset" && <fieldset className="space-y-2">
          <legend className={labelClass}>Paperclip</legend>
          <label className="block"><span className={labelClass}>Role</span>
            <select value={role} onChange={e => setRole(e.target.value)} className={inputClass}>
              <option value="">Not set (exports general)</option>
              {[...new Set([...roles, ...(role ? [role] : [])])].map(value => <option key={value} value={value}>{value}</option>)}
            </select>
          </label>
          <label className="flex items-center gap-2 text-[13px] text-secondary">
            <input type="checkbox" checked={canCreateAgents} onChange={e => setCanCreateAgents(e.target.checked)} />
            Can create agents
          </label>
        </fieldset>}
      </>}
      {error && <p role="alert" className="text-[13px] text-danger">{error}</p>}
      <div className={footerClass}>
        <button type="button" onClick={onClose} disabled={loading} className="rounded-lg px-3 py-1.5 text-[13px] font-medium text-tertiary transition-colors hover:bg-surface-hover hover:text-secondary">Cancel</button>
        <button type="submit" disabled={!name.trim() || loading} className="rounded-lg border border-accent-border bg-accent-dark px-3 py-1.5 text-[13px] font-medium text-white transition-colors hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50">
          {initial ? (loading ? "Applying…" : "Apply changes") : (loading ? "Creating…" : "Create")}
        </button>
      </div>
    </form>
  </Modal>;
}

