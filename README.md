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

The CAO preset holds its Instruction, four skills (`agent-operating-standards`, `find-tools`, `find-skills`, `humanizer`), the `cao-stop` hook and the `session-report` plugin. The Web app engineer preset holds its Instruction, 31 skills, the Playwright MCP server, the `web-session-start` hook and the `frontend-design` plugin. The two hooks only echo a line, and the two plugins are not there for real use: both pairs test how hooks and plugins convert.

`x-preset-labels` stores display metadata and the Paperclip role (`general` when unset; CAO sets `ceo`) and whether the agent may create agents. APM dependencies store membership; there is no second ASM preset format. The component catalog is an index of source references and creation templates, not a second list of each preset's components.

## Consumers

| Consumer | Available |
|---|---|
| Paperclip | Package export |
| Codex | Placeholder |
| Claude Code | Placeholder |
| CC Switch | Placeholder |

The Paperclip export writes the Instruction as the agent's `AGENTS.md` and one skill stub per GitHub skill that follows the skill's branch. Paperclip's [company package spec](https://github.com/paperclipai/paperclip/blob/master/docs/companies/companies-spec.md) has no entry for MCP servers, hooks or plugins. The export writes no adapter, and Paperclip's docs do not say how an imported agent gets an MCP server, so the report asks for MCP to be set in the agent's adapter after import; hooks and plugins are left out. Each is reported with that cause, and anything else that does not convert is reported as needing attention.

Every preset's Paperclip package is committed under `exports/paperclip/<id>/`: [CAO](exports/paperclip/cao), [Web app engineer](exports/paperclip/web-app-engineer). Paperclip imports a preset from its folder's GitHub URL, such as `https://github.com/kwonzweig/agent-stack-manager/tree/main/exports/paperclip/cao`. Saving in the dashboard rewrites the folders; commit the changed files with Git. From the command line:

```sh
python -m asm_app export          # rewrite exports/paperclip/ and list what each preset leaves out
python -m asm_app export --check  # write nothing; fail if exports/paperclip/ is out of date
```

Both exit with 1 when a component needs attention. A folder holds `COMPANY.md`, `agents/<id>/AGENTS.md`, `.paperclip.yaml` and `skills/<key>/SKILL.md` stubs; [the API contract](docs/api-contract.md) lists their fields. The Export tab downloads the same files as a ZIP, and Source files downloads the APM package. Nothing here installs a preset into a consumer.

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
python -m asm_app export --check
```

[Design](docs/design.md) · [API contract](docs/api-contract.md)
