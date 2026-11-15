# Agent Stack Manager implementation plan

**Goal:** Ship a runnable repo-backed APM catalog/editor with Paperclip export and readback.

This records the initial implementation. The frontend replacement is tracked in
the company an internal Task and `frontend/IMPLEMENTATION.md`; it retains the existing
package store and Paperclip adapter.

**Architecture:** Python package storage and consumer adapter behind a loopback HTTP API; a prebuilt React bundle for the UI. Native APM packages are the sole preset source.

**Tech stack:** Python 3.11+, PyYAML, standard-library HTTP/ZIP/Git process calls; React, TypeScript and Vite for the frontend in `frontend/`. Reuse the tested Python converter instead of maintaining two runtimes for local storage.

**Spec:** [design.md](design.md).

## Tasks

- [x] Package store: catalog, create/edit stacks and presets, native ZIP, comments, explicit APM lock. Test persistence, stale revision rejection, unsafe paths, unknown extension preservation and membership edits.
- [x] Paperclip adapter: native package conversion, remote source plan, per-component outcomes, explicit import/readback. Test unsupported hook/plugin disclosure, source identity and MCP CLI engine.
- [x] Dashboard: reference-backed catalog + selection, named preset editor, Instruction, metadata, source files, Paperclip conversion/readback and other consumer placeholders. Test actual API interactions and mobile layout where available.
- [x] Local server/CLI and distribution: loopback by default, origin/write protection, bounded errors, package data, reproducible setup and CI. No arbitrary subprocess execution from input.
- [x] Board cleanup: cancel superseded plans with links to the replacement, retain independent/deferred work and completed evidence.

## Completion checks

Create a preset from real catalog entries, edit and reload native files, download current package, convert every component with explicit outcome, query the isolated Paperclip company, and run the repository test suite. No production company or host configuration writes. Initial import experiment stays in the test company.

## Verification scope

Storage, HTTP editing/export/comments and consumer conversion/readback are covered by automated tests. Paperclip imports were exercised only in the test company. The React frontend was rendered at 1440px and 390px and exercised in a browser against an isolated data copy: create a preset from catalog entries, edit and save, reload, comment, inspect source and download the APM ZIP ([PR #2](https://github.com/kwonzweig/agent-stack-manager/pull/2)).
