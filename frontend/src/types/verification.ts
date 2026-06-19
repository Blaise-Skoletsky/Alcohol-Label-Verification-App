export type UiStatus =
  | "queued"
  | "processing"
  | "pass"
  | "fail"
  | "needs-review"
  | "processing-error";

export type FieldSummary = {
  key:
    | "artifact_legibility"
    | "brand_name"
    | "class_type_designation"
    | "alcohol_content"
    | "net_contents"
    | "name_address"
    | "country_of_origin"
    | "government_warning";
  label: string;
  status: UiStatus;
  applicationValue: string;
  labelValue: string;
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
  { key: "government_warning", label: "Government warning" },
  { key: "alcohol_content", label: "Alcohol content" },
  { key: "net_contents", label: "Net contents" },
  { key: "class_type_designation", label: "Class/type designation" },
  { key: "name_address", label: "Name & address" },
  { key: "country_of_origin", label: "Country of origin" },
  { key: "artifact_legibility", label: "Artifact legibility" },
];
