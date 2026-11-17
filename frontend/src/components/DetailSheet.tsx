import { createPortal } from "react-dom";
import { ArrowLeft } from "lucide-react";
import { useEffect, useRef, type ReactNode } from "react";




interface DetailSheetProps {
  open: boolean;
  title: ReactNode;
  description?: ReactNode;
  meta?: ReactNode;
  /** The page the back button returns to, such as "Catalog". */
  backLabel: string;
  onClose: () => void;
  children: ReactNode;
}

export function DetailSheet({
  open,
  title,
  description,
  meta,
  backLabel,
  onClose,
  children,
}: DetailSheetProps) {
  const sheetRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key !== "Escape" || e.defaultPrevented || e.isComposing) return;
      const sheet = sheetRef.current;
      if (!sheet) return;
      const rect = sheet.getBoundingClientRect();
      // Leave Escape to any dialog covering the detail sheet.
      const topElement = document.elementFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2);
      if (!topElement || !sheet.contains(topElement)) return;
      e.preventDefault();
      onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) return null;


  return createPortal(
    <div
      ref={sheetRef}
      className="fixed inset-y-0 right-0 left-0 z-40 isolate md:left-[220px]"
    >
      <div
        className="absolute inset-0 z-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />
      <div role="dialog" aria-label={typeof title === "string" ? title : "Component details"} className="absolute inset-0 z-10 flex min-h-0 flex-col overflow-hidden border-l border-border-subtle bg-bg-secondary">
        <div className="min-h-0 flex-1 overflow-y-auto px-6 pt-4 pb-6 scrollbar-hide">
          <button
            type="button"
            onClick={onClose}
            autoFocus
            aria-label={"Back to " + backLabel}
            title={"Back to " + backLabel}
            className="-ml-2 mb-3 inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-[13px] font-medium text-muted transition-colors hover:bg-surface-hover hover:text-secondary focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
          >
            <ArrowLeft className="h-4 w-4" aria-hidden="true" /> {backLabel}
          </button>
          <h2 className="mb-3 min-w-0 text-[28px] font-semibold leading-tight tracking-tight text-primary">
            <span className="block">{title}</span>
          </h2>
          {description ? (
            <div className="text-[15px] leading-7 text-secondary">{description}</div>
          ) : null}
          {meta ? <div className="mt-4">{meta}</div> : null}
          <div className="mt-5">{children}</div>
        </div>
      </div>
    </div>,
    document.body
  );
}

