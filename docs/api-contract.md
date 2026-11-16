# Local API

All JSON errors are `{ "error": "message" }`. Paths use URL-encoded package ids. Existing writes require the package `revision`; conflicts return 409. No route contacts a consumer.

## Store interface (`asm_app/store.py`)

`Store(root: Path)` where root contains `packages/`, `catalog/`, and ignored `.asm/`.

- `catalog()` -> `{items: [Component or PackageSummary], sources: [{name,url}]}`
- `list_packages()` -> list of PackageSummary
- `get(id)` -> Package
- `create(payload)` -> Package
- `save(id,payload)` -> Package (requires revision)
- `export(id)` -> bytes (ZIP)
- `comments(id,component_id)` -> list
- `add_comment(id,component_id,payload)` -> comment
- `lock(id,update=False)` -> `{ok,output}`; bounded fixed APM invocation, no shell.

PackageSummary: `id,title,description,kind` (`preset` or `stack`), `icon` (a lowercase icon name such as `rocket`, or empty when none was chosen), `version,workArea:[],usage:[],componentCount`.

Package extends summary: `revision,instruction,components:[],files:[{path,content}]`.

Component: `id,name,kind` (`skill,mcp,hook,plugin,instruction,package,other`), `description,sourceUrl,source,configuration`. Source uses `repositoryUrl,path,ref`; `ref` names a branch, and an empty `ref` follows the default branch. Catalog components additionally contain `type:"component"` and native `apm` creation metadata; catalog package summaries contain `type:"preset"|"stack"` and `packageId`.

Create/save payload: `title,description,kind,icon,workArea,usage,instruction,componentIds`. An empty `icon` removes the stored one. `componentIds` accepts catalog component ids and `package:<id>` for a stack dependency. Save retains unsupported native fields unless deliberately removed. A new package id is derived from the title; a collision is rejected rather than replaced.

## HTTP routes (`asm_app/server.py`)

- GET `/api/catalog` -> store.catalog()
- GET `/api/presets` -> `{presets: store.list_packages()}`
- GET `/api/presets/{id}` -> Package
- POST `/api/presets` -> Package
- PATCH `/api/presets/{id}` -> Package
- GET `/api/presets/{id}/export` -> native ZIP
- POST `/api/presets/{id}/lock` -> store.lock(id, update)
- GET `/api/comments?presetId=&componentId=` -> `{comments:[]}`
- POST `/api/comments` with `presetId,componentId,body,author` -> `{comment}`
- GET `/api/consumers` -> `{consumers:[{id,name,supported}]}`
- GET `/api/presets/{id}/paperclip` -> conversion report from `convert()`
- GET `/api/presets/{id}/paperclip/export` -> Paperclip ZIP

## Paperclip interface (`asm_app/paperclip.py`)

`convert(package, *, root:Path)` -> `{consumer:"paperclip",items:[{id,name,kind,conversion:{status,reason,cause?},source,target}],summary:{total,converted,unconverted},files:[{path,content}]}`.

Conversion statuses are `converted` and `unconverted`. Reasons are concise English. There is no runtime field. Every source component appears. Unsupported hooks and plugins are unconverted, not silently flattened or dropped.

`cause` is `unsupported` when Paperclip has no setting for the component's kind. An unconverted component without a `cause` is a conversion that failed and needs attention.

The files are `COMPANY.md`, `agents/<slug>/AGENTS.md`, `.paperclip.yaml` and `remote-import-plan.json`, which lists the remote skill sources (`repositoryUrl,path,ref?`) for whoever imports the package.

`export_package(report)` -> ZIP bytes of those files.
