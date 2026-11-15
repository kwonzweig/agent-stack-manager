// Grid and list cards from AITMPL dashboard/src/components/ComponentGrid.tsx (MIT).
import type { CatalogItem } from '../types';
import { KIND_STYLES } from '../lib/kinds';
import { KindIcon } from '../components/ComponentUI';
import { itemName } from './catalogItem';

interface Props {
  item: CatalogItem;
  index: number;
  viewMode: 'grid' | 'list';
  inCart: boolean;
  onOpen: (item: CatalogItem) => void;
  onToggle: (item: CatalogItem) => void;
}

export default function ComponentCard({ item, index, viewMode, inCart, onOpen, onToggle }: Props) {
  const config = KIND_STYLES[item.kind];
  const name = itemName(item);
  const isList = viewMode === 'list';
  const actionLabel = inCart ? 'Remove ' + name + ' from stack' : 'Add ' + name + ' to stack';
  const label = item.componentCount === undefined
    ? config.singular
    : item.componentCount + (item.componentCount === 1 ? ' component' : ' components');
  const badge = (
    <span className="font-mono text-[10px] font-semibold px-2 py-0.5 rounded border border-[var(--color-border)] bg-[var(--color-surface-2)] text-[var(--color-text-tertiary)]">
      {label}
    </span>
  );

  return (
    <article
      className={'group relative flex rounded-md bg-[var(--color-card-bg)] border border-[var(--color-border)] hover:bg-[var(--color-card-hover)] hover:border-[var(--color-accent)] transition-all duration-150 cursor-pointer animate-fade-in-up ' +
        (isList ? 'items-center gap-5 p-4' : 'items-start gap-4 p-5')}
      style={{ animationDelay: index * (isList ? 30 : 50) + 'ms', animationFillMode: 'both' }}
    >
      <div
        className={'rounded flex items-center justify-center shrink-0 ' + (isList ? 'w-11 h-11' : 'w-10 h-10')}
        style={{ backgroundColor: config.color + '15', color: config.color, border: '1px solid ' + config.color + '30' }}
      >
        <KindIcon kind={item.kind} className={isList ? 'h-[22px] w-[22px]' : 'h-5 w-5'} />
      </div>

      <div className="min-w-0 flex-1">
        <h3 className={'font-mono text-[14px] font-bold text-[var(--color-text-primary)] group-hover:text-[var(--color-accent)] transition-colors ' +
          (isList ? 'mb-1' : 'leading-tight mb-1.5')}>
          <button type="button" className="text-left break-words after:absolute after:inset-0 after:rounded-md focus-visible:outline-none focus-visible:after:outline focus-visible:after:outline-2 focus-visible:after:outline-[var(--color-primary-500)]" onClick={() => onOpen(item)}>
            {name}
          </button>
        </h3>
        {item.description && (
          <p className={'text-[12px] text-[var(--color-text-secondary)] ' + (isList ? 'line-clamp-1 leading-relaxed' : 'line-clamp-2 leading-[1.6]')}>
            {item.description}
          </p>
        )}
        {!isList && <div className="flex flex-wrap items-center gap-2 mt-3">{badge}</div>}
      </div>

      {isList && <div className="hidden sm:flex items-center gap-2 shrink-0">{badge}</div>}
      {item.type !== 'preset' && (
        <button
          type="button"
          onClick={() => onToggle(item)}
          className={`relative z-[1] w-8 h-8 rounded flex items-center justify-center transition-all duration-150 ${
            inCart
              ? 'bg-[var(--color-accent)] text-white border border-[var(--color-accent)]'
              : 'text-[var(--color-text-tertiary)] opacity-75 group-hover:opacity-100 focus-visible:opacity-100 hover:text-[var(--color-accent)] hover:bg-[var(--color-surface-2)] border border-transparent hover:border-[var(--color-border)]'
          }`}
          title={actionLabel}
          aria-label={actionLabel}
          aria-pressed={inCart}
        >
          {inCart ? (
            <svg aria-hidden="true" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="3">
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
          ) : (
            <svg aria-hidden="true" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
            </svg>
          )}
        </button>
      )}
    </article>
  );
}
