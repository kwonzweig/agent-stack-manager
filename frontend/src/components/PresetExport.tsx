import type { ReactNode } from "react";
import type { Consumer } from "../types";
import { cn } from "../utils";
import { hrefFor, type Route } from "./Sidebar";

// One tab per consumer the server supports. The consumer's view places the tabs in its own heading row.
export function PresetExport({ consumers, loading, error, onRetry, route, onNavigate, render }: {
  consumers: Consumer[]; loading: boolean; error: string; onRetry: () => void;
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
