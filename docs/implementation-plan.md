# Agent Stack Manager implementation plan

**Goal:** Ship a runnable repo-backed APM catalog/editor with Paperclip export and readback.

**Architecture:** Python package storage and consumer adapter behind a loopback HTTP API; browser modules for the UI. Native APM packages are the sole preset source.

**Tech stack:** Python 3.11+, PyYAML, standard-library HTTP/ZIP/Git process calls; HTML/CSS/JavaScript. Reuse the tested Python converter instead of maintaining two runtimes for local storage.

**Spec:** [design.md](design.md).

## Tasks

- [ ] Package store: catalog, create/edit stacks and presets, native ZIP, comments, explicit APM lock. Test persistence, stale revision rejection, unsafe paths, unknown extension preservation and membership edits.
- [ ] Paperclip adapter: native package conversion, remote source plan, per-component outcomes, explicit import/readback. Test unsupported hook/plugin disclosure, source identity and MCP CLI engine.
- [ ] Dashboard: reference-backed catalog + selection, named preset editor, Instruction, metadata, source files, Paperclip conversion/readback and other consumer placeholders. Test actual API interactions and mobile layout where available.
- [ ] Local server/CLI and distribution: loopback by default, origin/write protection, bounded errors, package data, reproducible setup and CI. No arbitrary subprocess execution from input.
- [ ] Board cleanup: cancel superseded plans with links to the replacement, retain independent/deferred work and completed evidence.

## Completion checks

Create a preset from real catalog entries, edit and reload native files, download current package, convert every component with explicit outcome, query the isolated Paperclip company, and run the repository test suite. No production company or host configuration writes. Initial import experiment stays in Preset Import Lab.
