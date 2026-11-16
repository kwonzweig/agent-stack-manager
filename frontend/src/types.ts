export type PackageKind = "preset" | "stack";
export type Kind = "skill" | "mcp" | "hook" | "plugin" | "instruction" | "package" | "other";
export interface Source {
  repositoryUrl?: string;
  path?: string;
  ref?: string;
}
export interface PackageSummary {
  id: string;
  title: string;
  description: string;
  kind: PackageKind;
  icon: string;
  version: string;
  workArea: string[];
  usage: string[];
  componentCount: number;
}
export interface CatalogItem {
  id: string;
  type: "component" | PackageKind;
  kind: Kind | PackageKind;
  description?: string;
  title?: string;
  name?: string;
  sourceUrl?: string | null;
  source?: Source | null;
  configuration?: unknown;
  componentCount?: number;
  /** GitHub stars of the source repository and the day they were read; absent without a repository. */
  stars?: number;
  starsCheckedOn?: string;
  version?: string;
  packageId?: string;
  workArea?: string[];
  usage?: string[];
}
export interface Component {
  id: string;
  name: string;
  kind: Kind;
  description?: string;
  sourceUrl?: string | null;
  source?: Source | null;
  configuration?: unknown;
  /** The file inside the package, for a component stored there. */
  file?: string;
}
export interface NativeFile {
  path: string;
  content: string;
}
export interface Package extends PackageSummary {
  revision: string;
  instruction: string;
  components: Component[];
  files: NativeFile[];
  paperclip: { role: string | null; canCreateAgents: boolean };
}
/** The rows of the support table: the component kinds, with Plugin split by the manifest each app reads. */
export type SupportKind = "instruction" | "skill" | "mcp" | "hook" | "claude-code-plugin" | "codex-plugin";
/** One app's support of one kind, from catalog/consumers.json, with the page that says so. */
export interface SupportCell {
  value: "yes" | "no" | "not-documented";
  /** The app's own term, shown in the cell. */
  name?: string;
  note?: string;
  doc: string;
}
export interface Consumer {
  id: string;
  name: string;
  /** Whether ASM exports to this app. */
  export: boolean;
  /** For an app that manages other tools, the tools its column covers. */
  tools?: string[];
  roles?: { values: string[]; doc: string };
  support: Record<SupportKind, SupportCell>;
}
export interface ConsumerData {
  kinds: SupportKind[];
  consumers: Consumer[];
}
export interface Result {
  status: string;
  reason: string;
  cause?: "not-in-format" | "adapter";
}
export interface ReportItem {
  id: string;
  name: string;
  kind: Kind;
  /** The support table row; null for a stack, a plugin with no known manifest, or a row that is no component. */
  supportKind: SupportKind | null;
  conversion: Result;
  source: unknown;
  target: unknown;
}
export interface Report {
  /** The consumer this report converts for. */
  consumer: string;
  items: ReportItem[];
  files: NativeFile[];
  // Where the preset's export is committed, and its GitHub page; null for a stack.
  folder: { path: string; url: string | null } | null;
}
export interface Comment {
  id: string;
  body: string;
  author: string;
  createdAt: string;
}
