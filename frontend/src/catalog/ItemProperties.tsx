import { Download, FolderGit2, Star } from 'lucide-react';
import type { Kind, PackageKind, Source, SourceCopies } from '../types';
import { KindBadge } from '../components/ComponentUI';
import { countLabel, installsTitle, repositoryLabel, starsTitle } from './catalogItem';

// --color-surface-2 is the Catalog's own; the detail page outside it falls back to the app's hover surface.
const repositoryClass = 'relative z-[1] inline-flex min-w-0 max-w-full items-center gap-1 rounded px-1.5 py-0.5 font-mono text-[11px] text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-2,var(--color-surface-hover))] hover:text-[var(--color-accent)]';
const countClass = 'inline-flex shrink-0 items-center gap-1 font-mono text-[11px] tabular-nums text-[var(--color-text-secondary)]';

// A Catalog item's properties under its title. The card and the detail page both render this,
// so the detail page shows everything the card does (instructions/design-policy.md).
export default function ItemProperties({ item, repository }: {
  item: SourceCopies & { kind: Kind | PackageKind; source?: Source | null; componentCount?: number };
  /** A function filters the Catalog to the repository; "link" opens it; unset hides it where a group heading names it. */
  repository?: 'link' | ((url: string) => void);
}) {
  const url = item.source?.repositoryUrl || '';
  const label = repositoryLabel(url);
  const repositoryBody = <>
    <FolderGit2 className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
    <span className="truncate">{label}</span>
  </>;
  return <>
    <KindBadge kind={item.kind} />
    {item.componentCount !== undefined && <span className={countClass}>
      {item.componentCount + (item.componentCount === 1 ? ' component' : ' components')}
    </span>}
    {url && repository === 'link' && /^https?:\/\//i.test(url) && (
      <a href={url} target="_blank" rel="noreferrer" className={repositoryClass} title={'Open ' + label}>{repositoryBody}</a>
    )}
    {url && typeof repository === 'function' && (
      <button type="button" onClick={() => repository(url)} className={repositoryClass} title={'Show everything from ' + label}>
        {repositoryBody}
      </button>
    )}
    {item.stars !== undefined && <span className={countClass} title={starsTitle(item)} aria-label={starsTitle(item)}>
      <Star className="h-3.5 w-3.5" aria-hidden="true" />{countLabel(item.stars)}
    </span>}
    {item.installs !== undefined && <span className={countClass} title={installsTitle(item)} aria-label={installsTitle(item)}>
      <Download className="h-3.5 w-3.5" aria-hidden="true" />{countLabel(item.installs)}
    </span>}
  </>;
}
