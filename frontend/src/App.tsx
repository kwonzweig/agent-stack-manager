import { useCallback, useEffect, useRef, useState } from "react";
import { AlertCircle, ArrowRight, Plug2 } from "lucide-react";
import { api, ApiError, catalogMember, errorMessage, packagePath } from "./api";
import type { CatalogItem, Component, Consumer, Package, PackageKind, PackageSummary } from "./types";
import { createDraft, isDirty, makePayload, overlappingChanges, rebaseDraft, type Draft } from "./draft";
import CatalogPage from "./catalog/CatalogPage";
import { hrefFor, Sidebar, type Route } from "./components/Sidebar";
import { Modal, PresetDialog } from "./components/PresetDialog";
import { WorkspaceHeader, PresetContents } from "./components/Workspace";
import { ComponentPicker } from "./components/ComponentPicker";
import { ComponentDetails } from "./components/ComponentDetails";
import { PaperclipReport } from "./components/PaperclipReport";
import { PresetExport } from "./components/PresetExport";
import { SourceFiles } from "./components/SourceFiles";

interface CatalogData {
  items: CatalogItem[];
  sources: { name: string; url: string }[];
}
const defaultCatalog: CatalogData = { items: [], sources: [] };

type ListState<T> = { data: T; loading: boolean; error: string };
function useList<T>(path: string, initial: T) {
  const [current, setCurrent] = useState<ListState<T>>({ data: initial, loading: true, error: "" });
  const request = useRef<AbortController | undefined>(undefined);
  const refresh = useCallback(async () => {
    request.current?.abort();
    const pending = new AbortController();
    request.current = pending;
    setCurrent(prev => ({ ...prev, loading: true, error: "" }));
    try {
      const data = await api<T>(path, { signal: pending.signal });
      if (!pending.signal.aborted) setCurrent({ data, loading: false, error: "" });
    } catch (error) {
      if (!pending.signal.aborted) setCurrent(prev => ({ ...prev, loading: false, error: errorMessage(error) }));
    }
  }, [path]);
  useEffect(() => {
    void refresh();
    return () => request.current?.abort();
  }, [refresh]);
  return { ...current, refresh, setCurrent };
}

function readRoute(): Route {
  const hash = location.hash.slice(1);
  const params = new URLSearchParams(hash);
  const view = params.get("view") || hash.split("/")[0];
  if (view === "presets") {
    const tab = params.get("tab");
    let legacyId: string | undefined;
    try { legacyId = hash.startsWith("presets/") ? decodeURIComponent(hash.slice(8)) : undefined; } catch {}
    const id = params.get("preset") || legacyId;
    if (tab === "source") return { view, id, tab };
    // "paperclip" is the tab's name before Export held one tab per consumer.
    if (tab === "export" || tab === "paperclip") return { view, id, tab: "export", consumer: params.get("consumer") || (tab === "paperclip" ? "paperclip" : undefined) };
    return { view, id, tab: "components" };
  }
  return { view: view === "consumers" ? "consumers" : "catalog" };
}

function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return <div className="flex flex-wrap items-center gap-2 rounded-lg border border-danger bg-danger-bg px-3 py-2 text-[13px] text-danger" role="alert">
    <AlertCircle className="h-4 w-4 shrink-0" /> {message}
    {onRetry && <button type="button" className="ml-auto underline" onClick={onRetry}>Retry</button>}
  </div>;
}

export function App() {
  const [route, setRoute] = useState(readRoute);
  const [theme, setTheme] = useState<"light" | "dark">(() => localStorage.getItem("asm:theme") === "dark" ? "dark" : "light");
  const presets = useList("/api/presets", { presets: [] as PackageSummary[] });
  const catalog = useList("/api/catalog", defaultCatalog);
  const consumers = useList("/api/consumers", { consumers: [] as Consumer[] });
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [loadErrors, setLoadErrors] = useState<Record<string, string>>({});
  const pendingLoads = useRef(new Map<string, Promise<Package>>());
  const [saving, setSaving] = useState<string[]>([]);
  const [saveErrors, setSaveErrors] = useState<Record<string, { message: string; conflict: boolean }>>({});
  const [overlay, setOverlay] = useState<
    | { type: "create"; selected: string[]; kind: PackageKind }
    | { type: "edit" | "picker" | "conflict"; id: string }
    | { type: "component"; item: Component; id?: string }
  >();
  const [notice, setNotice] = useState("");
  const timer = useRef<number | undefined>(undefined);
  const main = useRef<HTMLElement>(null);
  const preferred = presets.data.presets.find(p => p.kind === "preset") || presets.data.presets[0];
  const routeId = route.view === "presets" ? route.id || preferred?.id : undefined;
  const [lastPreset, setLastPreset] = useState<string>();
  const draft = routeId && Object.hasOwn(drafts, routeId) ? drafts[routeId] : undefined;
  const activeSave = routeId && Object.hasOwn(saveErrors, routeId) ? saveErrors[routeId] : undefined;
  const activeLoadError = routeId && Object.hasOwn(loadErrors, routeId) ? loadErrors[routeId] : "";
  const activeLoading = routeId ? saving.includes(routeId) : false;
  const closeOverlay = useCallback(() => setOverlay(undefined), []);

  useEffect(() => {
    const sync = () => { setRoute(readRoute()); setOverlay(undefined); };
    window.addEventListener("popstate", sync);
    window.addEventListener("hashchange", sync);
    return () => {
      window.removeEventListener("popstate", sync);
      window.removeEventListener("hashchange", sync);
      window.clearTimeout(timer.current);
    };
  }, []);
  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    document.documentElement.style.colorScheme = theme;
    localStorage.setItem("asm:theme", theme);
  }, [theme]);
  useEffect(() => { main.current?.scrollTo(0, 0); }, [route.view, routeId, route.tab, route.consumer]);

  const getPackage = useCallback((id: string) => {
    const existing = pendingLoads.current.get(id);
    if (existing) return existing;
    setLoadErrors(prev => ({ ...prev, [id]: "" }));
    const pending = api<Package>(packagePath(id)).then(pkg => {
      setDrafts(prev => Object.hasOwn(prev, id) ? prev : { ...prev, [id]: createDraft(pkg) });
      return pkg;
    }).catch(error => {
      setLoadErrors(prev => ({ ...prev, [id]: errorMessage(error) }));
      throw error;
    }).finally(() => pendingLoads.current.delete(id));
    pendingLoads.current.set(id, pending);
    return pending;
  }, []);

  useEffect(() => {
    if (!routeId) return;
    setLastPreset(routeId);
    if (!draft) void getPackage(routeId).catch(() => {});
  }, [routeId, draft, getPackage]);

  function navigate(next: Route) {
    setOverlay(undefined);
    const href = hrefFor(next);
    if (location.hash !== href) history.pushState(null, "", href);
    setRoute(next);
  }
  const openPreset = (id: string) => navigate({ view: "presets", id });
  const pickerItems = catalog.data.items.filter(item => item.type !== "preset").map(catalogMember)
    .filter(item => item.id !== "package:" + routeId && item.id !== "instruction");
  const currentItems = new Map(pickerItems.map(item => [item.id, item]));
  function chosen(ids: string[]) {
    return [...new Set(ids)].map(id => currentItems.get(id)).filter((item): item is Component => !!item);
  }
  function updateDraft(id: string, update: (draft: Draft) => Draft) {
    setDrafts(prev => Object.hasOwn(prev, id) ? { ...prev, [id]: update(prev[id]) } : prev);
  }
  function addMembers(id: string, items: Component[], pkg?: Package) {
    setDrafts(prev => {
      const before = Object.hasOwn(prev, id) ? prev[id] : pkg && createDraft(pkg);
      if (!before) return prev;
      const existing = new Set(before.members.map(item => item.id));
      return { ...prev, [id]: { ...before, members: [...before.members, ...items.filter(item => !existing.has(item.id))] } };
    });
  }
  async function addToPreset(id: string, componentIds: string[]) {
    const pkg = Object.hasOwn(drafts, id) ? undefined : await getPackage(id);
    addMembers(id, chosen(componentIds).filter(item => item.id !== "package:" + id), pkg);
    openPreset(id);
  }
  function feedback(message: string) {
    setNotice(message);
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setNotice(""), 2800);
  }
  function recordSave(pkg: Package, snapshot?: Draft) {
    setDrafts(prev => {
      const current = Object.hasOwn(prev, pkg.id) ? prev[pkg.id] : undefined;
      return { ...prev, [pkg.id]: current && snapshot && current !== snapshot ? rebaseDraft(current, pkg, snapshot) : createDraft(pkg) };
    });
    // Keep the newly saved title/count visible while reloading catalog sources.
    presets.setCurrent(prev => ({ ...prev, data: { presets: [...prev.data.presets.filter(item => item.id !== pkg.id), pkg].sort((a, b) => a.id.localeCompare(b.id)) } }));
    void presets.refresh(); void catalog.refresh();
  }
  async function save(id: string) {
    const snapshot = Object.hasOwn(drafts, id) ? drafts[id] : undefined;
    if (!snapshot || saving.includes(id)) return;
    setSaving(prev => [...prev, id]);
    setSaveErrors(prev => ({ ...prev, [id]: { message: "", conflict: false } }));
    try {
      const pkg = await api<Package>(packagePath(id), { method: "PATCH", body: makePayload(snapshot) });
      recordSave(pkg, snapshot);
      feedback("Saved " + pkg.title + ".");
    } catch (error) {
      setSaveErrors(prev => ({ ...prev, [id]: { message: errorMessage(error), conflict: error instanceof ApiError && error.status === 409 } }));
    } finally {
      setSaving(prev => prev.filter(value => value !== id));
    }
  }

  return <div className="relative flex h-full w-full flex-col overflow-hidden bg-background text-primary md:flex-row">
    <Sidebar route={routeId ? { ...route, id: routeId } : route} presets={presets.data.presets} onNavigate={navigate}
      onCreate={() => setOverlay({ type: "create", selected: [], kind: "preset" })} theme={theme}
      onTheme={() => setTheme(value => value === "light" ? "dark" : "light")} />
    <main ref={main} inert={overlay?.type === "component"} className="min-h-0 min-w-0 flex-1 overflow-y-auto" id="main">
      {presets.error && <div className="mx-auto max-w-[1240px] px-5 pt-5"><ErrorBox message={presets.error} onRetry={presets.refresh} /></div>}
      {route.view === "catalog" ? <CatalogPage
        items={catalog.data.items} sources={catalog.data.sources} presets={presets.data.presets}
        onOpenItem={item => setOverlay({ type: "component", item: catalogMember(item) })}
        onOpenPreset={openPreset}
        onCreatePreset={(selected, kind = "preset") => setOverlay({ type: "create", selected, kind })}
        onAddToPreset={addToPreset} isLoading={catalog.loading} error={catalog.error} onRetry={catalog.refresh}
      /> : <div className="mx-auto flex min-h-full max-w-[1240px] flex-col gap-4 px-5 pb-5 pt-5">
        {route.view === "consumers" ? <section className="app-page">
          <header className="app-page-header"><h1 className="app-page-title">Consumers</h1></header>
          {consumers.loading ? <p className="text-[13px] text-muted" role="status">Loading consumers…</p> :
            consumers.error ? <ErrorBox message={consumers.error} onRetry={consumers.refresh} /> :
            <ul className="app-panel divide-y divide-border-subtle">
              {consumers.data.consumers.map(consumer => <li key={consumer.id} className="flex flex-wrap items-center gap-3 px-3.5 py-3">
                <span className="flex h-7 w-7 items-center justify-center rounded-lg border border-border-subtle bg-surface-hover text-muted"><Plug2 className="h-4 w-4" /></span>
                <div className="min-w-0 flex-1"><h2 className="text-[14px] font-semibold text-primary">{consumer.name}</h2>
                  <p className="text-[12px] text-muted">{consumer.supported ? "Conversion and import status" : "Not implemented"}</p>
                </div>
                {consumer.supported && preferred && <button type="button" className="app-button-secondary" onClick={() =>
                  navigate({ view: "presets", id: lastPreset && presets.data.presets.some(p => p.id === lastPreset) ? lastPreset : preferred.id, tab: "export", consumer: consumer.id })}>
                  Open preset report <ArrowRight className="h-4 w-4" />
                </button>}
              </li>)}
            </ul>}
        </section> : !draft ? routeId ? activeLoadError ?
          <ErrorBox message={activeLoadError} onRetry={() => { void getPackage(routeId).catch(() => {}); }} /> :
          <p role="status" className="text-[13px] text-muted">Loading preset…</p> : presets.loading ?
          <p role="status" className="text-[13px] text-muted">Loading presets…</p> :
          <p className="text-[13px] text-muted">No presets yet.</p> : <div className="app-page" key={draft.original.id}>
            <WorkspaceHeader draft={draft} route={{ ...route, id: draft.original.id }} onNavigate={navigate}
              onEdit={() => setOverlay({ type: "edit", id: draft.original.id })}
              onIcon={icon => updateDraft(draft.original.id, before => ({ ...before, icon }))}
              onSave={() => void save(draft.original.id)} saving={activeLoading} />
            {activeSave?.message && <div className="space-y-2">
              <ErrorBox message={activeSave.message} />
              {activeSave.conflict && <button type="button" className="app-button-secondary" onClick={() => setOverlay({ type: "conflict", id: draft.original.id })}>Review saved version</button>}
            </div>}
            {route.tab === "export" ? <PresetExport consumers={consumers.data.consumers.filter(consumer => consumer.supported)}
                loading={consumers.loading} error={consumers.error} onRetry={consumers.refresh}
                route={{ ...route, id: draft.original.id }} onNavigate={navigate}
                render={(consumer, tabs) => consumer === "paperclip" ? <PaperclipReport heading={tabs}
                  id={draft.original.id} revision={draft.original.revision} dirty={isDirty(draft)} /> : null} />
              : route.tab === "source" ? <SourceFiles id={draft.original.id} files={draft.original.files} dirty={isDirty(draft)} />
              : <PresetContents draft={draft} busy={activeLoading}
                onOpen={item => setOverlay({ type: "component", item, id: draft.original.id })}
                onAdd={() => setOverlay({ type: "picker", id: draft.original.id })}
                onRemove={ids => updateDraft(draft.original.id, before => ({ ...before, members: before.members.filter(item => !ids.includes(item.id)) }))} />}
          </div>}
      </div>}
    </main>
    {overlay?.type === "create" && <PresetDialog defaultKind={overlay.kind} onClose={closeOverlay}
      onSave={async fields => {
        const pkg = await api<Package>("/api/presets", { method: "POST", body: { ...fields, componentIds: chosen(overlay.selected).map(item => item.id) } });
        recordSave(pkg); openPreset(pkg.id); feedback("Created " + pkg.title + ".");
      }} />}
    {overlay?.type === "edit" && drafts[overlay.id] && <PresetDialog initial={drafts[overlay.id]} onClose={closeOverlay}
      onSave={fields => updateDraft(overlay.id, before => ({ ...before, ...fields }))} />}
    {overlay?.type === "picker" && drafts[overlay.id] && <ComponentPicker items={pickerItems}
      existing={new Set(drafts[overlay.id].members.map(item => item.id))} onClose={closeOverlay}
      onAdd={items => { addMembers(overlay.id, items); closeOverlay(); }}
      error={catalog.error} loading={catalog.loading} onRetry={catalog.refresh} />}
    {overlay?.type === "component" && <ComponentDetails item={overlay.item} onClose={closeOverlay}
      presetId={overlay.id && drafts[overlay.id].original.components.some(item => item.id === overlay.item.id) ? overlay.id : undefined}
      instruction={overlay.id ? drafts[overlay.id].instruction : undefined}
      onInstruction={overlay.id && overlay.item.id === "instruction" ? instruction =>
        updateDraft(overlay.id!, before => ({ ...before, instruction })) : undefined}
      onBrowseStack={overlay.item.kind === "package" && overlay.item.id.startsWith("package:") ?
        () => openPreset(overlay.item.id.slice(8)) : undefined} />}
    {overlay?.type === "conflict" && drafts[overlay.id] && <ConflictDialog draft={drafts[overlay.id]} onClose={closeOverlay}
      onResolve={next => {
        updateDraft(overlay.id, () => next);
        setSaveErrors(prev => ({ ...prev, [overlay.id]: { message: "", conflict: false } }));
        closeOverlay();
      }} />}
    <div role="status" aria-live="polite" className="pointer-events-none fixed bottom-4 right-4 z-50">
      {notice && <p className="rounded-lg border border-border-subtle bg-surface px-4 py-2 text-[13px] text-secondary shadow-lg">{notice}</p>}
    </div>
  </div>;
}

function ConflictDialog({ draft, onClose, onResolve }: { draft: Draft; onClose: () => void; onResolve: (next: Draft) => void }) {
  const [latest, setLatest] = useState<Package>();
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const id = draft.original.id;
  useEffect(() => {
    const pending = new AbortController();
    setError("");
    api<Package>(packagePath(id), { signal: pending.signal }).then(result => {
      if (!pending.signal.aborted) setLatest(result);
    }).catch(err => { if (!pending.signal.aborted) setError(errorMessage(err)); });
    return () => pending.abort();
  }, [id, attempt]);
  const fieldNames = { title: "Name", description: "Description", kind: "Type", icon: "Icon", workArea: "Work area", usage: "Usage", instruction: "Instruction" };
  return <Modal title="Review saved version" onClose={onClose}>
    {error ? <ErrorBox message={error} onRetry={() => setAttempt(v => v + 1)} /> : latest ?
      <div className="space-y-3 text-[13px] text-secondary">
        <p><strong>{latest.title}</strong> has changed since you started editing.</p>
        <p>{latest.components.length} components in the saved version.</p>
        {overlappingChanges(draft, latest).length > 0 && <p>Both versions changed: {overlappingChanges(draft, latest).map(field => fieldNames[field]).join(", ")}. Keep your edits to use your values for these fields.</p>}
        <div className="flex flex-wrap justify-end gap-2">
          <button type="button" className="app-button-secondary" onClick={() => onResolve(createDraft(latest))}>Use saved version</button>
          <button type="button" className="app-button-primary" onClick={() => onResolve(rebaseDraft(draft, latest))}>Keep my edits</button>
        </div>
      </div> : <p role="status" className="text-[13px] text-muted">Loading saved version…</p>}
  </Modal>;
}

