import { errorMessage, iconButton } from './ui.js';
import { navigation, catalogView, catalogResults, selectionPanel, presetsView, presetList,
  consumersView, componentDetails, commentsView, commentResults, conflictView,
  itemName, membershipId, packagePath } from './views.js';

const main = document.querySelector('#main');
const nav = document.querySelector('#navigation');
const sheet = document.querySelector('#sheet');
const notice = document.querySelector('#notice');
const drafts = new Map();
const reports = new Map();
const packageRequests = new Set();
const commentDrafts = new Map();
const state = {
  route: 'catalog',
  catalogType: 'component',
  catalogKind: '',
  catalogView: 'grid',
  catalogSearch: '',
  presetSearch: '',
  editorTab: 'contents',
  activeId: '',
  catalogSelection: new Map(),
  editorSelection: new Map(),
};
let openSheet;
let noticeTimer;

async function request(path, options = {}) {
  const response = await fetch(path, {
    method: options.method || 'GET',
    cache: 'no-store',
    ...(options.body === undefined ? {} : {
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(options.body),
    }),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const error = new Error(data.error || 'Request failed (' + response.status + ').');
    error.status = response.status;
    throw error;
  }
  return options.blob ? response.blob() : response.json();
}

const currentDraft = () => drafts.get(state.activeId);
const activeSelection = () => state.editTarget ? state.editorSelection : state.catalogSelection;
const catalogItem = id => state.catalog?.items.find(item => item.type !== 'preset' && membershipId(item) === id);
const visibleStates = { catalog: catalogView, presets: presetsView, consumers: consumersView };

function viewState() {
  const activeDraft = currentDraft();
  const target = drafts.get(state.editTarget);
  return {
    ...state,
    activeDraft,
    activeReport: reports.get(state.activeId),
    selection: activeSelection(),
    targetTitle: target && (target.fields.title.trim() || 'new ' + target.fields.kind),
    existingMembers: target && new Set(target.members.map(member => member.id)),
    dirtyIds: new Set([...drafts].filter(([, draft]) => draft.dirty).map(([id]) => id)),
    openCreations: [...drafts].filter(([, draft]) => !draft.original).map(([id, draft]) => ({
      id, kind: draft.fields.kind, title: draft.fields.title || 'New ' + draft.fields.kind,
    })),
  };
}

function captureFocus() {
  const element = document.activeElement;
  if (!main.contains(element) && !nav.contains(element)) return null;
  return {
    id: element.id, name: element.name, action: element.dataset?.action, value: element.dataset?.value,
    start: element.selectionStart, end: element.selectionEnd,
  };
}

function restoreFocus(focus, container = document) {
  if (!focus || sheet.open) return;
  const element = focus.id ? document.getElementById(focus.id) :
    focus.name ? container.querySelector('[name="' + CSS.escape(focus.name) + '"]') :
    focus.action ? [...container.querySelectorAll('[data-action]')].find(button =>
      button.dataset.action === focus.action && button.dataset.value === focus.value) : null;
  if (!element) return;
  element.focus({ preventScroll: true });
  if (focus.start != null) element.setSelectionRange(focus.start, focus.end);
}

function render() {
  const focus = captureFocus();
  const model = viewState();
  nav.innerHTML = navigation(model);
  main.innerHTML = visibleStates[state.route](model);
  restoreFocus(focus);
}

function paintResults() {
  const focus = captureFocus();
  const model = viewState();
  document.querySelector('#catalog-results').innerHTML = catalogResults(model);
  document.querySelector('#selection-panel').innerHTML = selectionPanel(model);
  document.querySelector('#selection-count .count').textContent = model.selection.size;
  if (openSheet?.type === 'selection') {
    sheet.innerHTML = selectionPanel(model, true);
    sheet.querySelector('[data-action="close-sheet"]').focus();
  } else if (openSheet?.type === 'component' && openSheet.catalog) {
    paintComponentDetails(openSheet.item, true);
  } else {
    restoreFocus(focus);
  }
}

function announce(message) {
  clearTimeout(noticeTimer);
  notice.textContent = message;
  noticeTimer = setTimeout(() => { notice.textContent = ''; }, 3800);
}

const loads = {
  catalog: ['/api/catalog', 'catalog', null],
  presets: ['/api/presets', 'packages', 'presets'],
  consumers: ['/api/consumers', 'consumers', 'consumers'],
};
const loadTickets = new Map();

async function loadList(which) {
  const [path, key, field] = loads[which];
  const errorKey = which + 'Error';
  const token = Symbol(which);
  loadTickets.set(which, token);
  state[errorKey] = '';
  if (state.route === which) render();
  try {
    const data = await request(path);
    if (loadTickets.get(which) !== token) return;
    state[key] = field ? data[field] : data;
  } catch (error) {
    if (loadTickets.get(which) !== token) return;
    state[errorKey] = 'Could not load ' + which + '. ' + error.message;
  }
  if (state.route !== which) return;
  if (which === 'presets' && !state.activeId && preferredPreset()) {
    openPackage(preferredPreset().id, state.editorTab, { replace: true });
  } else {
    render();
  }
}

function preferredPreset() {
  return state.packages?.find(item => item.kind === 'preset') || state.packages?.[0];
}

function setLocation(route, id, replace = false) {
  const hash = '#' + route + (id ? '/' + encodeURIComponent(id) : '');
  if (location.hash === hash) return;
  history[replace ? 'replaceState' : 'pushState'](null, '', hash);
}

function navigate(route, { sync = true } = {}) {
  const switched = state.route !== route;
  state.route = route;
  if (route === 'presets') {
    const id = state.activeId || preferredPreset()?.id;
    if (id) {
      openPackage(id, state.editorTab, { sync });
      return;
    }
  }
  if (sync) setLocation(route);
  render();
  if (switched) {
    window.scrollTo(0, 0);
    main.focus({ preventScroll: true });
  }
}

function readLocation() {
  const [route, encoded] = location.hash.slice(1).split('/');
  if (route === 'main') return;
  if (route === 'presets' && encoded) {
    try {
      const id = decodeURIComponent(encoded);
      if (!id.startsWith(':') || drafts.has(id)) {
        openPackage(id, 'contents', { sync: false });
        return;
      }
    } catch {
      // Invalid percent encoding falls back to the preset list.
    }
  }
  navigate(Object.hasOwn(visibleStates, route) ? route : 'catalog', { sync: false });
}

function makeDraft(kind, original = null) {
  const fields = {
    kind,
    title: original?.title || '',
    description: original?.description || '',
    workArea: original?.workArea.join('\n') || '',
    usage: original?.usage.join('\n') || '',
    instruction: original?.instruction || '',
  };
  const draft = { original, fields, members: (original?.components || []).filter(item => item.id !== 'instruction') };
  draft.baseline = draftSnapshot(draft);
  draft.dirty = !original;
  return draft;
}

function draftSnapshot(draft) {
  return JSON.stringify([draft.fields, draft.members.map(item => item.id)]);
}

function updateDirty(draft) {
  draft.dirty = !draft.original || draft.baseline !== draftSnapshot(draft);
  const status = document.querySelector('#save-status');
  if (status) status.textContent = draft.saving ? 'Saving…' : draft.dirty ? 'Unsaved changes' : '';
  const button = document.querySelector('[data-action="save-package"]');
  if (button) button.disabled = draft.saving || !draft.dirty;
}

async function openPackage(id, tab = 'contents', { sync = true, replace = false } = {}) {
  const switched = state.route !== 'presets' || state.activeId !== id;
  state.route = 'presets';
  if (switched) {
    state.activeId = id;
    state.activeFile = '';
    state.downloadError = '';
  }
  state.editorTab = tab;
  state.packageError = '';
  if (sync) setLocation('presets', id, replace);
  render();
  if (switched) {
    window.scrollTo(0, 0);
    main.focus({ preventScroll: true });
  }
  if (!drafts.has(id) && !packageRequests.has(id)) {
    packageRequests.add(id);
    try {
      const data = await request(packagePath(id));
      if (!drafts.has(id)) drafts.set(id, makeDraft(data.kind, data));
    } catch (error) {
      if (state.activeId === id) state.packageError = 'Could not open package. ' + error.message;
    } finally {
      packageRequests.delete(id);
      if (state.route === 'presets' && state.activeId === id) render();
    }
  }
  if (state.route === 'presets' && state.activeId === id && state.editorTab === 'paperclip' &&
      drafts.get(id)?.original && !reports.has(id)) {
    void loadReport(id);
  }
}

function memberFromItem(id, item) {
  return item.type === 'stack' ? { ...item, id } : item;
}

function addSelected(draft, selection) {
  const membership = new Set(draft.members.map(member => member.id));
  for (const [id, item] of selection) {
    if (!membership.has(id)) draft.members.push(memberFromItem(id, item));
  }
}

function createDraft(kind, withSelection) {
  const id = ':new-' + kind;
  const draft = drafts.get(id) || makeDraft(kind);
  drafts.set(id, draft);
  if (withSelection) {
    addSelected(draft, state.catalogSelection);
    state.catalogSelection.clear();
  }
  closeDialog();
  void openPackage(id);
  document.querySelector('#preset-form [name="title"]')?.focus();
}

function browseAdditions() {
  const id = state.activeId;
  if (state.editTarget && state.editTarget !== id && state.editorSelection.size) {
    announce('Finish the selection for ' + (drafts.get(state.editTarget)?.fields.title || 'the open draft') + ' first.');
    return;
  }
  state.editTarget = id;
  state.catalogType = 'component';
  state.catalogKind = '';
  state.catalogSearch = '';
  navigate('catalog');
  document.querySelector('#catalog-search')?.focus();
}

function returnToEditor(apply) {
  const id = state.editTarget;
  const draft = drafts.get(id);
  if (!draft) return;
  if (apply) {
    addSelected(draft, state.editorSelection);
    draft.dirty = true;
    state.editorSelection.clear();
    state.editTarget = '';
  } else if (!state.editorSelection.size) {
    state.editTarget = '';
  }
  closeDialog();
  void openPackage(id);
}

function selectComponent(id) {
  const item = catalogItem(id);
  if (!item || (state.editTarget && id === 'package:' + state.editTarget)) return;
  const selection = activeSelection();
  if (selection.has(id)) {
    selection.delete(id);
  } else {
    selection.set(id, item);
  }
  paintResults();
}

async function savePackage() {
  const draft = currentDraft();
  if (!draft || draft.saving) return;
  const form = document.querySelector('#preset-form');
  if (form && !form.reportValidity()) return;
  if (!draft.fields.title.trim()) {
    draft.error = 'Enter a name.';
    state.editorTab = 'contents';
    render();
    document.querySelector('#preset-form [name="title"]').focus();
    return;
  }
  const id = state.activeId;
  const snapshot = draftSnapshot(draft);
  const splitLines = value => value.split('\n').map(entry => entry.trim()).filter(Boolean);
  const payload = {
    ...draft.fields,
    title: draft.fields.title.trim(),
    workArea: splitLines(draft.fields.workArea),
    usage: splitLines(draft.fields.usage),
    componentIds: draft.members.map(item => item.id),
  };
  if (draft.original) payload.revision = draft.original.revision;
  draft.saving = true;
  draft.error = '';
  draft.conflict = false;
  render();
  try {
    const data = await request(draft.original ? packagePath(id) : '/api/presets', {
      method: draft.original ? 'PATCH' : 'POST', body: payload,
    });
    const saved = makeDraft(data.kind, data);
    if (draftSnapshot(draft) !== snapshot) {
      saved.fields = draft.fields;
      saved.members = draft.members.map(member =>
        data.components.find(item => item.id === member.id) || member);
      saved.dirty = saved.baseline !== draftSnapshot(saved);
    }
    if (state.editTarget === id) state.editTarget = data.id;
    drafts.delete(id);
    drafts.set(data.id, saved);
    reports.delete(id);
    if (state.activeId === id) {
      state.activeId = data.id;
      if (state.route === 'presets') setLocation('presets', data.id, true);
    }
    announce('Saved ' + data.title + '.');
    void loadList('presets');
    void loadList('catalog');
    if (state.route === 'presets' && state.activeId === data.id && state.editorTab === 'paperclip') {
      void loadReport(data.id);
    }
  } catch (error) {
    draft.error = 'Could not save changes. ' + error.message;
    draft.conflict = error.status === 409 && Boolean(draft.original);
  } finally {
    draft.saving = false;
    if (state.route === 'presets') render();
  }
}

async function loadReport(id, observe = false) {
  if (reports.get(id)?.running) return;
  const pending = { ...reports.get(id), running: observe ? 'observe' : 'convert', error: '' };
  reports.set(id, pending);
  const isActive = () => state.route === 'presets' && state.activeId === id && state.editorTab === 'paperclip';
  if (isActive()) render();
  try {
    pending.report = await request(packagePath(id) + '/paperclip' + (observe ? '/observe' : ''),
      observe ? { method: 'POST', body: {} } : {});
  } catch (error) {
    pending.error = (observe ? 'Could not refresh import status. ' : 'Could not convert package. ') + error.message;
  } finally {
    pending.running = '';
    if (reports.get(id) === pending && isActive()) render();
  }
}

async function downloadPackage(paperclip) {
  const id = state.activeId;
  const suffix = paperclip ? '/paperclip/export' : '/export';
  const fileName = paperclip ? id + '-paperclip.zip' : id + '-apm.zip';
  state.downloadError = '';
  try {
    const blob = await request(packagePath(id) + suffix, { blob: true });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = fileName;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 5000);
    announce('Downloaded ' + fileName + '.');
  } catch (error) {
    if (state.route === 'presets' && state.activeId === id) {
      state.downloadError = 'Could not download ' + fileName + '. ' + error.message;
      render();
    }
  }
}

function showDialog(context, content) {
  openSheet = context;
  sheet.innerHTML = content;
  if (!sheet.open) sheet.showModal();
  sheet.querySelector('[data-action="close-sheet"]')?.focus();
}

function closeDialog() {
  if (sheet.open) sheet.close();
  openSheet = null;
}

function paintComponentDetails(item, catalog) {
  const id = membershipId(item);
  const included = catalog && (viewState().existingMembers?.has(id) || id === 'package:' + state.editTarget);
  const selected = catalog && activeSelection().has(id);
  const label = (selected ? 'Remove from selection' : 'Add to selection');
  const action = catalog && !included ? iconButton(selected ? 'check' : 'plus', label, 'select-component',
    { value: id, pressed: selected, className: 'primary' }) : '';
  const content = componentDetails(item, action);
  if (openSheet?.type === 'component' && openSheet.item === item) {
    sheet.innerHTML = content;
    sheet.querySelector('[data-action="select-component"]')?.focus();
  } else {
    showDialog({ type: 'component', item, catalog }, content);
  }
}

function commentKey(context) {
  return JSON.stringify([context.presetId, context.componentId]);
}

function commentsParams(context) {
  return new URLSearchParams({ presetId: context.presetId, componentId: context.componentId });
}

async function loadComments(context) {
  const token = Symbol('comments');
  context.loadToken = token;
  try {
    const { comments } = await request('/api/comments?' + commentsParams(context));
    if (openSheet === context && context.loadToken === token) {
      sheet.querySelector('#comment-results').innerHTML = commentResults(comments);
    }
  } catch (error) {
    if (openSheet === context && context.loadToken === token) {
      sheet.querySelector('#comment-results').innerHTML = errorMessage('Could not load comments. ' + error.message) +
        '<button type="button" class="button" data-action="retry-comments">Retry comments</button>';
    }
  }
}

function openComments(id) {
  const item = currentDraft()?.original?.components.find(member => member.id === id);
  if (!item) return;
  const context = { type: 'comments', presetId: state.activeId, componentId: id };
  showDialog(context, commentsView(item));
  const saved = commentDrafts.get(commentKey(context));
  const form = sheet.querySelector('#comment-form');
  if (saved) {
    form.elements.author.value = saved.author;
    form.elements.body.value = saved.body;
  }
  void loadComments(context);
}

async function addComment(form, context) {
  const author = form.elements.author.value.trim();
  const body = form.elements.body.value.trim();
  const errorNode = form.querySelector('#comment-error');
  if (context.saving) return;
  if (!author || !body) {
    errorNode.innerHTML = errorMessage('Enter an author and a comment.');
    return;
  }
  context.saving = true;
  errorNode.innerHTML = '';
  form.querySelector('button[type="submit"]').disabled = true;
  try {
    await request('/api/comments', {
      method: 'POST',
      body: { presetId: context.presetId, componentId: context.componentId, author, body },
    });
    const saved = commentDrafts.get(commentKey(context));
    const sameBody = saved?.body.trim() === body;
    if (sameBody) commentDrafts.set(commentKey(context), { ...saved, body: '' });
    if (openSheet === context) {
      if (sameBody) form.elements.body.value = '';
      void loadComments(context);
    }
    announce('Comment added.');
  } catch (error) {
    if (openSheet === context) errorNode.innerHTML = errorMessage('Could not add comment. ' + error.message);
    else announce('Could not add comment. ' + error.message);
  } finally {
    context.saving = false;
    form.querySelector('button[type="submit"]').disabled = false;
  }
}

async function reviewLatest() {
  const context = { type: 'conflict', id: state.activeId };
  showDialog(context, conflictView(null));
  try {
    context.result = await request(packagePath(context.id));
    if (openSheet === context) showDialog(context, conflictView(context.result));
  } catch (error) {
    if (openSheet === context) {
      sheet.querySelector('#conflict-error').innerHTML = errorMessage('Could not load saved version. ' + error.message);
    }
  }
}

function useSavedVersion() {
  const { id, result } = openSheet;
  drafts.set(id, makeDraft(result.kind, result));
  reports.delete(id);
  closeDialog();
  if (state.editorTab === 'paperclip') void loadReport(id);
  render();
}

const actions = {
  navigate: navigate,
  'retry-catalog': () => loadList('catalog'),
  'retry-presets': () => loadList('presets'),
  'retry-consumers': () => loadList('consumers'),
  'retry-package': () => openPackage(state.activeId, state.editorTab),
  'catalog-type': value => { state.catalogType = value; render(); },
  'catalog-view': value => { state.catalogView = value; render(); },
  'show-selection': () => showDialog({ type: 'selection' }, selectionPanel(viewState(), true)),
  'select-component': selectComponent,
  'create-from-selection': kind => createDraft(kind, true),
  'new-preset': () => createDraft('preset', false),
  'open-package': id => openPackage(id),
  'component-detail': id => {
    const item = catalogItem(id);
    if (item) paintComponentDetails(item, true);
  },
  'member-detail': id => {
    const item = currentDraft()?.members.find(member => member.id === id);
    if (item) paintComponentDetails(item, false);
  },
  'browse-additions': browseAdditions,
  'apply-selection': () => returnToEditor(true),
  'return-to-editor': () => returnToEditor(false),
  'remove-member': id => {
    const draft = currentDraft();
    draft.members = draft.members.filter(member => member.id !== id);
    draft.dirty = !draft.original || draft.baseline !== draftSnapshot(draft);
    render();
  },
  'save-package': savePackage,
  'review-latest': reviewLatest,
  'keep-draft': closeDialog,
  'load-saved': useSavedVersion,
  'editor-tab': value => openPackage(state.activeId, value),
  'view-file': path => { state.activeFile = path; render(); },
  'download-native': () => downloadPackage(false),
  'download-paperclip': () => downloadPackage(true),
  'refresh-conversion': () => loadReport(state.activeId),
  'observe-paperclip': () => loadReport(state.activeId, true),
  'consumer-paperclip': () => {
    const id = state.activeId && currentDraft()?.original ? state.activeId : preferredPreset()?.id;
    if (id) void openPackage(id, 'paperclip');
    else navigate('presets');
  },
  'open-comments': openComments,
  'retry-comments': () => loadComments(openSheet),
  'close-sheet': closeDialog,
};

document.addEventListener('click', event => {
  const button = event.target.closest('[data-action]');
  if (!button || button.disabled) return;
  if (button.tagName === 'A' && (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey)) return;
  event.preventDefault();
  actions[button.dataset.action]?.(button.dataset.value);
});

document.addEventListener('input', event => {
  const field = event.target;
  if (field.id === 'catalog-search') {
    state.catalogSearch = field.value;
    document.querySelector('#catalog-results').innerHTML = catalogResults(viewState());
  } else if (field.id === 'preset-search') {
    state.presetSearch = field.value;
    document.querySelector('#preset-results').innerHTML = presetList(viewState());
  } else if (field.form?.id === 'preset-form') {
    const draft = currentDraft();
    draft.fields[field.name] = field.value;
    updateDirty(draft);
    document.querySelector('#preset-results').innerHTML = presetList(viewState());
  } else if (field.form?.id === 'comment-form' && openSheet?.type === 'comments') {
    commentDrafts.set(commentKey(openSheet),
      { author: field.form.elements.author.value, body: field.form.elements.body.value });
  }
});

document.addEventListener('change', event => {
  if (event.target.id === 'catalog-kind') {
    state.catalogKind = event.target.value;
    document.querySelector('#catalog-results').innerHTML = catalogResults(viewState());
  }
});

document.addEventListener('submit', event => {
  if (event.target.id === 'preset-form') {
    event.preventDefault();
    void savePackage();
  } else if (event.target.id === 'comment-form') {
    event.preventDefault();
    void addComment(event.target, openSheet);
  }
});

sheet.addEventListener('cancel', event => {
  event.preventDefault();
  closeDialog();
});
sheet.addEventListener('click', event => {
  if (event.target === sheet) {
    const bounds = sheet.getBoundingClientRect();
    if (event.clientX < bounds.left || event.clientX > bounds.right ||
        event.clientY < bounds.top || event.clientY > bounds.bottom) closeDialog();
  }
});
window.addEventListener('hashchange', () => { closeDialog(); readLocation(); });
window.addEventListener('beforeunload', event => {
  if ([...drafts.values()].some(draft => draft.dirty)
      || [...commentDrafts.values()].some(comment => comment.body.trim())) {
    event.preventDefault();
    event.returnValue = true;
  }
});
readLocation();
void loadList('catalog');
void loadList('presets');
void loadList('consumers');
