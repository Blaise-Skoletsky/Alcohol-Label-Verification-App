import type { BatchItem, FieldSummary, UiStatus } from "../types/verification";

// Short labels used for the per-row mini-checks in the table.
export const FIELD_SHORT_LABELS: Record<FieldSummary["key"], string> = {
  artifact_legibility: "Legibility",
  brand_name: "Brand",
  class_type_designation: "Class/type",
  alcohol_content: "ABV",
  net_contents: "Net contents",
  name_address: "Name/address",
  country_of_origin: "Origin",
  government_warning: "Warning",
};

// Display labels tuned for the "Console" redesign (e.g. "Passed" / "Checking").
export const STATUS_DISPLAY_LABELS: Record<UiStatus, string> = {
  queued: "Queued",
  processing: "Checking",
  pass: "Passed",
  fail: "Failed",
  "needs-review": "Needs review",
  "processing-error": "Failed",
};

// Short verdict shown at the top of the slide-over.
export function verdictTitle(status: UiStatus): string {
  switch (status) {
    case "pass":
      return "Looks good";
    case "fail":
    case "processing-error":
      return "Found a problem";
    case "needs-review":
      return "Needs your review";
    default:
      return "Checking…";
  }
}

const PLACEHOLDER_VALUES = new Set([
  "",
  "waiting for result",
  "not provided",
  "not available",
  "not available yet",
]);

function isMeaningfulValue(value: string | undefined | null): value is string {
  if (!value) {
    return false;
  }
  return !PLACEHOLDER_VALUES.has(value.trim().toLowerCase());
}

// The data layer has no dedicated brand field, so we derive a friendly brand
// name from the verified brand_name result and fall back to the file name.
export function getItemBrand(item: BatchItem): string {
  const brandField = item.fields.find((field) => field.key === "brand_name");
  if (brandField) {
    if (isMeaningfulValue(brandField.labelValue)) {
      return brandField.labelValue;
    }
    if (isMeaningfulValue(brandField.applicationValue)) {
      return brandField.applicationValue;
    }
  }
  return brandFromFileName(item.fileName);
}

function brandFromFileName(fileName: string): string {
  const base = fileName.replace(/\.[^.]+$/, "");
  const words = base
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (!words) {
    return fileName;
  }
  return words.replace(/\b\w/g, (character) => character.toUpperCase());
}

export function getInitials(brand: string): string {
  const words = brand
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  if (words.length === 0) {
    return "?";
  }
  if (words.length === 1) {
    return words[0].slice(0, 2).toUpperCase();
  }
  return (words[0][0] + words[1][0]).toUpperCase();
}
