export type UiStatus =
  | "draft"
  | "queued"
  | "processing"
  | "pass"
  | "fail"
  | "processing-error";

export type BeverageClass = "spirits" | "wine" | "malt";

export type FieldKey =
  | "artifact_legibility"
  | "brand_name"
  | "class_type_designation"
  | "alcohol_content"
  | "net_contents"
  | "name_address"
  | "country_of_origin"
  | "color_additive_disclosure"
  | "government_warning";

export type FieldSummary = {
  key: FieldKey;
  label: string;
  status: UiStatus;
  applicationValue: string;
  labelValue: string;
  reason: string;
  evidence: string[];
};

// A single label in the working table: the reviewer-entered application values
// plus the latest verification result. This is the core unit of the redesign —
// the user types the values, attaches an image, and the model compares them.
export type LabelRow = {
  localId: string;
  brand: string;
  beverageClass: BeverageClass;
  classType: string;
  abv: string;
  net: string;
  nameAddr: string;
  country: string;
  maltAddedNonbeverageAlcohol: boolean;
  maltColorAdditiveApplicable: boolean;
  fileName: string;
  imageUrl: string | null;
  imageFile: File | null;
  // Sample labels are referenced by URL and fetched into a File at verify time.
  sampleUrl: string | null;
  status: UiStatus;
  fields: FieldSummary[] | null;
  summary: string;
  updatedAtLabel: string;
  flagged: boolean;
  edited: boolean;
  dirtyFields: FieldKey[];
  serverId?: string;
  batchId?: string;
};

// Retained for the result-normalization helpers (single + batch responses).
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

export const FIELD_DEFS: Array<{ key: FieldKey; label: string; short: string }> = [
  { key: "brand_name", label: "Brand name", short: "Brand" },
  { key: "government_warning", label: "Government warning", short: "Gov" },
  { key: "alcohol_content", label: "Alcohol content", short: "ABV" },
  { key: "net_contents", label: "Net contents", short: "Net" },
  { key: "class_type_designation", label: "Class/type designation", short: "Type" },
  { key: "name_address", label: "Name & address", short: "Addr" },
  { key: "country_of_origin", label: "Country of origin", short: "Origin" },
  { key: "color_additive_disclosure", label: "Color additive disclosure", short: "Color" },
  { key: "artifact_legibility", label: "Artifact legibility", short: "Read" },
];
