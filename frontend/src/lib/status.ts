import type { UiStatus } from "../types/verification";

export const STATUS_LABELS: Record<UiStatus, string> = {
  queued: "Queued",
  processing: "Processing",
  pass: "Pass",
  fail: "Fail",
  "needs-review": "Needs review",
  "processing-error": "Processing error",
};

export const STATUS_TONES: Record<UiStatus, string> = {
  queued: "neutral",
  processing: "working",
  pass: "pass",
  fail: "fail",
  "needs-review": "review",
  "processing-error": "error",
};

export function normalizeStatus(rawStatus?: string | null): UiStatus {
  const normalized = (rawStatus ?? "").toLowerCase().trim();
  if (normalized.includes("pass") || normalized === "approved" || normalized === "match") {
    return "pass";
  }
  if (
    normalized.includes("fail") ||
    normalized.includes("reject") ||
    normalized === "mismatch"
  ) {
    return "fail";
  }
  if (
    normalized.includes("review") ||
    normalized.includes("manual") ||
    normalized === "warning"
  ) {
    return "needs-review";
  }
  if (normalized.includes("error") || normalized.includes("invalid")) {
    return "processing-error";
  }
  if (
    normalized.includes("process") ||
    normalized.includes("running") ||
    normalized === "started"
  ) {
    return "processing";
  }
  return "queued";
}

export function defaultReasonForStatus(status: UiStatus) {
  switch (status) {
    case "pass":
      return "The application and label values appear to match.";
    case "fail":
      return "The application and label values do not match.";
    case "needs-review":
      return "The system could not make a confident decision.";
    case "processing-error":
      return "The system could not complete this check.";
    case "processing":
      return "This check is still running.";
    case "queued":
    default:
      return "This check is waiting to start.";
  }
}

export function isPendingStatus(status: UiStatus) {
  return status === "queued" || status === "processing";
}
