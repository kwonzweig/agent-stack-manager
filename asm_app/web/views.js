import { KINDS, escape as e, icon, iconButton, glyph, search, errorMessage, sourceLink, searchMatch } from './ui.js';

const catalogTypes = [['component', 'Components'], ['stack', 'Stacks'], ['preset', 'Presets']];
const editorTabs = [['contents', 'Contents'], ['files', 'Source files'], ['paperclip', 'Paperclip']];
const routes = [
  ['catalog', 'Catalog', 'catalog'],
  ['presets', 'Presets', 'preset'],
  ['consumers', 'Consumers', 'consumers'],
];

export const itemName = item => item.title || item.name;
export const itemKind = item => item.type === 'stack' || item.type === 'preset' ? item.type : item.kind === 'package' && item.configuration?.packageId ? 'stack' : item.kind;
export const membershipId = item => item.type === 'stack' ? 'package:' + item.packageId : item.id;
export const packagePath = id => '/api/presets/' + encodeURIComponent(id);

function segmented(items, active, action, label) {
  return '<div class="segments" role="group" aria-label="' + label + '">' +
    items.map(([id, title]) => `<button type="button" data-action="${action}" data-value="${id}"
      aria-pressed="${active === id}">${title}</button>`).join('') + '</div>';
}

export function navigation(state) {
  return `
    <a href="/" class="brand" data-action="navigate" data-value="catalog">
      <span class="brand-mark">${icon('layers', 21)}</span><span>Agent Stack<br class="brand-break"> Manager</span>
    </a>
    <nav aria-label="Main">
      ${routes.map(([id, title, glyphName]) => `<a href="#${id}" data-action="navigate"
        data-value="${id}" ${state.route === id ? 'aria-current="page"' : ''}>${icon(glyphName)}<span>${title}</span></a>`).join('')}
    </nav>
  `;
}

function count(number) {
  return `<span class="count">${number}</span>`;
}

export function catalogView(state) {
  const kinds = [...new Set((state.catalog?.items || []).filter(item => item.type === 'component').map(item => item.kind))]
    .sort((left, right) => (KINDS[left] || left).localeCompare(KINDS[right] || right));
  return `
    <header class="page-header">
      <h1>Catalog</h1>
      <button type="button" class="button selection-toggle" data-action="show-selection">${icon('layers')} Selection
        <span id="selection-count">${count(state.selection.size)}</span></button>
    </header>
    ${errorMessage(state.catalogError)}
    ${state.catalogError ? '<button type="button" class="button" data-action="retry-catalog">Retry catalog</button>' : ''}
    <div class="catalog-layout">
      <section class="catalog-main" aria-label="Catalog results">
        <div class="catalog-tools">
          ${segmented(catalogTypes, state.catalogType, 'catalog-type', 'Catalog type')}
          <div class="filter-row">
            ${search('catalog-search', 'Search catalog…', state.catalogSearch)}
            ${state.catalogType === 'component' ? `<label class="kind-filter">
              <span class="sr-only">Component kind</span>
              <select id="catalog-kind">
                <option value="">All kinds</option>
                ${kinds.map(kind => `<option value="${e(kind)}" ${kind === state.catalogKind ? 'selected' : ''}>${e(KINDS[kind] || kind)}</option>`).join('')}
              </select></label>` : ''}
            <div class="segments view-toggle" role="group" aria-label="Catalog view">
              ${iconButton('grid', 'Grid view', 'catalog-view', { value: 'grid', pressed: state.catalogView === 'grid' })}
              ${iconButton('list', 'List view', 'catalog-view', { value: 'list', pressed: state.catalogView === 'list' })}
            </div>
          </div>
        </div>
        <div id="catalog-results">${catalogResults(state)}</div>
      </section>
      <aside id="selection-panel" class="selection-panel" aria-label="Selection">${selectionPanel(state)}</aside>
    </div>
    ${state.catalog?.sources?.length ? `<details class="catalog-sources"><summary>Catalog sources</summary>
      <ul>${state.catalog.sources.map(source => `<li>${sourceLink(source.url, source.name) || e(source.name)}</li>`).join('')}</ul>
    </details>` : ''}
  `;
}

function catalogCard(item, state) {
  const name = itemName(item);
  const kind = itemKind(item);
  const isPreset = item.type === 'preset';
  const selectionId = membershipId(item);
  const added = state.selection.has(selectionId);
  const current = !isPreset && state.existingMembers?.has(selectionId);
  const opensPackage = Boolean(item.packageId);
  return `<article class="catalog-card${added ? ' is-selected' : ''}">
    ${glyph(kind)}
    <div class="card-content">
      <h2><button type="button" class="item-name" data-action="${opensPackage ? 'open-package' : 'component-detail'}"
        data-value="${e(opensPackage ? item.packageId : item.id)}">${e(name)}</button></h2>
      ${item.description ? `<p class="card-description">${e(item.description)}</p>` : ''}
      <div class="card-meta">
        <span class="type-label">${e(KINDS[kind] || kind)}</span>
        ${item.componentCount != null ? `<span class="meta" title="Components">${e(item.componentCount)} components</span>` : ''}
      </div>
    </div>
    ${isPreset ? iconButton('arrow', 'Open ' + name, 'open-package', { value: item.packageId }) :
      current ? `<span class="included" title="In preset"><span class="sr-only">In preset</span>${icon('check')}</span>` :
      iconButton(added ? 'check' : 'plus', added ? 'Remove ' + name + ' from selection' : 'Add ' + name + ' to selection',
        'select-component', { value: selectionId, pressed: added, className: 'pick-button' })}
  </article>`;
}

export function catalogResults(state) {
  const items = (state.catalog?.items || []).filter(item => item.type === state.catalogType && (item.type !== 'stack' || item.packageId !== state.editTarget) &&
    (!state.catalogKind || state.catalogType !== 'component' || item.kind === state.catalogKind) &&
    searchMatch(state.catalogSearch, itemName(item), item.description, KINDS[itemKind(item)], item.workArea, item.usage, item.source?.path));
  const heading = catalogTypes.find(([id]) => id === state.catalogType)[1].toLowerCase();
  if (!state.catalog && !state.catalogError) return '<p class="empty">Loading catalog…</p>';
  if (!state.catalog) return '';
  return `<div class="result-heading"><p class="meta" role="status">${items.length} ${items.length === 1 ? heading.slice(0, -1) : heading}</p></div>
    ${items.length ? `<div class="catalog-results ${state.catalogView === 'list' ? 'as-list' : 'as-grid'}">
      ${items.map(item => catalogCard(item, state)).join('')}</div>` : '<p class="empty">No matching items.</p>'}`;
}

export function selectionPanel(state, inDialog = false) {
  const { selection, targetTitle } = state;
  const options = [['component', 'Components'], ['stack', 'Stacks']];
  return `
    <header class="panel-header">
      <h2 ${inDialog ? 'id="sheet-title"' : ''}>Selection ${count(selection.size)}</h2>
      ${inDialog ? iconButton('close', 'Close selection', 'close-sheet') : ''}
    </header>
    <div class="selection-body">
      ${selection.size ? options.map(([type, label]) => {
        const items = [...selection.entries()].filter(([, item]) => item.type === type);
        if (!items.length) return '';
        return `<section aria-label="${label}" class="selection-group"><h3>${label}</h3><ul>
          ${items.map(([id, item]) => `<li>${glyph(itemKind(item))}<span>${e(itemName(item))}</span>
            ${iconButton('close', 'Remove ' + itemName(item), 'select-component', { value: id, className: 'remove-button' })}</li>`).join('')}
          </ul></section>`;
      }).join('') : '<p class="empty">No items selected.</p>'}
    </div>
    ${selection.size || targetTitle ? `<footer class="selection-footer">
      ${targetTitle ? `<button type="button" class="button primary" data-action="apply-selection"${selection.size ? '' : ' disabled'}>
        Add to ${e(targetTitle)}</button><button type="button" class="button" data-action="return-to-editor">Back to editor</button>`
        : `<button type="button" class="button primary" data-action="create-from-selection" data-value="preset">Create preset</button>
          <button type="button" class="button" data-action="create-from-selection" data-value="stack">Create stack</button>`}
    </footer>` : ''}
  `;
}

function presetListRow(item, state) {
  const active = state.activeId === item.id;
  return `<button class="preset-row" type="button" data-action="open-package" data-value="${e(item.id)}"
      ${active ? 'aria-current="true"' : ''}>
    ${glyph(item.kind)}
    <span class="preset-row-label"><strong>${e(item.title)}</strong>${item.description ? `<small>${e(item.description)}</small>` : ''}</span>
    ${state.dirtyIds.has(item.id) ? '<span class="unsaved-dot" title="Unsaved changes"><span class="sr-only">Unsaved changes</span></span>' : ''}
    ${icon(active ? 'check' : 'arrow', 15)}
  </button>`;
}

export function presetList(state) {
  const items = [...state.openCreations, ...(state.packages || [])].filter(item =>
    searchMatch(state.presetSearch, item.title, item.description, KINDS[item.kind]));
  if (!state.packages && !state.presetsError && !items.length) return '<p class="empty">Loading presets…</p>';
  if (!items.length) return '<p class="empty">No matching presets.</p>';
  return ['preset', 'stack'].map(kind => {
    const rows = items.filter(item => item.kind === kind);
    return rows.length ? `<section class="preset-group" aria-label="${kind === 'preset' ? 'Presets' : 'Stacks'}">
      <h3>${kind === 'preset' ? 'Presets' : 'Stacks'}</h3>${rows.map(item => presetListRow(item, state)).join('')}
    </section>` : '';
  }).join('');
}

export function presetsView(state) {
  const draft = state.activeDraft;
  return `<header class="page-header">
    <h1>Presets</h1>
    ${iconButton('plus', 'New preset', 'new-preset', { className: 'primary' })}
  </header>
  ${errorMessage(state.presetsError)}
  ${state.presetsError ? '<button type="button" class="button" data-action="retry-presets">Retry presets</button>' : ''}
  <div class="preset-layout">
    <aside class="preset-list" aria-label="Saved presets">
      <div class="preset-search">${search('preset-search', 'Search presets…', state.presetSearch)}</div>
      <div id="preset-results">${presetList(state)}</div>
    </aside>
    <section class="editor" aria-label="Preset editor">
      ${state.packageError ? `${errorMessage(state.packageError)}
        <button type="button" class="button" data-action="retry-package">Retry opening package</button>` : ''}
      ${draft ? editor(draft, state) : state.activeId && !state.packageError ? '<p class="empty">Loading package…</p>' :
        state.packageError ? '' : '<p class="empty">No preset selected.</p>'}
    </section>
  </div>`;
}

function editor(draft, state) {
  const title = draft.original?.title || (draft.fields.kind === 'stack' ? 'New stack' : 'New preset');
  const selection = state.editorTab;
  return `<header class="editor-header">
      <div class="editor-heading">${glyph(draft.fields.kind)}<h2>${e(title)}</h2></div>
      <div class="editor-actions">
        <span id="save-status" class="meta" role="status">${draft.saving ? 'Saving…' : draft.dirty ? 'Unsaved changes' : ''}</span>
        ${iconButton('check', 'Save ' + draft.fields.kind, 'save-package',
          { className: 'primary', disabled: draft.saving || (!draft.dirty && Boolean(draft.original)) })}
      </div>
    </header>
    ${errorMessage(draft.error)}
    ${draft.conflict ? '<button type="button" class="button conflict-action" data-action="review-latest">Review saved version</button>' : ''}
    ${state.downloadError ? errorMessage(state.downloadError) : ''}
    ${draft.original ? `<div class="editor-tabs">${segmented(editorTabs, selection, 'editor-tab', 'Preset sections')}</div>` : ''}
    ${selection === 'files' && draft.original ? files(draft, state) :
      selection === 'paperclip' && draft.original ? paperclip(draft, state) : details(draft)}
  `;
}

function memberRow(item, draft) {
  const name = itemName(item);
  const kind = itemKind(item);
  return `<li class="member-row">
    ${glyph(kind)}
    <div class="member-label">
      <button type="button" class="item-name" data-action="member-detail" data-value="${e(item.id)}">${e(name)}</button>
      <span class="meta">${e(KINDS[kind] || kind)}</span>
    </div>
    <div class="row-actions">
      ${draft.original?.components.some(component => component.id === item.id) ?
        iconButton('comment', 'Comments on ' + name, 'open-comments', { value: item.id }) : ''}
      ${iconButton('close', 'Remove ' + name, 'remove-member', { value: item.id, className: 'remove-button' })}
    </div>
  </li>`;
}

function details(draft) {
  const { fields, members } = draft;
  return `<form id="preset-form" class="editor-body">
    <div class="field-grid">
      <label class="field field-wide">Name<input name="title" value="${e(fields.title)}" required></label>
      <label class="field field-wide">Description<textarea name="description" rows="2">${e(fields.description)}</textarea></label>
      <label class="field">Work areas<textarea name="workArea" rows="2" aria-label="Work areas, one per line">${e(fields.workArea)}</textarea></label>
      <label class="field">Usage<textarea name="usage" rows="2" aria-label="Usage, one per line">${e(fields.usage)}</textarea></label>
      <div class="field field-wide">
        <div class="section-heading"><label for="instruction">Instruction</label>
          ${draft.original?.components.some(component => component.id === 'instruction') ?
            iconButton('comment', 'Comments on Instruction', 'open-comments', { value: 'instruction' }) : ''}
        </div>
        <textarea id="instruction" class="instruction-input" name="instruction" rows="7">${e(fields.instruction)}</textarea>
      </div>
    </div>
    <section class="membership" aria-label="Components and stacks">
      <header class="section-heading"><h3>Components and stacks ${count(members.length)}</h3>
        ${iconButton('plus', 'Add components or stacks', 'browse-additions')}</header>
      ${members.length ? `<ul class="member-list">${members.map(item => memberRow(item, draft)).join('')}</ul>` :
        '<p class="empty">No components or stacks.</p>'}
    </section>
  </form>`;
}

function files(draft, state) {
  const items = draft.original.files || [];
  const active = items.find(file => file.path === state.activeFile) || items[0];
  return `<section class="editor-body">
    ${draft.dirty ? '<p class="meta status-note">Showing the saved revision.</p>' : ''}
    <div class="section-heading"><h3>Source files</h3>
      <button class="button" type="button" data-action="download-native">${icon('download')} Download APM package</button>
    </div>
    ${items.length ? `<div class="files">
      <ul class="file-list">${items.map(file => `<li><button type="button" data-action="view-file" data-value="${e(file.path)}"
        ${active === file ? 'aria-current="true"' : ''}>${icon('instruction', 15)}<span>${e(file.path)}</span></button></li>`).join('')}</ul>
      <pre class="file-content" tabindex="0" aria-label="${e(active.path)}"><code>${e(active.content)}</code></pre>
    </div>` : '<p class="empty">No source files.</p>'}
  </section>`;
}

const statusStyles = {
  converted: ['Converted', 'positive', 'check'],
  unconverted: ['Unconverted', 'caution', 'warning'],
  saved: ['Saved', 'positive', 'check'],
  missing: ['Missing', 'caution', 'warning'],
  not_checked: ['Not checked', 'neutral', 'status'],
};

function reportStatus(value) {
  const [label, tone, statusIcon] = statusStyles[value.status] || statusStyles.not_checked;
  return `<span class="result-status ${tone}">${icon(statusIcon, 14)} ${label}</span>
    ${value.reason ? `<small class="result-reason">${e(value.reason)}</small>` : ''}`;
}

function paperclip(draft, state) {
  const { report, error, running } = state.activeReport || {};
  return `<section class="editor-body report">
    ${draft.dirty ? '<p class="meta status-note">Showing the saved revision.</p>' : ''}
    <div class="section-heading paperclip-heading"><h3>Paperclip</h3>
      <div class="toolbar">
        <button class="button" type="button" data-action="refresh-conversion"${running ? ' disabled' : ''}>${icon('refresh')} Convert</button>
        <button class="button" type="button" data-action="observe-paperclip"${running ? ' disabled' : ''}>${icon('refresh')} Refresh import status</button>
        <button class="button" type="button" data-action="download-paperclip"${!report || running || !report.summary.converted ? ' disabled' : ''}>${icon('download')} Download Paperclip package</button>
      </div>
    </div>
    ${errorMessage(error)}
    ${running ? `<p class="meta" role="status">${running === 'observe' ? 'Checking saved Paperclip state…' : 'Converting package…'}</p>` : ''}
    ${report ? `<dl class="report-totals">
      <div><dt>Converted</dt><dd>${e(report.summary.converted)}</dd></div>
      <div><dt>Unconverted</dt><dd>${e(report.summary.unconverted)}</dd></div>
      <div><dt>Saved</dt><dd>${e(report.summary.imported)}</dd></div>
    </dl>
    <div class="report-table"><table>
      <thead><tr><th scope="col">Component</th><th scope="col">Conversion</th><th scope="col">Paperclip import</th></tr></thead>
      <tbody>${report.items.map(item => `<tr>
        <th scope="row"><span class="report-component">${glyph(item.kind)}<span>${e(item.name)}</span></span></th>
        <td>${reportStatus(item.conversion)}</td><td>${reportStatus(item.import)}</td>
      </tr>`).join('')}</tbody>
    </table></div>` : !running && !error ? '<p class="empty">No conversion report.</p>' : ''}
  </section>`;
}

export function consumersView(state) {
  return `<header class="page-header"><h1>Consumers</h1></header>
    ${errorMessage(state.consumersError)}
    ${state.consumersError ? '<button type="button" class="button" data-action="retry-consumers">Retry consumers</button>' : ''}
    ${state.consumers ? `<ul class="consumer-list">${state.consumers.map(consumer => `
      <li class="consumer-row">
        ${glyph(consumer.id === 'paperclip' ? 'paperclip' : 'consumers')}
        <div><h2>${e(consumer.name)}</h2><span class="meta">${consumer.supported ? 'Conversion and import status' : 'Not implemented'}</span></div>
        ${consumer.supported ? `<button type="button" class="button" data-action="consumer-paperclip">Open preset reports ${icon('arrow', 15)}</button>` : ''}
      </li>`).join('')}</ul>` : state.consumersError ? '' : '<p class="empty">Loading consumers…</p>'}
  `;
}

export function componentDetails(item, action = '') {
  const name = itemName(item);
  const kind = itemKind(item);
  const source = item.source || {};
  return `<header class="panel-header"><h2 id="sheet-title">${glyph(kind)} ${e(name)}</h2>
      ${iconButton('close', 'Close details', 'close-sheet')}</header>
    <div class="sheet-body">
      ${item.description ? `<p>${e(item.description)}</p>` : ''}
      <dl class="source-fields">
        <div><dt>Kind</dt><dd>${e(KINDS[kind] || kind)}</dd></div>
        ${source.repositoryUrl || item.sourceUrl ? `<div><dt>Source</dt><dd>${sourceLink(item.sourceUrl || source.repositoryUrl, source.repositoryUrl || 'View source')}</dd></div>` : ''}
        ${source.path ? `<div><dt>Path</dt><dd><code>${e(source.path)}</code></dd></div>` : ''}
        ${source.ref ? `<div><dt>Ref</dt><dd><code>${e(source.ref)}</code></dd></div>` : ''}
      </dl>
    </div>${action ? `<footer class="selection-footer">${action}</footer>` : ''}`;
}

export function commentsView(item) {
  return `<header class="panel-header"><div><h2 id="sheet-title">Comments</h2><span class="meta">${e(itemName(item))}</span></div>
    ${iconButton('close', 'Close comments', 'close-sheet')}</header>
    <div class="sheet-body comments-body">
      <div id="comment-results"><p class="empty">Loading comments…</p></div>
      <form id="comment-form" class="comment-form">
        <label class="field">Author<input name="author" autocomplete="name" required maxlength="100"></label>
        <label class="field">Comment<textarea name="body" rows="4" required maxlength="5000"></textarea></label>
        <div id="comment-error"></div>
        <button class="button primary" type="submit">${icon('send')} Add comment</button>
      </form>
    </div>`;
}

export function commentResults(comments) {
  return comments.length ? `<ul class="comments">${comments.map(comment => {
    const createdAt = comment.createdAt || comment.created_at;
    return `<li><div class="comment-top"><strong>${e(comment.author)}</strong>
      ${createdAt ? `<time datetime="${e(createdAt)}">${e(createdAt.replace('T', ' ').replace(/Z$/, ' UTC'))}</time>` : ''}
      </div><p>${e(comment.body)}</p></li>`;
  }).join('')}</ul>` : '<p class="empty">No comments yet.</p>';
}

export function conflictView(result) {
  return `<header class="panel-header"><h2 id="sheet-title">Saved version</h2>
    ${iconButton('close', 'Close saved version', 'close-sheet')}</header>
    <div class="sheet-body">
      ${result ? `<dl class="source-fields">
        <div><dt>Name</dt><dd>${e(result.title)}</dd></div>
        <div><dt>Description</dt><dd>${e(result.description)}</dd></div>
        <div><dt>Work areas</dt><dd>${e(result.workArea.join(', '))}</dd></div>
        <div><dt>Usage</dt><dd>${e(result.usage.join(', '))}</dd></div>
        <div><dt>Instruction</dt><dd><pre>${e(result.instruction)}</pre></dd></div>
        <div><dt>Components and stacks</dt><dd>${e(result.components.map(itemName).join(', '))}</dd></div>
      </dl>` : '<p class="empty">Loading saved version…</p>'}
      <div id="conflict-error"></div>
    </div>
    ${result ? `<footer class="selection-footer">
      <button class="button" type="button" data-action="keep-draft">Keep draft</button>
      <button class="button" type="button" data-action="load-saved">Discard draft and load saved version</button>
    </footer>` : ''}
  `;
}
