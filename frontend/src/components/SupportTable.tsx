import { Info } from "lucide-react";
import type { ConsumerData, Report } from "../types";
import { columnName, SUPPORT_ICONS, SUPPORT_LABELS, supportRows, unplacedPlugins, type TableCell } from "../lib/support";
import { KindIcon } from "./ComponentUI";

function Cell({ cell }: { cell: TableCell }) {
  const hover = [cell.note, cell.doc].filter(Boolean).join("\n");
  return <td>
    <span className="support-cell">
      <span className={"support-text support-" + cell.tone}>{cell.text}</span>
      <a className="support-info" href={cell.doc} target="_blank" rel="noreferrer" title={hover}
        aria-label={"Source: " + cell.doc}><Info className="h-3.5 w-3.5" aria-hidden="true" /></a>
    </span>
  </td>;
}

// CC Switch's "Supported Features by Tool" form: one row per component kind, one column per app.
export function SupportTable({ data, report }: { data: ConsumerData; report?: Report }) {
  if (!data.consumers.length) return null;
  const rows = supportRows(data, report);
  const unplaced = unplacedPlugins(report?.items);
  return <section className="asm-preset support-by-app" aria-label="Support by app">
    <div className="section-heading"><h3>Support by app</h3></div>
    <div className="summary-box support-scroll"><table className="summary-table support-table">
      <thead><tr>
        <th scope="col">Component type (in this preset)</th>
        {data.consumers.map(consumer => <th key={consumer.id} scope="col">{columnName(consumer)}</th>)}
      </tr></thead>
      <tbody>{rows.map(row => <tr key={row.kind}>
        <th scope="row"><span className="kind-label"><KindIcon kind={SUPPORT_ICONS[row.kind]} className="h-4 w-4 text-muted" />
          {SUPPORT_LABELS[row.kind]}{row.count !== null && <span className="support-count">({row.count})</span>}</span></th>
        {row.cells.map((cell, index) => <Cell key={data.consumers[index].id} cell={cell} />)}
      </tr>)}</tbody>
    </table></div>
    {unplaced.length > 0 && <p role="alert" className="mt-2 text-[12px] text-danger">
      Needs attention: {unplaced.map(row => row.name).join(", ")} {unplaced.length === 1 ? "is" : "are"} in
      neither plugin row, because {unplaced.length === 1 ? "its source names" : "their sources name"} no
      .claude-plugin/ or .codex-plugin/ manifest.
    </p>}
  </section>;
}
