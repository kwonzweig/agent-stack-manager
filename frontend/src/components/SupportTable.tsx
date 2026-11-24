import type { ConsumerData, PackageKind, Report } from "../types";
import { columnName, SUPPORT_ICONS, SUPPORT_LABELS, supportRows, unplacedPlugins, type TableCell } from "../lib/support";
import { KindIcon } from "./ComponentUI";
import { InfoPopover } from "./InfoPopover";

function Cell({ cell, label }: { cell: TableCell; label: string }) {
  return <td>
    <span className="support-cell">
      <span className={"support-text support-" + cell.tone}>{cell.text}</span>
      <InfoPopover label={label} note={cell.note} doc={cell.doc} />
    </span>
  </td>;
}

// CC Switch's "Supported Features by Tool" form: one row per component kind, one column per app.
export function SupportTable({ data, report, packageKind }: { data: ConsumerData; report?: Pick<Report, "consumer" | "items">; packageKind: PackageKind }) {
  if (!data.consumers.length) return null;
  const rows = supportRows(data, report);
  const unplaced = unplacedPlugins(report?.items);
  return <section className="asm-preset support-by-app" aria-label="Support by app">
    <div className="section-heading"><h3>Support by app</h3></div>
    <div className="summary-box support-scroll"><table className="summary-table support-table">
      <thead><tr>
        <th scope="col">Component type (in this {packageKind})</th>
        {data.consumers.map(consumer => <th key={consumer.id} scope="col">{columnName(consumer)}</th>)}
      </tr></thead>
      <tbody>{rows.map(row => <tr key={row.kind}>
        <th scope="row"><span className="kind-label"><KindIcon kind={SUPPORT_ICONS[row.kind]} className="h-4 w-4 text-muted" />
          {SUPPORT_LABELS[row.kind]}{row.count !== null && <span className="support-count">({row.count})</span>}</span></th>
        {row.cells.map((cell, index) => <Cell key={data.consumers[index].id} cell={cell}
          label={`About ${SUPPORT_LABELS[row.kind]} in ${data.consumers[index].name}`} />)}
      </tr>)}</tbody>
    </table></div>
    {unplaced.length > 0 && <p role="alert" className="mt-2 text-[12px] text-danger">
      Needs attention: {unplaced.map(row => row.name).join(", ")} {unplaced.length === 1 ? "is" : "are"} in
      neither plugin row, because {unplaced.length === 1 ? "its source names" : "their sources name"} no
      .claude-plugin/ or .codex-plugin/ manifest.
    </p>}
  </section>;
}
