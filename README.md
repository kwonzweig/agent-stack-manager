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

- Catalog: search components, stacks and presets, optionally grouped by source repository. Add a component to a preset or stack from its + menu, or select several and add them together.
- Presets: create and edit title, description, icon, workArea, usage, Instruction and component membership.
- Source files: inspect and download the current APM package.
- Component comments: persist local observations in ignored `.asm/` files.

The initial Web app engineer and CAO packages preserve the selections used in the format comparison. Each includes a test hook and a different official marketplace plugin.

`x-preset-labels` stores display metadata. APM dependencies store membership; there is no second ASM preset format. The component catalog is an index of source references and creation templates, not a second list of each preset's components.

## Consumers

| Consumer | Available |
|---|---|
| Paperclip | Package export |
| Codex | Placeholder |
| Claude Code | Placeholder |
| CC Switch | Placeholder |

The Paperclip adapter converts Instruction, GitHub skill references and stdio MCP configuration. Paperclip has no setting for agent hooks or plugins, so each is reported as unconverted with that cause. Non-stdio or unrecognized components are also reported explicitly.

Export without touching a consumer:

```sh
python -m asm_app export web-app-engineer --consumer paperclip --output dist/web-app-engineer-paperclip.zip
python -m asm_app export web-app-engineer --consumer apm --output dist/web-app-engineer-apm.zip
```

The Paperclip ZIP includes a native package and remote-source import plan. The agent in the ZIP lists no skills. Paperclip's package importer does not read `remote-import-plan.json`, so whoever imports the package adds those skill sources in Paperclip by hand. Opening the dashboard and editing/exporting a preset never installs it into a consumer.

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

[Design](docs/design.md) · [API contract](docs/api-contract.md)
