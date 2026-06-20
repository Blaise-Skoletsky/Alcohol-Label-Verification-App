import { useEffect, useMemo, useRef, useState } from "react";
import { BatchGridModal } from "./components/BatchGridModal";
import { DetailModal } from "./components/DetailModal";
import { LabelListView } from "./components/LabelListView";
import { SamplePickerModal } from "./components/SamplePickerModal";
import { Sidebar } from "./components/Sidebar";
import { TutorialModal } from "./components/TutorialModal";
import { makeRow, useLabelRows } from "./hooks/useLabelRows";
import { loadDemoBatchRows, type DemoBatchGridRow } from "./lib/demoBatch";
import type { SampleEntry } from "./generated/sampleLabels";
import type { LabelRow } from "./types/verification";

type Filter = "all" | "pass" | "fail" | "edited" | "draft";

function matchesFilter(row: LabelRow, filter: Filter): boolean {
  const edited = row.edited && Boolean(row.fields);
  if (filter === "all") return true;
  if (filter === "edited") return edited;
  if (edited) return false;
  if (filter === "pass") return row.status === "pass";
  if (filter === "fail") return row.status === "fail" || row.status === "processing-error";
  return row.status === "draft" || row.status === "processing" || row.status === "queued";
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
  const [toast, setToast] = useState("");
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

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
    replaceAndVerify,
    verifyRows,
  } = useLabelRows(notify);

  const [filter, setFilter] = useState<Filter>("all");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [detailId, setDetailId] = useState<string | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [batchPhotos, setBatchPhotos] = useState<File[] | null>(null);
  const [demoBatchRows, setDemoBatchRows] = useState<DemoBatchGridRow[] | null>(null);
  const [demoBatchLoading, setDemoBatchLoading] = useState(false);
  const [tutorialOpen, setTutorialOpen] = useState(false);

  useEffect(() => {
    try {
      if (/tutorial/i.test(location.hash) || /[?&]tutorial(=|&|$)/i.test(location.search)) {
        setTutorialOpen(true);
      }
    } catch {
      // ignore
    }
  }, []);

  const visibleRows = useMemo(
    () => rows.filter((row) => matchesFilter(row, filter)),
    [rows, filter],
  );

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

  function changeFilter(nextFilter: Filter) {
    if (nextFilter !== filter) {
      clearSelection();
    }
    setFilter(nextFilter);
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

  function openAddLabel() {
    const id = addBlankRow();
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
          counts={statusCounts}
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

              <div className="toolbar-right">
                {selected.size > 0 ? (
                  <span className="selection-summary">
                    <span className="selection-count">{selected.size} selected</span>
                    <button type="button" className="selection-clear" onClick={clearSelection}>
                      Clear
                    </button>
                    <span className="selection-divider" />
                  </span>
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

          <div className="table-region">
            <LabelListView
              rows={visibleRows}
              selected={selected}
              allSelected={allSelected}
              onToggleAll={toggleSelectAll}
              onToggle={toggleSelect}
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
          onClose={() => setDetailId(null)}
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

      {tutorialOpen ? <TutorialModal onClose={() => setTutorialOpen(false)} /> : null}

      {toast ? (
        <div className="toast">
          <span className="toast-dot" aria-hidden="true" />
          {toast}
        </div>
      ) : null}
    </>
  );
}
