import { useEffect, useState, type ReactNode } from "react";
import { Ban, CircleCheck, CircleHelp, Download, Link2 } from "lucide-react";
import { api, ApiError, downloadFile, errorMessage, packagePath } from "../api";
import type { ConsumerData, InventoryApp, PackageKind, Report, ReportItem } from "../types";
import { cn } from "../utils";
import { hrefFor, type Route } from "./Sidebar";
import { PaperclipReport } from "./PaperclipReport";
import { SupportTable } from "./SupportTable";

const switchStatuses = {
  "import-ready": { label: "Import ready", icon: CircleCheck, tone: "good" },
  "registration-only": { label: "Repository registration", icon: Link2, tone: "neutral" },
  manual: { label: "Manual review", icon: CircleHelp, tone: "neutral" },
  unsupported: { label: "Unsupported", icon: Ban, tone: "neutral" },
  excluded: { label: "Excluded", icon: Ban, tone: "neutral" },
} as const;

interface ReviewRow {
  id: string; name: string; app?: InventoryApp; originPackage?: ReportItem["originPackage"]; status: keyof typeof switchStatuses; reason: string;
}
type TargetBase = { name: string; available: boolean; reason: string; download?: string; filename?: string };
type PaperclipTarget = TargetBase & { id: "paperclip"; preview: Omit<Report, "files"> };
type SwitchTarget = TargetBase & { id: "ccswitch"; preview: { items: ReviewRow[] } };
type ExportTarget = PaperclipTarget | SwitchTarget;
type Choices = { targets: ExportTarget[] };

interface ExportTabProps {
  id: string; kind: PackageKind; revision: string; dirty: boolean; data: ConsumerData; loading: boolean; error: string;
  onRetry: () => void; route: Route; onNavigate: (route: Route) => void;
}

function SwitchRows({ items }: { items: ReviewRow[] }) {
  if (!items.length) return null;
  return <div className="summary-box support-scroll"><table className="summary-table max-sm:block max-sm:!min-w-0">
    <colgroup className="max-sm:hidden"><col className="w-[24%]" /><col className="w-[18%]" /><col className="w-[22%]" /><col className="w-[36%]" /></colgroup>
    <thead className="max-sm:sr-only"><tr><th scope="col">Component</th><th scope="col">App</th><th scope="col">Result</th><th scope="col">Reason</th></tr></thead>
    <tbody className="max-sm:block">{items.map(row => {
      const { label, icon: Icon, tone } = switchStatuses[row.status];
      return <tr key={`${row.id}:${row.app ?? ""}`} className="max-sm:grid max-sm:grid-cols-[minmax(0,1fr)_auto]">
        <th scope="row" className="[overflow-wrap:anywhere] max-sm:!h-auto max-sm:!w-auto">
          {row.name}
          {row.originPackage && <span className="block text-[12px] font-normal text-muted">From {row.originPackage.title}</span>}
        </th>
        <td className="[overflow-wrap:anywhere] max-sm:col-span-2 max-sm:row-start-2 max-sm:!h-auto max-sm:text-muted">
          {row.app === "claude" ? "Claude Code" : row.app === "codex" ? "Codex" : "Unassigned"}
        </td>
        <td className="max-sm:col-start-2 max-sm:row-start-1 max-sm:!h-auto">
          <span className={`status status-${tone} max-w-full !whitespace-normal`}>
          <Icon className="h-3.5 w-3.5 shrink-0" aria-hidden="true" /><span className="[overflow-wrap:anywhere]">{label}</span>
        </span></td>
        <td className="[overflow-wrap:anywhere] max-sm:col-span-2 max-sm:row-start-3 max-sm:!h-auto">{row.reason}</td>
      </tr>;
    })}</tbody>
  </table></div>;
}

function ExportDownload({ path, filename, label, refresh }: {
  path: string; filename: string; label: string; refresh: () => void;
}) {
  const [downloading, setDownloading] = useState(false);
  const [failure, setFailure] = useState<{ message: string; stale: boolean }>();
  async function download() {
    setFailure(undefined);
    setDownloading(true);
    try {
      downloadFile(filename, await api<Blob>(path, { blob: true }));
    } catch (error) {
      setFailure({ message: errorMessage(error), stale: error instanceof ApiError && error.status === 409 });
    } finally {
      setDownloading(false);
    }
  }
  return <>
    <button type="button" className="app-button-secondary" disabled={downloading || failure?.stale}
      onClick={() => void download()}>
      <Download className="h-4 w-4" aria-hidden="true" /> {downloading ? "Preparing download…" : label}
    </button>
    {failure && <p role="alert" className="text-[13px] text-danger">{failure.message}{" "}
      {failure.stale && <button type="button" className="underline" onClick={refresh}>Reload preview</button>}
    </p>}
  </>;
}

function SwitchReport({ target, download, dirty, heading }: {
  target: SwitchTarget; download: ReactNode; dirty: boolean; heading: ReactNode;
}) {
  const [filter, setFilter] = useState<ReviewRow["status"] | "all">("all");
  const items = target.preview.items;
  const visible = filter === "all" ? items : items.filter(row => row.status === filter);
  return <section className="asm-preset" aria-label="CC Switch review">
    <div className="section-heading flex-wrap">
      {heading}
      {download}
    </div>
    {dirty && <p className="mb-2 text-[12px] text-muted">Showing the saved revision.</p>}
    {items.length ? <><div className="section-heading flex-wrap">
      <h3>Component results</h3>
      <label className="inline-flex items-center gap-2 text-[13px]">
        Result
        <select className="app-input" value={filter} onChange={event => setFilter(event.target.value as typeof filter)}>
          <option value="all">All ({items.length})</option>
          {Object.entries(switchStatuses).map(([status, entry]) => {
            const count = items.filter(row => row.status === status).length;
            return count > 0 && <option key={status} value={status}>{entry.label} ({count})</option>;
          })}
        </select>
      </label>
    </div>
    <SwitchRows items={visible} /></> : <p className="empty">No components in this review.</p>}
  </section>;
}

export function PresetExportTab({ id, kind, revision, dirty, data, loading, error, onRetry, route, onNavigate }: ExportTabProps) {
  const [request, setRequest] = useState(0);
  const refresh = () => setRequest(previous => previous + 1);
  const key = `${id}:${revision}:${request}`;
  const [result, setResult] = useState<{ key: string; targets?: ExportTarget[]; error?: string }>();
  useEffect(() => {
    const controller = new AbortController();
    api<Choices>(packagePath(id, "/exports"), { signal: controller.signal })
      .then(({ targets }) => { if (!controller.signal.aborted) setResult({ key, targets }); })
      .catch(err => { if (!controller.signal.aborted) setResult({ key, error: errorMessage(err) }); });
    return () => controller.abort();
  }, [id, key]);
  if (result?.key !== key) return <p role="status" className="text-[13px] text-muted">Loading export targets…</p>;
  if (result.error) return <p role="alert" className="text-[13px] text-danger">{result.error}{" "}
    <button type="button" className="underline" onClick={refresh}>Retry</button></p>;
  const targets = result.targets ?? [];
  const choices = targets.filter(target => target.available && target.download);
  const active = choices.find(target => target.id === route.consumer) ?? choices[0];
  const download = active?.download && active.filename ? <ExportDownload path={packagePath(id, active.download)}
    filename={active.filename} label={active.id === "paperclip" ? "Download Paperclip package" : "Download CC Switch review"}
    refresh={refresh} /> : null;
  const paperclip = targets.find(target => target.id === "paperclip");
  const tabs = <nav className="app-segmented w-fit max-w-full" aria-label="Export targets">
    {choices.map(target => {
      const next: Route = { ...route, tab: "export", consumer: target.id };
      return <a key={target.id} href={hrefFor(next)} aria-current={target === active ? "page" : undefined}
        onClick={event => { if (!event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) {
          event.preventDefault();
          onNavigate(next);
        } }}
        className={cn("app-segmented-button py-1.5", target === active && "app-segmented-button-active")}>{target.name}</a>;
    })}
  </nav>;
  return <>
    {loading ? <p role="status" className="text-[13px] text-muted">Loading app support…</p> :
      error ? <p role="alert" className="text-[13px] text-danger">{error}{" "}<button type="button" className="underline" onClick={onRetry}>Retry</button></p> :
        <SupportTable data={data} report={paperclip?.preview} packageKind={kind} />}
    {active && (active.id === "paperclip"
      ? <PaperclipReport key={key} heading={tabs} download={download} report={active.preview} dirty={dirty} />
      : <SwitchReport key={key} heading={tabs} download={download} target={active} dirty={dirty} />)}
    {targets.filter(target => !target.available).map(target => <section className="asm-preset" key={target.id}>
      <details className="summary-box p-3">
        <summary className="cursor-pointer text-[13px] font-semibold">{target.name} unavailable</summary>
        <p className="mt-2 text-[13px] text-muted">{target.reason}</p>
        {target.id === "ccswitch" ? <SwitchRows items={target.preview.items} /> :
          <PaperclipReport report={target.preview} heading={null} download={null} dirty={false} />}
      </details>
    </section>)}
  </>;
}
