import type { Route } from "../components/Sidebar";

// Reads the location hash that hrefFor writes.
export function readRoute(hash: string): Route {
  const params = new URLSearchParams(hash);
  if (params.get("view") !== "presets") return { view: "catalog" };
  const id = params.get("preset") || undefined;
  const tab = params.get("tab");
  if (tab === "source") return { view: "presets", id, tab };
  if (tab === "export") return { view: "presets", id, tab, consumer: params.get("consumer") || undefined };
  return { view: "presets", id, tab: "components" };
}
