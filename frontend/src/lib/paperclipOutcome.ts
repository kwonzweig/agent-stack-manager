import type { ReportItem, Result } from "../types";

// How a component converts for Paperclip. "expected" is a component Paperclip has no setting for,
// so nobody has to act on it; "attention" is a conversion that failed for a reason somebody can fix.
export type Outcome = "converted" | "expected" | "attention";

export function outcome(item: ReportItem): Outcome {
  if (item.conversion.status !== "unconverted") return "converted";
  return item.conversion.cause === "unsupported" ? "expected" : "attention";
}

export type ConversionStatus = "converted" | "unsupported" | "unconverted";
export type Tone = "good" | "bad" | "neutral";

const shown: Record<ConversionStatus, [string, Tone]> = {
  converted: ["Converted", "good"], unsupported: ["Not supported", "neutral"], unconverted: ["Unconverted", "bad"],
};

export function conversionStatus(result: Result): { id: ConversionStatus; label: string; tone: Tone } {
  const id: ConversionStatus = result.status !== "unconverted" ? "converted"
    : result.cause === "unsupported" ? "unsupported" : "unconverted";
  const [label, tone] = shown[id];
  return { id, label, tone };
}
