// The support table's info popover: what opened it, and what each event does to it.
export type PopoverEvent = "pointer-enter" | "pointer-leave" | "focus-in" | "focus-out" | "click" | "escape" | "outside";
export interface PopoverState {
  open: boolean;
  by: "hover" | "focus" | "click" | null;
}

export const CLOSED: PopoverState = { open: false, by: null };

export function nextPopover(state: PopoverState, event: PopoverEvent): PopoverState {
  switch (event) {
    case "pointer-enter": return { open: true, by: state.by ?? "hover" };
    case "focus-in": return { open: true, by: state.by ?? "focus" };
    // Opened from the keyboard, it stays open while the pointer passes over.
    case "pointer-leave": return state.by === "focus" ? state : CLOSED;
    case "click": return state.by === "click" ? CLOSED : { open: true, by: "click" };
    default: return CLOSED;
  }
}

// What a key pressed anywhere on the page does to the popover. Escape closes an open one, even one opened by hover
// while focus is elsewhere; focus goes back to the button only when it was inside the icon or the popover.
export function escapeKey(key: string, open: boolean, focusInside: boolean) {
  if (key !== "Escape" || !open) return null;
  return { close: true, refocus: focusInside };
}

// A link's text: the page's host and path.
export function sourceLinkText(url: string) {
  try {
    const { host, pathname } = new URL(url);
    return host + pathname.replace(/\/$/, "");
  } catch {
    return url;
  }
}
