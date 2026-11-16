import { useEffect, useRef } from 'react';

// Native checkbox with the mixed state used by page and repository selection.
export default function Checkbox({ checked, mixed = false, label, onChange, className = '' }: {
  checked: boolean; mixed?: boolean; label: string; onChange: (checked: boolean) => void; className?: string;
}) {
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (input.current) input.current.indeterminate = mixed;
  }, [mixed]);
  return (
    <input ref={input} type="checkbox" checked={checked} aria-label={label} title={label}
      onChange={(event) => onChange(event.target.checked)}
      className={'relative z-[1] h-4 w-4 shrink-0 cursor-pointer accent-[var(--color-accent)] ' + className} />
  );
}
