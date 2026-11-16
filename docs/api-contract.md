# Data files and local API

For agents and people who edit ASM data. ASM's data lives in these files; no route contacts a consumer.

## Files

- `packages/<id>/apm.yml` and its `.apm/` files: one stack or preset as an APM package; the folder name is the package id. APM `dependencies` hold the members, `x-preset-labels` holds ASM's labels: `title`, `kind` (`preset` or `stack`), `icon`, `workArea`, `usage` and `paperclip: {role, canCreateAgents}`. A repository member names a branch as `ref`, never a commit or a version.
- `catalog/components.json`: the components that can be added to a stack or preset, and every source repository with its GitHub stars and the day they were read. It does not repeat a preset's members.
- `catalog/consumers.json`: what each app supports per component kind (below).
- `exports/paperclip/<id>/`: each preset's Paperclip package, generated; never edit it by hand. [paperclip.md](paperclip.md) says how to import it.
- `.asm/`: component comments, ignored by Git.

## Conventions

All JSON errors are `{ "error": "message" }`. Paths use URL-encoded package ids. Existing writes require the package `revision`; conflicts return 409. No route contacts a consumer.

## Store interface (`asm_app/store.py`)

`Store(root: Path)` where root contains `packages/`, `catalog/`, and ignored `.asm/`.

- `catalog()` -> `{items: [Component or PackageSummary], sources: [{name,url}]}`. It refuses a `catalog/components.json` whose `repositories` row lacks `stars` (a non-negative integer read from the repository's GitHub page) or `starsCheckedOn` (`YYYY-MM-DD`), or whose item comes from a repository with no row.
- `list_packages()` -> list of PackageSummary
- `get(id)` -> Package
- `create(payload)` -> Package
- `save(id,payload)` -> Package (requires revision). Create and save then rewrite `exports/paperclip/` (`write_exports`), every preset, since a saved stack changes the export of each preset that includes it.
- `export(id)` -> bytes (ZIP of the native package, the dashboard's download)
- `consumers()` -> `catalog/consumers.json` (below), or no consumers when the file is missing.
- `comments(id,component_id)` -> list
- `add_comment(id,component_id,payload)` -> comment
- `lock(id,update=False)` -> `{ok,output}`; bounded fixed APM invocation, no shell. It runs `apm lock` in `packages/<id>/`, which writes `apm.lock.yaml` there.

PackageSummary: `id,title,description,kind` (`preset` or `stack`), `icon` (a lowercase icon name such as `rocket`, or empty when none was chosen), `version,workArea:[],usage:[],componentCount`.

Package extends summary: `revision,instruction,components:[],files:[{path,content}]` and `paperclip:{role,canCreateAgents}`, read from `x-preset-labels.paperclip` in `apm.yml`; `role` is null and `canCreateAgents` false when unset. The preset details dialog edits them.

Component: `id,name,kind` (`skill,mcp,hook,plugin,instruction,package,other`), `description,sourceUrl,source,configuration`. Source uses `repositoryUrl,path,ref`; `ref` names a branch, and an empty `ref` follows the default branch. A component stored as a file in the package also has `file`, its path inside the package (for example `.apm/skills/<name>/SKILL.md`). Catalog components additionally contain `type:"component"` and native `apm` creation metadata, and, when they come from a repository, its `stars` and `starsCheckedOn`. A catalog row with an APM `git` value stores no `source` or `sourceUrl`; `catalog()` derives both from that value, and only rows without `git` (marketplace plugins, MCP servers) store them; catalog package summaries contain `type:"preset"|"stack"` and `packageId`.

Create/save payload: `title,description,kind,icon,workArea,usage,instruction,paperclip,componentIds`. An empty `icon` removes the stored one. `paperclip` is `{role,canCreateAgents}`: `role` empty, null or one of the Paperclip `roles` in `catalog/consumers.json` (a role already stored is kept even when it is not in the list, so other edits still save), `canCreateAgents` a boolean; anything else is a 400. An empty role and `canCreateAgents: false` remove their keys from `x-preset-labels.paperclip`, and an empty block is removed. `componentIds` accepts catalog component ids and `package:<id>` for a stack dependency. Save retains unsupported native fields unless deliberately removed. A new package id is derived from the title; a collision is rejected rather than replaced.

## HTTP routes (`asm_app/server.py`)

- GET `/api/catalog` -> store.catalog()
- GET `/api/presets` -> `{presets: store.list_packages()}`
- GET `/api/presets/{id}` -> Package
- POST `/api/presets` -> Package
- PATCH `/api/presets/{id}` -> Package
- GET `/api/presets/{id}/export` -> native ZIP, the dashboard's download
- POST `/api/presets/{id}/lock` -> store.lock(id, update)
- GET `/api/comments?presetId=&componentId=` -> `{comments:[]}`
- POST `/api/comments` with `presetId,componentId,body,author` -> `{comment}`
- GET `/api/consumers` -> store.consumers()
- GET `/api/presets/{id}/paperclip` -> conversion report from `convert()`
- GET `/api/presets/{id}/paperclip/export` -> the same files as `exports/paperclip/{id}/`, as a ZIP

## Paperclip interface (`asm_app/paperclip.py`)

`convert(package, *, root:Path)` -> `{consumer:"paperclip",items:[{id,name,kind,supportKind,conversion:{status,reason,cause?},source,target}],summary:{total,converted,unconverted},files:[{path,content}],folder:{path,url}}`. `folder` is where the export is committed, `exports/paperclip/<id>`, with its GitHub page on `main` (null without `project.urls.Repository`); it is null for a stack, which is not one agent and is not exported.

`supportKind` is the support table row the component counts in (a `kinds` value of `catalog/consumers.json`): its kind, or for a plugin `claude-code-plugin` or `codex-plugin` by the `.claude-plugin/` or `.codex-plugin/` folder its source names; null for a stack, a plugin that names neither, and the role row.

Conversion statuses are `converted` and `unconverted`. Reasons are concise English. There is no runtime field. Every source component appears; `target` is the written file the component went to (`agents/<id>/AGENTS.md`, `skills/<key>/SKILL.md`), or `{packageId}` for an expanded stack.

`cause` names why the export leaves a component out as expected: `not-in-format` for hooks and plugins, which Paperclip's company package has no entry for, and `adapter` for MCP servers: the company package has no MCP entry either, the export writes no adapter, and Paperclip's docs do not say how an imported agent gets an MCP server, so the report asks for it to be set in the agent's adapter after import. An unconverted component without a `cause` needs attention: a skill with no branch, outside GitHub, or a role that is not one of Paperclip's.

The files, named by the package id:

- `COMPANY.md`: `schema: agentcompanies/v1`, `kind: company`, `slug`, `name`, `description`.
- `agents/<id>/AGENTS.md`: `kind: agent`, `name`, `title`, `slug`, `role` and `skills`, the stub keys in member order; no `reportsTo`. The body is the Instruction.
- `skills/<key>/SKILL.md`: one stub per skill with `key`, `name`, `description` and `metadata.sources[0] = {kind: github-dir, repo, path, trackingRef, url}`, no commit. `path` is the skill's folder, `.` for a skill at the repository root. Paperclip does not read the stubs; [paperclip.md](paperclip.md) turns them into skill sources. `trackingRef` is the member's APM `ref`. A skill the preset holds itself is read from this repository, the `project.urls.Repository` of `pyproject.toml`, at `packages/<id>/.apm/skills/<name>` on `main`; its stub takes `name` and `description` from that `SKILL.md`'s frontmatter, or the folder name when it has none. The key is the folder name, or the repository name for a root skill; when two skills share it, both take `<repo>-<name>`.
- `.paperclip.yaml`: `schemaVersion: 7` and, under `agents.<id>`, `role`, `permissions.canCreateAgents`, `runtime.heartbeat.enabled: false` and `metadata.agentStackManagerPackageId` and `metadata.agentStackManagerRevision`, a SHA-256 over the preset's files and those of its nested stacks with LF line endings (`store._export_digest`). No adapter and no budget.

`role` comes from `x-preset-labels.paperclip.role`, `general` when unset; it must be one of the Paperclip `roles` in `catalog/consumers.json`, which cite Paperclip's list. `canCreateAgents` is true only where the labels set it.

`export_package(report)` -> ZIP bytes of those files.

`write_exports(root)` writes `exports/paperclip/<id>/` for every package of kind `preset`, exactly the files `convert` gives, with LF line endings, and removes every other file there, so a deleted preset or skill loses its export. A package that cannot be read keeps the folder it had and is reported with its error. `check_exports(root)` writes nothing and returns the same results with the `changed`, `missing` and `extra` files.

## Export command (`asm_app/cli.py`)

- `python -m asm_app export` runs `write_exports` and prints, per preset, its folder and one line per component not exported, in the report's reason; it exits 1 if any needs attention.
- `python -m asm_app export --check` writes nothing, prints the same report and each changed, missing or extra file, and exits 1 if any needs attention or `exports/paperclip/` differs. CI runs it.

## Consumer support (`catalog/consumers.json`)

`{kinds, consumers}`. `kinds` is `instruction, skill, mcp, hook, claude-code-plugin, codex-plugin`: the component kinds with Plugin split by the manifest each app reads. Each consumer has `id`, `name`, `export` (true only for Paperclip, the one app ASM exports to), optional `tools` (for CC Switch, the tools of its own table that its column covers), optional `roles: {values, doc}` (Paperclip's agent roles and the page that lists them) and `support`, one cell per kind in that order: `{value, name?, note?, doc}`. `value` is `yes`, `no` or `not-documented` (the app's page on that format says nothing); `name` is the app's own term, required for `yes`; `note` is hover text; `doc` is the https page that says so. The store refuses a file with a missing kind, another value, or a cell without `doc`.

The Export tab shows the cells as a table, one row per kind with this preset's count. Paperclip's cell for a kind the preset has comes from the conversion report instead.
