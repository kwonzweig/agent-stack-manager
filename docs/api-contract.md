# Local API

All JSON errors are `{ "error": "message" }`. Paths use URL-encoded package ids. Existing writes require the package `revision`; conflicts return 409. API changes are coordinated between workers.

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

Component: `id,name,kind` (`skill,mcp,hook,plugin,instruction,package,other`), `description,sourceUrl,source,configuration`. Source uses `repositoryUrl,path,ref`. Catalog components additionally contain `type:"component"` and native `apm` creation metadata; catalog package summaries contain `type:"preset"|"stack"` and `packageId`.

Create/save payload: `title,description,kind,icon,workArea,usage,instruction,componentIds`. An empty `icon` removes the stored one. `componentIds` accepts catalog component ids and `package:<id>` for a stack dependency. Save should retain unsupported native fields unless deliberately removed. New package id derived from title, with collision rejection rather than replacement.

## HTTP routes (`asm_app/server.py`, root owns)

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
- GET `/api/presets/{id}/paperclip` -> conversion report
- GET `/api/presets/{id}/paperclip/export` -> Paperclip ZIP
- POST `/api/presets/{id}/paperclip/observe` -> report with live saved-state readback; read only on Paperclip

## Paperclip interface (`asm_app/paperclip.py`)

`convert(package, *, root:Path)` -> `{consumer:"paperclip",items:[{id,name,kind,conversion:{status,reason,cause?},import:{status,reason,cause?},source,target}],summary:{total,converted,unconverted,imported,notImported},files:[{path,content}]}`.

Conversion statuses `converted,unconverted`; import statuses `saved,missing,not_checked`. Reasons concise English. No runtime field. Every source component appears. Unsupported hooks/plugins must be unconverted, not silently flattened/dropped.

`cause` is present when the adapter knows why Paperclip left the component out: `unsupported` (Paperclip has no setting for this kind), `refused` (Paperclip's scan refused the skill), `access` (Paperclip could not read the source repository). Without a `cause`, a component that is not saved is a failure to look into.

`export_package(report)` -> ZIP bytes.

`observe(package, *, root:Path, base_url:str, company_id:str)` -> report after readback.

`import_package(package, *, root:Path, base_url:str, company_id:str)` -> report; CLI only, explicit `--apply` and company required. Native remote source import and paused role; no employees run. Failed components remain in report. Do not silently choose production company.
