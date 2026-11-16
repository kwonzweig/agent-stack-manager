# Agent Stack Manager

Agent Stack Manager browses components, composes reusable stacks and agent presets, and converts a preset into a package that a consumer can import. APM packages in `packages/` are canonical. There is no separate ASM preset schema. ASM does not connect to a consumer: a person or an agent imports the exported package by hand.

The dashboard runs locally. The UI uses Skills Manager's theme, icons, sidebar, workspace cards, dialogs and detail sheet. Catalog adapts AITMPL's component grid; a per-card add menu and a selection bar replace its Stack drawer.

## Data and behavior

- `packages/<id>/apm.yml` plus native `.apm/` files store stack/preset content. `x-preset-labels` holds title, icon, workArea, usage and catalog kind. APM dependencies hold membership.
- `catalog/components.json` indexes reusable component sources and creation templates. It does not duplicate a preset's membership. Catalog also reads stack/preset packages directly.
- Python reuses the existing Python APM conversion work and APM CLI. The local HTTP server serves a prebuilt React bundle from `asm_app/web/`; frontend source lives in `frontend/`. Filesystem access runs on this machine, not a hosted Worker.
- Editing writes real package files and checks a content revision to avoid overwriting another editor. Downloads contain the current native package files.
- The Paperclip conversion runs by itself when a preset opens. It emits a native Paperclip package and `remote-import-plan.json`, the list of remote skill sources for whoever imports the package. Every component has an explicit converted or unconverted outcome with its reason. No runtime success badge.
- Remote first. Where a consumer supports importing from a remote, it imports each component from its source repository and follows that repository's default branch with its own update. Only where a consumer cannot import from a remote does it get a snapshot. A preset and the catalog name a source by repository, path and branch, never by a commit or a version.
- The snapshot fallback is not built yet. Paperclip, the one supported consumer, imports skills from their remote.
- ASM makes what a consumer supports work and does not implement what the consumer does not officially support. A kind Paperclip has no setting for (hooks, plugins) is unconverted with the cause `unsupported`. The dashboard shows it as left out as expected, apart from conversions that failed and need attention.
- Codex, Claude Code and CC Switch show an unimplemented state and perform no configuration writes.
- Comments live in ignored `.asm/` runtime files. Presets remain reviewable through Git.
- APM lock is optional and runs only on an explicit action; it does not deploy into host agent configuration folders.

## Workflow

Search Catalog, select components or saved stacks, create a preset, edit Instruction and metadata, save it as APM files, read the Paperclip conversion and export the package. Opening the dashboard never changes a consumer.

Source provenance: `frontend/IMPLEMENTATION.md` and bundled license notices.
