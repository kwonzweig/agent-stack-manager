const icons = {
  layers: '<path d="m12 2 10 5-10 5L2 7l10-5Z"/><path d="m2 12 10 5 10-5M2 17l10 5 10-5"/>',
  catalog: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  preset: '<path d="M6 4h12a1 1 0 0 1 1 1v15l-7-4-7 4V5a1 1 0 0 1 1-1Z"/><path d="M9 8h6"/>',
  consumers: '<path d="M10 13a4 4 0 0 0 6 .4l3-3a4 4 0 0 0-5.7-5.7l-1.7 1.7m2.4 4.6a4 4 0 0 0-6-.4l-3 3a4 4 0 0 0 5.7 5.7l1.7-1.7"/>',
  search: '<circle cx="11" cy="11" r="6.5"/><path d="m16 16 4 4"/>',
  grid: '<rect x="4" y="4" width="6" height="6" rx="1"/><rect x="14" y="4" width="6" height="6" rx="1"/><rect x="4" y="14" width="6" height="6" rx="1"/><rect x="14" y="14" width="6" height="6" rx="1"/>',
  list: '<path d="M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  close: '<path d="m6 6 12 12M18 6 6 18"/>',
  arrow: '<path d="m10 6 6 6-6 6"/>',
  external: '<path d="M13 5h6v6m0-6-9 9m7-1v5a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V8a1 1 0 0 1 1-1h5"/>',
  skill: '<path d="m12 2 1.9 6.1L20 10l-6.1 1.9L12 18l-1.9-6.1L4 10l6.1-1.9L12 2ZM6 17v5m-2.5-2.5h5m11-4v5m-2.5-2.5h5"/>',
  mcp: '<path d="M9 3v4m6-4v4m-8 0h10v3a5 5 0 0 1-5 5v6m0-6a5 5 0 0 1-5-5V7Z"/>',
  hook: '<path d="M12 3v11m0 0 3-3m-3 3-3-3M5 11v4a7 7 0 0 0 14 0v-4"/>',
  plugin: '<path d="M19 5h-5a2 2 0 1 0-4 0H5v5a2 2 0 1 1 0 4v5h5a2 2 0 1 1 4 0h5v-5a2 2 0 1 0 0-4V5Z"/>',
  instruction: '<path d="M6 3h8l4 4v14H6zM14 3v5h4M9 12h6m-6 4h6"/>',
  package: '<path d="m3 7 9-4 9 4v10l-9 4-9-4V7Zm0 0 9 4 9-4m-9 4v10M7.5 5l9 4"/>',
  comment: '<path d="M20 11.5a7.5 7.5 0 0 1-7.5 7.5H5l1.7-3.1A7.5 7.5 0 1 1 20 11.5Z"/><path d="M9 11h6"/>',
  download: '<path d="M12 3v12m-5-5 5 5 5-5M5 16v4h14v-4"/>',
  refresh: '<path d="M20 11a8 8 0 0 0-13.6-5.6L4 8m0-5v5h5m-5 5a8 8 0 0 0 13.6 5.6l2.4-2.6m0 5v-5h-5"/>',
  status: '<circle cx="12" cy="12" r="7"/>',
  warning: '<path d="M12 5v7m0 4h.01"/><circle cx="12" cy="12" r="9"/>',
  paperclip: '<path d="m9 14 6.5-6.5a2 2 0 1 1 2.8 2.8l-8 8a4 4 0 1 1-5.7-5.7l8.5-8.5"/>',
  send: '<path d="m4 4 16 8-16 8 3-8-3-8Zm3 8h13"/>',
};

export const KINDS = {
  skill: 'Skill', mcp: 'MCP', hook: 'Hook', plugin: 'Plugin',
  instruction: 'Instruction', package: 'Package', other: 'Other',
  preset: 'Preset', stack: 'Stack',
};

export const escape = (value = '') => String(value ?? '')
  .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
  .replaceAll('"', '&quot;').replaceAll("'", '&#39;');

export const icon = (name, size = 18) => `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name] || icons.instruction}</svg>`;

export function iconButton(name, label, action, options = {}) {
  const { value, pressed, className, disabled } = options;
  return `<button type="button" class="icon-button ${className || ''}" data-action="${action}" ${value == null ? '' : `data-value="${escape(value)}"`} aria-label="${escape(label)}" title="${escape(label)}"${pressed == null ? '' : ` aria-pressed="${pressed}"`}${disabled ? ' disabled' : ''}>${icon(name)}</button>`;
}

export function glyph(kind) {
  return `<span class="item-glyph type-${escape(kind)}">${icon(kind === 'stack' ? 'layers' : kind)}</span>`;
}

export function search(id, placeholder, value) {
  return `<label class="search" for="${id}">${icon('search')}<span class="sr-only">${escape(placeholder)}</span>
    <input id="${id}" type="search" placeholder="${escape(placeholder)}" value="${escape(value)}" autocomplete="off">
  </label>`;
}

export function errorMessage(error) {
  return error ? `<p class="error-message" role="alert">${icon('warning')}${escape(error)}</p>` : '';
}

export function sourceLink(url, label) {
  if (typeof url !== 'string' || !/^https?:\/\/[^/]/i.test(url)) return '';
  return `<a class="external-link" href="${escape(url)}" target="_blank" rel="noreferrer">${escape(label)}${icon('external', 13)}</a>`;
}

export function searchMatch(query, ...values) {
  const words = query.trim().toLowerCase().split(/\s+/);
  const searchable = values.flat().filter(Boolean).join(' ').toLowerCase();
  return words.every(word => searchable.includes(word));
}
