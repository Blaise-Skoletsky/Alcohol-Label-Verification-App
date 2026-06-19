export type UiStatus =
  | "queued"
  | "processing"
  | "pass"
  | "fail"
  | "needs-review"
  | "processing-error";

export type FieldSummary = {
  key: "brand_name" | "abv" | "government_warning";
  label: string;
  status: UiStatus;
  applicationValue: string;
  labelValue: string;
  confidence: string;
  reason: string;
  evidence: string[];
};

export type BatchItem = {
  localId: string;
  serverId?: string;
  batchId?: string;
  fileName: string;
  fileSize: number;
  mimeType: string;
  previewUrl: string;
  status: UiStatus;
  overallLabel: string;
  summary: string;
  updatedAtLabel: string;
  fields: FieldSummary[];
  rawResult?: unknown;
  errorMessage?: string;
  isPolling: boolean;
};

export const FIELD_DEFS: Array<{ key: FieldSummary["key"]; label: string }> = [
  { key: "brand_name", label: "Brand name" },
  { key: "abv", label: "ABV" },
  { key: "government_warning", label: "Government warning" },
];
