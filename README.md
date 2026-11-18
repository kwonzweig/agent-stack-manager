# Agent Stack Manager

Agent skills, stacks and presets kept in one place as Microsoft APM packages, with a local dashboard and automatic export to Paperclip.

[Run](#run) · [Export](#export) · [Import into Paperclip](docs/paperclip.md) · [Data files and local API](docs/api-contract.md) · [Development](#development)

![The Export tab of the Web app engineer preset: what each app supports, and the Paperclip conversion](docs/screenshot.png)

## Why

Agent stacks change fast. Following them needs one central place to keep and organize skills, and to say what each agent is made of. Agent Stack Manager (ASM) is that place: an agent stack centralization effort.

It works in three units:

- **Agent config component**: one Instruction, Skill, MCP server, Hook or Plugin, with its source repository when it comes from one.
- **Stack**: components that are used together.
- **Agent preset**: one role. Its Instruction, its components and the stacks it includes, more than a list of skills.

Every stack and preset is a [Microsoft APM](https://github.com/microsoft/apm) package in `packages/`, the common language. ASM keeps its own labels (title, icon, work area, usage) under `x-preset-labels` in `apm.yml`; there is no second preset format. The aim is that ASM exports each preset from APM into the formats apps such as Paperclip and CC Switch read, and imports their formats back into APM.

Paper Kit owns the instructions and scripts that set up and maintain Paperclip companies. It consumes the CAO and AI Resources role presets from ASM. Personal Kit owns the instructions and scripts for managing a personal machine through CC Switch. It consumes the machine's private Personal Kit preset from ASM. ASM owns the preset data, its APM extensions, and the conversions both kits use.

## What each app supports

| Component | Paperclip | Claude Code | Codex | CC Switch (Claude Code · Codex) |
| --- | --- | --- | --- | --- |
| Instruction | [AGENTS.md](https://github.com/paperclipai/paperclip/blob/master/docs/companies/companies-spec.md) | [CLAUDE.md](https://code.claude.com/docs/en/memory) | [AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md) | [Prompts: CLAUDE.md · AGENTS.md](https://github.com/farion1231/cc-switch#supported-features-by-tool) |
| Skill | [Skills](https://github.com/paperclipai/paperclip/blob/master/docs/guides/agent-developer/skills-store.md) | [Skills](https://code.claude.com/docs/en/skills) | [Skills](https://learn.chatgpt.com/docs/build-skills) | [Skills · Skills](https://github.com/farion1231/cc-switch#supported-features-by-tool) |
| MCP | [Not documented](https://github.com/paperclipai/paperclip/blob/master/docs/companies/companies-spec.md) | [MCP servers](https://code.claude.com/docs/en/mcp) | [MCP servers](https://learn.chatgpt.com/docs/extend/mcp) | [MCP · MCP](https://github.com/farion1231/cc-switch#supported-features-by-tool) |
| Hook | [Not documented](https://github.com/paperclipai/paperclip/blob/master/docs/companies/companies-spec.md) | [Hooks](https://code.claude.com/docs/en/hooks) | [Hooks](https://learn.chatgpt.com/docs/hooks) | [Not managed](https://github.com/farion1231/cc-switch) |
| Claude Code plugin | [Not documented](https://github.com/paperclipai/paperclip/blob/master/docs/companies/companies-spec.md) | [Plugins](https://code.claude.com/docs/en/plugins) | [Not documented](https://developers.openai.com/codex/plugins/build/) | [Not managed](https://github.com/farion1231/cc-switch) |
| Codex plugin | [Not documented](https://github.com/paperclipai/paperclip/blob/master/docs/companies/companies-spec.md) | [Not documented](https://code.claude.com/docs/en/plugins) | [Plugins](https://developers.openai.com/codex/plugins/build/) | [Not managed](https://github.com/farion1231/cc-switch) |

Each cell is the app's own term, linked to the page that says so; "Not documented" means that page says nothing on it. The table is [`catalog/consumers.json`](catalog/consumers.json), and the dashboard's Export tab shows it for each preset with its counts. What an app does not take, or an export leaves out, stays in the APM package, so the same preset serves the next app.

## Export

Saving a preset or stack writes its `apm.yml` in `packages/` and converts every preset for Paperclip, rewriting only the files in `exports/paperclip/<id>/` whose content changed; `git status` shows both, and you commit them with Git. Every component is accounted for: exported, left out as expected (with the reason), or needs attention. Import a folder by hand as [docs/paperclip.md](docs/paperclip.md) describes.

```sh
python -m asm_app export          # rewrite exports/paperclip/ and list what each preset leaves out
python -m asm_app export --check  # write nothing; fail if exports/paperclip/ is out of date
```

The Export tab previews what each exporter can produce from the saved preset and explains unavailable targets and omitted items. A mixed preset can offer both a Paperclip package and a CC Switch review. Paperclip reports per-app inventory states it cannot carry.

For a private preset with an [app inventory](docs/api-contract.md#app-inventory), the dashboard shows each installed component and lets you include or exclude it for Codex and Claude Code separately. Download the CC Switch review from the Export tab, or run `python -m asm_app --root <private-root> cc-switch <preset-id>`. The review identifies eligible import links, skill repository registrations, unassigned APM components, and items that need a different route. ASM saves the preset and does not apply it to any app.

Direct export to Claude Code or Codex and reverse conversion are planned.

## Presets in this repo

- **CAO** ([package](packages/cao), [export](exports/paperclip/cao)): takes the human's request and delegates it.
- **AI Resources** ([package](packages/ar), [export](exports/paperclip/ar)): researches, builds and hires roles as presets in ASM.
- **Web app engineer** ([package](packages/web-app-engineer), [export](exports/paperclip/web-app-engineer)): builds and reviews web apps.

Each package lists its members, and the dashboard's Export tab counts them. CAO also holds a Stop hook that echoes one line and Anthropic's `session-report` plugin, a report of Claude Code session and subagent usage. Web app engineer holds a SessionStart hook that reminds the agent to check the project's build and test commands, and Anthropic's `frontend-design` plugin. The Paperclip export lists these hooks and plugins as left out.

## What ASM is not

- Not connected to any app: it reads nothing from one, imports nothing into one, and does not know whether an import succeeded.
- Not an agent runner: no button starts an agent or research.
- Not a version pin: a component from a repository follows its branch, never a commit, so an app that tracks the branch gets its updates.
- Not a workaround: it does not make an app take what the app's docs do not support.
- Not hosted: the dashboard runs on your machine, on loopback.

## Run

Python 3.11 or newer. ASM installs into a virtual environment in the clone. On Debian or Ubuntu, install `python3-venv` first.

```sh
git clone https://github.com/kwonzweig/agent-stack-manager
cd agent-stack-manager
python3 -m venv .venv      # Windows: py -m venv .venv
. .venv/bin/activate       # Windows: .venv\Scripts\activate
python -m pip install -e .
python -m asm_app serve
```

Every `python` command in this README runs in the clone with `.venv` active; activate it again in a new terminal. The install also gives the command `agent-stack-manager`, the same as `python -m asm_app`; both act on the folder they run in, and `--root <clone>` names another. If PowerShell says running scripts is disabled, use Command Prompt.

Open [127.0.0.1:4319](http://127.0.0.1:4319) in Chrome. If another program has that port, `serve` stops with `Address already in use` (`WinError 10048` on Windows); pick another port with `python -m asm_app serve --port 4320`. The dashboard edits the files in your clone: browse the Catalog, with each component's description, GitHub stars and skills.sh installs read from its source when the page opens, add components to a stack or preset, edit a preset, and read its Export tab. Adding from the Catalog saves at once and rewrites the exports; edits on a preset's own page stay in the page until you press **Save changes** at its top. To save from a script instead, use the local API on the dashboard's address, described in [docs/api-contract.md](docs/api-contract.md): `GET /api/presets/cao` returns the preset with its `revision`, and `PATCH /api/presets/cao` with `Content-Type: application/json` and the body `{"revision": "<that revision>", "description": "New text"}` changes only the description.

## APM lock

The optional APM CLI resolves a package's dependencies into `apm.lock.yaml` without deploying anything into an app's folders. The lockfile records the commit each branch [resolved to](https://github.com/microsoft/apm/blob/main/docs/src/content/docs/reference/lockfile-spec.md) when it ran; the presets and the Paperclip exports keep naming branches. Git ignores the lockfile, and it does not change a preset's revision or its export.

```sh
python -m pip install -e ".[apm]"
python -m asm_app lock ar   # --update resolves again from upstream
```

A preset with a marketplace plugin, such as CAO or Web app engineer, needs that marketplace registered in APM first, or `lock` stops with `Marketplace '…' is not registered`. Their plugins come from Anthropic's: `apm marketplace add anthropics/claude-plugins-official --name claude-plugins-official --branch main` ([`apm marketplace`](https://github.com/microsoft/apm/blob/main/docs/src/content/docs/reference/cli/marketplace.md)). A large preset takes APM minutes to resolve; `lock` waits up to ten.

## Development

```sh
python -m unittest discover -s tests
python -m asm_app export --check
```

The built dashboard is committed in `asm_app/web/`, so running it needs no Node.js. To change the dashboard, rebuild it with Node.js 22.12 or newer and commit it with the source:

```sh
cd frontend
npm ci
npm test
npm run build
```

Get Node.js from [nodejs.org/download](https://nodejs.org/en/download); a Linux distribution's own package may be older. The data files and the local API are in [docs/api-contract.md](docs/api-contract.md); the dashboard's design rules are in [instructions/design-policy.md](instructions/design-policy.md); reused frontend code and its licences are in [frontend/IMPLEMENTATION.md](frontend/IMPLEMENTATION.md).

## Contributing

Open an [issue](https://github.com/kwonzweig/agent-stack-manager/issues) before changing behaviour. A pull request passes the commands in [Development](#development). The [Check workflow](.github/workflows/check.yml) runs them on every push and pull request, and fails when `asm_app/web/` is not the build of `frontend/`.

## Licence

[MIT](LICENSE). The frontend code reused from other projects keeps its own licences, listed in [frontend/IMPLEMENTATION.md](frontend/IMPLEMENTATION.md).
