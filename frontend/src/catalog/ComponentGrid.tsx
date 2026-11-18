// Adapted from AITMPL dashboard/src/components/ComponentGrid.tsx (MIT).
import { Fragment, useEffect, useMemo, useRef, useState } from 'react';
import { FolderGit2 } from 'lucide-react';
import type { CatalogItem, PackageKind, PackageSummary } from '../types';
import { KIND_STYLES } from '../lib/kinds';
import Checkbox from './Checkbox';
import ComponentCard from './ComponentCard';
import RepositoryFilter from './RepositoryFilter';
import { byStars, filterCatalogFacets, itemName, itemRepository, repositoryLabel, type CatalogKind } from './catalogItem';

const ITEMS_PER_PAGE = 24;
const CATALOG_TYPES = { all: 'All', component: 'Components', stack: 'Stacks', preset: 'Presets' };
type CatalogType = keyof typeof CATALOG_TYPES;
type Sort = 'catalog' | 'name' | 'repository' | 'stars';
const SORTS = [['catalog', 'Catalog order'], ['name', 'Alphabetical'], ['repository', 'Repository'], ['stars', 'Stars']] as const;

interface Props {
  items: CatalogItem[];
  selection: ReadonlySet<string>;
  onlySelected: boolean;
  targets: PackageSummary[];
  isLoading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  onOpen: (item: CatalogItem) => void;
  onSelect: (items: CatalogItem[], selected: boolean) => void;
  onAdd: (packageId: string, componentIds: string[]) => Promise<void>;
  onCreate: (componentIds: string[], kind: PackageKind) => void;
}

const selectable = (item: CatalogItem) => item.type !== 'preset' && item.addable !== false;

// Checked when every entry is selected, mixed when only some are.
function SelectAll({ items, selection, label, onSelect }: {
  items: CatalogItem[]; selection: ReadonlySet<string>; label: string; onSelect: Props['onSelect'];
}) {
  const count = items.filter((item) => selection.has(item.id)).length;
  if (!items.length) return null;
  return <Checkbox checked={count === items.length} mixed={count > 0 && count < items.length} label={label}
    onChange={(checked) => onSelect(items, checked)} />;
}

export default function ComponentGrid({
  items, selection, onlySelected, targets, isLoading, error, onRetry, onOpen, onSelect, onAdd, onCreate,
}: Props) {
  const [activeType, setActiveType] = useState<CatalogType>('all');
  const [category, setCategory] = useState<CatalogKind>('all');
  const [minimumStars, setMinimumStars] = useState<number | null>(null);
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState<Sort>('catalog');
  const [page, setPage] = useState(1);
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [showFilters, setShowFilters] = useState(false);
  const [selectedRepositories, setSelectedRepositories] = useState<string[]>([]);
  const searchInput = useRef<HTMLInputElement>(null);
  const resultsTop = useRef<HTMLDivElement>(null);
  const shortcut = typeof navigator !== 'undefined' && /Mac/.test(navigator.platform) ? '⌘K' : 'Ctrl K';

  useEffect(() => {
    function focusSearch(event: KeyboardEvent) {
      if (event.defaultPrevented || document.querySelector('dialog[open], [aria-modal="true"]')) return;
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k' && searchInput.current) {
        event.preventDefault();
        searchInput.current.focus();
      }
    }
    window.addEventListener('keydown', focusSearch);
    return () => window.removeEventListener('keydown', focusSearch);
  }, []);
  useEffect(() => setPage(1), [onlySelected]);

  const typeComponents = useMemo(
    () => items.filter((item) => activeType === 'all' || item.type === activeType),
    [items, activeType],
  );
  const categories = [...new Set(typeComponents.map((item) => item.kind))].sort((a, b) =>
    KIND_STYLES[a].singular.localeCompare(KIND_STYLES[b].singular),
  );
  const hasStarCounts = useMemo(() => typeComponents.some((item) => item.stars != null), [typeComponents]);
  const repositories = useMemo(() => [...new Set(typeComponents.map(itemRepository).filter(Boolean))]
    .sort((a, b) => repositoryLabel(a).localeCompare(repositoryLabel(b))), [typeComponents]);

  const filtered = useMemo(() => {
    let results = filterCatalogFacets(typeComponents, category, selectedRepositories, minimumStars);
    if (onlySelected) results = results.filter((item) => selection.has(item.id));
    const query = search.trim().toLowerCase();
    if (query) {
      results = results.filter((item) =>
        [
          itemName(item), item.description, item.source?.path, item.source?.repositoryUrl,
          item.sourceUrl, KIND_STYLES[item.kind].singular, ...(item.workArea ?? []), ...(item.usage ?? []),
        ].some((value) => value?.toLowerCase().includes(query)),
      );
    }
    if (sortBy === 'name') return [...results].sort((a, b) => itemName(a).localeCompare(itemName(b)));
    if (sortBy === 'stars') return byStars(results);
    // Entries without a source repository go last; catalog order holds within each repository.
    if (sortBy === 'repository') {
      const key = (item: CatalogItem) => itemRepository(item) ? repositoryLabel(itemRepository(item)).toLowerCase() : '￿';
      return [...results].sort((a, b) => key(a).localeCompare(key(b)));
    }
    return results;
  }, [typeComponents, onlySelected, selection, category, selectedRepositories, minimumStars, search, sortBy]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / ITEMS_PER_PAGE));
  const currentPage = Math.min(page, totalPages);
  const paged = filtered.slice((currentPage - 1) * ITEMS_PER_PAGE, currentPage * ITEMS_PER_PAGE);
  const selectableOnPage = paged.filter(selectable);
  const resultLabel = {
    all: ['result', 'results'],
    component: ['component', 'components'],
    stack: ['stack', 'stacks'],
    preset: ['preset', 'presets'],
  }[activeType];
  const activeFilterCount = Number(category !== 'all') + Number(selectedRepositories.length > 0) + Number(minimumStars !== null);
  const hasActiveFilters = Boolean(search || activeFilterCount);

  function toggleRepositoryFilter(repository: string) {
    setSelectedRepositories((previous) => previous.includes(repository)
      ? previous.filter((value) => value !== repository)
      : [...previous, repository]);
    setPage(1);
  }

  function showRepository(repository: string) {
    setSelectedRepositories([repository]);
    setShowFilters(true);
    setPage(1);
  }

  function clearAllFilters() {
    setSearch('');
    setCategory('all');
    setSelectedRepositories([]);
    setMinimumStars(null);
    setPage(1);
  }

  function turnPage(nextPage: number) {
    setPage(nextPage);
    resultsTop.current?.scrollIntoView({ block: 'start' });
  }

  if (isLoading && !items.length) return <p role="status" className="px-6 py-12 text-sm text-[var(--color-text-secondary)]">Loading catalog…</p>;
  if (error) {
    return (
      <div className="px-6 py-24">
        <div className="flex flex-col items-center gap-4 max-w-md mx-auto text-center">
          <div className="w-12 h-12 rounded-full bg-red-500/10 border border-red-500/20 flex items-center justify-center">
            <svg aria-hidden="true" className="w-6 h-6 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <div role="alert">
            <h2 className="text-[14px] font-semibold mb-1">Failed to load catalog</h2>
            <p className="text-[13px] text-[var(--color-text-secondary)]">{error}</p>
          </div>
          {onRetry && (
            <button type="button" onClick={onRetry} className="px-4 py-2 text-[13px] font-medium rounded-lg bg-[var(--color-primary-500)] text-white hover:bg-[var(--color-primary-600)] transition-all active:scale-95">
              Try again
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div ref={resultsTop}>
      <div className="border-b border-[var(--color-border)] bg-[var(--color-surface-0)] backdrop-blur-sm sm:sticky sm:top-0 z-10">
        <nav className="flex gap-1.5 overflow-x-auto px-4 sm:px-6 pt-3 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden" aria-label="Catalog type">
          {Object.entries(CATALOG_TYPES).map(([type, label]) => (
            <button
              key={type}
              type="button"
              aria-pressed={type === activeType}
              onClick={() => {
                setActiveType(type as CatalogType);
                setCategory('all');
                setSelectedRepositories([]);
                setMinimumStars(null);
                setPage(1);
              }}
              className={'shrink-0 px-3 py-1.5 rounded-full border text-[12px] font-ui-mono font-semibold transition-colors ' + (
                type === activeType
                  ? 'bg-[var(--color-accent)] text-white border-[var(--color-accent)]'
                  : 'bg-[var(--color-surface-2)] text-[var(--color-text-secondary)] border-[var(--color-border)] hover:text-[var(--color-text-primary)]'
              )}
            >
              {label}
            </button>
          ))}
        </nav>
        <div className="flex flex-col sm:flex-row sm:flex-wrap sm:items-center gap-2.5 px-4 sm:px-6 py-3 sm:py-4">
          {/* Search */}
          <div className="relative sm:flex-1 sm:min-w-[140px]">
            <svg aria-hidden="true" className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--color-text-tertiary)] pointer-events-none transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              type="search"
              ref={searchInput}
              aria-label="Search catalog"
              aria-keyshortcuts="Control+K Meta+K"
              placeholder="Search catalog..."
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }}
              className="w-full bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-lg text-[13px] text-[var(--color-text-primary)] placeholder:text-[var(--color-text-tertiary)] pl-10 pr-9 py-2.5 outline-none focus:bg-[var(--color-surface-3)] focus:border-[var(--color-primary-500)] focus:ring-2 focus:ring-[var(--color-primary-500)]/20 transition-all hover:border-[var(--color-border-hover)]"
            />
            {search && (
              <button
                onClick={() => { setSearch(''); setPage(1); searchInput.current?.focus(); }}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 w-5 h-5 rounded-md flex items-center justify-center text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-surface-3)] transition-all active:scale-95"
                aria-label="Clear search"
              >
                <svg aria-hidden="true" className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
          </div>

          <button
            type="button"
            onClick={() => setShowFilters((open) => !open)}
            aria-expanded={showFilters}
            aria-controls="aitmpl-filters"
            className={'flex w-fit shrink-0 items-center gap-2 rounded-lg border px-3 py-2 text-[13px] font-semibold transition-colors ' + (
              showFilters || activeFilterCount
                ? 'border-[var(--color-accent)] bg-[var(--color-accent-light)] text-[var(--color-text-primary)]'
                : 'border-[var(--color-border)] bg-[var(--color-surface-2)] text-[var(--color-text-secondary)] hover:border-[var(--color-accent)]'
            )}
          >
            <svg aria-hidden="true" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
            </svg>
            Filters
            {activeFilterCount > 0 && (
              <span className="rounded-md bg-[var(--color-surface-2)] px-1.5 py-0.5 text-xs tabular-nums">{activeFilterCount}</span>
            )}
          </button>

          {/* View Mode Toggle */}
          <div role="group" aria-label="Catalog view" className="flex w-fit items-center gap-1 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-lg p-1">
            <button
              onClick={() => setViewMode('grid')}
              className={`p-2 rounded-md transition-all ${
                viewMode === 'grid'
                  ? 'bg-[var(--color-surface-4)] text-[var(--color-text-primary)] shadow-sm'
                  : 'text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)]'
              }`}
              title="Grid view"
              aria-label="Grid view"
              aria-pressed={viewMode === 'grid'}
            >
              <svg aria-hidden="true" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
              </svg>
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={`p-2 rounded-md transition-all ${
                viewMode === 'list'
                  ? 'bg-[var(--color-surface-4)] text-[var(--color-text-primary)] shadow-sm'
                  : 'text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)]'
              }`}
              title="List view"
              aria-label="List view"
              aria-pressed={viewMode === 'list'}
            >
              <svg aria-hidden="true" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
          </div>

          {/* Sort */}
          <div className="hidden sm:flex items-center gap-2 sm:ml-auto">
            <span className="text-[11px] text-[var(--color-text-tertiary)] font-medium hidden sm:inline">Sort by</span>
            <select
              aria-label="Sort by"
              value={sortBy}
              onChange={(e) => { setSortBy(e.target.value as Sort); setPage(1); }}
              className="font-mono bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded text-[13px] text-[var(--color-text-secondary)] font-medium px-3 py-2 pr-9 outline-none focus:border-[var(--color-accent)] cursor-pointer transition-all appearance-none hover:border-[var(--color-accent)] hover:text-[var(--color-text-primary)] bg-[url('data:image/svg+xml;charset=utf-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20fill%3D%22none%22%20viewBox%3D%220%200%2020%2020%22%3E%3Cpath%20stroke%3D%22%237d8590%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%20stroke-width%3D%221.5%22%20d%3D%22m6%208%204%204%204-4%22%2F%3E%3C%2Fsvg%3E')] bg-[length:1.25rem] bg-[right_0.5rem_center] bg-no-repeat"
            >
              {SORTS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </div>
        </div>

        {showFilters && (
          <div id="aitmpl-filters" className="border-t border-[var(--color-border)] bg-[var(--color-surface-1)] px-4 py-3 sm:max-h-[55dvh] sm:overflow-y-auto sm:px-6">
            <div className="grid items-start gap-3 sm:grid-cols-2 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1.5fr)]">
              <label className="min-w-0 space-y-1.5">
                <span className="block text-xs font-medium text-[var(--color-text-secondary)]">Kind</span>
                <select value={category}
                  onChange={(event) => { setCategory(event.currentTarget.value as CatalogKind); setPage(1); }}
                  className="catalog-filter-control">
                  <option value="all">All kinds</option>
                  {categories.map((kind) => <option key={kind} value={kind}>{KIND_STYLES[kind].singular}</option>)}
                </select>
              </label>
              {hasStarCounts && (
                <label className="min-w-0 space-y-1.5">
                  <span className="block text-xs font-medium text-[var(--color-text-secondary)]">Minimum GitHub stars</span>
                  <input type="number" min={0} step={1} inputMode="numeric" placeholder="Any"
                    value={minimumStars ?? ''} className="catalog-filter-control"
                    onChange={(event) => {
                      const { value, valueAsNumber, validity } = event.currentTarget;
                      if (validity.badInput) return;
                      if (value && (!Number.isSafeInteger(valueAsNumber) || valueAsNumber < 0)) return;
                      setMinimumStars(value ? valueAsNumber : null);
                      setPage(1);
                    }} />
                </label>
              )}
              {repositories.length > 0 && (
                <div className="min-w-0 sm:col-span-2 lg:col-span-1">
                  <RepositoryFilter repositories={repositories} selected={selectedRepositories}
                    onToggle={toggleRepositoryFilter} onClear={() => { setSelectedRepositories([]); setPage(1); }} />
                </div>
              )}
              <label className="min-w-0 space-y-1.5 sm:hidden">
                <span className="block text-xs font-medium text-[var(--color-text-secondary)]">Sort by</span>
                <select value={sortBy} onChange={(event) => { setSortBy(event.currentTarget.value as Sort); setPage(1); }}
                  className="catalog-filter-control">
                  {SORTS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
              </label>
            </div>
            {hasActiveFilters && (
              <button type="button" onClick={clearAllFilters} className="mt-2 rounded px-1 py-1 text-xs font-medium underline hover:text-[var(--color-accent)]">
                Clear filters
              </button>
            )}
          </div>
        )}
      </div>
      {/* Results count with quick actions */}
      <div className="px-4 sm:px-6 pt-4 sm:pt-5 pb-3 flex items-center justify-between">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <span role="status" className="text-[13px] text-[var(--color-text-secondary)] font-medium">
              {filtered.length} {filtered.length === 1 ? resultLabel[0] : resultLabel[1]}
            </span>
            {search && (
              <span className="text-[12px] text-[var(--color-text-tertiary)]">
                matching <span className="font-medium text-[var(--color-text-secondary)]">"{search}"</span>
              </span>
            )}
            {category !== 'all' && (
              <span className="text-[11px] px-2 py-0.5 rounded-md bg-[var(--color-surface-3)] text-[var(--color-text-tertiary)] border border-[var(--color-border)]">
                {KIND_STYLES[category].singular}
              </span>
            )}
          </div>

          {selectableOnPage.length > 0 && (
            <label className="flex items-center gap-2 text-[12px] font-medium text-[var(--color-text-secondary)] sm:ml-4">
              <SelectAll items={selectableOnPage} selection={selection} label="Select this page" onSelect={onSelect} />
              Select this page
            </label>
          )}
        </div>

        {/* Keyboard shortcuts hint */}
        <div className="hidden lg:flex items-center gap-2 text-[11px] text-[var(--color-text-tertiary)]">
          <kbd className="px-2 py-1 rounded bg-[var(--color-surface-2)] border border-[var(--color-border)] font-mono">{shortcut}</kbd>
          <span>to search</span>
        </div>
      </div>

      {/* Grid or List View */}
      <div className={viewMode === 'grid'
        ? "grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4 sm:gap-5 px-4 sm:px-6 pb-6"
        : "flex flex-col gap-4 px-4 sm:px-6 pb-6"
      }>
        {paged.map((item, index) => {
          const repository = itemRepository(item);
          const group = sortBy === 'repository' && (index === 0 || itemRepository(paged[index - 1]) !== repository)
            ? filtered.filter((entry) => itemRepository(entry) === repository) : undefined;
          const groupName = repository ? repositoryLabel(repository) : 'No source repository';
          return (
            <Fragment key={item.id}>
              {group && (
                <div className={'col-span-full flex items-center gap-2.5 ' + (index ? 'pt-3' : '')}>
                  <SelectAll items={group.filter(selectable)} selection={selection} onSelect={onSelect}
                    label={'Select all ' + group.filter(selectable).length + ' from ' + groupName} />
                  <FolderGit2 className="h-4 w-4 shrink-0 text-[var(--color-text-tertiary)]" aria-hidden="true" />
                  <h2 className="min-w-0 truncate font-mono text-[13px] font-semibold text-[var(--color-text-primary)]">
                    {/^https?:\/\//i.test(repository)
                      ? <a className="hover:text-[var(--color-accent)] hover:underline" href={repository} target="_blank" rel="noreferrer">{groupName}</a>
                      : groupName}
                  </h2>
                  <span className="text-[12px] tabular-nums text-[var(--color-text-tertiary)]">{group.length}</span>
                </div>
              )}
              <ComponentCard
                item={item}
                index={index}
                viewMode={viewMode}
                selected={selection.has(item.id)}
                targets={targets}
                onOpen={onOpen}
                onSelect={(entry, checked) => onSelect([entry], checked)}
                onAdd={onAdd}
                onCreate={onCreate}
                onRepository={sortBy === 'repository' ? undefined : showRepository}
              />
            </Fragment>
          );
        })}
      </div>

      {paged.length === 0 && (
        <div className="flex flex-col items-center justify-center px-6 py-20">
          <h2 className="text-[17px] font-bold text-[var(--color-text-primary)] mb-3">
            {search.trim() ? `No results for "${search.trim()}"` : 'No matching items'}
          </h2>
          {hasActiveFilters && (
            <button onClick={clearAllFilters} className="px-5 py-2.5 text-[13px] font-semibold rounded-xl bg-[var(--color-surface-2)] text-[var(--color-text-primary)] hover:bg-[var(--color-surface-3)] border border-[var(--color-border)] hover:border-[var(--color-border-hover)] transition-all active:scale-95">
              Clear filters
            </button>
          )}
        </div>
      )}
      {/* Pagination - Premium style */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-3 px-6 pb-10 pt-4">
          <button
            onClick={() => turnPage(currentPage - 1)}
            disabled={currentPage === 1}
            className="group flex items-center gap-2 px-4 py-2.5 text-[13px] font-semibold rounded-xl text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-surface-2)] border border-[var(--color-border)] hover:border-[var(--color-border-hover)] disabled:opacity-30 disabled:cursor-not-allowed hover:shadow-md transition-all active:scale-95 disabled:active:scale-100 disabled:hover:shadow-none"
            aria-label="Previous page"
          >
            <svg aria-hidden="true" className="w-4 h-4 transition-transform group-hover:-translate-x-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
            <span className="hidden sm:inline">Previous</span>
          </button>

          <div className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[var(--color-surface-2)] border border-[var(--color-border)] shadow-sm">
            <span className="text-[13px] font-bold text-[var(--color-text-primary)] tabular-nums">
              {currentPage}
            </span>
            <span className="text-[13px] text-[var(--color-text-tertiary)] font-medium">/</span>
            <span className="text-[13px] font-semibold text-[var(--color-text-secondary)] tabular-nums">
              {totalPages}
            </span>
          </div>

          <button
            onClick={() => turnPage(currentPage + 1)}
            disabled={currentPage === totalPages}
            className="group flex items-center gap-2 px-4 py-2.5 text-[13px] font-semibold rounded-xl text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-surface-2)] border border-[var(--color-border)] hover:border-[var(--color-border-hover)] disabled:opacity-30 disabled:cursor-not-allowed hover:shadow-md transition-all active:scale-95 disabled:active:scale-100 disabled:hover:shadow-none"
            aria-label="Next page"
          >
            <span className="hidden sm:inline">Next</span>
            <svg aria-hidden="true" className="w-4 h-4 transition-transform group-hover:translate-x-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </div>
      )}
    </div>
  );
}
