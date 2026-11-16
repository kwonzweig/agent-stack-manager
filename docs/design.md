# Agent Stack Manager

Agent Stack Manager browses components, composes reusable stacks and agent presets, and converts a preset into a package that a consumer can import. APM packages in `packages/` are canonical. There is no separate ASM preset schema. ASM does not connect to a consumer: a person or an agent imports the exported package by hand.

The dashboard runs locally. The UI uses Skills Manager's theme, icons, sidebar, workspace cards, dialogs and detail sheet. Catalog adapts AITMPL's component grid; a per-card add menu and a selection bar replace its Stack drawer.

## Data and behavior

- `packages/<id>/apm.yml` plus native `.apm/` files store stack/preset content. `x-preset-labels` holds title, icon, workArea, usage, catalog kind and the Paperclip `role` and `canCreateAgents`. APM dependencies hold membership.
- `catalog/components.json` indexes reusable component sources and creation templates. It does not duplicate a preset's membership. Catalog also reads stack/preset packages directly.
- `catalog/consumers.json` holds data about the apps ASM exports to: for Paperclip, its list of agent roles with the page that publishes it.
- Python reuses the existing Python APM conversion work and APM CLI. The local HTTP server serves a prebuilt React bundle from `asm_app/web/`; frontend source lives in `frontend/`. Filesystem access runs on this machine, not a hosted Worker.
- Editing writes real package files and checks a content revision to avoid overwriting another editor. Downloads contain the current native package files.
- The Paperclip conversion loads by itself when the preset's Export tab opens; there is no Convert button. It emits a Paperclip company package named by the package id: `COMPANY.md`, the agent's `AGENTS.md` listing its skills, `.paperclip.yaml`, and one skill stub per skill that names its GitHub repository, folder and branch, with no commit. A skill the preset holds itself follows this repository's `main`. The export writes no adapter, and Paperclip's docs do not say how an imported agent gets an MCP server, so the report asks for MCP to be set in the agent's adapter after import. Every component has an explicit converted or unconverted outcome with its reason. No runtime success badge. Every preset's export is committed under `exports/paperclip/<id>/`, which Paperclip [imports by its GitHub URL](https://github.com/paperclipai/paperclip/blob/master/docs/guides/board-operator/importing-and-exporting.md#github-sources); each save rewrites the folders of every preset, and CI fails when they are out of date (`python -m asm_app export --check`). Stacks are not exported on their own.
- Remote first. Where a consumer supports importing from a remote, it imports each component from its source repository and follows that repository's default branch with its own update. Only where a consumer cannot import from a remote does it get a snapshot. A preset and the catalog name a source by repository, path and branch, never by a commit or a version.
- The snapshot fallback is not built yet. Paperclip, the one supported consumer, can import a skill from its remote repository.
- ASM makes what a consumer supports work and does not implement what the consumer does not officially support. A kind Paperclip's company package has no entry for (hooks, plugins) is unconverted with the cause `not-in-format`; MCP is unconverted with the cause `adapter`. The dashboard shows it as left out as expected, apart from conversions that failed and need attention.
- Codex, Claude Code and CC Switch show an unimplemented state and perform no configuration writes.
- Comments live in ignored `.asm/` runtime files. Presets remain reviewable through Git.
- APM lock is optional and runs only on an explicit action; it does not deploy into host agent configuration folders.

## Workflow

Search Catalog, select components or saved stacks, create a preset, edit Instruction and metadata, save it as APM files, read the Paperclip conversion, and commit the rewritten `exports/paperclip/<id>/` with the preset. Opening the dashboard never changes a consumer.

Source provenance: `frontend/IMPLEMENTATION.md` and bundled license notices.
