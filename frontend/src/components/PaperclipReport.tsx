import { useEffect, useRef, useState, type ReactNode } from "react";
import { ChevronRight, CircleCheck, CircleMinus, CircleX, Download, RefreshCw } from "lucide-react";
import { api, downloadArchive, errorMessage, packagePath } from "../api";
import { cn } from "../utils";
import type { Report, ReportItem, Result } from "../types";
import { KindBadge, KindIcon, KIND_LABELS, KINDS } from "./ComponentUI";
import { formatDate, ValuePanel } from "./ComponentDetails";
import { DetailSheet } from "./DetailSheet";

const stages = [["conversion", "Conversion"], ["import", "Paperclip import"]] as const;
const statuses = {
  converted: ["Converted", "good"], unconverted: ["Unconverted", "bad"],
  saved: ["Saved", "good"], missing: ["Missing", "bad"], not_checked: ["Not checked", "neutral"],
} as const;
function Status({ result }: { result: Result }) {
  const [label, tone] = statuses[result.status as keyof typeof statuses] || statuses.not_checked;
  const Icon = tone === "good" ? CircleCheck : tone === "bad" ? CircleX : CircleMinus;
  return <span className={"status status-" + tone}><Icon className="h-3.5 w-3.5" aria-hidden="true" />{label}</span>;
}
function needsAttention(item: ReportItem) {
  return item.conversion.status === "unconverted" || item.import.status === "missing";
}

export function PaperclipReport({ id, revision, dirty, heading }: {
  id: string; revision: string; dirty: boolean; heading: ReactNode;
}) {
  const [report, setReport] = useState<Report>();
  const [filter, setFilter] = useState<"all" | "attention">("all");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<"" | "convert" | "observe" | "download">("convert");
  const [item, setItem] = useState<ReportItem>();
  const request = useRef<AbortController | null>(null);
  async function load(observe = false) {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setError(""); setBusy(observe ? "observe" : "convert");
    try {
      const result = await api<Report>(packagePath(id, observe ? "/paperclip/observe" : "/paperclip"), {
        signal: controller.signal, ...(observe ? { method: "POST", body: {} } : {}),
      });
      if (!controller.signal.aborted) setReport(result);
    } catch (err) {
      if (!controller.signal.aborted) setError(errorMessage(err));
    } finally {
      if (!controller.signal.aborted) setBusy("");
    }
  }
  useEffect(() => {
    setReport(undefined);
    void load();
    return () => request.current?.abort();
  }, [id, revision]);
  async function download() {
    setError(""); setBusy("download");
    try { await downloadArchive(id, true); } catch (err) { setError(errorMessage(err)); } finally { setBusy(""); }
  }
  const all = report?.items ?? [];
  const attention = all.filter(needsAttention);
  const visible = filter === "all" ? all : attention;
  const groups = KINDS.map(kind => [kind, all.filter(row => row.kind === kind)] as const).filter(([, rows]) => rows.length);
  const metrics = (rows: ReportItem[]) => [rows.length, rows.filter(row => row.conversion.status === "converted").length,
    rows.filter(row => row.conversion.status === "unconverted").length, rows.filter(row => row.import.status === "saved").length];
  function cells(rows: ReportItem[]) {
    return metrics(rows).map((count, index) => <td className={cn("number", count && index > 0 && (index === 2 ? "count-bad" : "count-good"))} key={index}>{count}</td>);
  }
  return <section className="asm-lab" aria-label="Paperclip conversion report">
    <div className="section-heading flex-wrap">
      {heading}
      <div className="flex flex-wrap items-center gap-2">
        <button className="app-button-secondary" type="button" disabled={Boolean(busy)} onClick={() => void load()}><RefreshCw className="h-4 w-4" /> Convert</button>
        <button className="app-button-secondary" type="button" disabled={Boolean(busy)} onClick={() => void load(true)}><RefreshCw className="h-4 w-4" /> Refresh import status</button>
        <button className="app-button-secondary" type="button" disabled={Boolean(busy) || !all.some(row => row.conversion.status === "converted")}
          onClick={download}><Download className="h-4 w-4" /> Download Paperclip package</button>
      </div>
    </div>
    {dirty && <p className="mb-2 text-[12px] text-muted">Showing the saved revision.</p>}
    {error && <p role="alert" className="mb-2 text-[13px] text-danger">{error}</p>}
    {busy && <p role="status" className="mb-2 text-[13px] text-muted">{{ convert: "Converting package…", observe: "Checking saved Paperclip state…", download: "Preparing download…" }[busy]}</p>}
    {report && <>
      <section aria-label="Conversion summary">
        <div className="section-heading"><h3>Conversion summary</h3></div>
        <div className="summary-box"><table className="summary-table">
          <thead><tr>{["Type", "Total", "Converted", "Unconverted", "Saved"].map((name, index) => <th key={name} className={index ? "number" : ""} scope="col">{name}</th>)}</tr></thead>
          <tbody>{groups.map(([kind, rows]) => <tr key={kind}>
            <th scope="row"><span className="kind-label"><KindIcon kind={kind} className="h-4 w-4 text-muted" /> {KIND_LABELS[kind]}</span></th>{cells(rows)}
          </tr>)}</tbody>
          <tfoot><tr><th scope="row">Total</th>{cells(all)}</tr></tfoot>
        </table></div>
      </section>
      <section className="report-items" aria-label="Component results">
        <div className="section-heading"><h3>Component results</h3>
          <div className="app-segmented" role="group" aria-label="Report filter">
            {([{ id: "all", label: `All (${all.length})` }, { id: "attention", label: `Needs attention (${attention.length})` }] as const).map(({ id, label }) =>
              <button key={id} type="button" aria-pressed={filter === id} onClick={() => setFilter(id)}
                className={cn("app-segmented-button", filter === id && "app-segmented-button-active")}>{label}</button>)}
          </div>
        </div>
        {visible.length ? <div className="report-list">
          <div className="report-row report-head" aria-hidden="true"><span>Component</span>{stages.map(([key, label]) => <span key={key}>{label}</span>)}<span>Reason</span><span /></div>
          <ul>{visible.map((row, index) => <li key={row.id + index} className="report-row">
            <div className="component-label"><KindIcon kind={row.kind} className="h-4 w-4 shrink-0 text-muted" />
              <div className="component-name"><button type="button" className="row-action" onClick={() => setItem(row)}>{row.name}</button><span className="component-kind">{KIND_LABELS[row.kind]}</span></div>
            </div>
            {stages.map(([key, label]) => <div className="stage-cell" key={key}><span className="stage-label">{label}</span><Status result={row[key]} /></div>)}
            <p className="row-reason">{(row.conversion.status === "unconverted" ? row.conversion.reason : row.import.reason) || row.conversion.reason}</p>
            <ChevronRight className="row-arrow h-4 w-4" aria-hidden="true" />
          </li>)}</ul>
        </div> : <p className="empty">{filter === "attention" ? "No components need attention." : "No conversion results."}</p>}
      </section>
      {report.observedAt && <p className="report-footer text-[12px] text-muted">Last import check: {formatDate(report.observedAt)}</p>}
    </>}
    {item && <DetailSheet open title={item.name} meta={<KindBadge kind={item.kind} />} onClose={() => setItem(undefined)}>
      <div className="asm-lab space-y-4">
        <div className="stage-details">{stages.map(([key, label]) => <section className="stage-detail" key={key}>
          <h3>{label}<Status result={item[key]} /></h3>
          <p>{item[key].reason}</p>
        </section>)}</div>
        <div className="values"><ValuePanel label="Source value" value={item.source} /><ValuePanel label="Paperclip value" value={item.target} /></div>
      </div>
    </DetailSheet>}
  </section>;
}
