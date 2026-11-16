# Importing an export into Paperclip

`exports/paperclip/<id>/` holds one preset as a Paperclip [company package](https://github.com/paperclipai/paperclip/blob/master/docs/companies/companies-spec.md) with one agent. ASM never contacts Paperclip: a person or an agent imports the folder by hand, as below. The calls are those of Paperclip [2026.1106.0](https://github.com/paperclipai/paperclip/releases/tag/v2026.1106.0); what no page states is marked as observed on that release.

| File | Holds |
| --- | --- |
| `COMPANY.md` | The package's slug, name and description. |
| `agents/<id>/AGENTS.md` | The agent's name, title, role and skill names; the body is the preset's Instruction. |
| `.paperclip.yaml` | Role, `canCreateAgents`, heartbeat off, and `metadata.agentStackManagerPackageId` and `agentStackManagerRevision`. No adapter. |
| `skills/<key>/SKILL.md` | One stub per skill: repository, path and branch, no commit. |

## Import a preset

Only the board and CEO agents may import a company package ([companies.ts](https://github.com/paperclipai/paperclip/blob/v2026.1106.0/server/src/routes/companies.ts#L364-L378)).

1. **Create a skill source for each repository and branch the stubs name.** An import creates no source (observed on 2026.1106.0), and Paperclip refuses a remote skill that is not pinned to a commit ([company skill policy](https://github.com/paperclipai/paperclip/blob/master/doc/company-skill-policy.md)), so the stubs only say which sources to create. Call `POST /api/companies/{companyId}/skill-sources/discover` with `repositoryUrl` and `trackingRef` (the branch), then `POST /api/companies/{companyId}/skill-sources` with the `commitSha` it returned and `selectedPaths` set to `<path>/SKILL.md`, or `SKILL.md` when the path is `.`. Reuse a source that exists. A source re-checks its branch every five minutes unless its automatic updates are paused ([PRODUCT.md](https://github.com/paperclipai/paperclip/blob/v2026.1106.0/doc/PRODUCT.md#L157-L162)). Paperclip names each skill `github/<repositoryId>/<hash>/<slug>`, where the slug is the skill's folder name, or the repository name for a skill at the root (observed on 2026.1106.0).
2. **Import the agent without `skills/`.** Send `COMPANY.md`, `agents/<id>/AGENTS.md` and `.paperclip.yaml` as inline files, with `include` set to agents only and `target` to the existing company. The stubs would make the import fail with a 422 (observed on 2026.1106.0). The board uses `POST /api/companies/import`. A CEO agent uses `POST /api/companies/{companyId}/imports/apply` and passes `adapterOverrides` for the agent's slug: the export has no adapter, and this route refuses the `process` adapter Paperclip [falls back to](https://github.com/paperclipai/paperclip/blob/v2026.1106.0/server/src/services/company-portability.ts#L3270) ([company-portability.ts](https://github.com/paperclipai/paperclip/blob/v2026.1106.0/server/src/services/company-portability.ts#L3678-L3680)).
3. **Check the skills.** The skill names in `AGENTS.md` become the agent's desired skills and resolve by slug to the skills of step 1 (observed on 2026.1106.0). A skill whose source was created later is attached with `POST /api/agents/{agentId}/skills/sync`, `{"mode": "add", "desiredSkills": [...]}`.
4. **Set the adapter**, and in it any MCP server the preset has.

An agent without import rights hires instead: the sources of step 1, then `POST /api/companies/{companyId}/agent-hires` with the package's name, title, role, metadata, skills and an adapter, `PUT /api/agents/{agentId}/instructions-bundle/file` with the `AGENTS.md` body, and step 3. It needs `canCreateAgents`. The AI Resources preset's Instruction follows this path.

## Apply a preset update

When `agentStackManagerRevision` in the new export differs from the agent's metadata, update the agent in place. A second import that replaces the agent sets its adapter from the package and clears its reporting line, since the export names no manager ([company-portability.ts](https://github.com/paperclipai/paperclip/blob/v2026.1106.0/server/src/services/company-portability.ts#L5680-L5682), [update](https://github.com/paperclipai/paperclip/blob/v2026.1106.0/server/src/services/company-portability.ts#L5700-L5704)), and the CEO route refuses `replace` ([companies.ts](https://github.com/paperclipai/paperclip/blob/v2026.1106.0/server/src/routes/companies.ts#L1166-L1168)).

1. `PUT /api/agents/{agentId}/instructions-bundle/file` with the new `AGENTS.md` body.
2. Sources for any new repository or branch, as in step 1 above.
3. `POST /api/agents/{agentId}/skills/sync` in `add` mode for new skills and `remove` mode for dropped ones.
4. `PATCH /api/agents/{agentId}` with the new `metadata.agentStackManagerRevision`.

## What the export leaves out

`python -m asm_app export` and the dashboard's Export tab list every component the export does not carry, with the reason. They stay in the APM package.

- **MCP servers**: the company package has no MCP entry. Set them in the agent's adapter after import.
- **Hooks and plugins**: the company package has no entry for them.
- **A further APM instruction**: Paperclip takes one Instruction per agent; merge it into the preset's Instruction.
- **Skill files Paperclip rejects**: its [skills store guide](https://github.com/paperclipai/paperclip/blob/master/docs/guides/agent-developer/skills-store.md) lists what an import omits.
