import { useEffect, useMemo, useRef, useState } from "react";
import { BatchGridModal } from "./components/BatchGridModal";
import { DetailModal } from "./components/DetailModal";
import { LabelListView } from "./components/LabelListView";
import { SamplePickerModal } from "./components/SamplePickerModal";
import { Sidebar } from "./components/Sidebar";
import { TutorialModal } from "./components/TutorialModal";
import { useAppConfig } from "./hooks/useAppConfig";
import { makeRow, useLabelRows } from "./hooks/useLabelRows";
import { loadDemoBatchRows, type DemoBatchGridRow } from "./lib/demoBatch";
import type { SampleEntry } from "./generated/sampleLabels";
import type { LabelRow } from "./types/verification";

type Filter = "all" | "pass" | "fail" | "edited" | "draft";
type SortDirection = "asc" | "desc";

function matchesFilter(row: LabelRow, filter: Filter): boolean {
  const edited = row.edited && Boolean(row.fields);
  if (filter === "all") return true;
  if (filter === "edited") return edited;
  if (edited) return false;
  if (filter === "pass") return row.status === "pass";
  if (filter === "fail") return row.status === "fail" || row.status === "processing-error";
  return row.status === "draft" || row.status === "processing" || row.status === "queued";
}

function matchesSearch(row: LabelRow, query: string): boolean {
  const needle = query.trim().toLowerCase();
  if (!needle) return true;

  return [row.brand, row.fileName].some((value) =>
    value.toLowerCase().includes(needle),
  );
}

function compareUpdatedRows(a: LabelRow, b: LabelRow, direction: SortDirection): number {
  const aHasDate = a.modifiedAtMs > 0;
  const bHasDate = b.modifiedAtMs > 0;
  if (aHasDate !== bHasDate) return aHasDate ? -1 : 1;
  if (aHasDate && bHasDate && a.modifiedAtMs !== b.modifiedAtMs) {
    return direction === "asc" ? a.modifiedAtMs - b.modifiedAtMs : b.modifiedAtMs - a.modifiedAtMs;
  }
  return a.createdOrder - b.createdOrder;
}

function isEmptyManualDraft(row: LabelRow): boolean {
  if (row.status !== "draft" || row.edited) return false;
  if (row.imageFile || row.imageUrl || row.sampleUrl) return false;

  return [row.brand, row.classType, row.abv, row.net, row.nameAddr, row.country, row.fileName].every(
    (value) => value.trim().length === 0,
  );
}

function entryToRow(entry: SampleEntry): LabelRow {
  const values = entry.applicationValues;
  const fileName = entry.file.split("/").pop() ?? entry.file;
  const url = `/sample_labels/${entry.file}`;
  return makeRow({
    brand: values.brand_name,
    beverageClass: values.beverage_class,
    classType: values.class_type_designation,
    abv: values.alcohol_content,
    net: values.net_contents,
    nameAddr: values.name_address,
    country: values.country_of_origin,
    maltAddedNonbeverageAlcohol: values.malt_added_nonbeverage_alcohol ?? false,
    maltColorAdditiveApplicable: values.malt_color_additive_applicable ?? false,
    fileName,
    imageUrl: url,
    sampleUrl: url,
  });
}

export function App() {
  const { config } = useAppConfig();
  const [toast, setToast] = useState("");
  const toastBelowModal = /^Loaded \d+ hosted sample rows\./.test(toast);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const tutorialRequestHandled = useRef(false);

  function notify(message: string) {
    setToast(message);
    if (toastTimer.current !== null) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(""), 3200);
  }

  useEffect(() => () => {
    if (toastTimer.current !== null) clearTimeout(toastTimer.current);
  }, []);

  const {
    rows,
    statusCounts,
    editRow,
    attachImage,
    addBlankRow,
    removeRows,
    replaceAndVerify,
    verifyRows,
  } = useLabelRows(notify);

  const [filter, setFilter] = useState<Filter>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [updatedSortDirection, setUpdatedSortDirection] = useState<SortDirection>("desc");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [detailId, setDetailId] = useState<string | null>(null);
  const [manualDraftIds, setManualDraftIds] = useState<Set<string>>(new Set());
  const [pickerOpen, setPickerOpen] = useState(false);
  const [batchPhotos, setBatchPhotos] = useState<File[] | null>(null);
  const [demoBatchRows, setDemoBatchRows] = useState<DemoBatchGridRow[] | null>(null);
  const [demoBatchLoading, setDemoBatchLoading] = useState(false);
  const [tutorialOpen, setTutorialOpen] = useState(false);

  useEffect(() => {
    try {
      if (tutorialRequestHandled.current) return;
      const tutorialRequested =
        /tutorial/i.test(location.hash) || /[?&]tutorial(=|&|$)/i.test(location.search);
      if (!tutorialRequested) {
        tutorialRequestHandled.current = true;
        return;
      }
      if (
        config.environment.toLowerCase() === "production" &&
        config.tutorialVideoUrl
      ) {
        setTutorialOpen(true);
        tutorialRequestHandled.current = true;
      }
    } catch {
      // ignore
    }
  }, [config.environment, config.tutorialVideoUrl]);

  const visibleRows = useMemo(() => {
    const filteredRows = rows
      .filter((row) => matchesFilter(row, filter))
      .filter((row) => matchesSearch(row, searchQuery));
    return [...filteredRows].sort((a, b) => compareUpdatedRows(a, b, updatedSortDirection));
  }, [rows, filter, searchQuery, updatedSortDirection]);

  const emptyState = useMemo(() => {
    if (rows.length === 0) {
      return {
        title: "Nothing here yet",
        body: "Add labels or load the sample set to get started.",
      };
    }

    if (searchQuery.trim().length > 0) {
      return {
        title: "No matching labels",
        body: "Try another brand, name, or file.",
      };
    }

    return {
      title: "No labels in this view",
      body: "Try another status.",
    };
  }, [rows.length, searchQuery]);

  // Keep the selection clean of rows that no longer exist.
  useEffect(() => {
    setSelected((current) => {
      const ids = new Set(rows.map((row) => row.localId));
      const next = new Set([...current].filter((id) => ids.has(id)));
      return next.size === current.size ? current : next;
    });
  }, [rows]);

  const visibleIds = visibleRows.map((row) => row.localId);
  const allSelected = visibleIds.length > 0 && visibleIds.every((id) => selected.has(id));

  function toggleSelect(id: string) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleSelectAll() {
    setSelected((current) => {
      if (allSelected) {
        const next = new Set(current);
        for (const id of visibleIds) next.delete(id);
        return next;
      }
      return new Set([...current, ...visibleIds]);
    });
  }

  function clearSelection() {
    setSelected(new Set());
  }

  function clearRows(ids: string[]) {
    if (ids.length === 0) return;
    removeRows(ids);
    setSelected((current) => {
      const targetIds = new Set(ids);
      return new Set([...current].filter((id) => !targetIds.has(id)));
    });
    setManualDraftIds((current) => {
      const targetIds = new Set(ids);
      const next = new Set([...current].filter((id) => !targetIds.has(id)));
      return next.size === current.size ? current : next;
    });
    if (detailId && ids.includes(detailId)) setDetailId(null);
  }

  function clearSelectedRows() {
    clearRows([...selected]);
  }

  function changeFilter(nextFilter: Filter) {
    if (nextFilter !== filter) {
      clearSelection();
    }
    setFilter(nextFilter);
  }

  function toggleUpdatedSort() {
    setUpdatedSortDirection((current) => (current === "desc" ? "asc" : "desc"));
  }

  // ---- primary action (contextual) ----
  const draftIds = rows.filter((row) => row.status === "draft").map((row) => row.localId);
  const selectedIds = [...selected];

  let primaryLabel = "Verify";
  let primaryAction: (() => void) | null = null;

  if (selectedIds.length > 0) {
    primaryLabel = `Verify ${selectedIds.length} selected`;
    primaryAction = () => {
      verifyRows(selectedIds);
      clearSelection();
    };
  } else if (draftIds.length > 0) {
    primaryLabel = `Verify ${draftIds.length} new`;
    primaryAction = () => verifyRows(draftIds);
  } else if (rows.length > 0) {
    primaryLabel = "Re-verify all";
    primaryAction = () => verifyRows(rows.map((row) => row.localId));
  }

  // ---- detail navigation ----
  const detailRow = detailId ? rows.find((row) => row.localId === detailId) ?? null : null;
  const detailIndex = detailRow
    ? visibleRows.findIndex((row) => row.localId === detailRow.localId)
    : -1;

  function moveDetail(direction: -1 | 1) {
    if (detailIndex === -1) return;
    const next = visibleRows[detailIndex + direction];
    if (next) setDetailId(next.localId);
  }

  function closeDetail() {
    const manualRows = rows.filter((row) => manualDraftIds.has(row.localId));
    if (manualRows.length > 0) {
      const manualRowIds = new Set(manualRows.map((row) => row.localId));
      const emptyIds = manualRows.filter(isEmptyManualDraft).map((row) => row.localId);
      setManualDraftIds((current) => {
        const next = new Set([...current].filter((id) => !manualRowIds.has(id)));
        return next;
      });
      clearRows(emptyIds);
    }
    setDetailId(null);
  }

  function openAddLabel() {
    const id = addBlankRow();
    setManualDraftIds((current) => new Set(current).add(id));
    setDetailId(id);
  }

  function loadSamples(entries: SampleEntry[]) {
    const sampleRows = entries.map(entryToRow);
    replaceAndVerify(sampleRows, sampleRows.map((row) => row.localId));
    setSelected(new Set());
    setDetailId(null);
    setFilter("all");
    notify(
      `Verifying ${entries.length} sample label${entries.length === 1 ? "" : "s"} now.`,
    );
  }

  // Batch upload completion: every row lands in the workspace, but only the
  // complete/matched subset (verifyIds) starts verifying immediately.
  function completeBatch(allRows: LabelRow[], verifyIds: string[], summary: string) {
    replaceAndVerify(allRows, verifyIds);
    setSelected(new Set());
    setDetailId(null);
    setFilter("all");
    setBatchPhotos(null);
    setDemoBatchRows(null);
    notify(summary);
  }

  function startBatchUpload(files: File[]) {
    if (files.length === 0) return;
    setDemoBatchRows(null);
    setBatchPhotos(files);
  }

  async function loadDemoBatch(manifestUrl: string) {
    if (!manifestUrl || demoBatchLoading) return;
    setDemoBatchLoading(true);
    try {
      const rows = await loadDemoBatchRows(manifestUrl);
      setBatchPhotos(null);
      setDemoBatchRows(rows);
      notify(`Loaded ${rows.length} hosted sample rows. Review them, then verify.`);
    } catch (error) {
      notify(error instanceof Error ? error.message : "We could not load the hosted sample batch.");
    } finally {
      setDemoBatchLoading(false);
    }
  }

  const filters: { key: Filter; label: string; count: number }[] = [
    { key: "all", label: "All", count: statusCounts.total },
    { key: "pass", label: "Pass", count: statusCounts.pass },
    { key: "fail", label: "Fail", count: statusCounts.fail },
    { key: "edited", label: "Edited", count: statusCounts.edited },
    { key: "draft", label: "Not verified", count: statusCounts.notRun },
  ];

  return (
    <>
      <div className="app-shell">
        <Sidebar
          config={config}
          onAddLabel={openAddLabel}
          onBatchUpload={startBatchUpload}
          onUseSamples={() => setPickerOpen(true)}
          onLoadDemoBatch={loadDemoBatch}
        />

        <main className="main">
          <div className="main-top">
            <div className="toolbar">
              <div className="filter-pills">
                {filters.map((pill) => (
                  <button
                    key={pill.key}
                    type="button"
                    className={`filter-pill${filter === pill.key ? " active" : ""}`}
                    onClick={() => changeFilter(pill.key)}
                  >
                    {pill.label}
                    <span className="filter-pill-count">{pill.count}</span>
                  </button>
                ))}
              </div>

              <div className="toolbar-lower">
                <div className="table-search">
                  <input
                    type="text"
                    className="table-search-input"
                    aria-label="Search Applications"
                    placeholder="Search Applications"
                    value={searchQuery}
                    onChange={(event) => setSearchQuery(event.target.value)}
                  />
                  {searchQuery ? (
                    <button
                      type="button"
                      className="table-search-clear"
                      aria-label="Clear filter"
                      onClick={() => setSearchQuery("")}
                    >
                      X
                    </button>
                  ) : null}
                </div>

                <div className="toolbar-right">
                  {selected.size > 0 ? (
                    <span className="selection-summary">
                      <span className="selection-count">{selected.size} selected</span>
                      <button type="button" className="selection-clear" onClick={clearSelection}>
                        Deselect
                      </button>
                      <span className="selection-divider" />
                    </span>
                  ) : null}
                  {selected.size > 0 ? (
                    <button
                      type="button"
                      className="clear-selected-action"
                      onClick={clearSelectedRows}
                    >
                      Clear selected
                    </button>
                  ) : null}
                  <button
                    type="button"
                    className="primary-action"
                    disabled={!primaryAction}
                    onClick={() => primaryAction?.()}
                  >
                    {primaryLabel}
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div className="table-region">
            <LabelListView
              rows={visibleRows}
              selected={selected}
              allSelected={allSelected}
              sortDirection={updatedSortDirection}
              emptyStateTitle={emptyState.title}
              emptyStateBody={emptyState.body}
              onToggleAll={toggleSelectAll}
              onToggleUpdatedSort={toggleUpdatedSort}
              onToggle={toggleSelect}
              onRemove={clearRows}
              onOpen={setDetailId}
            />
          </div>
        </main>
      </div>

      {demoBatchLoading ? (
        <div className="demo-batch-loading" role="status" aria-live="polite">
          <div className="demo-batch-loading-panel">
            <span className="demo-batch-loading-spinner" aria-hidden="true" />
            <span className="demo-batch-loading-copy">
              <span>Loading hosted sample batch...</span>
              <span>
                This demonstration includes a balanced mix of labels expected to pass and
                labels expected to fail.
              </span>
            </span>
          </div>
        </div>
      ) : null}

      {detailRow ? (
        <DetailModal
          row={detailRow}
          index={detailIndex}
          total={visibleRows.length}
          onClose={closeDetail}
          onPrev={() => moveDetail(-1)}
          onNext={() => moveDetail(1)}
          onEdit={editRow}
          onAttachImage={attachImage}
          onAction={(id) => verifyRows([id])}
        />
      ) : null}

      <SamplePickerModal
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        onLoad={loadSamples}
      />

      {batchPhotos ? (
        <BatchGridModal
          initialPhotos={batchPhotos}
          onStartOver={() => setBatchPhotos(null)}
          onClose={() => setBatchPhotos(null)}
          onComplete={completeBatch}
          onError={notify}
        />
      ) : null}

      {demoBatchRows ? (
        <BatchGridModal
          initialPhotos={[]}
          initialRows={demoBatchRows}
          onStartOver={() => setDemoBatchRows(null)}
          onClose={() => setDemoBatchRows(null)}
          onComplete={completeBatch}
          onError={notify}
        />
      ) : null}

      {tutorialOpen && config.tutorialVideoUrl ? (
        <TutorialModal
          videoUrl={config.tutorialVideoUrl}
          onClose={() => setTutorialOpen(false)}
        />
      ) : null}

      {toast ? (
        <div className={`toast${toastBelowModal ? " toast-below-modal" : ""}`}>
          <span className="toast-dot" aria-hidden="true" />
          {toast}
        </div>
      ) : null}
    </>
  );
}
