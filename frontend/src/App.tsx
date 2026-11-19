import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AlertCircle } from "lucide-react";
import { api, ApiError, catalogMember, errorMessage, packagePath } from "./api";
import type { CatalogItem, Component, ConsumerData, Package, PackageKind, PackageSummary, SourceData } from "./types";
import { withSourceFacts } from "./catalog/catalogItem";
import { createDraft, isDirty, listedMember, makePayload, overlappingChanges, rebaseDraft, withComponentInclusion, withInventorySelection, withMembers, type Draft } from "./draft";
import CatalogPage from "./catalog/CatalogPage";
import { hrefFor, Sidebar, type Route } from "./components/Sidebar";
import { readRoute } from "./lib/route";
import { Modal, PresetDialog } from "./components/PresetDialog";
import { WorkspaceHeader, PresetContents } from "./components/Workspace";
import { ComponentPicker } from "./components/ComponentPicker";
import { ComponentDetails } from "./components/ComponentDetails";
import { PresetExportTab } from "./components/PresetExport";
import { PresetList } from "./components/PresetList";
import { SourceFiles } from "./components/SourceFiles";
import { ComponentMemberships } from "./components/ComponentMemberships";

interface CatalogData {
  items: CatalogItem[];
}
const defaultCatalog: CatalogData = { items: [] };

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

const currentRoute = () => readRoute(location.hash.slice(1));

function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return <div className="flex flex-wrap items-center gap-2 rounded-lg border border-danger bg-danger-bg px-3 py-2 text-[13px] text-danger" role="alert">
    <AlertCircle className="h-4 w-4 shrink-0" /> {message}
    {onRetry && <button type="button" className="ml-auto underline" onClick={onRetry}>Retry</button>}
  </div>;
}

export function App() {
  const [route, setRoute] = useState(currentRoute);
  const [theme, setTheme] = useState<"light" | "dark">(() => localStorage.getItem("asm:theme") === "dark" ? "dark" : "light");
  const presets = useList("/api/presets", { presets: [] as PackageSummary[] });
  const catalog = useList("/api/catalog", defaultCatalog);
  // Descriptions, stars and installs come from each item's source, read when the dashboard opens.
  const sourceFacts = useList<SourceData>("/api/catalog/sources", { items: {}, errors: [] });
  const catalogItems = useMemo(() => withSourceFacts(catalog.data.items, sourceFacts.data.items),
    [catalog.data.items, sourceFacts.data.items]);
  const consumers = useList<ConsumerData>("/api/consumers", { kinds: [], consumers: [] });
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [loadErrors, setLoadErrors] = useState<Record<string, string>>({});
  const pendingLoads = useRef(new Map<string, Promise<Package>>());
  const [saving, setSaving] = useState<string[]>([]);
  const [saveErrors, setSaveErrors] = useState<Record<string, { message: string; conflict: boolean }>>({});
  const [overlay, setOverlay] = useState<
    | { type: "create"; selected: string[]; kind: PackageKind }
    | { type: "edit" | "picker"; id: string }
    | { type: "component"; item: Component; id?: string }
  >();
  const [conflictId, setConflictId] = useState<string>();
  const [notice, setNotice] = useState("");
  const timer = useRef<number | undefined>(undefined);
  const main = useRef<HTMLElement>(null);
  const routeId = route.view === "presets" ? route.id : undefined;
  const draft = routeId && Object.hasOwn(drafts, routeId) ? drafts[routeId] : undefined;
  const componentDraft = overlay?.type === "component" && overlay.id ? drafts[overlay.id] : undefined;
  const inventoryItem = overlay?.type === "component" && overlay.item.inventoryId
    ? componentDraft?.original.appInventory?.find(item => item.id === overlay.item.inventoryId) : undefined;
  const activeSave = routeId && Object.hasOwn(saveErrors, routeId) ? saveErrors[routeId] : undefined;
  const activeLoadError = routeId && Object.hasOwn(loadErrors, routeId) ? loadErrors[routeId] : "";
  const activeLoading = routeId ? saving.includes(routeId) : false;
  const closeOverlay = useCallback(() => setOverlay(undefined), []);

  useEffect(() => {
    const sync = () => { setRoute(currentRoute()); setOverlay(undefined); setConflictId(undefined); };
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
    if (!draft) void getPackage(routeId).catch(() => {});
  }, [routeId, draft, getPackage]);

  function navigate(next: Route) {
    setOverlay(undefined);
    setConflictId(undefined);
    const href = hrefFor(next);
    if (location.hash !== href) history.pushState(null, "", href);
    setRoute(next);
  }
  const openPreset = (id: string) => navigate({ view: "presets", id });
  // A Catalog item's page has its own address. Back returns to the Catalog as it was left,
  // through history when the Catalog opened it, so the browser's Back button does the same.
  const catalogItem = route.view === "catalog" && route.item ? catalogItems.find(item =>
    item.id === route.item || item.canonicalId === route.item || item.aliases?.includes(route.item!)) : undefined;
  function openCatalogItem(id: string) {
    setOverlay(undefined);
    history.pushState({ fromCatalog: true }, "", hrefFor({ view: "catalog", item: id }));
    setRoute({ view: "catalog", item: id });
  }
  function closeCatalogItem() {
    if (history.state?.fromCatalog) history.back();
    else navigate({ view: "catalog" });
  }
  const createPreset = () => setOverlay({ type: "create", selected: [], kind: "preset" });
  const pickerItems = catalogItems.filter(item => item.type !== "preset" && item.addable !== false).map(catalogMember)
    .filter(item => item.id !== "package:" + routeId && item.id !== "instruction");
  const currentItems = new Map(pickerItems.map(item => [item.id, item]));
  function chosen(ids: string[]) {
    return [...new Set(ids)].map(id => currentItems.get(id)).filter((item): item is Component => !!item);
  }
  function updateDraft(id: string, update: (draft: Draft) => Draft) {
    setDrafts(prev => Object.hasOwn(prev, id) ? { ...prev, [id]: update(prev[id]) } : prev);
  }
  const memberships = (definition: import("./types").ComponentDefinition) => <ComponentMemberships
    definition={definition} drafts={drafts} loadPreset={getPackage} saving={saving} errors={saveErrors}
    loadErrors={loadErrors} onConflict={setConflictId}
    onSelect={(id, item, app, selected) => updateDraft(id, before => withInventorySelection(before, item, app, selected))}
    onNativeSelect={(id, item, included) => updateDraft(id, before => ({
      ...before, members: included ? [...before.members.filter(row => row.id !== item.id), item] : before.members.filter(row => row.id !== item.id),
    }))}
    onSave={id => void save(id)} />;
  function addMembers(id: string, items: Component[]) {
    updateDraft(id, before => withMembers(before, items).draft);
  }
  // Catalog adds save straight onto the latest saved version; an open draft keeps its own unsaved edits.
  async function addToPackage(id: string, componentIds: string[]) {
    const { added, draft: next } = withMembers(createDraft(await api<Package>(packagePath(id))), chosen(componentIds));
    if (!added.length) {
      feedback((componentIds.length === 1 ? "Already in " : "All already in ") + next.original.title + ".");
      return;
    }
    const pkg = await api<Package>(packagePath(id), { method: "PATCH", body: makePayload(next) });
    setDrafts(prev => Object.hasOwn(prev, id) ? { ...prev, [id]: rebaseDraft(prev[id], pkg) } : prev);
    showSaved(pkg);
    feedback("Added " + (added.length === 1 ? added[0].name : added.length + " components") + " to " + pkg.title + ".");
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
    showSaved(pkg);
  }
  function showSaved(pkg: Package) {
    // Keep the newly saved title and count visible while reloading the catalog.
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
    <Sidebar route={route} presets={presets.data.presets} onNavigate={navigate}
      onCreate={createPreset} theme={theme}
      onTheme={() => setTheme(value => value === "light" ? "dark" : "light")} />
    <main ref={main} inert={overlay?.type === "component" || !!catalogItem} className="min-h-0 min-w-0 flex-1 overflow-y-auto" id="main">
      {presets.error && <div className="mx-auto max-w-[1240px] px-5 pt-5"><ErrorBox message={presets.error} onRetry={presets.refresh} /></div>}
      {route.view === "catalog" ? <CatalogPage
        items={catalogItems} presets={presets.data.presets}
        onOpenItem={item => openCatalogItem(item.id)}
        sourceStatus={{ loading: sourceFacts.loading, error: sourceFacts.error, failed: sourceFacts.data.errors, onRetry: sourceFacts.refresh }}
        onOpenPreset={openPreset}
        onCreatePreset={(selected, kind = "preset") => setOverlay({ type: "create", selected, kind })}
        onAdd={addToPackage} isLoading={catalog.loading} error={catalog.error} onRetry={catalog.refresh}
      /> : <div className="mx-auto flex min-h-full max-w-[1240px] flex-col gap-4 px-5 pb-5 pt-5">
        {!routeId ? <PresetList presets={presets.data.presets} loading={presets.loading} onNavigate={navigate} onCreate={createPreset} />
          : !draft ? activeLoadError ?
          <ErrorBox message={activeLoadError} onRetry={() => { void getPackage(routeId).catch(() => {}); }} /> :
          <p role="status" className="text-[13px] text-muted">{presets.data.presets.find(item => item.id === routeId)?.kind === "stack" ? "Loading stack…" : "Loading preset…"}</p> : <div className="app-page" key={draft.original.id}>
            <WorkspaceHeader draft={draft} route={{ ...route, id: draft.original.id }} onNavigate={navigate}
              onEdit={() => setOverlay({ type: "edit", id: draft.original.id })}
              onIcon={icon => updateDraft(draft.original.id, before => ({ ...before, icon }))}
              onSave={() => void save(draft.original.id)} saving={activeLoading} />
            {activeSave?.message && <div className="space-y-2">
              <ErrorBox message={activeSave.message} />
              {activeSave.conflict && <button type="button" className="app-button-secondary" onClick={() => setConflictId(draft.original.id)}>Review saved version</button>}
            </div>}
            {route.tab === "export" ? <PresetExportTab id={draft.original.id} kind={draft.original.kind}
                revision={draft.original.revision}
                dirty={isDirty(draft)} data={consumers.data} loading={consumers.loading} error={consumers.error}
                onRetry={consumers.refresh} route={{ ...route, id: draft.original.id }} onNavigate={navigate} />
              : route.tab === "source" ? <SourceFiles id={draft.original.id} files={draft.original.files} dirty={isDirty(draft)} />
              : <PresetContents draft={draft} busy={activeLoading} facts={sourceFacts.data.items}
                onOpen={item => setOverlay({ type: "component", item, id: draft.original.id })}
                onAdd={() => setOverlay({ type: "picker", id: draft.original.id })}
                onSetIncluded={(rows, included) => updateDraft(draft.original.id, before => withComponentInclusion(before, rows, included))} />}
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
      existing={new Set(pickerItems.filter(listedMember(drafts[overlay.id])).map(item => item.id))}
      packageKind={drafts[overlay.id].kind} onClose={closeOverlay}
      onAdd={items => { addMembers(overlay.id, items); closeOverlay(); }}
      error={catalog.error} loading={catalog.loading} onRetry={catalog.refresh} />}
    {catalogItem && <ComponentDetails item={catalogMember(catalogItem)} backLabel="Catalog" onClose={closeCatalogItem} membership={memberships} />}
    {overlay?.type === "component" && <ComponentDetails
      item={inventoryItem ? overlay.item : { ...overlay.item, ...sourceFacts.data.items[overlay.item.id] }} onClose={closeOverlay}
      backLabel={overlay.id ? drafts[overlay.id].title : "Catalog"}
      presetId={overlay.id && drafts[overlay.id].original.components.some(item => item.id === overlay.item.id) ? overlay.id : undefined}
      instruction={overlay.id ? drafts[overlay.id].instruction : undefined}
      onInstruction={overlay.id && overlay.item.id === "instruction" ? instruction =>
        updateDraft(overlay.id!, before => ({ ...before, instruction })) : undefined}
      membership={memberships}
      onBrowseStack={overlay.item.kind === "package" && overlay.item.id.startsWith("package:") ?
        () => openPreset(overlay.item.id.slice(8)) : undefined} />}
    {conflictId && drafts[conflictId] && <ConflictDialog draft={drafts[conflictId]} onClose={() => setConflictId(undefined)}
      onResolve={next => {
        updateDraft(conflictId, () => next);
        setSaveErrors(prev => ({ ...prev, [conflictId]: { message: "", conflict: false } }));
        setConflictId(undefined);
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
        <p>{latest.componentCount} components in the saved version.</p>
        {overlappingChanges(draft, latest).length > 0 && <p>Both versions changed: {overlappingChanges(draft, latest).map(field => fieldNames[field]).join(", ")}. Keep your edits to use your values for these fields.</p>}
        <div className="flex flex-wrap justify-end gap-2">
          <button type="button" className="app-button-secondary" onClick={() => onResolve(createDraft(latest))}>Use saved version</button>
          <button type="button" className="app-button-primary" onClick={() => onResolve(rebaseDraft(draft, latest))}>Keep my edits</button>
        </div>
      </div> : <p role="status" className="text-[13px] text-muted">Loading saved version…</p>}
  </Modal>;
}

