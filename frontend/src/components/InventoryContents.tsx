import { Check, CircleHelp, Download, Minus } from "lucide-react";
import { useEffect, useState } from "react";
import { api, errorMessage, packagePath } from "../api";
import { inventorySelection, isDirty, type Draft } from "../draft";
import type { InventoryApp, InventoryItem, InventorySelection } from "../types";
import { SearchField } from "./ComponentUI";

const apps = [["codex", "Codex"], ["claude", "Claude Code"]] as const;
const kindNames: Record<string, string> = { mcp: "MCP", lsp: "LSP", "codex-plugin": "Codex plugin", "claude-code-plugin": "Claude Code plugin" };
const kindName = (kind: string) => Object.hasOwn(kindNames, kind) ? kindNames[kind] : kind[0].toUpperCase() + kind.slice(1);

const exportStatuses = {
  "import-ready": "Import ready",
  "registration-only": "Repository registration",
  manual: "Manual action",
  unsupported: "Unsupported",
  excluded: "Excluded",
};

export function InventoryExport({ id, dirty }: { id: string; dirty: boolean }) {
  const path = packagePath(id) + "/cc-switch";
  const [report, setReport] = useState<{ items: { status: keyof typeof exportStatuses }[] }>();
  const [error, setError] = useState("");
  useEffect(() => {
    const request = new AbortController();
    api<NonNullable<typeof report>>(path, { signal: request.signal }).then(setReport, failure => {
      if (!request.signal.aborted) setError(errorMessage(failure));
    });
    return () => request.abort();
  }, [path]);
  return <section aria-label="CC Switch review" className="app-panel space-y-3 p-4 text-[13px]">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h2 className="text-base font-semibold text-primary">CC Switch review</h2>
      {dirty ? <p className="text-muted">Save changes to download</p> :
        report && <a className="app-toolbar-button" href={path} download><Download className="h-3.5 w-3.5" aria-hidden /> Download review</a>}
    </div>
    {error && <p role="alert" className="text-danger">{error}</p>}
    {!error && !report && <p role="status" className="text-muted">Loading saved review…</p>}
    {report && <dl className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
      {Object.entries(exportStatuses).map(([status, label]) => <div key={status} className="rounded border border-border-subtle px-3 py-2">
        <dt className="text-muted">{label}</dt>
        <dd className="font-medium text-primary">{report.items.filter(item => item.status === status).length}</dd>
      </div>)}
    </dl>}
  </section>;
}

function Observation({ value, labels }: { value: boolean | null; labels: [string, string, string] }) {
  const Icon = value === true ? Check : value === false ? Minus : CircleHelp;
  return <span className="inline-flex items-center gap-1 text-secondary"><Icon className={value === true ? "h-3.5 w-3.5 text-accent" : "h-3.5 w-3.5 text-muted"} aria-hidden />
    {labels[value === true ? 0 : value === false ? 1 : 2]}</span>;
}

export function InventoryContents({ draft, onSelect }: {
  draft: Draft; onSelect: (item: InventoryItem, app: InventoryApp, selected: InventorySelection) => void;
}) {
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState("");
  const items = draft.original.appInventory ?? [];
  const kinds = [...new Set(items.map(item => item.kind))].sort();
  const search = query.trim().toLowerCase();
  const visible = items.filter(item => (!kind || item.kind === kind) &&
    [item.name, item.description, item.kind, item.source].some(value => value?.toLowerCase().includes(search)));
  const coverage = draft.original.appInventoryCoverage;
  return <section className="space-y-3" aria-label="App inventory">
    <div className="app-toolbar">
      <SearchField value={query} onChange={setQuery} />
      <div className="flex items-center gap-2">
        <select className="app-toolbar-button" aria-label="Component type" value={kind} onChange={event => setKind(event.target.value)}>
          <option value="">All types</option>
          {kinds.map(value => <option key={value} value={value}>{kindName(value)}</option>)}
        </select>
        {isDirty(draft) ? <span className="text-[13px] text-muted">Save changes to download</span> :
          <a className="app-toolbar-button" href={packagePath(draft.original.id) + "/cc-switch"} download>
            <Download className="h-3.5 w-3.5" aria-hidden /> CC Switch review
          </a>}
      </div>
    </div>
    {Array.isArray(coverage) && coverage.length > 0 && <details className="rounded-lg border border-border-subtle bg-surface p-3 text-[13px] text-secondary">
      <summary className="cursor-pointer font-medium">Scan coverage</summary>
      <ul className="mt-2 space-y-1">{coverage.map((row, index) =>
        <li key={index}><strong>{apps.find(([app]) => app === row.app)?.[1] ?? row.app} {row.area}</strong><p>{row.note}</p></li>)}</ul>
    </details>}
    {visible.length === 0 ? <p className="asm-preset empty">No matching inventory items.</p> :
      <ul className="space-y-2" aria-label="Installed components">{visible.map(item =>
        <li key={item.id} className="grid gap-3 rounded-lg border border-border-subtle bg-surface p-3 text-[13px] lg:grid-cols-[minmax(12rem,1.4fr)_minmax(15rem,1fr)_minmax(15rem,1fr)]">
          <div className="min-w-0">
            <h3 className="break-words font-semibold text-primary">{item.name}</h3>
            <span className="text-muted">{kindName(item.kind)}</span>
            {item.description && <p className="mt-1 break-words text-secondary">{item.description}</p>}
          </div>
          {apps.map(([app, name]) => {
            const observation = item.apps[app];
            const chosen = inventorySelection(draft, item, app);
            return <div key={app} className="min-w-0 border-t border-border-subtle pt-2 lg:border-l lg:border-t-0 lg:pl-3 lg:pt-0">
              <h4 className="font-medium text-primary">{name}</h4>
              <dl className="mt-1 grid grid-cols-[4.5rem_minmax(0,1fr)] items-center gap-x-2 gap-y-1">
                <dt className="text-muted">Install</dt><dd><Observation value={observation?.installed ?? null} labels={["Installed", "Previously installed", "No record"]} /></dd>
                {observation && <>
                  <dt className="text-muted">Activity</dt><dd><Observation value={observation.enabled} labels={["Enabled", "Disabled", "Unknown"]} /></dd>
                  {observation.scope && <><dt className="text-muted">Scope</dt><dd className="break-words text-secondary">{observation.scope}</dd></>}
                  <dt className="text-muted">Preset</dt><dd>
                    <select className="app-toolbar-button min-h-7 w-full justify-start" aria-label={`${item.name}, ${name}, preset membership`}
                      value={chosen === null ? "" : String(chosen)}
                      onChange={event => onSelect(item, app, event.target.value === "" ? null : event.target.value === "true")}>
                      <option value="true">Included</option><option value="false">Excluded</option><option value="">Not set</option>
                    </select>
                  </dd>
                </>}
              </dl>
            </div>;
          })}
        </li>)}</ul>}
  </section>;
}
