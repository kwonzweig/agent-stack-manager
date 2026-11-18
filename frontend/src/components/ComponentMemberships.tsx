import { useEffect } from "react";
import type { Component, ComponentDefinition, InventoryApp, InventoryItem, InventorySelection } from "../types";
import { isDirty, type Draft } from "../draft";
import { InventoryMembership } from "./InventoryMembership";

export function ComponentMemberships({ definition, drafts, loadPreset, onSelect, onNativeSelect, onSave, saving, errors }: {
  definition: ComponentDefinition;
  drafts: Record<string, Draft>;
  loadPreset: (id: string) => Promise<unknown>;
  onSelect: (presetId: string, item: InventoryItem, app: InventoryApp, selected: InventorySelection) => void;
  onNativeSelect: (presetId: string, component: Component, included: boolean) => void;
  onSave: (presetId: string) => void;
  saving: string[];
  errors: Record<string, { message: string; conflict: boolean }>;
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
        {!draft && <p role="status" className="text-muted">Loading preset…</p>}
        {errors[id]?.message && <p role="alert" className="text-danger">{errors[id].message}</p>}
        {draft && observations.map(item => <InventoryMembership key={item.id} draft={draft} item={item}
          onSelect={(app, selected) => onSelect(id, item, app, selected)} />)}
        {draft && native.map(item => item.id === "instruction" ? <p key={item.id} className="text-secondary">Primary instruction</p> :
          <label className="form-field" key={item.id}>Preset membership
            <select className="app-input" value={draft.members.some(row => row.id === item.id) ? "true" : "false"}
              onChange={event => onNativeSelect(id, item, event.target.value === "true")}>
              <option value="true">Included</option><option value="false">Excluded</option>
            </select>
          </label>)}
      </section>;
    })}
  </section>;
}
