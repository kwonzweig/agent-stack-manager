import type { Consumer, ConsumerData, Kind, Report, ReportItem, SupportCell, SupportKind } from "../types";
import { conversionStatus, outcome, type Tone } from "./paperclipOutcome.ts";

export const SUPPORT_LABELS: Record<SupportKind, string> = {
  instruction: "Instruction", skill: "Skill", mcp: "MCP", hook: "Hook",
  "claude-code-plugin": "Claude Code plugin", "codex-plugin": "Codex plugin",
};
// The shared kind icon of each row; both plugin rows take the Plugin icon.
export const SUPPORT_ICONS: Record<SupportKind, Kind> = {
  instruction: "instruction", skill: "skill", mcp: "mcp", hook: "hook",
  "claude-code-plugin": "plugin", "codex-plugin": "plugin",
};

export interface TableCell {
  text: string;
  tone: Tone;
  note?: string;
  doc: string;
}
export interface TableRow {
  kind: SupportKind;
  /** How many of this preset's components the row holds; null until the report has loaded. */
  count: number | null;
  cells: TableCell[];
}

const tones: Record<SupportCell["value"], Tone> = { yes: "good", no: "bad", "not-documented": "neutral" };
const shownValue: Record<SupportCell["value"], string> = { yes: "Supported", no: "No", "not-documented": "Not documented" };

export function cellOf(cell: SupportCell): TableCell {
  return { text: cell.name || shownValue[cell.value], tone: tones[cell.value], note: cell.note, doc: cell.doc };
}

// The column heading: the app, and for an app that manages other tools, the tools it covers.
export function columnName(consumer: Consumer) {
  return consumer.tools?.length ? `${consumer.name} (${consumer.tools.join(" · ")})` : consumer.name;
}

// What the export did with this preset's components of one kind, in the report's own words.
export function reportText(rows: ReportItem[]): { text: string; tone: Tone } {
  const parts: string[] = [];
  const converted = rows.filter(row => outcome(row) === "converted").length;
  if (converted) parts.push(`${converted} exported`);
  const expected = new Map<string, number>();
  for (const row of rows.filter(row => outcome(row) === "expected")) {
    const label = conversionStatus(row.conversion).label;
    expected.set(label, (expected.get(label) ?? 0) + 1);
  }
  for (const [label, count] of expected) parts.push(`${count} ${label[0].toLowerCase()}${label.slice(1)}`);
  const attention = rows.filter(row => outcome(row) === "attention").length;
  if (attention) parts.push(`${attention} need${attention === 1 ? "s" : ""} attention`);
  return { text: parts.join(" · "), tone: attention ? "bad" : expected.size ? "neutral" : "good" };
}

/**
 * One row per kind, one cell per app. An app ASM exports to shows, for a kind this preset has, what its
 * report did with those components; every other cell is what the app's own page says.
 */
export function supportRows(data: ConsumerData, report?: Pick<Report, "consumer" | "items">): TableRow[] {
  return data.kinds.map(kind => {
    const own = report?.items.filter(row => row.supportKind === kind);
    const cells = data.consumers.map(consumer => {
      const cell = cellOf(consumer.support[kind]);
      const rows = consumer.export && consumer.id === report?.consumer ? own : undefined;
      return rows?.length ? { ...cell, ...reportText(rows), note: [cell.text, cell.note].filter(Boolean).join(". ") } : cell;
    });
    return { kind, count: own ? own.length : null, cells };
  });
}

// Plugins whose source names neither manifest, so no plugin row holds them.
export function unplacedPlugins(items: ReportItem[] | undefined) {
  return (items ?? []).filter(row => row.kind === "plugin" && !row.supportKind);
}
