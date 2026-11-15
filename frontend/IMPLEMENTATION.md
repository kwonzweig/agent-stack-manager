# Frontend reuse plan

The existing local server owns packages, catalog sources, and Paperclip conversion. The browser bundle is the only runtime change.

1. Port Skills Manager’s theme, sidebar, workspace cards, dialogs, picker and detail sheet. The app shell loads the existing catalog API and named presets independently; use hash routes so the existing server can serve them.
2. Keep a draft per preset. Save against its original revision. On conflict, fetch the saved version and keep unaffected changes from both sides when explicitly rebasing the draft. Test with external membership changes and overlapping metadata. Keep Instruction and comments in the detail sheet.
3. Port the Lab’s component details, file toolbar and conversion report. Use the current report routes and statuses. Both native and Paperclip ZIP downloads must use the original API endpoints.
4. Integrate the Catalog component, build to the server’s existing flat static directory, and run the frontend and Python tests. Check wheel contents and exercise the served UI separately.

## Reused source files

[Skills Manager 1.44.0](https://github.com/xingkongliang/skills-manager/tree/v1.44.0) (MIT, see [license](public/Skills-Manager.LICENSE.txt)):

| Original source | ASM source | Adaptation |
|---|---|---|
| src/index.css, tailwind.config.js, postcss.config.js | src/index.css, tailwind.config.js, postcss.config.js | Same light/dark tokens, type stack, controls, panels and geometry. Add a keyboard focus outline. |
| src/components/Layout.tsx and src/components/Sidebar.tsx | src/App.tsx and src/components/Sidebar.tsx | Keep the 220 px sidebar, scroll region, navigation and icon/count rows. Use the ASM routes and package summaries; collapse navigation on narrow screens. |
| src/views/WorkspaceView.tsx | src/components/Workspace.tsx | Take the workspace header, count, search, tags, segmented controls and card body. Components replace installed skills; saved files and Paperclip use existing ASM APIs. |
| src/components/CreatePresetDialog.tsx and RenamePresetDialog.tsx | src/components/PresetDialog.tsx | Keep the dialog width, inputs and action styles. The creation dialog handles name, description and package type; metadata edit adds supported work area and usage. ASM has no stored icon field; the original inference rules select the icon. |
| src/components/AddSkillsSheet.tsx and SkillPickerRow.tsx | src/components/ComponentPicker.tsx | Preserve the picker header/search, row checkbox, included-state indicator and footer. Add to a preset draft rather than to a host. |
| src/components/DetailSheet.tsx | src/components/DetailSheet.tsx | Port the workspace overlay, scroll area, heading and close action. Drop the Tauri drag bar and support narrow browser viewports. |
| src/components/CardActionMenu.tsx, src/components/SkillMarkdown.tsx | same paths | Copy the action menu and Markdown renderer. |
| src/lib/presetIcons.tsx, src/lib/skillTags.ts, src/utils.ts | same paths | Copy icon maps and inference, tag palette and utility classes. Change the preset icon helper's input type from the Tauri type to an equivalent local shape. |

Agent Presets Lab (2026-11-14), dist/app.js and dist/app.css:

| Original JSX-equivalent template / CSS region | ASM source | Adaptation |
|---|---|---|
| contentsRows, .contents-* and row controls | src/components/Workspace.tsx, src/components/lab.css | Port the content list with a component name, type, source and detail affordance. Add selection to the existing row pattern, alongside the Skills Manager grid. |
| renderSource, .source-panel, .file-toolbar and .source-code | src/components/SourceFiles.tsx, src/components/lab.css | Port the file picker, copy control, and source code view. The file endpoint gives text previews; download original file bytes in the APM ZIP. |
| renderReport, reportRow, kindSummary, reportDetail, .summary-table, .report-* and .stage-* | src/components/PaperclipReport.tsx, src/components/lab.css | Port the grouped conversion summary, All/Needs attention filter, result rows and source/target inspector. Bind only conversion and import statuses returned by ASM. |
| contentsDetail, valuePanel, commentsSection and renderComment | src/components/ComponentDetails.tsx, src/components/lab.css | Port source links, collapsible data panels and component comments inside the Skills Manager detail sheet. Use the copied Markdown reader for the primary Instruction. |

The Lab rules are scoped to these views and use the Skills Manager theme variables. Lucide icons replace the Lab's character glyphs.

The catalog has its own [AITMPL source inventory](src/catalog/UPSTREAM.md).


