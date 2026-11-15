# Agent Stack Manager

A local catalog and editor for APM stacks and agent presets. Select components, save an APM package, and see what converts for each consumer.

## Run

Python 3.11 or newer is required. From this checkout:

```powershell
python -m venv .venv
.venv/Scripts/Activate.ps1
python -m pip install -e .
python -m asm_app serve
```

On macOS/Linux, activate with `source .venv/bin/activate` instead. Open [localhost:4319](http://127.0.0.1:4319). The server binds to loopback.

## Packages

`packages/` contains the editable APM packages. Changes from the dashboard write to their `apm.yml` and native `.apm/` files. Review and commit them with Git.

- Catalog: search components, stacks and presets; collect components into a selection.
- Presets: create and edit title, description, workArea, usage, Instruction and component membership.
- Source files: inspect and download the current APM package.
- Component comments: persist local observations in ignored `.asm/` files.

The initial Web app engineer and CAO packages preserve the selections used in the format comparison. Each includes a test hook and a different official marketplace plugin. Source access and target validation failures remain visible in conversion/import results.

`x-preset-labels` stores display metadata. APM dependencies store membership; there is no second ASM preset format. The component catalog is an index of source references and creation templates, not a second list of each preset's components.

## Consumers

| Consumer | Available |
|---|---|
| Paperclip | Package export, explicit CLI import, saved-state readback |
| Codex | Placeholder |
| Claude Code | Placeholder |
| CC Switch | Placeholder |

The Paperclip adapter converts Instruction, GitHub skill references and stdio MCP configuration. Paperclip has no setting for agent hooks or plugins, so each is reported as unconverted with that cause. A skill that Paperclip's scan refuses is left out and reported as refused. Non-stdio or unrecognized components are also reported explicitly. A saved configuration does not establish runtime success.

Export without touching a consumer:

```sh
python -m asm_app export web-app-engineer --consumer paperclip --output dist/web-app-engineer-paperclip.zip
python -m asm_app export web-app-engineer --consumer apm --output dist/web-app-engineer-apm.zip
```

The Paperclip ZIP includes a native package and remote-source import plan. Paperclip's package importer alone does not execute that source-registration plan. Use the explicit CLI import to register the original skill repos before importing the role:

```sh
python -m asm_app paperclip web-app-engineer --url http://127.0.0.1:3106 --company YOUR_COMPANY_ID --apply
```

Omit `--apply` for readback only. New agents are paused; this command does not start employee runs. Nonzero exit status means some components were not saved or the operation failed; the JSON result identifies them.

For the dashboard's readback action, set `ASM_PAPERCLIP_URL` and `ASM_PAPERCLIP_COMPANY_ID` before starting the server. Opening the dashboard and editing/exporting a preset never installs it into a consumer. No company is selected implicitly.

## APM lock

Microsoft APM is optional. Install the pinned CLI into the same Python environment:

```sh
python -m pip install -e '.[apm]'
python -m asm_app lock web-app-engineer
```

This resolves dependencies and writes `apm.lock.yaml` without deploying into host agent directories. Use `--update` to request upstream resolution. A lock operation can fail if a referenced source is inaccessible. The app reports the command result; it does not install missing host tools.

## Development

The React frontend is in `frontend/`. Its production build is included in
`asm_app/web/`, so running the Python app does not require Node.js.

To change the frontend, use Node.js 22.12 or newer:

```sh
cd frontend
npm ci
npm test
npm run build
```

Reload the local dashboard after building. UI source and compiled files belong
in the same commit. The interface reuses Skills Manager and Claude Code
Templates components; source versions and adaptations are recorded in
`frontend/IMPLEMENTATION.md` and the bundled license notices.

Run the backend checks from the repository root:

```sh
python -m unittest discover -s tests -v
```

[Design](docs/design.md) · [Reference screens](docs/design-references.md) · [API contract](docs/api-contract.md)
