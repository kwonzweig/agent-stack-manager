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
export interface Consumer {
  id: string;
  name: string;
  supported: boolean;
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
  conversion: Result;
  source: unknown;
  target: unknown;
}
export interface Report {
  items: ReportItem[];
  files: NativeFile[];
}
export interface Comment {
  id: string;
  body: string;
  author: string;
  createdAt: string;
}
