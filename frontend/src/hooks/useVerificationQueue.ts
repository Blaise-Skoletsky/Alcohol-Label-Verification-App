import { useEffect, useMemo, useRef, useState } from "react";
import { ApiError, getBatch, submitBatch as submitBatchRequest, verifySingle } from "../api/client";
import { createLocalItem, validateFiles } from "../lib/fileValidation";
import { formatTimestamp } from "../lib/format";
import {
  getBatchId,
  mergeBatchUpdates,
  normalizeBatchResponse,
  normalizeSingleResult,
} from "../lib/resultNormalization";
import { isPendingStatus, STATUS_LABELS } from "../lib/status";
import type { AppConfig } from "../types/config";
import type { BatchItem, UiStatus } from "../types/verification";

export function useVerificationQueue(config: AppConfig) {
  const [items, setItems] = useState<BatchItem[]>([]);
  const [formError, setFormError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [activeBatchId, setActiveBatchId] = useState<string | null>(null);
  const itemsRef = useRef<BatchItem[]>([]);

  useEffect(() => {
    itemsRef.current = items;
  }, [items]);

  useEffect(() => {
    if (!activeBatchId) {
      return;
    }

    const intervalId = window.setInterval(() => {
      void pollBatch(activeBatchId);
    }, 2500);

    void pollBatch(activeBatchId);

    return () => window.clearInterval(intervalId);
  }, [activeBatchId]);

  useEffect(() => {
    const hasInFlight = items.some(
      (item) => item.batchId === activeBatchId && isPendingStatus(item.status),
    );
    if (activeBatchId && !hasInFlight) {
      setActiveBatchId(null);
    }
  }, [activeBatchId, items]);

  const statusCounts = useMemo(() => {
    const counts: Record<UiStatus, number> = {
      queued: 0,
      processing: 0,
      pass: 0,
      fail: 0,
      "needs-review": 0,
      "processing-error": 0,
    };

    for (const item of items) {
      counts[item.status] += 1;
    }

    return counts;
  }, [items]);

  function handleFiles(files: File[]) {
    const validationError = validateFiles(files, config);
    if (validationError) {
      setFormError(validationError);
      return { accepted: false, addedCount: 0 };
    }

    setFormError("");
    setIsSubmitting(true);

    const newItems = files.map(createLocalItem);
    setItems((currentItems) => [...newItems, ...currentItems]);

    void (async () => {
      try {
        if (files.length === 1) {
          await submitSingle(files[0], newItems[0]);
        } else {
          await submitBatch(files, newItems);
        }
      } finally {
        setIsSubmitting(false);
      }
    })();

    return { accepted: true, addedCount: newItems.length };
  }

  async function pollBatch(batchId: string) {
    try {
      const payload = await getBatch(batchId);
      const updates = normalizeBatchResponse(payload, itemsRef.current);

      if (updates.length === 0) {
        return;
      }

      setItems((currentItems) => mergeBatchUpdates(currentItems, updates, batchId));
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        markBatchPollingFailed(
          batchId,
          "This batch is no longer available. Please upload the files again.",
          friendlyErrorMessage(error, "The review service could not find this batch."),
        );
        setActiveBatchId((currentBatchId) => (currentBatchId === batchId ? null : currentBatchId));
        return;
      }

      setItems((currentItems) =>
        currentItems.map((item) => {
          if (item.batchId !== batchId || !isPendingStatus(item.status)) {
            return item;
          }
          return {
            ...item,
            isPolling: false,
            summary:
              "We are still waiting for an update from the service. Please try again shortly.",
          };
        }),
      );
    }
  }

  function markBatchPollingFailed(batchId: string, summary: string, errorMessage: string) {
    setItems((currentItems) =>
      currentItems.map((item) => {
        if (item.batchId !== batchId || !isPendingStatus(item.status)) {
          return item;
        }
        return {
          ...item,
          status: "processing-error",
          overallLabel: STATUS_LABELS["processing-error"],
          summary,
          errorMessage,
          updatedAtLabel: formatTimestamp(Date.now()),
          isPolling: false,
        };
      }),
    );
  }

  async function submitSingle(file: File, localItem: BatchItem) {
    setItems((currentItems) =>
      currentItems.map((item) =>
        item.localId === localItem.localId
          ? {
              ...item,
              status: "processing",
              summary: "This file is being reviewed now.",
            }
          : item,
      ),
    );

    try {
      const payload = await verifySingle(file);
      const normalizedItem = normalizeSingleResult(payload, localItem);

      setItems((currentItems) =>
        currentItems.map((item) => (item.localId === localItem.localId ? normalizedItem : item)),
      );
    } catch (error) {
      markItemsFailed(
        new Set([localItem.localId]),
        "We could not complete this review. Please try the file again.",
        friendlyErrorMessage(
          error,
          "The review service did not return a usable result for this file.",
        ),
      );
    }
  }

  async function submitBatch(files: File[], localItems: BatchItem[]) {
    try {
      const payload = await submitBatchRequest(files);
      const batchId = getBatchId(payload);

      if (!batchId) {
        throw new Error("missing-batch-id");
      }

      setItems((currentItems) =>
        currentItems.map((item) => {
          const index = localItems.findIndex((localItem) => localItem.localId === item.localId);
          if (index === -1) {
            return item;
          }
          return {
            ...item,
            batchId,
            serverId: item.serverId ?? `local-${batchId}-${index}`,
            status: "queued",
            summary: "This file is in line for review.",
            updatedAtLabel: formatTimestamp(Date.now()),
            isPolling: true,
          };
        }),
      );
      setActiveBatchId(batchId);
    } catch (error) {
      markItemsFailed(
        new Set(localItems.map((item) => item.localId)),
        "We could not start the batch review. Please try again.",
        friendlyErrorMessage(error, "The review service did not accept the selected batch."),
      );
    }
  }

  function markItemsFailed(failedIds: Set<string>, summary: string, errorMessage: string) {
    setItems((currentItems) =>
      currentItems.map((item) =>
        failedIds.has(item.localId)
          ? {
              ...item,
              status: "processing-error",
              overallLabel: STATUS_LABELS["processing-error"],
              summary,
              errorMessage,
              updatedAtLabel: formatTimestamp(Date.now()),
              isPolling: false,
            }
          : item,
      ),
    );
  }

  return {
    items,
    statusCounts,
    formError,
    isSubmitting,
    handleFiles,
  };
}

function friendlyErrorMessage(error: unknown, fallback: string) {
  if (error instanceof ApiError && error.message.trim().length > 0) {
    return error.message;
  }
  return fallback;
}
