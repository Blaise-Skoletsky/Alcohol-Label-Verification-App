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
import type { BeverageClass, LabelRow, UiStatus } from "../types/verification";

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
    | "fileName"
    | "imageUrl"
    | "imageFile"
    | "sampleUrl"
    | "flagged"
  >
>;

export function makeRow(input: NewRowInput = {}): LabelRow {
  return {
    localId: nextId(),
    brand: input.brand ?? "",
    beverageClass: input.beverageClass ?? "spirits",
    classType: input.classType ?? "",
    abv: input.abv ?? "",
    net: input.net ?? "",
    nameAddr: input.nameAddr ?? "",
    country: input.country ?? "",
    fileName: input.fileName ?? (input.imageFile?.name ?? ""),
    imageUrl: input.imageUrl ?? null,
    imageFile: input.imageFile ?? null,
    sampleUrl: input.sampleUrl ?? null,
    status: "draft",
    fields: null,
    summary: "Not verified yet.",
    updatedAtLabel: "—",
    flagged: input.flagged ?? false,
    edited: false,
  };
}

const EDITABLE_FIELDS = ["brand", "classType", "net", "nameAddr"] as const;

export function rowReady(row: LabelRow): boolean {
  const hasImage = Boolean(row.imageFile || row.sampleUrl);
  return hasImage && EDITABLE_FIELDS.every((key) => String(row[key] || "").trim().length > 0);
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
  };
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
    const counts: StatusCounts = { total: rows.length, pass: 0, fail: 0, notRun: 0 };
    for (const row of rows) {
      if (row.status === "pass") counts.pass += 1;
      else if (row.status === "fail" || row.status === "processing-error") counts.fail += 1;
      else counts.notRun += 1;
    }
    return counts;
  }, [rows]);

  function patchRow(id: string, patch: Partial<LabelRow>) {
    setRows((current) => current.map((row) => (row.localId === id ? { ...row, ...patch } : row)));
  }

  function editRow(id: string, patch: NewRowInput) {
    setRows((current) =>
      current.map((row) => (row.localId === id ? { ...row, ...patch, edited: true } : row)),
    );
  }

  function attachImage(id: string, file: File) {
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

  function removeRow(id: string) {
    setRows((current) => {
      const target = current.find((row) => row.localId === id);
      if (target?.imageUrl && target.imageUrl.startsWith("blob:")) URL.revokeObjectURL(target.imageUrl);
      return current.filter((row) => row.localId !== id);
    });
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

  async function verifySingle(id: string) {
    const row = rowsRef.current.find((entry) => entry.localId === id);
    if (!row) return;
    const file = await ensureFile(row);
    if (!file) {
      patchRow(id, { flagged: true });
      notify("Attach an image before verifying this label.");
      return;
    }
    patchRow(id, { status: "processing", summary: "Verifying this label…", edited: false });
    try {
      const payload = await verifyRowRequest(file, rowValues(row));
      const core = normalizeResultCore(payload);
      patchRow(id, {
        status: core.status,
        fields: core.fields,
        summary: core.summary,
        updatedAtLabel: core.updatedAtLabel,
        serverId: findString(payload, ["item_id", "id"]) ?? row.serverId,
      });
    } catch (error) {
      patchRow(id, {
        status: "processing-error",
        summary: friendlyError(error, "We could not verify this label. Please try again."),
        updatedAtLabel: formatTimestamp(Date.now()),
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

    setRows((current) =>
      current.map((row) =>
        orderedIds.includes(row.localId)
          ? { ...row, status: "processing", summary: "Verifying…", edited: false }
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
      setRows((current) =>
        current.map((row) =>
          orderedIds.includes(row.localId)
            ? {
                ...row,
                status: "processing-error",
                summary: friendlyError(error, "We could not start the batch."),
                updatedAtLabel: formatTimestamp(Date.now()),
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
            return {
              ...row,
              status: core.status,
              fields: core.fields,
              summary: core.summary,
              updatedAtLabel: core.updatedAtLabel,
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
    replaceRows,
    verifyRows,
  };
}

function friendlyError(error: unknown, fallback: string): string {
  if (error instanceof ApiError && error.message.trim().length > 0) return error.message;
  return fallback;
}

export const BEVERAGE_CLASS_LABELS: Record<BeverageClass, string> = {
  spirits: "Distilled spirits",
  wine: "Wine",
  malt: "Malt beverage",
};
