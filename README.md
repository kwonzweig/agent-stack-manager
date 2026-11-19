# Agent Stack Manager

Compose reusable agent configurations from instructions, skills, MCP servers, hooks and plugins. Group components into stacks and role presets, keep them as [Microsoft APM](https://github.com/microsoft/apm) packages, and review exports for Paperclip and CC Switch in a local dashboard.

[Run locally](#run-locally) · [Create a preset](#create-a-preset) · [Export](#export) · [Data and API](docs/api-contract.md)

![The Web app engineer preset's Components tab, showing components and their source labels](docs/screenshot.png)

## Run locally

You need Python 3.11 or newer and Git. The built dashboard is included; Node.js is needed only to develop the frontend.

On macOS or Linux:

```sh
git clone https://github.com/kwonzweig/agent-stack-manager.git
cd agent-stack-manager
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
python -m asm_app serve
```

On Windows, after cloning and entering the folder, use PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m asm_app serve
```

On Debian or Ubuntu, install `python3-venv` if creating the environment fails. Open [127.0.0.1:4319](http://127.0.0.1:4319). To use another port, add `--port 4320` after `serve`.

The commands below use `python` with the virtual environment active. On Windows, you can keep using `.\.venv\Scripts\python.exe` instead. Run from the clone, or put `--root <folder>` before the subcommand to choose another data folder. The installed `agent-stack-manager` command has the same options.

## Create a preset

A **component** is an individual configuration item. A **stack** groups components you reuse together. A **preset** combines an agent's instruction with components and stacks for a role.

1. Open **Catalog** to search and inspect a component's source and details.
2. Choose **New preset** in the sidebar, enter a name, and press **Create**. Choose **Stack** in the Type field instead when building a reusable group.
3. Open **Add components**, choose components or stacks, and add them to the draft. Open **Instruction** to edit the role's instruction.
4. Press **Save changes**. Open **Source files** to inspect the saved package, or **Export** to review the saved revision's target results and downloads.

Changes made inside a preset remain a draft until saved. Adding from the Catalog directly to an existing preset saves immediately. Each save updates `packages/<id>/apm.yml` and generated Paperclip files under `exports/paperclip/<id>/`; review and commit these files with Git.

The Catalog also brings together components from loaded packages and captured app inventories. Details show their sources, origins and preset memberships. An item without reusable source data can be inspected but cannot be added elsewhere. Source descriptions and available repository metrics are read from their owners, with missing information shown explicitly.

For captured inventory, open a component's details to change its membership separately for Codex and Claude Code. Excluding an observation keeps it available for later review and inclusion; it does not uninstall anything.

## Export

The **Export** tab separates what an app supports from what ASM can produce for the saved preset. Review every omitted or manual item before using a download. A stack contributes through a preset when exporting a Paperclip agent.

| Target | Output | Next step |
| --- | --- | --- |
| Paperclip | Company-package ZIP with an agent instruction and skill references | [Import the agent and configure its skill sources, adapter and permissions](docs/paperclip.md). |
| CC Switch | JSON review for recorded Codex or Claude Code inventory, including inventory in nested stacks | Review eligible import links, repository registrations and items requiring their host's own route. [Format and limits](docs/api-contract.md#cc-switch-review). |

A skill repository link registers a source in CC Switch; it does not install or enable its skills. Hooks, plugins and other unsupported items remain in the APM package. ASM does not scan your machine, apply configuration to apps, or confirm that an external import succeeded. Direct Claude Code/Codex deployment and reverse conversion are not implemented.

The dashboard reads the app support matrix from [catalog/consumers.json](catalog/consumers.json), whose entries link to each app's documentation. Export availability and omissions are assessed for each preset.

```sh
python -m asm_app export          # regenerate Paperclip folders
python -m asm_app export --check  # check without writing
python -m asm_app cc-switch <preset-id>  # print an inventory review
```

To review a captured private inventory alongside the shared presets, use a separate write folder and a read-only base checkout. See [app inventory](docs/api-contract.md#app-inventory) for the command, data format and source-access policy.

## Development

```sh
python -m unittest discover -s tests
python -m asm_app export --check
```

Frontend changes require Node.js 22.12 or newer. Rebuild the committed dashboard with its source:

```sh
cd frontend
npm ci
npm test
npm run build
```

The [Check workflow](.github/workflows/check.yml) checks tests, exports and the frontend build. See [data files and the local API](docs/api-contract.md) for scripting and [APM dependency resolution](docs/api-contract.md#apm-dependency-resolution) for the optional lock command. Report bugs or propose changes in [issues](https://github.com/kwonzweig/agent-stack-manager/issues).

## Licence

[MIT](LICENSE). Reused frontend code and fonts retain their own [licence notices](frontend/IMPLEMENTATION.md).
