import { FIELD_DEFS, type BatchItem, type FieldSummary, type UiStatus } from "../types/verification";
import { camelCase, formatTimestamp } from "./format";
import {
  findArray,
  findNestedRecord,
  findNumber,
  findRecord,
  findString,
  isRecord,
} from "./objectLookup";
import {
  defaultReasonForStatus,
  isPendingStatus,
  normalizeStatus,
  STATUS_LABELS,
} from "./status";

type BatchUpdate = Pick<
  BatchItem,
  | "localId"
  | "serverId"
  | "fileName"
  | "status"
  | "overallLabel"
  | "summary"
  | "updatedAtLabel"
  | "fields"
  | "rawResult"
  | "errorMessage"
  | "isPolling"
>;

export function normalizeSingleResult(payload: unknown, localItem: BatchItem): BatchItem {
  const status = normalizeStatusFromUnknown(payload);
  const fields = extractFieldSummaries(payload);
  const summary = buildSummary(status, fields, payload);

  return {
    ...localItem,
    serverId:
      findString(payload, ["item_id", "itemId", "id", "verification_id"]) ?? localItem.serverId,
    status,
    overallLabel: STATUS_LABELS[status],
    summary,
    updatedAtLabel: extractUpdatedAt(payload),
    fields,
    rawResult: payload,
    errorMessage: getFriendlyError(payload),
    isPolling: false,
  };
}

export function normalizeBatchResponse(payload: unknown, existingItems: BatchItem[]) {
  const records = findArray(payload, ["items", "results", "entries", "labels"]);
  if (!records) {
    return [];
  }

  return records.map((record, index) => {
    const matchedItem = matchLocalItem(record, index, existingItems);
    const result = findRecord(record, ["result"]);
    const resultSource = result ?? record;
    const fields = extractFieldSummaries(resultSource);
    const status = normalizeStatusFromUnknown(resultSource);
    return {
      localId: matchedItem?.localId,
      serverId:
        findString(record, ["item_id", "itemId", "id"]) ??
        findString(resultSource, ["item_id", "itemId", "id"]) ??
        matchedItem?.serverId ??
        `batch-item-${index}`,
      fileName:
        findString(record, ["file_name", "filename", "name", "artifact_name"]) ??
        findString(resultSource, ["file_name", "filename", "name", "artifact_name"]) ??
        matchedItem?.fileName ??
        `File ${index + 1}`,
      status,
      overallLabel: STATUS_LABELS[status],
      summary: buildSummary(status, fields, resultSource),
      updatedAtLabel: extractUpdatedAt(resultSource),
      fields,
      rawResult: resultSource,
      errorMessage: getFriendlyError(resultSource),
      isPolling: isPendingStatus(status),
    };
  });
}

export function mergeBatchUpdates(
  currentItems: BatchItem[],
  updates: BatchUpdate[],
  batchId: string,
) {
  return currentItems.map((item) => {
    if (item.batchId !== batchId) {
      return item;
    }

    const update =
      updates.find((entry) => entry.localId && entry.localId === item.localId) ??
      updates.find((entry) => entry.serverId && entry.serverId === item.serverId) ??
      updates.find((entry) => entry.fileName === item.fileName);

    if (!update) {
      return item;
    }

    return {
      ...item,
      serverId: update.serverId ?? item.serverId,
      fileName: update.fileName,
      status: update.status,
      overallLabel: update.overallLabel,
      summary: update.summary,
      updatedAtLabel: update.updatedAtLabel,
      fields: update.fields,
      rawResult: update.rawResult,
      errorMessage: update.errorMessage,
      isPolling: update.isPolling,
    };
  });
}

export function getBatchId(payload: unknown) {
  return findString(payload, ["batch_id", "batchId", "id"]);
}

function matchLocalItem(record: unknown, index: number, existingItems: BatchItem[]) {
  const serverId = findString(record, ["item_id", "itemId", "id"]);
  if (serverId) {
    const byServerId = existingItems.find((item) => item.serverId === serverId);
    if (byServerId) {
      return byServerId;
    }
  }

  const fileName = findString(record, ["file_name", "filename", "name", "artifact_name"]);
  if (fileName) {
    const byName = existingItems.find((item) => item.fileName === fileName);
    if (byName) {
      return byName;
    }
  }

  return existingItems[index];
}

// The API exposes more granular field names than the three the UI tracks
// (most notably `alcohol_content` for what the UI calls "abv"). Map each UI
// field to every API key it may arrive under so real results populate.
const FIELD_SOURCE_KEYS: Record<FieldSummary["key"], string[]> = {
  artifact_legibility: ["artifact_legibility", "artifactLegibility", "legibility"],
  brand_name: ["brand_name", "brandName", "brand"],
  class_type_designation: ["class_type_designation", "classTypeDesignation", "class_type", "classType"],
  alcohol_content: ["alcohol_content", "alcoholContent", "abv", "alcohol"],
  net_contents: ["net_contents", "netContents", "net_content", "contents"],
  name_address: ["name_address", "nameAddress", "name_and_address", "nameAndAddress"],
  country_of_origin: ["country_of_origin", "countryOfOrigin", "country"],
  government_warning: ["government_warning", "governmentWarning", "warning"],
};

function extractFieldSummaries(source: unknown): FieldSummary[] {
  const container =
    findRecord(source, ["fields", "checks", "requirements", "summary"]) ??
    (isRecord(source) ? source : null);

  return FIELD_DEFS.map((definition) => {
    const fieldSource =
      FIELD_SOURCE_KEYS[definition.key]
        .map((key) => findNestedRecord(container, key))
        .find((record) => record !== null) ??
      findNestedRecord(container, camelCase(definition.key)) ??
      findNestedRecord(container, definition.label.toLowerCase().replace(/\s+/g, "_"));
    const status = normalizeFieldStatus(fieldSource, source);

    return {
      key: definition.key,
      label: definition.label,
      status,
      applicationValue:
        findString(fieldSource, ["application_value", "applicationValue", "expected_value", "expected"]) ??
        "Not provided",
      labelValue:
        findString(fieldSource, ["label_value", "labelValue", "observed_value", "observed", "value"]) ??
        "Not provided",
      reason:
        findString(fieldSource, ["reason", "message", "notes", "detail"]) ??
        findString(source, [`${definition.key}_reason`]) ??
        defaultReasonForStatus(status),
      evidence: extractEvidence(fieldSource),
    };
  });
}

function normalizeFieldStatus(fieldSource: unknown, fallback: unknown): UiStatus {
  const rawStatus =
    findString(fieldSource, ["status", "result", "decision"]) ??
    findString(fallback, ["overall_status", "status"]);
  return normalizeStatus(rawStatus);
}

function buildSummary(status: UiStatus, fields: FieldSummary[], payload: unknown) {
  const explicit =
    findString(payload, ["summary", "message", "overall_reason", "detail"]) ??
    findString(findRecord(payload, ["result", "output"]), ["summary", "message"]);
  if (explicit) {
    return explicit;
  }

  if (status === "processing-error") {
    return "This file could not be processed.";
  }

  if (isPendingStatus(status)) {
    return "This file is still being reviewed.";
  }

  const failedFields = fields.filter((field) => field.status === "fail").map((field) => field.label);
  const reviewFields = fields
    .filter((field) => field.status === "needs-review")
    .map((field) => field.label);

  if (status === "pass") {
    return "All reviewed fields passed.";
  }
  if (failedFields.length > 0) {
    return `Check ${failedFields.join(", ")}.`;
  }
  if (reviewFields.length > 0) {
    return `Manual review needed for ${reviewFields.join(", ")}.`;
  }
  return "Review complete.";
}

function getFriendlyError(source: unknown) {
  return (
    findString(source, ["error_message", "error", "detail", "message"]) ??
    findString(findRecord(source, ["error_details", "errorDetails"]), ["message", "detail"]) ??
    ""
  );
}

function extractEvidence(source: unknown) {
  const evidenceArray =
    findArray(source, ["evidence", "reasons", "citations"]) ??
    findArray(findRecord(source, ["evidence_details", "evidenceDetails"]), ["items"]);

  if (!evidenceArray) {
    const singleEvidence = findString(source, ["evidence_text", "evidenceText"]);
    return singleEvidence ? [singleEvidence] : [];
  }

  return evidenceArray
    .map((entry) => {
      if (typeof entry === "string") {
        return entry;
      }
      return findString(entry, ["text", "message", "detail", "value"]) ?? JSON.stringify(entry);
    })
    .filter((entry) => entry.trim().length > 0);
}

function extractUpdatedAt(source: unknown) {
  const timestamp =
    findString(source, ["updated_at", "updatedAt", "completed_at", "completedAt", "created_at"]) ??
    "";
  if (!timestamp) {
    return formatTimestamp(Date.now());
  }
  const parsed = Date.parse(timestamp);
  if (Number.isNaN(parsed)) {
    return formatTimestamp(Date.now());
  }
  return formatTimestamp(parsed);
}

function normalizeStatusFromUnknown(source: unknown) {
  const rawStatus =
    findString(source, ["status", "overall_status", "overallStatus", "decision", "result"]) ??
    findString(findRecord(source, ["result", "output"]), ["status", "decision"]);
  return normalizeStatus(rawStatus);
}
