import { useId, useMemo, useRef, useState } from 'react';
import { ChevronDown, ChevronLeft, ChevronRight } from 'lucide-react';
import Checkbox from './Checkbox';
import { repositoryLabel } from './catalogItem';

const REPOSITORIES_PER_PAGE = 6;

interface Props {
  repositories: string[];
  selected: string[];
  onToggle: (repository: string) => void;
  onClear: () => void;
}

export default function RepositoryFilter({ repositories, selected, onToggle, onClear }: Props) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [selectedOnly, setSelectedOnly] = useState(false);
  const optionsId = useId();
  const labelId = useId();
  const summaryId = useId();
  const trigger = useRef<HTMLButtonElement>(null);
  const searchInput = useRef<HTMLInputElement>(null);
  const options = selectedOnly ? selected : repositories;
  const matches = useMemo(() => {
    const query = search.trim().toLowerCase();
    return query ? options.filter((url) => url.toLowerCase().includes(query)) : options;
  }, [options, search]);
  const selection = useMemo(() => new Set(selected), [selected]);
  const totalPages = Math.max(1, Math.ceil(matches.length / REPOSITORIES_PER_PAGE));
  const currentPage = Math.min(page, totalPages);
  const start = (currentPage - 1) * REPOSITORIES_PER_PAGE;
  const visible = matches.slice(start, start + REPOSITORIES_PER_PAGE);
  const summary = selected.length === 1
    ? repositoryLabel(selected[0])
    : selected.length ? selected.length + ' selected' : 'Any repository';

  return (
    <div className="min-w-0 space-y-1.5">
      <span className="block text-xs font-medium text-[var(--color-text-secondary)]" id={labelId}>Source repositories</span>
      <button type="button" ref={trigger} aria-expanded={open} aria-controls={optionsId} aria-labelledby={labelId + ' ' + summaryId}
        onClick={() => setOpen((previous) => !previous)}
        className="catalog-filter-control flex items-center gap-2 text-left">
        <span className="min-w-0 truncate" id={summaryId} title={summary}>{summary}</span>
        <ChevronDown className={'ml-auto h-4 w-4 shrink-0' + (open ? ' rotate-180' : '')} aria-hidden="true" />
      </button>
      <div id={optionsId} hidden={!open}>
        {open && (
          <div className="mt-1 space-y-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-0)] p-2"
            onKeyDown={(event) => {
              if (event.key !== 'Escape') return;
              event.preventDefault();
              setOpen(false);
              trigger.current?.focus();
            }}>
            <div className="flex items-center gap-2">
              <input ref={searchInput} type="search" aria-label="Search repositories" placeholder="Search repositories…" autoFocus
                value={search} onChange={(event) => { setSearch(event.currentTarget.value); setPage(1); }}
                className="catalog-filter-control min-w-0 flex-1" />
              {(selected.length > 0 || selectedOnly) && (
                <button type="button" aria-pressed={selectedOnly} onClick={() => {
                  setSelectedOnly((current) => !current);
                  setSearch('');
                  setPage(1);
                }} className={'shrink-0 rounded-md border px-2 py-2 text-xs font-medium ' + (selectedOnly
                  ? 'border-[var(--color-accent)] bg-[var(--color-accent-light)]'
                  : 'border-[var(--color-border)] hover:border-[var(--color-accent)]')}>
                  Selected ({selected.length})
                </button>
              )}
            </div>
            {visible.length > 0 ? (
              <ul className="divide-y divide-[var(--color-border)]">
                {visible.map((repository) => {
                  const label = repositoryLabel(repository);
                  return (
                    <li key={repository}>
                      <label className="flex min-w-0 cursor-pointer items-center gap-2 rounded px-1.5 py-1.5 text-sm hover:bg-[var(--color-surface-2)]">
                        <Checkbox checked={selection.has(repository)} label={label} onChange={() => {
                          onToggle(repository);
                          if (selectedOnly) searchInput.current?.focus();
                        }} />
                        <span className="truncate" title={label}>{label}</span>
                      </label>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p role="status" className="px-1.5 py-2 text-sm text-[var(--color-text-secondary)]">
                {selectedOnly && !selected.length ? 'No selected repositories' : 'No matching repositories'}
              </p>
            )}
            {(totalPages > 1 || selected.length > 0) && (
              <div className="flex flex-wrap items-center justify-between gap-1.5 px-1">
                {totalPages > 1 && (
                  <div className="flex items-center gap-1.5 text-xs text-[var(--color-text-secondary)]">
                    <button type="button" onClick={() => setPage(currentPage - 1)} disabled={currentPage === 1}
                      aria-label="Previous repositories" title="Previous repositories" className="catalog-filter-page">
                      <ChevronLeft className="h-4 w-4" aria-hidden="true" />
                    </button>
                    <span aria-live="polite" className="tabular-nums">{start + 1}–{start + visible.length} of {matches.length.toLocaleString('en')}</span>
                    <button type="button" onClick={() => setPage(currentPage + 1)} disabled={currentPage === totalPages}
                      aria-label="Next repositories" title="Next repositories" className="catalog-filter-page">
                      <ChevronRight className="h-4 w-4" aria-hidden="true" />
                    </button>
                  </div>
                )}
                {selected.length > 0 && (
                  <button type="button" onClick={() => {
                    onClear();
                    setSelectedOnly(false);
                    setPage(1);
                    searchInput.current?.focus();
                  }} className="ml-auto rounded px-1 py-1 text-xs font-medium underline hover:text-[var(--color-accent)]">
                    Clear repositories
                  </button>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
