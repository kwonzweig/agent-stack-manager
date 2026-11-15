# Agent Stack Manager

Agent Stack Manager browses components, composes reusable stacks and agent presets, and exports them for consumers. APM packages in `packages/` are canonical. There is no separate ASM preset schema.

The first release is a local dashboard. The UI uses Skills Manager's theme, icons, sidebar, workspace cards, dialogs and detail sheet. Catalog adapts AITMPL's component grid and selection drawer. The Lab's component details, source files and conversion results remain part of the preset reader. The same Web app engineer and CAO definitions from the comparison are retained. Historical prototype sites remain separate.

## Data and behavior

- `packages/<id>/apm.yml` plus native `.apm/` files store stack/preset content. `x-preset-labels` holds title, workArea, usage and catalog kind. APM dependencies hold membership.
- `catalog/components.json` indexes reusable component sources and creation templates. It does not duplicate a preset's membership. Catalog also reads stack/preset packages directly.
- Python reuses the existing Python APM conversion work and APM CLI. The local HTTP server serves a prebuilt React bundle from `asm_app/web/`; frontend source lives in `frontend/`. Filesystem access and local Paperclip access run on this machine, not a hosted Worker.
- Editing writes real package files and checks a content revision to avoid overwriting another editor. Downloads contain the current native package files.
- Paperclip conversion emits a native package and remote source import plan. Every component has an explicit converted/unconverted outcome. Import readback is separate from conversion. No runtime success badge; observations belong in component comments.
- Remote sources are preserved for consumer-native import. Snapshot fallback is explicit when native remote import is unavailable.
- ASM makes what a consumer supports work and does not implement what the consumer does not officially support. A component Paperclip leaves out carries its cause: `unsupported` for a kind Paperclip has no setting for (hooks, plugins), `refused` for a skill its scan refuses, `access` for a source it cannot read.
- Codex, Claude Code and CC Switch show an unimplemented state and perform no configuration writes.
- Comments and observed consumer state live in ignored `.asm/` runtime files. Presets remain reviewable through Git.
- APM lock is optional and runs only on an explicit action; it does not deploy into host agent configuration folders.

## First release workflow

Search Catalog, select components or saved stacks, create a preset, edit Instruction and metadata, save it as APM files, inspect the Paperclip conversion, export the package. An explicit CLI command can import into a named Paperclip company and read back the result. Opening the dashboard never changes a consumer.

Source provenance: `frontend/IMPLEMENTATION.md` and bundled license notices. Initial reference investigation: `docs/design-references.md`. Work tracking: the company an internal Task (initial implementation), an internal Task (UI replacement).
