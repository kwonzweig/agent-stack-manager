import { Check, CircleHelp, Minus } from "lucide-react";
import { inventorySelection, type Draft } from "../draft";
import type { InventoryApp, InventoryItem, InventorySelection } from "../types";
import { observationAppName } from "../lib/componentLocation";

const apps = [["codex", "Codex"], ["claude", "Claude Code"]] as const;

function Observation({ value, labels }: { value: boolean | null; labels: [string, string, string] }) {
  const Icon = value === true ? Check : value === false ? Minus : CircleHelp;
  return <span className="inline-flex items-center gap-1 text-secondary">
    <Icon className={value === true ? "h-3.5 w-3.5 text-accent" : "h-3.5 w-3.5 text-muted"} aria-hidden />
    {labels[value === true ? 0 : value === false ? 1 : 2]}
  </span>;
}

export function InventoryMembership({ draft, item, onSelect }: {
  draft: Draft; item: InventoryItem; onSelect: (app: InventoryApp, selection: InventorySelection) => void;
}) {
  return <section className="inspector-section" aria-label="Preset membership">
    <div className="section-heading"><h3>Preset membership</h3></div>
    <div className="values sm:grid-cols-2">
      {apps.map(([app]) => {
        const observation = item.apps[app];
        const chosen = inventorySelection(draft, item, app);
        if (!observation) return null;
        const name = observationAppName(app, observation);
        return <section className="app-panel p-3 text-[13px]" key={app} aria-label={name}>
          <h4 className="font-semibold text-primary">{name}</h4>
          <dl className="mt-2 grid grid-cols-[5.5rem_minmax(0,1fr)] items-center gap-x-2 gap-y-1.5">
            <dt className="text-muted">Install</dt><dd><Observation value={observation.installed} labels={["Installed", "Previously installed", "Unknown"]} /></dd>
            <dt className="text-muted">Activity</dt><dd><Observation value={observation.enabled} labels={["Enabled", "Disabled", "Unknown"]} /></dd>
            {observation.scope && <><dt className="text-muted">Scope</dt><dd className="break-words text-secondary">{observation.scope}</dd></>}
            <dt className="text-muted">Preset</dt><dd>
              <select className="app-input min-h-7 max-w-full" aria-label={`${name} preset membership`}
                value={chosen === null ? "" : String(chosen)}
                onChange={event => onSelect(app, event.target.value === "" ? null : event.target.value === "true")}>
                <option value="true">Included</option><option value="false">Excluded</option><option value="">Not set</option>
              </select>
            </dd>
          </dl>
        </section>;
      })}
    </div>
  </section>;
}
