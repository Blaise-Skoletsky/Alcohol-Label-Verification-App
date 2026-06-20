import { FIELD_DEFS, type FieldKey, type LabelRow, type UiStatus } from "../types/verification";
import { STATUS_LABELS, STATUS_TONES } from "./status";

export type MiniCheck = {
  key: FieldKey;
  short: string;
  tone: string;
};

function fieldStatus(row: LabelRow, key: FieldKey): UiStatus {
  if (row.status === "processing") return "processing";
  if (row.status === "draft" || !row.fields) return "draft";
  const field = row.fields.find((entry) => entry.key === key);
  return field?.status ?? "pass";
}

export function miniChecks(row: LabelRow): MiniCheck[] {
  return FIELD_DEFS.map((definition) => ({
    key: definition.key,
    short: definition.short,
    tone: STATUS_TONES[fieldStatus(row, definition.key)],
  }));
}

export type DetailFieldCard = {
  key: FieldKey;
  label: string;
  tone: string;
  statusLabel: string;
  appVal: string;
  labelVal: string;
  reason: string;
  isFail: boolean;
};

export function detailFieldCards(row: LabelRow): DetailFieldCard[] {
  if (!row.fields) return [];
  return FIELD_DEFS.map((definition) => {
    const field = row.fields?.find((entry) => entry.key === definition.key);
    const status = field?.status ?? "pass";
    const isFail = status === "fail" || status === "processing-error";
    return {
      key: definition.key,
      label: definition.label,
      tone: STATUS_TONES[status],
      statusLabel: STATUS_LABELS[status],
      appVal: field?.applicationValue ?? "—",
      labelVal: field?.labelValue ?? "—",
      reason: field?.reason ?? "",
      isFail,
    };
  });
}

export function rowInitials(brand: string): string {
  const trimmed = (brand || "?").trim();
  return trimmed.slice(0, 2).toUpperCase();
}
