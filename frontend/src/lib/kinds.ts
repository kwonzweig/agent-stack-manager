import type { LucideIcon } from "lucide-react";
import { Bookmark, Braces, Cable, CircleEllipsis, FileText, Layers, PackageOpen, Plug, Server, Settings, Waypoints, Webhook } from "lucide-react";
import type { Kind, PackageKind } from "../types";

export interface KindStyle {
  singular: string;
  plural: string;
  icon: LucideIcon;
  /** Hex for inline styles on Catalog cards. */
  color: string;
  chip: string;
  chipActive: string;
}

// The one icon and color per component type, used by Catalog and preset pages alike.
const stack: KindStyle = { singular: "Stack", plural: "Stacks", icon: PackageOpen, color: "#06b6d4",
  chip: "bg-cyan-500/15 text-cyan-600 dark:text-cyan-400", chipActive: "bg-cyan-500 text-white" };

export const KIND_STYLES: Record<Kind | PackageKind, KindStyle> = {
  instruction: { singular: "Instruction", plural: "Instructions", icon: FileText, color: "#3b82f6",
    chip: "bg-blue-500/15 text-blue-600 dark:text-blue-400", chipActive: "bg-blue-500 text-white" },
  skill: { singular: "Skill", plural: "Skills", icon: Layers, color: "#10b981",
    chip: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400", chipActive: "bg-emerald-500 text-white" },
  mcp: { singular: "MCP", plural: "MCPs", icon: Server, color: "#8b5cf6",
    chip: "bg-violet-500/15 text-violet-600 dark:text-violet-400", chipActive: "bg-violet-500 text-white" },
  hook: { singular: "Hook", plural: "Hooks", icon: Webhook, color: "#f59e0b",
    chip: "bg-amber-500/15 text-amber-600 dark:text-amber-400", chipActive: "bg-amber-500 text-white" },
  plugin: { singular: "Plugin", plural: "Plugins", icon: Plug, color: "#f43f5e",
    chip: "bg-rose-500/15 text-rose-600 dark:text-rose-400", chipActive: "bg-rose-500 text-white" },
  connector: { singular: "Connector", plural: "Connectors", icon: Cable, color: "#0d9488",
    chip: "bg-teal-500/15 text-teal-700 dark:text-teal-400", chipActive: "bg-teal-600 text-white" },
  provider: { singular: "Provider", plural: "Providers", icon: Waypoints, color: "#9333ea",
    chip: "bg-purple-500/15 text-purple-700 dark:text-purple-400", chipActive: "bg-purple-600 text-white" },
  setting: { singular: "Setting", plural: "Settings", icon: Settings, color: "#64748b",
    chip: "bg-slate-500/15 text-slate-700 dark:text-slate-300", chipActive: "bg-slate-600 text-white" },
  lsp: { singular: "LSP", plural: "LSPs", icon: Braces, color: "#0284c7",
    chip: "bg-sky-500/15 text-sky-700 dark:text-sky-400", chipActive: "bg-sky-600 text-white" },
  package: stack,
  stack,
  preset: { singular: "Preset", plural: "Presets", icon: Bookmark, color: "#6366f1",
    chip: "bg-indigo-500/15 text-indigo-600 dark:text-indigo-400", chipActive: "bg-indigo-500 text-white" },
  other: { singular: "Other", plural: "Other components", icon: CircleEllipsis, color: "#737373",
    chip: "bg-neutral-500/15 text-neutral-600 dark:text-neutral-400", chipActive: "bg-neutral-500 text-white" },
};
