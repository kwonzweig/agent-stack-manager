# Agent Stack Manager interface references

## Screens inspected

| Reference screen | Visible layout and controls | Published image |
| --- | --- | --- |
| AITMPL catalog | Dark shell. A fixed left rail lists component types with icons and counts. The main area puts search, category, filters, grid/list and sort above a result count and a three-column grid. Each card leads with a colored type glyph, then a name and two-line description. Category and popularity sit below the description. A separate right rail shows Jobs. | [Catalog screenshot](https://raw.githubusercontent.com/davila7/claude-code-templates/8c9a4a2c4a12a3010a0d26eddd3c40e7cef16af1/docs/images/readme/aitmpl-catalog-dark.png) |
| CC Switch main interface | A pale navigation rail and a single top bar frame a dense list. The selected provider has a blue outline and tinted row with an “In use” marker. All other rows use a light border. Names and source links align on the left. Controls at the right align consistently, with activate, pencil and overflow glyphs. A clear page-level add control occupies the top right. | [Main interface](https://raw.githubusercontent.com/farion1231/cc-switch/v4.0.31/assets/release-notes/v4.0.0/main-en.png) |
| Skills Manager Library | The sidebar gives a named preset and New Preset their own group. Search and the All/Enabled/Available filter sit above source and tag chips. The card footer separates provenance and deployment from the name and description. | [Library screenshot](https://raw.githubusercontent.com/xingkongliang/skills-manager/v1.44.0/assets/demo/library.png) |
| Skills Manager Codex workspace | A dedicated Presets row sits below Tags. Each preset is a named chip with a glyph. Complete membership shows a check, partial shows a fraction and available choices show a neutral outline. The grid below carries skill names, tags and per-skill status. | [Agent workspace screenshot](https://raw.githubusercontent.com/xingkongliang/skills-manager/v1.44.0/assets/demo/agent-workspace.png) |

All four image files were visually inspected and their SHA-256 hashes matched the cited upstream assets. The CC Switch screenshot depicts providers. The Skills Manager screenshots depict library and deployment surfaces. Their preset edit controls were checked in the released source.

## Behavior inspected in source

- AITMPL has separate grid and list layouts. Each card allows inspecting the component and has an independent add/remove control. The card's plus changes to a checked state as the shared selection changes. The catalog also has a bulk action for the visible page. [ComponentGrid.tsx](https://github.com/davila7/claude-code-templates/blob/8c9a4a2c4a12a3010a0d26eddd3c40e7cef16af1/dashboard/src/components/ComponentGrid.tsx#L559-L795)
- AITMPL's counted Stack launcher appears at the bottom right after items are picked. The drawer opens from the right with close and clear controls, then groups the removable items by component type. Its footer holds the install command and actions for sharing or saving the stack. The component page has its own selection control, a copyable install command and a GitHub source link. [CartSidebar.tsx](https://github.com/davila7/claude-code-templates/blob/8c9a4a2c4a12a3010a0d26eddd3c40e7cef16af1/dashboard/src/components/CartSidebar.tsx#L194-L421) · [Component page](https://github.com/davila7/claude-code-templates/blob/8c9a4a2c4a12a3010a0d26eddd3c40e7cef16af1/dashboard/src/pages/component/%5Btype%5D/%5B...slug%5D.astro#L445-L536) · [AddToStackButton.tsx](https://github.com/davila7/claude-code-templates/blob/8c9a4a2c4a12a3010a0d26eddd3c40e7cef16af1/dashboard/src/components/AddToStackButton.tsx#L29-L66)
- CC Switch's ProfileSwitcher has a searchable, named picker with a check on the current profile. It offers create from current and a separate manage view. The management dialog presents compact named rows with pencil and trash actions. A pencil turns the selected row into an inline input with check and cross controls. [ProfileSwitcher.tsx](https://github.com/farion1231/cc-switch/blob/v4.0.31/src/components/profiles/ProfileSwitcher.tsx#L103-L251) · [ProfileManageDialog.tsx](https://github.com/farion1231/cc-switch/blob/v4.0.31/src/components/profiles/ProfileManageDialog.tsx#L85-L199)
- Skills Manager's sidebar opens the selected preset and exposes a create control nearby. Create and edit use labeled Name and Description fields and an icon picker. The workspace PresetBar derives complete and partial membership from its skills and uses those states to drive the check or fraction visible in the screenshot. [Sidebar.tsx](https://github.com/xingkongliang/skills-manager/blob/v1.44.0/src/components/Sidebar.tsx#L446-L555) · [CreatePresetDialog.tsx](https://github.com/xingkongliang/skills-manager/blob/v1.44.0/src/components/CreatePresetDialog.tsx#L39-L111) · [RenamePresetDialog.tsx](https://github.com/xingkongliang/skills-manager/blob/v1.44.0/src/components/RenamePresetDialog.tsx#L73-L146) · [PresetBar.tsx](https://github.com/xingkongliang/skills-manager/blob/v1.44.0/src/components/PresetBar.tsx#L125-L184)

## Layout for ASM

Use one quiet dark desktop shell for both tasks. The rail links to Catalog and Presets, with named presets listed below when the sidebar has room. Use AITMPL's type-led browse structure within Catalog and CC Switch's compact selected row and trailing icon actions inside Presets. Make the Catalog selection directly visible at desktop widths where a third column fits. Its placement and grouping come from AITMPL's Stack drawer. At narrower widths the selection count opens an end drawer, as in the reference.

```text
Catalog             Components   Stacks   Presets
                    [Search catalog…      ] [Category ▾] [Grid | List]
Agent Stack         ┌─────────────┬──────────────┐ ┌──────────────────┐
Manager             │ ◇ Skill   + │ ⧉ Stack    ✓ │ │ Selection       1│
                    │ Name        │ Name         │ │ Stacks           │
  Catalog           │ Description │ Description  │ │   Name          ×│
  Presets           ├─────────────┼──────────────┤ │                  │
                    │ ◇ Skill   + │ ◇ Skill    + │ │ [Create preset]  │
                    └─────────────┴──────────────┘ └──────────────────┘

Presets        [Search presets…]   + │ Preset name                [check]
              ┌───────────────────┐ │ Details   Source files   Paperclip
              │ ▣ Selected preset │ │ Name          [                  ]
              │ ▣ Another preset  │ │ Description   [                  ]
              └───────────────────┘ │ Instruction   [                  ]
                                    │ Stacks         ───────────────────
                                    │   Name                          ×
```

### Catalog

- Put Components, Stacks and Presets under the page title. Keep the search, meaningful filter and view switch in a single toolbar at desktop widths. Show the matching count beside the results. The grid lets users scan names and descriptions. The list gives source or category its own cell when users need that information side by side.
- Give each card a type glyph, a readable name and up to two lines of author-provided description. The name opens details and source. Separate the plus/check button so it works from the keyboard and stays visible on touch. Place a source link or category on its own line when relevant. Put a real GitHub link beside a pinned file path in details.
- Use the same selection across Catalog tabs, grouped by type. Explicitly identify the APM dependency before it enters a preset. A component backed by a whole-repo dependency can open that repo or containing stack before staging it. Where the current model supports a component-level dependency, show the selected subpath in the detail. Preserve provenance when several discovery paths resolve to one package.
- Place an explicit Create preset action in the selection footer. When browsing from an existing preset editor, use the named destination in the returned state. Browsing a preset opens its details. If duplication is supported, it is a distinct action from adding an item to a selection.

### Presets

- Use a compact searchable list of named presets with explicit selected styling, a page-level create action and aligned row-end actions. Keep project names and descriptions as real data. The editor owns the preset name, description, role Instruction and selected stack membership. List selected stacks at the same visual level, with source refs available from their detail.
- Keep manifest and instruction files in Source files, with paths in a compact list and readable plain-text previews. Show the files from the selected preset and use specific download names. Treat this view as the way to inspect the actual APM inputs.
- Put conversion and import in the Paperclip section of the active preset. Show results with columns for component or stack, result and actionable reason. Label exported and imported results distinctly and pair status words with a glyph. Give any other consumer its own simple availability entry only when the existing implementation exposes it.

### Visual and responsive details

Use Geist for the application and Geist Mono for paths and source previews. Suggested dark tokens are canvas `#101215`, panels `#171A1F`, borders `#30363E`, primary text `#ECEFF3`, secondary text `#A8B1BD` and selection accent `#7EB6FF`. Use readable semantic colors for imported, warning and failure states. Component type glyphs may differ by color and shape. Keep 34–40 px controls, a 6–8 px radius, 14–16 px card gaps and 132–148 px catalog cards. Reserve grid cards for discovery and use row dividers for management.

At about 1200 px, show a roughly 200 px navigation rail and a 300 px selection panel when space permits. Give central cards a minimum width around 240 px and allow the grid to fit two or three columns. Below that, use a selection drawer and let filters wrap. At phone widths, use one column, switch between named presets through a picker or navigation sheet, and keep the selection launcher within easy reach. Icon buttons need accessible names, hover or focus tooltips and visible focus. Close any drawer with Escape and return focus to its opener.

The desktop selection rail and shared dark theme are ASM design choices. The reference screenshots provide navigation and control patterns. Catalog and editor density should give most of the viewport to real catalog entries and preset data.
