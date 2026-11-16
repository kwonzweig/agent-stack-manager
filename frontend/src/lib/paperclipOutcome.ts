import type { ReportItem, Result } from "../types";

// What became of a component in Paperclip. "expected" is a component Paperclip left out for a
// reason nobody has to act on; "attention" is one left out for a reason somebody can fix.
export type Outcome = "saved" | "expected" | "attention" | "pending";

export function outcome(item: ReportItem): Outcome {
  if (item.conversion.status === "unconverted") return item.conversion.cause === "unsupported" ? "expected" : "attention";
  if (item.import.status === "saved") return "saved";
  if (item.import.status === "missing") return item.import.cause === "refused" ? "expected" : "attention";
  return "pending";
}

export type StageStatus = "converted" | "unsupported" | "unconverted" | "saved" | "refused" | "no_access" | "missing" | "not_checked";
export type Tone = "good" | "bad" | "neutral";

const shown: Record<StageStatus, [string, Tone]> = {
  converted: ["Converted", "good"], unsupported: ["Not supported", "neutral"], unconverted: ["Unconverted", "bad"],
  saved: ["Saved", "good"], refused: ["Refused", "neutral"], no_access: ["No access", "bad"], missing: ["Missing", "bad"],
  not_checked: ["Not checked", "neutral"],
};

function stage(result: Result): StageStatus {
  if (result.status === "unconverted") return result.cause === "unsupported" ? "unsupported" : "unconverted";
  if (result.status === "missing") return result.cause === "refused" ? "refused" : result.cause === "access" ? "no_access" : "missing";
  return result.status === "converted" || result.status === "saved" ? result.status : "not_checked";
}

export function stageStatus(result: Result): { id: StageStatus; label: string; tone: Tone } {
  const id = stage(result);
  const [label, tone] = shown[id];
  return { id, label, tone };
}
