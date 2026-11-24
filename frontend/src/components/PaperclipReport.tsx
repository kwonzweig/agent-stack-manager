import { useState, type ReactNode } from "react";
import { Ban, ChevronRight, CircleCheck, CircleX, FolderGit2 } from "lucide-react";
import { cn } from "../utils";
import type { Report, ReportItem, Result } from "../types";
import { KindBadge, KindIcon, KIND_LABELS, KINDS } from "./ComponentUI";
import { ValuePanel } from "./ComponentDetails";
import { DetailSheet } from "./DetailSheet";
import { conversionStatus, outcome, targetFile } from "../lib/paperclipOutcome";

const icons = { converted: CircleCheck, "not-in-format": Ban, adapter: Ban, unconverted: CircleX } as const;
function Status({ result }: { result: Result }) {
  const { id, label, tone } = conversionStatus(result);
  const Icon = icons[id];
  return <span className={"status status-" + tone}><Icon className="h-3.5 w-3.5" aria-hidden="true" />{label}</span>;
}
const filters = [["all", "All"], ["expected", "Left out as expected"], ["attention", "Needs attention"]] as const;
const columns = ["Type", "Total", "Converted", "Left out as expected", "Needs attention"];
const countTones = ["", "count-good", "", "count-bad"];

function displayKind(kind: ReportItem["kind"]) {
  return KINDS.includes(kind) ? kind : "other";
}

export function PaperclipReport({ report, download, dirty, heading }: {
  report: Omit<Report, "files">; download: ReactNode; dirty: boolean; heading: ReactNode;
}) {
  const [filter, setFilter] = useState<(typeof filters)[number][0]>("all");
  const [item, setItem] = useState<ReportItem>();
  const all = report.items;
  const shown = { all, expected: all.filter(row => outcome(row) === "expected"), attention: all.filter(row => outcome(row) === "attention") };
  const visible = shown[filter];
  const groups = KINDS.map(kind => [kind, all.filter(row => displayKind(row.kind) === kind)] as const).filter(([, rows]) => rows.length);
  const metrics = (rows: ReportItem[]) => [rows.length,
    ...(["converted", "expected", "attention"] as const).map(result => rows.filter(row => outcome(row) === result).length)];
  function cells(rows: ReportItem[]) {
    return metrics(rows).map((count, index) => <td className={cn("number", count > 0 && countTones[index])} key={index}>{count}</td>);
  }
  return <section className="asm-preset" aria-label="Paperclip conversion report">
    <div className="section-heading flex-wrap">
      {heading}
      <div className="flex flex-wrap items-center gap-2">
        {report.folder && (report.folder.url
          ? <a className="app-button-secondary" href={report.folder.url} target="_blank" rel="noreferrer"
              title="The export folder on GitHub, once it is committed"><FolderGit2 className="h-4 w-4" /> {report.folder.path}</a>
          : <span className="inline-flex items-center gap-1.5 text-[13px] text-muted"><FolderGit2 className="h-4 w-4" /> {report.folder.path}</span>)}
        {download}
      </div>
    </div>
    {dirty && <p className="mb-2 text-[12px] text-muted">Showing the saved revision.</p>}
      <section aria-label="Conversion summary">
        <div className="section-heading"><h3>Conversion summary</h3></div>
        <div className="summary-box"><table className="summary-table">
          <thead><tr>{columns.map((name, index) => <th key={name} className={index ? "number" : ""} scope="col">{name}</th>)}</tr></thead>
          <tbody>{groups.map(([kind, rows]) => <tr key={kind}>
            <th scope="row"><span className="kind-label"><KindIcon kind={kind} className="h-4 w-4 text-muted" /> {KIND_LABELS[kind]}</span></th>{cells(rows)}
          </tr>)}</tbody>
          <tfoot><tr><th scope="row">Total</th>{cells(all)}</tr></tfoot>
        </table></div>
      </section>
      <section className="report-items" aria-label="Component results">
        <div className="section-heading"><h3>Component results</h3>
          <div className="app-segmented max-w-full flex-wrap" role="group" aria-label="Report filter">
            {filters.map(([id, label]) =>
              <button key={id} type="button" aria-pressed={filter === id} onClick={() => setFilter(id)}
                className={cn("app-segmented-button", filter === id && "app-segmented-button-active")}>{label} ({shown[id].length})</button>)}
          </div>
        </div>
        {visible.length ? <div className="report-list">
          <ul>{visible.map((row, index) => <li key={row.id + index} className="report-row">
            <div className="component-label"><KindIcon kind={displayKind(row.kind)} className="h-4 w-4 shrink-0 text-muted" />
              <div className="component-name"><button type="button" className="row-action" onClick={() => setItem(row)}>{row.name}</button><span className="component-kind">{KIND_LABELS[displayKind(row.kind)]}</span>
                {row.originPackage && <span className="component-kind">From {row.originPackage.title}</span>}</div>
            </div>
            <Status result={row.conversion} />
            <p className="row-reason">{row.conversion.reason}{targetFile(row) && <> <code className="row-target">{targetFile(row)}</code></>}</p>
            <ChevronRight className="row-arrow h-4 w-4" aria-hidden="true" />
          </li>)}</ul>
        </div> : <p className="empty">{{ all: "No conversion results.", expected: "No components left out as expected.", attention: "No components need attention." }[filter]}</p>}
      </section>
    {item && <DetailSheet open title={item.name} meta={<KindBadge kind={displayKind(item.kind)} />} backLabel="Paperclip export" onClose={() => setItem(undefined)}>
      <div className="asm-preset space-y-4">
        <section className="conversion-detail">
          <h3>Conversion<Status result={item.conversion} /></h3>
          <p>{item.conversion.reason}</p>
        </section>
        <div className="values"><ValuePanel label="Source value" value={item.source} /><ValuePanel label="Paperclip value" value={item.target} /></div>
      </div>
    </DetailSheet>}
  </section>;
}
