import { useEffect } from "react";
import type { Component, ComponentDefinition, InventoryApp, InventoryItem, InventorySelection } from "../types";
import { appSelection, isDirty, type Draft } from "../draft";
import { AppMembershipSelect, apps, InventoryMembership } from "./InventoryMembership";

export function ComponentMemberships({ definition, drafts, loadPreset, onSelect, onAppSelect, onNativeSelect, onSave, saving, errors, loadErrors, onConflict }: {
  definition: ComponentDefinition;
  drafts: Record<string, Draft>;
  loadPreset: (id: string) => Promise<unknown>;
  onSelect: (presetId: string, item: InventoryItem, app: InventoryApp, selected: InventorySelection) => void;
  onAppSelect: (presetId: string, item: Component, app: InventoryApp, selected: InventorySelection) => void;
  onNativeSelect: (presetId: string, component: Component, included: boolean) => void;
  onSave: (presetId: string) => void;
  saving: string[];
  errors: Record<string, { message: string; conflict: boolean }>;
  loadErrors: Record<string, string>;
  onConflict: (id: string) => void;
}) {
  const presets = [...new Map(definition.memberships.map(row => [row.presetId, row.presetName])).entries()];
  const ids = presets.map(([id]) => id).join("\n");
  useEffect(() => {
    for (const id of ids.split("\n").filter(Boolean)) {
      if (!Object.hasOwn(drafts, id)) void loadPreset(id).catch(() => {});
    }
  }, [ids, drafts, loadPreset]);
  if (!presets.length) return <section className="inspector-section"><h3>Presets</h3><p>No preset memberships.</p></section>;
  return <section className="space-y-3" aria-label="Presets">
    <h3 className="font-semibold text-primary">Presets</h3>
    {presets.map(([id, name]) => {
      const draft = Object.hasOwn(drafts, id) ? drafts[id] : undefined;
      const observations = draft?.original.appInventory?.filter(row => row.canonicalId === definition.canonicalId) ?? [];
      const native = draft?.original.components.filter(row => row.canonicalId === definition.canonicalId && !row.managedByInventory) ?? [];
      return <section key={id} className="app-panel space-y-3 p-3" aria-label={name}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h4 className="font-semibold text-primary">{name}</h4>
          {draft && isDirty(draft) && <button type="button" className="app-button-primary"
            onClick={() => onSave(id)} disabled={saving.includes(id)}>{saving.includes(id) ? "Saving…" : "Save " + name}</button>}
        </div>
        {!draft && (loadErrors[id]
          ? <p role="alert" className="text-danger">{loadErrors[id]} <button type="button" className="underline" onClick={() => void loadPreset(id).catch(() => {})}>Retry</button></p>
          : <p role="status" className="text-muted">Loading preset…</p>)}
        {errors[id]?.message && <p role="alert" className="text-danger">{errors[id].message}</p>}
        {errors[id]?.conflict && <button type="button" className="app-button-secondary" onClick={() => onConflict(id)}>Review saved version</button>}
        {draft && observations.map(item => <InventoryMembership key={item.id} draft={draft} item={item}
          onSelect={(app, selected) => onSelect(id, item, app, selected)} />)}
        {draft && native.map(item => {
          const instruction = item.id === "instruction";
          const included = instruction || draft.members.some(row => row.id === item.id);
          return <div className="space-y-3" key={item.id}>
            {instruction ? <p className="text-secondary">Primary instruction</p> :
              <label className="form-field">Preset membership
                <select className="app-input" value={String(included)}
                  onChange={event => onNativeSelect(id, item, event.target.value === "true")}>
                  <option value="true">Included</option><option value="false">Excluded</option>
                </select>
              </label>}
            {included && item.appSelectionKey && <div className="values sm:grid-cols-2">
              {apps.map(([app, appName]) => <label key={app} className="form-field">
                {appName}
                <AppMembershipSelect name={appName} chosen={appSelection(draft, item, app)}
                  onSelect={selected => onAppSelect(id, item, app, selected)} />
              </label>)}
            </div>}
          </div>;
        })}
      </section>;
    })}
  </section>;
}
