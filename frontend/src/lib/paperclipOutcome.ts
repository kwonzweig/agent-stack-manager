import type { ReportItem, Result } from "../types";

// How a component converts for Paperclip. "expected" is a component the export leaves out for a
// reason that is not a fault: Paperclip's package format has no entry for it, or it is set in the
// agent's adapter after import. "attention" is a conversion that failed for a reason somebody can fix.
export type Outcome = "converted" | "expected" | "attention";

const expectedCauses = new Set(["not-in-format", "adapter"]);

export function outcome(item: ReportItem): Outcome {
  if (item.conversion.status !== "unconverted") return "converted";
  return expectedCauses.has(item.conversion.cause ?? "") ? "expected" : "attention";
}

// The file in the export folder a component went to; an expanded stack's target names a package, not a file.
export function targetFile(item: ReportItem): string | null {
  return typeof item.target === "string" ? item.target : null;
}

export type ConversionStatus = "converted" | "not-in-format" | "adapter" | "unconverted";
export type Tone = "good" | "bad" | "neutral";

const shown: Record<ConversionStatus, [string, Tone]> = {
  converted: ["Converted", "good"],
  "not-in-format": ["Not in Paperclip's format", "neutral"],
  adapter: ["Set in the adapter", "neutral"],
  unconverted: ["Unconverted", "bad"],
};

export function conversionStatus(result: Result): { id: ConversionStatus; label: string; tone: Tone } {
  const id: ConversionStatus = result.status !== "unconverted" ? "converted"
    : result.cause === "not-in-format" || result.cause === "adapter" ? result.cause : "unconverted";
  const [label, tone] = shown[id];
  return { id, label, tone };
}
