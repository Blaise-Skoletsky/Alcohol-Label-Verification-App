import { useEffect, useMemo, useRef, useState } from "react";
import {
  ApiError,
  getBatch,
  submitBatch,
  verifyRow as verifyRowRequest,
  type BatchRowPayload,
} from "../api/client";
import { formatTimestamp } from "../lib/format";
import { normalizeResultCore } from "../lib/resultNormalization";
import { findArray, findRecord, findString } from "../lib/objectLookup";
import { normalizeStatus } from "../lib/status";
import type {
  BeverageClass,
  FieldKey,
  FieldSummary,
  LabelRow,
  UiStatus,
} from "../types/verification";

let rowCounter = 0;

function nextId(): string {
  rowCounter += 1;
  return `row-${Date.now().toString(36)}-${rowCounter}`;
}

export type NewRowInput = Partial<
  Pick<
    LabelRow,
    | "brand"
    | "beverageClass"
    | "classType"
    | "abv"
    | "net"
    | "nameAddr"
    | "country"
    | "maltAddedNonbeverageAlcohol"
    | "maltColorAdditiveApplicable"
    | "fileName"
    | "imageUrl"
    | "imageFile"
    | "sampleUrl"
    | "flagged"
  >
>;

export function makeRow(input: NewRowInput = {}): LabelRow {
  const localId = nextId();
  const createdAtMs = Date.now();
  return {
    localId,
    createdAtMs,
    createdOrder: rowCounter,
    brand: input.brand ?? "",
    beverageClass: input.beverageClass ?? "spirits",
    classType: input.classType ?? "",
    abv: input.abv ?? "",
    net: input.net ?? "",
    nameAddr: input.nameAddr ?? "",
    country: input.country ?? "",
    maltAddedNonbeverageAlcohol: input.maltAddedNonbeverageAlcohol ?? false,
    maltColorAdditiveApplicable: input.maltColorAdditiveApplicable ?? false,
    fileName: input.fileName ?? (input.imageFile?.name ?? ""),
    imageUrl: input.imageUrl ?? null,
    imageFile: input.imageFile ?? null,
    sampleUrl: input.sampleUrl ?? null,
    status: "draft",
    fields: null,
    summary: "Not verified yet.",
    modifiedAtMs: createdAtMs,
    modifiedAtLabel: formatTimestamp(createdAtMs),
    verificationStartedAtMs: null,
    verificationCompletedAtMs: null,
    flagged: input.flagged ?? false,
    edited: false,
    dirtyFields: [],
  };
}

export function rowReady(row: LabelRow): boolean {
  const hasImage = Boolean(row.imageFile || row.sampleUrl);
  if (!hasImage) return false;

  const baseReady = [row.brand, row.classType, row.net, row.nameAddr, row.country].every(
    (value) => value.trim().length > 0,
  );
  if (!baseReady) return false;

  if (row.beverageClass === "spirits") return row.abv.trim().length > 0;
  if (row.beverageClass === "malt") {
    return !row.maltAddedNonbeverageAlcohol || row.abv.trim().length > 0;
  }
  return isTableOrLightWine(row.classType) || row.abv.trim().length > 0;
}

function rowValues(row: LabelRow): BatchRowPayload {
  return {
    filename: row.fileName,
    brand_name: row.brand,
    beverage_class: row.beverageClass,
    class_type_designation: row.classType,
    alcohol_content: row.abv,
    net_contents: row.net,
    name_address: row.nameAddr,
    country_of_origin: row.country,
    malt_added_nonbeverage_alcohol: row.maltAddedNonbeverageAlcohol,
    malt_color_additive_applicable: row.maltColorAdditiveApplicable,
  };
}

function isTableOrLightWine(value: string): boolean {
  return /\b(table|light)\s+wine\b/i.test(value);
}

async function ensureFile(row: LabelRow): Promise<File | null> {
  if (row.imageFile) return row.imageFile;
  if (row.sampleUrl) {
    const response = await fetch(row.sampleUrl);
    if (!response.ok) return null;
    const blob = await response.blob();
    const name = row.fileName || row.sampleUrl.split("/").pop() || "label.png";
    return new File([blob], name, { type: blob.type || "image/png" });
  }
  return null;
}

function mapItemStatus(raw: string | null | undefined): UiStatus {
  const normalized = (raw ?? "").toLowerCase();
  if (normalized === "queued") return "queued";
  if (normalized === "processing") return "processing";
  return normalizeStatus(raw);
}

export type StatusCounts = {
  total: number;
  pass: number;
  fail: number;
  edited: number;
  notRun: number;
};

type Notify = (message: string) => void;

export function useLabelRows(notify: Notify) {
  const [rows, setRows] = useState<LabelRow[]>([]);
  const [activeBatchId, setActiveBatchId] = useState<string | null>(null);
  const rowsRef = useRef<LabelRow[]>([]);

  useEffect(() => {
    rowsRef.current = rows;
  }, [rows]);

  const statusCounts = useMemo<StatusCounts>(() => {
    const counts: StatusCounts = { total: rows.length, pass: 0, fail: 0, edited: 0, notRun: 0 };
    for (const row of rows) {
      if (row.edited && row.fields) counts.edited += 1;
      else if (row.status === "pass") counts.pass += 1;
      else if (row.status === "fail" || row.status === "processing-error") counts.fail += 1;
      else counts.notRun += 1;
    }
    return counts;
  }, [rows]);

  function patchRow(id: string, patch: Partial<LabelRow>) {
    setRows((current) => current.map((row) => (row.localId === id ? { ...row, ...patch } : row)));
  }

  function editRow(id: string, patch: NewRowInput) {
    const modified = modificationPatch();
    setRows((current) =>
      current.map((row) =>
        row.localId === id
          ? {
              ...row,
              ...patch,
              ...modified,
              edited: true,
              dirtyFields: mergeDirtyFields(row.dirtyFields ?? [], dirtyFieldKeysForPatch(patch)),
            }
          : row,
      ),
    );
  }

  function attachImage(id: string, file: File) {
    const modified = modificationPatch();
    setRows((current) =>
      current.map((row) => {
        if (row.localId !== id) return row;
        if (row.imageUrl && row.imageUrl.startsWith("blob:")) URL.revokeObjectURL(row.imageUrl);
        return {
          ...row,
          imageFile: file,
          imageUrl: URL.createObjectURL(file),
          fileName: file.name,
          sampleUrl: null,
          flagged: false,
          ...modified,
          edited: true,
        };
      }),
    );
  }

  function addBlankRow(): string {
    const row = makeRow();
    setRows((current) => [...current, row]);
    return row.localId;
  }

  function removeRows(ids: string[]) {
    const targetIds = new Set(ids);
    if (targetIds.size === 0) return;
    setRows((current) => {
      for (const row of current) {
        if (targetIds.has(row.localId) && row.imageUrl && row.imageUrl.startsWith("blob:")) {
          URL.revokeObjectURL(row.imageUrl);
        }
      }
      const next = current.filter((row) => !targetIds.has(row.localId));
      rowsRef.current = next;
      return next;
    });
  }

  function removeRow(id: string) {
    removeRows([id]);
  }

  function replaceRows(next: LabelRow[]) {
    setRows((current) => {
      for (const row of current) {
        if (row.imageUrl && row.imageUrl.startsWith("blob:")) URL.revokeObjectURL(row.imageUrl);
      }
      return next;
    });
    setActiveBatchId(null);
  }

  // Replace the workspace with `next`, then immediately verify the given rows.
  // Used by the batch-upload flow ("Verify N labels"): every row lands in the
  // workspace, but only the complete/matched subset starts verifying — the rest
  // stay as drafts for later.
  function replaceAndVerify(next: LabelRow[], verifyIds: string[]) {
    setRows((current) => {
      for (const row of current) {
        if (row.imageUrl && row.imageUrl.startsWith("blob:")) URL.revokeObjectURL(row.imageUrl);
      }
      return next;
    });
    // verifyRows reads from rowsRef synchronously, so seed it before calling.
    rowsRef.current = next;
    setActiveBatchId(null);
    if (verifyIds.length > 0) verifyRows(verifyIds);
  }

  async function verifySingle(id: string) {
    const row = rowsRef.current.find((entry) => entry.localId === id);
    if (!row) return;
    const file = await ensureFile(row);
    if (!file) {
      patchRow(id, { flagged: true });
      notify("Attach an image before verifying this label.");
      return;
    }
    const updatedAtMs = Date.now();
    patchRow(id, {
      status: "processing",
      summary: "Verifying this label…",
      modifiedAtMs: updatedAtMs,
      modifiedAtLabel: formatTimestamp(updatedAtMs),
      verificationStartedAtMs: updatedAtMs,
      edited: false,
      dirtyFields: [],
    });
    try {
      const payload = await verifyRowRequest(file, rowValues(row));
      const core = normalizeResultCore(payload);
      patchRow(id, {
        status: core.status,
        fields: core.fields,
        summary: core.summary,
        modifiedAtMs: core.updatedAtMs,
        modifiedAtLabel: core.updatedAtLabel,
        verificationCompletedAtMs: core.updatedAtMs,
        serverId: findString(payload, ["item_id", "id"]) ?? row.serverId,
      });
    } catch (error) {
      const updatedAtMs = Date.now();
      patchRow(id, {
        status: "processing-error",
        summary: friendlyError(error, "We could not verify this label. Please try again."),
        modifiedAtMs: updatedAtMs,
        modifiedAtLabel: formatTimestamp(updatedAtMs),
        verificationCompletedAtMs: updatedAtMs,
      });
    }
  }

  async function verifyViaBatch(ids: string[]) {
    const targets = rowsRef.current.filter((row) => ids.includes(row.localId));
    const files: File[] = [];
    const payloadRows: BatchRowPayload[] = [];
    const orderedIds: string[] = [];

    for (const row of targets) {
      const file = await ensureFile(row);
      if (!file) {
        patchRow(row.localId, { flagged: true });
        continue;
      }
      files.push(file);
      payloadRows.push(rowValues(row));
      orderedIds.push(row.localId);
    }

    if (files.length === 0) {
      notify("None of the selected labels have an image yet.");
      return;
    }

    const updatedAtMs = Date.now();
    setRows((current) =>
      current.map((row) =>
        orderedIds.includes(row.localId)
          ? {
              ...row,
              status: "processing",
              summary: "Verifying…",
              modifiedAtMs: updatedAtMs,
              modifiedAtLabel: formatTimestamp(updatedAtMs),
              verificationStartedAtMs: updatedAtMs,
              edited: false,
              dirtyFields: [],
            }
          : row,
      ),
    );

    try {
      const response = await submitBatch(files, payloadRows);
      const batchId = findString(response, ["batch_id", "batchId", "id"]);
      const items = findArray(response, ["items"]) ?? [];
      if (!batchId) throw new Error("missing batch id");

      setRows((current) =>
        current.map((row) => {
          const index = orderedIds.indexOf(row.localId);
          if (index === -1) return row;
          const item = items[index];
          const serverId = item ? findString(item, ["item_id", "id"]) : null;
          return { ...row, batchId, serverId: serverId ?? row.serverId };
        }),
      );
      setActiveBatchId(batchId);
      notify(
        `Verifying ${files.length} label${files.length === 1 ? "" : "s"} — results stream in as each completes.`,
      );
    } catch (error) {
      const updatedAtMs = Date.now();
      setRows((current) =>
        current.map((row) =>
          orderedIds.includes(row.localId)
            ? {
                ...row,
                status: "processing-error",
                summary: friendlyError(error, "We could not start the batch."),
                modifiedAtMs: updatedAtMs,
                modifiedAtLabel: formatTimestamp(updatedAtMs),
                verificationCompletedAtMs: updatedAtMs,
              }
            : row,
        ),
      );
    }
  }

  function verifyRows(ids: string[]) {
    if (ids.length === 0) return;
    if (ids.length === 1) {
      void verifySingle(ids[0]);
    } else {
      void verifyViaBatch(ids);
    }
  }

  async function pollBatch(batchId: string) {
    try {
      const payload = await getBatch(batchId);
      const items = findArray(payload, ["items"]) ?? [];
      const lifecycle = findString(payload, ["status"]);

      setRows((current) =>
        current.map((row) => {
          if (row.batchId !== batchId || !row.serverId) return row;
          const item = items.find((entry) => findString(entry, ["item_id", "id"]) === row.serverId);
          if (!item) return row;
          const result = findRecord(item, ["result"]);
          if (result) {
            const core = normalizeResultCore(result);
            const resultChanged = hasResultChanged(row, core.status, core.summary, core.fields);
            const modifiedAtMs = resultChanged ? core.updatedAtMs : row.modifiedAtMs;
            return {
              ...row,
              status: core.status,
              fields: core.fields,
              summary: core.summary,
              modifiedAtMs,
              modifiedAtLabel: resultChanged ? core.updatedAtLabel : row.modifiedAtLabel,
              verificationCompletedAtMs: resultChanged
                ? core.updatedAtMs
                : row.verificationCompletedAtMs,
            };
          }
          return { ...row, status: mapItemStatus(findString(item, ["status"])) };
        }),
      );

      if (lifecycle === "completed") {
        setActiveBatchId((current) => (current === batchId ? null : current));
      }
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        setActiveBatchId((current) => (current === batchId ? null : current));
      }
    }
  }

  useEffect(() => {
    if (!activeBatchId) return;
    const id = window.setInterval(() => void pollBatch(activeBatchId), 2000);
    void pollBatch(activeBatchId);
    return () => window.clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeBatchId]);

  return {
    rows,
    statusCounts,
    editRow,
    attachImage,
    addBlankRow,
    removeRow,
    removeRows,
    replaceRows,
    replaceAndVerify,
    verifyRows,
  };
}

function friendlyError(error: unknown, fallback: string): string {
  if (error instanceof ApiError && error.message.trim().length > 0) return error.message;
  return fallback;
}

function modificationPatch(atMs = Date.now()): Pick<LabelRow, "modifiedAtMs" | "modifiedAtLabel"> {
  return {
    modifiedAtMs: atMs,
    modifiedAtLabel: formatTimestamp(atMs),
  };
}

function dirtyFieldKeysForPatch(patch: NewRowInput): FieldKey[] {
  const keys = new Set<FieldKey>();
  if ("brand" in patch) keys.add("brand_name");
  if ("classType" in patch) keys.add("class_type_designation");
  if ("abv" in patch) keys.add("alcohol_content");
  if ("net" in patch) keys.add("net_contents");
  if ("nameAddr" in patch) keys.add("name_address");
  if ("country" in patch) keys.add("country_of_origin");
  if ("maltAddedNonbeverageAlcohol" in patch) keys.add("alcohol_content");
  if ("maltColorAdditiveApplicable" in patch) keys.add("color_additive_disclosure");
  if ("beverageClass" in patch) {
    keys.add("class_type_designation");
    keys.add("alcohol_content");
    keys.add("color_additive_disclosure");
  }
  return [...keys];
}

function mergeDirtyFields(current: FieldKey[], next: FieldKey[]): FieldKey[] {
  if (next.length === 0) return current;
  return [...new Set([...current, ...next])];
}

function hasResultChanged(
  row: LabelRow,
  status: UiStatus,
  summary: string,
  fields: FieldSummary[],
): boolean {
  return row.status !== status || row.summary !== summary || !sameFields(row.fields, fields);
}

function sameFields(current: FieldSummary[] | null, next: FieldSummary[]): boolean {
  if (!current || current.length !== next.length) return false;
  return JSON.stringify(current) === JSON.stringify(next);
}

export const BEVERAGE_CLASS_LABELS: Record<BeverageClass, string> = {
  spirits: "Distilled spirits",
  wine: "Wine",
  malt: "Malt beverage",
};
