import assert from 'node:assert/strict';
import test from 'node:test';
import { inventoryComponents } from '../src/draft.ts';
import { componentLocations, componentSearchText, observationAppName, displayDescription } from '../src/lib/componentLocation.ts';

const setting = (id, locator, scope = 'project (app)') => ({
  id, name: 'settings.local.json', kind: 'setting',
  description: 'Claude Code configuration file. Field types and choices are recorded for review.',
  apps: { claude: { installed: true, enabled: null, selected: null, scope, locator } },
});

test('same-named settings retain their full distinguishing source in preset and catalog projections', () => {
  const rows = [setting('one', '~/Desktop/projects/app/.claude/settings.local.json'),
    setting('two', '~/Desktop/archive/app/.claude/settings.local.json')];
  const projected = inventoryComponents(rows);
  assert.deepEqual(projected.map(row => componentLocations(row)[0].location), [
    '~/Desktop/projects/app/.claude/settings.local.json', '~/Desktop/archive/app/.claude/settings.local.json',
  ]);
  const catalog = { ...projected[1], origins: projected[1].origins, memberships: [{ apps: rows[1].apps }] };
  assert.equal(componentLocations(catalog).length, 1);
  assert.ok(componentSearchText(catalog).includes('desktop/archive/app'));
  assert.ok(componentSearchText(projected[0]).includes('project (app)'));
  assert.deepEqual(rows.map(row => row.apps.claude.selected), [null, null]);
});

test('Desktop observations and legacy setting descriptions cannot claim Claude Code ownership', () => {
  const row = setting('desktop', '~/AppData/Roaming/Claude/claude_desktop_config.json', 'Desktop');
  const projected = inventoryComponents([row])[0];
  assert.equal(componentLocations(projected)[0].owner, 'Claude Desktop');
  assert.equal(observationAppName('claude', row.apps.claude), 'Claude Desktop');
  assert.equal(displayDescription(projected), undefined);
  assert.equal(observationAppName('claude', { scope: 'user' }), 'Claude Code');
  assert.equal(observationAppName('claude', { scope: 'project (app)', locator: '~/app/claude_desktop_config.json' }), 'Claude Code');
  assert.equal(observationAppName('claude', { scope: 'Desktop (unavailable)' }), 'Claude Desktop');
});

test('legacy provenance and local source fallbacks stay searchable without guessing an owner', () => {
  const legacy = { kind: 'setting', name: 'settings.json', memberships: [{ apps: {
    claude: { installed: true, enabled: null, selected: false, provenance: { location: '~/.claude/settings.json' } },
  } }] };
  assert.equal(componentLocations(legacy)[0].location, '~/.claude/settings.json');
  assert.ok(componentSearchText(legacy).includes('~/.claude/settings.json'));
  assert.deepEqual(componentLocations({ kind: 'setting', source: { path: '~/project/.claude/settings.local.json' } }),
    [{ location: '~/project/.claude/settings.local.json' }]);
  assert.deepEqual(componentLocations({ kind: 'setting' }), []);
});

test('same-named local instructions retain native locations without replacing remote attribution', () => {
  const rows = [setting('one', '~/Desktop/projects/app/CLAUDE.md'), setting('two', '~/Desktop/archive/app/CLAUDE.md')]
    .map(row => ({ ...row, kind: 'instruction', name: 'CLAUDE.md', description: 'Authored instruction purpose.',
      source: 'https://github.com/example/instructions', sourcePath: 'CLAUDE.md' }));
  const projected = inventoryComponents(rows);
  assert.deepEqual(projected.map(row => componentLocations(row)[0].location), [
    '~/Desktop/projects/app/CLAUDE.md', '~/Desktop/archive/app/CLAUDE.md',
  ]);
  assert.equal(projected[0].source.repositoryUrl, 'https://github.com/example/instructions');
  assert.equal(displayDescription(projected[0]), 'Authored instruction purpose.');
  assert.ok(componentSearchText(projected[1]).includes('desktop/archive/app/claude.md'));
  assert.deepEqual(componentLocations({ kind: 'skill', source: { repositoryUrl: 'https://github.com/example/skills', path: 'SKILL.md' } }), []);
});
