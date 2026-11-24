export function SourceFailures({ errors, onRetry }: { errors: string[]; onRetry: () => void }) {
  if (!errors.length) return null;
  return <div className="flex flex-wrap items-baseline gap-x-3 text-[13px] text-muted">
    <details className="min-w-0">
      <summary className="cursor-pointer">{errors.length} source {errors.length === 1 ? "request" : "requests"} failed</summary>
      <ul className="space-y-1 py-2 [overflow-wrap:anywhere]">{errors.map(error => <li key={error}>{error}</li>)}</ul>
    </details>
    <button type="button" className="underline" onClick={onRetry}>Retry</button>
  </div>;
}
