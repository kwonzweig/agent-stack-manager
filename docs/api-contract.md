# Data files and local API

For agents and people who edit ASM data. ASM's data lives in these files; no route contacts a consumer. What a component's source owns (its description, its repository's GitHub stars, its skills.sh installs) is not stored here: ASM reads it from the source when the dashboard shows it.

ASM owns the shared preset data, APM extensions and conversions consumed by Paper Kit and Personal Kit.

## Files

- `packages/<id>/apm.yml` and its `.apm/` files: one stack or preset as an APM package; the folder name is the package id. APM `dependencies` hold the members, `x-preset-labels` holds ASM's labels: `title`, `kind` (`preset` or `stack`), `icon`, `workArea` and `usage`, none of them for one app alone. A repository member names a branch as `ref`, never a commit or a version.
- `catalog/components.json`: the components that can be added to a stack or preset. It does not repeat a preset's members, and holds no description, star count or install count for a component from a repository. A hook defined here has no repository and keeps its own description.
- `catalog/consumers.json`: what each app supports per component kind (below).
- `exports/paperclip/<id>/`: each preset's Paperclip package, generated; never edit it by hand. [paperclip.md](paperclip.md) says how to import it.
- `.asm/`: component comments, and `sources.json`, each source's last answer for `/api/catalog/sources`; ignored by Git.
- `packages/<id>/apm.lock.yaml`: written by `lock`, ignored by Git and by the store.

## Conventions

All JSON errors are `{ "error": "message" }`. A POST or PATCH body is a JSON object sent with `Content-Type: application/json`; any other type returns 415, and a body that is not valid JSON returns 400. Paths use URL-encoded package ids. Existing writes require the package `revision`: a save without one returns 400, and a revision that no longer matches returns 409. No route contacts a consumer.

## Store interface (`asm_app/store.py`)

`Store(root: Path, base_root: Path | None = None)` uses `root` for writes and ignored `.asm/` state. Without a base, it reads `packages/` and `catalog/` there too. With `base_root`, shared packages and Catalog data are read through from that checkout; edits to a shared package create a copy under `root`.

- `catalog()` -> `{items: [Component or PackageSummary]}`. It refuses a `catalog/components.json` item from a repository that stores a `description`, `stars` or `installs`, since the repository owns them.
- `list_packages()` -> list of PackageSummary
- `get(id)` -> Package
- `create(payload)` -> Package
- `save(id,payload)` -> Package (requires revision). Create and save then rewrite `exports/paperclip/` (`write_exports`), every preset, since a saved stack changes the export of each preset that includes it.
- `export(id)` -> bytes (ZIP of the native package, the dashboard's download)
- `consumers()` -> `catalog/consumers.json` (below), or no consumers when the file is missing.
- `comments(id,component_id)` -> list
- `add_comment(id,component_id,payload)` -> comment
- `lock(id,update=False)` -> `{ok,output}`; bounded fixed APM invocation, no shell. It runs `apm lock` in `packages/<id>/` for up to ten minutes, which writes `apm.lock.yaml` there. Git ignores that file, and it is not part of the package: its `revision`, its files and its export stay as they were.

PackageSummary: `id,title,description,kind` (`preset` or `stack`), `icon` (a lowercase icon name such as `rocket`, or empty when none was chosen), `version,workArea:[],usage:[],componentCount`.

Package extends summary: `revision,instruction,components:[],files:[{path,content}]`.

Component: `id,name,kind` (`skill,mcp,hook,plugin,instruction,package,other`), `description,sourceUrl,source,configuration`. Source uses `repositoryUrl,path,ref`; `ref` names a branch, and an empty `ref` follows the default branch. A component stored as a file in the package also has `file`, its path inside the package (for example `.apm/skills/<name>/SKILL.md`). Catalog components additionally contain `type:"component"` and native `apm` creation metadata; what their source says comes from `/api/catalog/sources`. A catalog row with an APM `git` value stores no `source` or `sourceUrl`; `catalog()` derives both from that value, and only rows without `git` (marketplace plugins, MCP servers) store them; catalog package summaries contain `type:"preset"|"stack"` and `packageId`.

Create/save payload: `title,description,kind,icon,workArea,usage,instruction,componentIds`; any other field is ignored. A save also carries the `revision` of the Package it edits; every other field may be left out, and a field left out keeps its stored value, so `{"revision":"…","description":"…"}` changes only the description. A field that is sent is written: `kind`, `workArea` and `usage` go into `x-preset-labels` even when they are the defaults `preset` and `[]`, and the dashboard sends every field, so its first save of a package without them adds those lines to `apm.yml`. `componentIds` replaces the member list: the ids of the Package's `components` to keep (a file in the package keeps its own id, such as `skill:.apm/skills/<name>/SKILL.md`; `instruction` is ignored, the `instruction` field holds it) plus catalog ids to add. An empty `icon` removes the stored one. `componentIds` accepts catalog component ids and `package:<id>` for a stack dependency. Save retains unsupported native fields unless deliberately removed. A new package id is derived from the title; a collision is rejected rather than replaced.

## HTTP routes (`asm_app/server.py`)

- GET `/api/catalog` -> store.catalog()
- GET `/api/catalog/sources` -> `{items: {<component id>: {description, descriptionUrl, descriptionReadAt, stars, starsReadAt, installs, installsReadAt}}, errors: []}`, what each catalog component's source says, read by `asm_app/sources.py`: a skill's description from its `SKILL.md` front matter and a plugin's from its `plugin.json` (raw.githubusercontent.com), any other component's and every repository's stars from the GitHub API, and a skill's installs from skills.sh. A value is absent when its source has none. Answers are reused for an hour from `.asm/sources.json`; a source that cannot be read is listed in `errors` and keeps its last answer. GitHub allows 60 unauthenticated requests an hour; `GITHUB_TOKEN` or `GH_TOKEN` in the server's environment raises that.
- GET `/api/presets` -> `{presets: store.list_packages()}`
- GET `/api/presets/{id}` -> Package
- POST `/api/presets` -> Package
- PATCH `/api/presets/{id}` -> Package
- GET `/api/presets/{id}/export` -> native ZIP, the dashboard's download
- POST `/api/presets/{id}/lock` -> store.lock(id, update)
- GET `/api/comments?presetId=&componentId=` -> `{comments:[]}`
- POST `/api/comments` with `presetId,componentId,body,author` -> `{comment}`
- GET `/api/consumers` -> store.consumers()
- GET `/api/presets/{id}/exports` -> the saved preset's assessed targets, previews and download paths.
- GET `/api/presets/{id}/paperclip` -> conversion report from `convert()`
- GET `/api/presets/{id}/paperclip/export` -> the same files as `exports/paperclip/{id}/`, as a ZIP
- GET `/api/presets/{id}/cc-switch` -> the saved app inventory's CC Switch review, as a JSON download (see below).

## Export targets

`GET /api/presets/{id}/exports` returns `{targets: [...]}`. Each target gives its `id`, `name`, `available`, `reason` and `preview`. An available target also gives a package-relative `download` path and a `filename`. Append the path to `/api/presets/{id}`. The download path carries the assessed artifact's revision. A download returns 409 if that artifact changed since the preview. The existing download paths without a revision still use the current saved data. The support matrix documents what each app supports. Download availability comes from the exporters' assessments.

Both exporters expand a shared nested stack's members and observations once, while accounting for each inclusion edge. Missing and cyclic references remain in the report with their reasons. Inherited rows carry `originPackage: {id,title}`. CC Switch scopes inherited inventory IDs to their source package; direct inventory IDs stay unchanged.

Paperclip assesses whether the package describes a single agent. A preset's preview is the Paperclip conversion report without file bodies. The conversion includes each observed app row as an omission because the company package cannot represent its installed, enabled and selected states, including excluded or unknown states. A matching shared APM skill may still produce a Paperclip skill reference independently. A stack has a preview and a reason, and produces a package only when a preset includes it. The Paperclip ZIP and generated directory use the same file map. Unavailable targets retain their omission reports.

CC Switch produces a review when the preset or its included stacks contain Codex or Claude Code inventory rows. It records existing per-app selections. Ordinary APM components with no app mapping appear as unassigned rows in the preview and under `unassignedItems` in the downloaded review. Its `items` field contains only per-app rows. ASM does not infer app selections or run any import.

## Component identity

`canonicalId` identifies a component definition across Catalog, preset dependencies and installed observations. A remote definition uses its kind, plugin host, repository, branch and exact component path. Repository names on GitHub compare without case; component paths and refs retain their case. An unknown branch stays distinct from a recorded branch. A repository without a skill path does not imply a root skill. A declared root APM skill does.

Local definitions use a proven file locator and field key when available. Otherwise the preset and original item ID scope the identity. Equal display names never establish identity. A copied observation without a proven locator receives a `definitionId` reference to its original definition. The original member IDs, inventory IDs, native source references and app selections stay intact.

`GET /api/catalog` includes component definitions from the configured Catalog, shared packages and private inventory. Each definition has `canonicalId`, legacy `aliases`, `origins`, `memberships` and `addable`. Existing Catalog IDs remain usable. A source-backed skill and its observation appear once when their proven coordinates match. Different local origins and unknown coordinates remain separate. Entries with no reusable source have `addable: false`.

Adding an observed definition retains complementary app observations and distinct origins. Existing destination choices are preserved; conflicting choices for the same observation in a new destination remain undecided (`selected: null`). A named parent copied only for provenance is excluded unless explicitly chosen. Editing a native source file creates a local fork rather than changing the shared definition.

## Source access and enrichment

`GET /api/catalog/sources` returns facts under both the existing Catalog ID and `canonicalId`. The configured shared Catalog declares sources permitted for enrichment. An inventory row's `sourceAccess` may be `verify`, `public` or `private`. No access value is inferred from its name or an HTTPS URL.

`verify` means an explicit configured GitHub remote established by its installation receipt or source manifest. The `public` value records an affirmative public-source decision, such as the scanner's GitHub visibility receipt in `sourceAccessEvidence`. For either value, ASM checks repository visibility with the owning GitHub API before raw source-file or skills.sh requests. Only an affirmative public response permits those reads; a current private response overrides prior public permission or a receipt. A local-only component and an unverified URL receive no requests. A private declaration takes precedence for every identity of that repository.

When an observed branch is unknown, a verified public repository's current default branch can be used for a source read. The response reports `sourceResolvedRef`; it does not rewrite the observed `sourceRef` or equate it to an installed revision. Missing paths, inaccessible content and metrics unavailable from their owners stay explicit. Facts and source bodies share an expiring runtime cache. Cache locks cover disk access, so a bulk Catalog query cannot hold the cache lock during network requests.

## Component details and origins

`GET /api/components/{canonicalId-or-legacy-id}` returns the locally resolved definition immediately. `GET /api/components/{id}/source` enriches that same definition when source access permits it. Catalog and preset item pages use these same calls and renderer. Public detail displays local metadata while the clicked source is read.

The response includes normalized `source`, `pluginHost` (`codex` or `claude` when established), `details`, `origins` and `memberships`. A details block has `availability` (`available`, `metadata-only` or `unavailable`), optional `content`, `format` and `reason`. A safe captured settings container may list typed `fields` without configuration values. A legacy selection conflict retains the individual field selections for review.

Origins identify the preset, app, scope, safe locator and parent container when known. Memberships refer to the original preset member or inventory IDs and observed app states. Editing memberships uses that preset's ordinary revision-checked save. Private or local metadata can be reviewed without resolving its files or contacting its source. Source bodies appear only when present in the package, captured safely, or read through the permitted remote-source route.

## App inventory

A private preset can hold a captured inventory under `x-app-inventory` in its `apm.yml`. ASM accepts an existing package file. The dashboard neither scans nor applies configuration to the apps. Open it beside the shared presets and Catalog with `python -m asm_app --root <private-root> --base-root <shared-checkout> serve`. The base is read-only. Editing a shared preset in this view creates a private copy for subsequent edits. Keep its package, generated files and downloads private. Do not add credentials or raw settings to the manifest. Source access follows the policy above.

The extension has an `items` list. Each item has a stable text `id`, `name`, `kind`, `description` and an `apps` map keyed by `codex` and/or `claude`. An app entry has `installed` (boolean), `enabled` (boolean or null if unverified) and `selected` (boolean or null if undecided). An absent app entry carries no observation. Optional item fields are `source`, `sourcePath`, `sourceRef` and `skillRepository`. Optional app fields are `scope`, `parentId`, `targetId` (the app's component key) and `path` relative to the app scope. An optional extension `coverage` list has entries with `app`, `area`, `status`, and `note`.

An inventory skill with a verified source can carry an `apm` reference with `git` (its GitHub repository), `ref` (a branch) and optional `path` (the skill's directory, omitted for a skill at the repository root). Seed matching native `dependencies.apm` entries when creating a preset. After a save, ASM keeps the native dependency as long as at least one app includes the item. Excluding it in both apps removes the native dependency and preserves the inventory row and its source. Per-app selections remain available to the CC Switch review.

`GET /api/presets/{id}` returns `appInventory` and, if supplied, `appInventoryCoverage`. `PATCH` accepts `appInventorySelections`, an object whose keys are item IDs and whose values are objects mapping an observed app to the new selection. For example, `{"revision":"…","appInventorySelections":{"sample":{"codex":false}}}` excludes an item in Codex. Saving changes only the named selections. The inventory retains excluded items so they can be included again.

### CC Switch review

`python -m asm_app --root <private-root> cc-switch <preset-id>` prints the same JSON as the dashboard download. The report includes `presetId`, `consumer: "cc-switch"`, one `items` row per item and app, a deduplicated `skillRepositories` list and, when needed, `unassignedItems`. Rows in `items` carry `id`, `name`, `kind`, `app`, `installed`, `enabled`, `selected`, `status` and `reason`, plus available source metadata. A repository entry contains `owner`, `repo`, `branch`, optional `directory`, and its official CC Switch deep link in `url`. Supply `skillRepository` only when you have approved the repository for CC Switch to read. Registering a repository does not install or enable a skill.

`status` is `excluded`, `unsupported`, `manual`, `registration-only`, or `import-ready`. Known hooks, plugins and Connectors require their own host route. Observations without portable configuration require manual action. For an item with an explicitly supplied, credential-free app payload, `portable: {prompt: "<text>"}` or `portable: {mcp: {name: "<id>", url: "<https-url>"}}` can generate a per-row import link in `url`. Review the prompt text before adding it. A prompt import defaults to disabled. An MCP link requires an observed enabled state because CC Switch writes the server into the app configuration on confirmation. The endpoint must be valid HTTPS without credentials, query or fragment.

A prompt or MCP whose recorded scope would be promoted to global remains `manual` with no import URL. Selected MCP rows with conflicting endpoints for one server ID also remain `manual`. Matching endpoints with absent or user scope remain eligible. These links are for review and confirmed import. Use CC Switch to reconcile existing entries before using a deep link. See [CC Switch's deep link reference](https://github.com/farion1231/cc-switch/blob/main/docs/user-manual/en/5-faq/5.3-deeplink.md).

## Paperclip interface (`asm_app/paperclip.py`)

`convert(package, *, root:Path)` -> `{consumer:"paperclip",items:[{id,name,kind,supportKind,conversion:{status,reason,cause?},source,target}],summary:{total,converted,unconverted},files:[{path,content}],folder:{path,url}}`. `folder` is where the export is committed, `exports/paperclip/<id>`, with its GitHub page on `main` (null without `project.urls.Repository`); it is null for a stack, which is not one agent and is not exported.

`supportKind` is the support table row the component counts in (a `kinds` value of `catalog/consumers.json`): its kind, or for a plugin `claude-code-plugin` or `codex-plugin` by the `.claude-plugin/` or `.codex-plugin/` folder its source names; null for a stack and a plugin that names neither.

Conversion statuses are `converted` and `unconverted`. Reasons are concise English. Every source component appears; `target` is the written file the component went to (`agents/<id>/AGENTS.md`, `skills/<key>/SKILL.md`), `{packageId}` for an expanded stack, or null when the component is not exported.

`cause` names why the export leaves a component out as expected: `not-in-format` for hooks and plugins, which Paperclip's company package has no entry for, and `adapter` for MCP servers: the company package has no MCP entry either, the export writes no adapter, and Paperclip's docs do not say how an imported agent gets an MCP server, so the report asks for it to be set in the agent's adapter after import. An unconverted component without a `cause` needs attention. For example, ASM can write a skill stub only when it has a GitHub repository and a branch.

The files, named by the package id:

- `COMPANY.md`: `schema: agentcompanies/v1`, `kind: company`, `slug`, `name`, `description`.
- `agents/<id>/AGENTS.md`: `kind: agent`, `name`, `title`, `slug`, `role: general` and `skills`, the stub keys in member order; no `reportsTo`. The body is the Instruction.
- `skills/<key>/SKILL.md`: one stub per skill with `key`, `name` and `metadata.sources[0] = {kind: github-dir, repo, path, trackingRef, url}`, no commit; a skill from a repository has no `description` in its stub, which Paperclip does not read. `path` is the skill's folder, `.` for a skill at the repository root. Paperclip does not read the stubs; [paperclip.md](paperclip.md) turns them into skill sources. `trackingRef` is the member's APM `ref`. A skill the preset holds itself is read from this repository, the `project.urls.Repository` of `pyproject.toml`, at `packages/<id>/.apm/skills/<name>` on `main`; its stub takes `name` and `description` from that `SKILL.md`'s frontmatter, or the folder name when it has none. The key is the folder name, or the repository name for a root skill; when two skills share it, both take `<repo>-<name>`.
- `.paperclip.yaml`: `schemaVersion: 7` and, under `agents.<id>`, `role: general`, `runtime.heartbeat.enabled: false` and `metadata.agentStackManagerPackageId` and `metadata.agentStackManagerRevision`, a SHA-256 over the preset's files and those of its nested stacks with LF line endings (`store._export_digest`). No adapter, no permissions and no budget.

Every agent's `role` is `general`, because Paperclip stores a role outside its own list when a package names none. A role or right the company needs is set in Paperclip after the import ([paperclip.md](paperclip.md)).

`export_package(report)` -> ZIP bytes of those files.

`write_exports(root)` writes `exports/paperclip/<id>/` for every package of kind `preset`, exactly the files `convert` gives, with LF line endings, and removes every other file there, so a deleted preset or skill loses its export. A package that cannot be read keeps the folder it had and is reported with its error. `check_exports(root)` writes nothing and returns the same results with the `changed`, `missing` and `extra` files.

## Export command (`asm_app/cli.py`)

- `python -m asm_app export` runs `write_exports` and prints, per preset, its folder and one line per component not exported, in the report's reason; it exits 1 if any needs attention.
- `python -m asm_app export --check` writes nothing, prints the same report and each changed, missing or extra file, and exits 1 if any needs attention or `exports/paperclip/` differs. CI runs it.

## APM dependency resolution

Install the optional APM CLI with `python -m pip install -e ".[apm]"`, then run `python -m asm_app lock <preset-id>`. Add `--update` to resolve again. This resolves dependencies without deploying configuration to an app. The ignored `packages/<id>/apm.lock.yaml` records the commits branches resolved to; it does not change the package revision or its exports.

A package with marketplace plugins needs that marketplace registered in APM first. For plugins from Anthropic's official marketplace, run `apm marketplace add anthropics/claude-plugins-official --name claude-plugins-official --branch main`. See [APM marketplace commands](https://microsoft.github.io/apm/reference/cli/marketplace/) and the [lockfile specification](https://microsoft.github.io/apm/reference/lockfile-spec/). ASM allows up to ten minutes for resolution.

## Consumer support (`catalog/consumers.json`)

`{kinds, consumers}`. `kinds` lists `instruction, skill, mcp, hook, claude-code-plugin, codex-plugin`. Each catalog consumer has `id`, `name`, optional `tools` (the apps its column covers), and `support`, one cell per kind in that order. Each cell has `value` of `yes`, `no` or `not-documented`, and a `doc` HTTPS URL to the source. `name` is the app's term and is required for `yes`. An optional `note` appears in the info popover with the source link. The store refuses missing or invalid cells.

`GET /api/consumers` adds the boolean `export` to every row. It tells whether the running ASM has a registered exporter, regardless of the current preset. Older catalogs may still include this field. ASM accepts that input and derives the response from the exporter registry. Use `GET /api/presets/{id}/exports` for saved-preset availability and omissions.

The Export tab shows the cells as a table, one row per kind with this preset's count. Paperclip's cell for a kind the preset has comes from the conversion report instead.
