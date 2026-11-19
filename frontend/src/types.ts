export type PackageKind = "preset" | "stack";
export type Kind = "skill" | "mcp" | "hook" | "plugin" | "instruction" | "package" | "connector" | "provider" | "setting" | "lsp" | "other";
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
/** What an item's source says now, from GET /api/catalog/sources; each value carries when it was read (ISO time). */
export interface SourceFacts {
  /** The item's own description, read from descriptionUrl. */
  description?: string;
  descriptionUrl?: string;
  descriptionReadAt?: string;
  /** GitHub stars of the source repository. */
  stars?: number;
  starsReadAt?: string;
  /** skills.sh installs; absent when skills.sh does not list the skill. */
  installs?: number;
  installsReadAt?: string;
  content?: string;
  contentFormat?: string;
  contentUrl?: string;
  sourceResolvedRef?: string;
}
export interface SourceData {
  items: Record<string, SourceFacts>;
  /** Sources that could not be read; their last answer, if any, is still shown. */
  errors: string[];
}
export interface CatalogItem extends SourceFacts {
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
  canonicalId?: string;
  pluginHost?: "codex" | "claude";
  aliases?: string[];
  origins?: ComponentOrigin[];
  memberships?: ComponentMembership[];
  remoteApproved?: boolean;
  addable?: boolean;
}
/** A preset member or a Catalog item, with what its source says once that has been read. */
export interface Component extends SourceFacts {
  id: string;
  name: string;
  kind: Kind;
  description?: string;
  sourceUrl?: string | null;
  source?: Source | null;
  configuration?: unknown;
  /** The file inside the package, for a component stored there. */
  file?: string;
  managedByInventory?: boolean;
  presetMembership?: "Included" | "Excluded" | "Mixed" | "Not set";
  inventoryId?: string;
  canonicalId?: string;
  pluginHost?: "codex" | "claude";
  details?: ComponentContent;
  inventoryIds?: string[];
  origins?: ComponentOrigin[];
}
export interface ComponentOrigin {
  type: string;
  presetId?: string;
  app?: InventoryApp;
  scope?: string;
  locator?: string;
  path?: string;
  parentId?: string;
  parentName?: string;
  file?: string;
  inventoryId?: string;
}
export interface ComponentMembership {
  presetId: string;
  presetName: string;
  memberId?: string;
  inventoryId?: string;
  apps?: Partial<Record<InventoryApp, InventoryAppState>>;
}
export interface ComponentContent {
  availability: "available" | "metadata-only" | "unavailable";
  reason?: string;
  content?: string;
  format?: string;
  fields?: { name: string; type: string; selections?: Partial<Record<InventoryApp, InventorySelection>> }[];
  selectionConflict?: boolean;
  entry?: string;
  files?: string[];
  resourceCount?: number;
}
export interface ComponentDefinition extends Component {
  origins: ComponentOrigin[];
  memberships: ComponentMembership[];
  details: ComponentContent;
  remoteApproved: boolean;
  sourceAccess?: "public" | "verify" | "private";
  addable?: boolean;
  sourceErrors?: string[];
}
export interface NativeFile {
  path: string;
  content: string;
}
export type InventoryApp = "codex" | "claude";
export type InventorySelection = boolean | null;
export interface InventoryAppState {
  installed: boolean;
  enabled: boolean | null;
  selected: InventorySelection;
  scope?: string;
  parentId?: string;
  locator?: string;
  path?: string;
  targetId?: string;
  provenance?: { location?: string };
}
export interface InventoryItem {
  id: string;
  name: string;
  kind: string;
  description: string;
  source?: string;
  sourcePath?: string;
  sourceRef?: string;
  apm?: { git: string; ref: string; path?: string };
  canonicalId?: string;
  pluginHost?: "codex" | "claude";
  definitionSource?: Source;
  sourceUrl?: string;
  details?: ComponentContent;
  apps: Partial<Record<InventoryApp, InventoryAppState>>;
}
export interface InventoryCoverage {
  app: InventoryApp;
  area: string;
  status: string;
  note: string;
}
export interface Package extends PackageSummary {
  revision: string;
  instruction: string;
  components: Component[];
  files: NativeFile[];
  appInventory?: InventoryItem[];
  appInventoryCoverage?: InventoryCoverage[];
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
  app?: InventoryApp;
  originPackage?: { id: string; title: string };
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
