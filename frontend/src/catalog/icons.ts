// SVGs and type colors from AITMPL dashboard/src/lib/icons.ts and CartSidebar.tsx (MIT).
import type { CatalogItem } from '../types';

export const ICONS: Record<string, string> = {
  skills: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>`,
  hooks: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71"/></svg>`,
  mcps: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4 14.899A7 7 0 1115.71 8h1.79a4.5 4.5 0 012.5 8.242"/><path d="M12 12v9"/><path d="M8 17l4 4 4-4"/></svg>`,
  plugins: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z"/></svg>`,
  stack: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"/></svg>`,
  preset: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"/></svg>`,
  instruction: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>`,
};

export const TYPE_CONFIG: Record<CatalogItem['kind'], { icon: string; label: string; singular: string; color: string }> = {
  skill: { icon: 'skills', label: 'Skills', singular: 'Skill', color: '#f59e0b' },
  mcp: { icon: 'mcps', label: 'MCPs', singular: 'MCP', color: '#06b6d4' },
  hook: { icon: 'hooks', label: 'Hooks', singular: 'Hook', color: '#f97316' },
  plugin: { icon: 'plugins', label: 'Plugins', singular: 'Plugin', color: '#ffd93d' },
  instruction: { icon: 'instruction', label: 'Instructions', singular: 'Instruction', color: '#3b82f6' },
  package: { icon: 'stack', label: 'Packages', singular: 'Package', color: '#5e6ad2' },
  other: { icon: 'instruction', label: 'Other components', singular: 'Other', color: '#737373' },
  stack: { icon: 'stack', label: 'Stacks', singular: 'Stack', color: '#d57455' },
  preset: { icon: 'preset', label: 'Presets', singular: 'Preset', color: '#5e6ad2' },
};
