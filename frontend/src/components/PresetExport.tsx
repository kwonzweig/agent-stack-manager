import type { ReactNode } from "react";
import { Download } from "lucide-react";
import { packagePath } from "../api";
import type { Consumer, ConsumerData, PackageKind } from "../types";
import { cn } from "../utils";
import { hrefFor, type Route } from "./Sidebar";
import { PaperclipReport, useConversion } from "./PaperclipReport";
import { SupportTable } from "./SupportTable";

// One tab per consumer ASM exports to. The consumer's view places the tabs in its own heading row.
export function PresetExport({ consumers, loading, error, onRetry, route, onNavigate, render }: {
  consumers: Pick<Consumer, "id" | "name">[]; loading: boolean; error: string; onRetry: () => void;
  route: Route; onNavigate: (route: Route) => void;
  render: (consumer: string, tabs: ReactNode) => ReactNode;
}) {
  if (loading && !consumers.length) return <p role="status" className="text-[13px] text-muted">Loading export targets…</p>;
  if (error) return <p role="alert" className="text-[13px] text-danger">{error} <button type="button" className="underline" onClick={onRetry}>Retry</button></p>;
  const active = consumers.find(consumer => consumer.id === route.consumer) ?? consumers[0];
  if (!active) return <p className="text-[13px] text-muted">No export targets.</p>;
  const tabs = <nav className="app-segmented w-fit max-w-full" aria-label="Export targets">
    {consumers.map(consumer => {
      const next: Route = { ...route, tab: "export", consumer: consumer.id };
      return <a key={consumer.id} href={hrefFor(next)} aria-current={consumer === active ? "page" : undefined}
        onClick={e => { if (!e.metaKey && !e.ctrlKey && !e.shiftKey && !e.altKey) { e.preventDefault(); onNavigate(next); } }}
        className={cn("app-segmented-button py-1.5", consumer === active && "app-segmented-button-active")}>{consumer.name}</a>;
    })}
  </nav>;
  return <>{render(active.id, tabs) ?? tabs}</>;
}

// The Export tab: what each app supports for this preset, then one tab per app ASM exports to.
interface ExportTabProps {
  id: string; kind: PackageKind; revision: string; dirty: boolean; data: ConsumerData; loading: boolean; error: string;
  onRetry: () => void; route: Route; onNavigate: (route: Route) => void;
  inventory?: boolean;
}

export function PresetExportTab(props: ExportTabProps) {
  if (props.inventory) {
    const { id, dirty, onRetry, route, onNavigate } = props;
    return <PresetExport consumers={[{ id: "ccswitch", name: "CC Switch" }]} loading={false} error=""
      onRetry={onRetry} route={route} onNavigate={onNavigate} render={(_, tabs) =>
        <section className="asm-preset" aria-label="CC Switch review">
          <div className="section-heading flex-wrap">
            {tabs}
            {dirty ? <p className="text-[12px] text-muted">Save changes to download.</p> :
              <a className="app-button-secondary" href={packagePath(id, "/cc-switch")} download>
                <Download className="h-4 w-4" aria-hidden /> Download CC Switch review
              </a>}
          </div>
        </section>} />;
  }
  return <PaperclipExportTab {...props} />;
}

function PaperclipExportTab({ id, kind, revision, dirty, data, loading, error, onRetry, route, onNavigate }: ExportTabProps) {
  const conversion = useConversion(id, revision);
  return <>
    <SupportTable data={data} report={conversion.report} packageKind={kind} />
    <PresetExport consumers={data.consumers.filter(consumer => consumer.export && consumer.id === "paperclip")} loading={loading} error={error}
      onRetry={onRetry} route={route} onNavigate={onNavigate}
      render={(consumer, tabs) => consumer === "paperclip"
        ? <PaperclipReport heading={tabs} id={id} conversion={conversion} dirty={dirty} /> : null} />
  </>;
}
