import { useEffect, useId, useLayoutEffect, useReducer, useRef, type PointerEvent } from "react";
import { Info } from "lucide-react";
import { CLOSED, escapeKey, nextPopover, sourceLinkText } from "../lib/infoPopover";

// Leaving the icon for the popover crosses a small gap; a pointer that comes back in time keeps it open.
const LEAVE_DELAY_MS = 150;

// The i icon of a support cell: a button whose popover holds the note and a link to the page that says so.
// The popover sits in the top layer, so the table's scroll box does not clip it.
export function InfoPopover({ label, note, doc }: { label: string; note?: string; doc: string }) {
  const [state, dispatch] = useReducer(nextPopover, CLOSED);
  const id = useId();
  const wrapper = useRef<HTMLSpanElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const leaving = useRef<number>(undefined);
  const returning = useRef(false);

  useLayoutEffect(() => {
    const element = panel.current;
    if (!state.open || !element) return;
    element.showPopover?.();
    const place = () => {
      const anchor = button.current!.getBoundingClientRect();
      const left = Math.min(Math.max(8, anchor.left - 8), window.innerWidth - element.offsetWidth - 8);
      element.style.left = `${Math.max(8, left)}px`;
      element.style.top = `${anchor.bottom + 4}px`;
    };
    place();
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    return () => {
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", place, true);
    };
  }, [state.open]);

  useEffect(() => {
    if (!state.open) return;
    const outside = (event: globalThis.PointerEvent) => {
      if (!wrapper.current?.contains(event.target as Node)) dispatch("outside");
    };
    // Escape is heard on the whole page, so a popover opened by hover closes while focus is elsewhere.
    const key = (event: globalThis.KeyboardEvent) => {
      const outcome = escapeKey(event.key, true, !!wrapper.current?.contains(document.activeElement));
      if (!outcome) return;
      event.stopPropagation();
      dispatch("escape");
      if (!outcome.refocus) return;
      // Focus goes back to the button without opening the popover again.
      returning.current = true;
      button.current?.focus();
      returning.current = false;
    };
    document.addEventListener("pointerdown", outside);
    document.addEventListener("keydown", key);
    return () => {
      document.removeEventListener("pointerdown", outside);
      document.removeEventListener("keydown", key);
    };
  }, [state.open]);

  useEffect(() => () => window.clearTimeout(leaving.current), []);

  // A touch fires enter and leave around every tap; the tap itself is the click.
  const enter = (event: PointerEvent) => {
    if (event.pointerType === "touch") return;
    window.clearTimeout(leaving.current);
    dispatch("pointer-enter");
  };
  const leave = (event: PointerEvent) => {
    if (event.pointerType === "touch") return;
    window.clearTimeout(leaving.current);
    leaving.current = window.setTimeout(() => dispatch("pointer-leave"), LEAVE_DELAY_MS);
  };

  return <span ref={wrapper} className="support-info-wrap" onPointerEnter={enter} onPointerLeave={leave}
    onBlur={event => { if (!wrapper.current?.contains(event.relatedTarget as Node | null)) dispatch("focus-out"); }}>
    <button ref={button} type="button" className="support-info" aria-label={label} aria-expanded={state.open}
      aria-controls={state.open ? id : undefined} onFocus={() => { if (!returning.current) dispatch("focus-in"); }} onClick={() => dispatch("click")}>
      <Info className="h-3.5 w-3.5" aria-hidden="true" />
    </button>
    {state.open && <div ref={panel} id={id} popover="manual" className="support-popover">
      {note && <p>{note}</p>}
      <p className="support-popover-source">Source: <a href={doc} target="_blank" rel="noreferrer">{sourceLinkText(doc)}</a></p>
    </div>}
  </span>;
}
