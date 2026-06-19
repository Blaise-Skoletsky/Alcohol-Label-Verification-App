import type { AppConfig } from "../types/config";
import type { BatchItem, FieldSummary } from "../types/verification";
import { FIELD_DEFS } from "../types/verification";
import { formatTimestamp } from "./format";
import { STATUS_LABELS } from "./status";

export function validateFiles(files: File[], config: AppConfig) {
  if (files.length > config.maxBatchLabels) {
    return `Please select ${config.maxBatchLabels} files or fewer.`;
  }

  const allowedExtensions = new Set(config.allowedFileTypes.map((value) => value.toLowerCase()));
  for (const file of files) {
    const extension = getExtension(file.name);
    if (!allowedExtensions.has(extension)) {
      return `${file.name} is not an accepted file type.`;
    }

    const maxBytes = config.maxUploadMb * 1024 * 1024;
    if (file.size > maxBytes) {
      return `${file.name} is larger than the ${config.maxUploadMb} MB limit.`;
    }
  }

  return "";
}

export function createLocalItem(file: File): BatchItem {
  const now = Date.now();
  return {
    localId: `${file.name}-${now}-${Math.random().toString(36).slice(2, 8)}`,
    fileName: file.name,
    fileSize: file.size,
    mimeType: file.type || inferMimeType(file.name),
    previewUrl: URL.createObjectURL(file),
    status: "queued",
    overallLabel: STATUS_LABELS.queued,
    summary: "Waiting to start review.",
    updatedAtLabel: formatTimestamp(now),
    fields: buildDefaultFields(),
    isPolling: false,
  };
}

export function buildDefaultFields(): FieldSummary[] {
  return FIELD_DEFS.map((field) => ({
    key: field.key,
    label: field.label,
    status: "queued",
    applicationValue: "Waiting for result",
    labelValue: "Waiting for result",
    confidence: "Not available yet",
    reason: "This check has not completed yet.",
    evidence: [],
  }));
}

export function getExtension(fileName: string) {
  const parts = fileName.toLowerCase().split(".");
  return parts.length > 1 ? `.${parts[parts.length - 1]}` : "";
}

function inferMimeType(fileName: string) {
  const extension = getExtension(fileName);
  if (extension === ".pdf") {
    return "application/pdf";
  }
  if (extension === ".png") {
    return "image/png";
  }
  return "image/jpeg";
}
