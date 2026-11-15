// Copied from AITMPL dashboard/src/components/TypeIcon.tsx (MIT).
import { ICONS } from './icons';

/**
 * Renders a type icon SVG inline.
 * Safe to use dangerouslySetInnerHTML here because ICONS are hardcoded
 * SVG strings defined in icons.ts — not user-supplied data.
 */
export default function TypeIcon({ type, size = 16, className = '' }: { type: string; size?: number; className?: string }) {
  const svg = ICONS[type];
  if (!svg) return <span aria-hidden="true" className={className} />;

  const sized = svg.replace(/width="16"/, `width="${size}"`).replace(/height="16"/, `height="${size}"`);

  return <span aria-hidden="true" className={className} dangerouslySetInnerHTML={{ __html: sized }} />;
}
