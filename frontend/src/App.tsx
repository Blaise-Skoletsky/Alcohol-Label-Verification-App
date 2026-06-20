import { useEffect, useMemo, useRef, useState } from "react";
import { BatchUploadModal } from "./components/BatchUploadModal";
import { DetailModal } from "./components/DetailModal";
import { LabelGridView } from "./components/LabelGridView";
import { LabelListView } from "./components/LabelListView";
import { SamplePickerModal } from "./components/SamplePickerModal";
import { Sidebar } from "./components/Sidebar";
import { TutorialModal } from "./components/TutorialModal";
import { makeRow, useLabelRows } from "./hooks/useLabelRows";
import type { SampleEntry } from "./generated/sampleLabels";
import type { LabelRow } from "./types/verification";

type View = "list" | "grid";
type Filter = "all" | "pass" | "fail" | "draft";

function matchesFilter(row: LabelRow, filter: Filter): boolean {
  if (filter === "all") return true;
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

  const { rows, statusCounts, editRow, attachImage, addBlankRow, replaceRows, verifyRows } =
    useLabelRows(notify);

  const [view, setView] = useState<View>("list");
  const [filter, setFilter] = useState<Filter>("all");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [detailId, setDetailId] = useState<string | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
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

  // ---- primary action (contextual) ----
  const draftIds = rows.filter((row) => row.status === "draft").map((row) => row.localId);
  const failIds = rows
    .filter((row) => row.status === "fail" || row.status === "processing-error")
    .map((row) => row.localId);
  const selectedIds = [...selected];

  let primaryLabel = "Verify";
  let primaryAction: (() => void) | null = null;

  if (selectedIds.length > 0) {
    const anyDraft = rows.some(
      (row) => selected.has(row.localId) && (row.status === "draft" || row.status === "processing-error"),
    );
    primaryLabel = `${anyDraft ? "Verify" : "Re-run"} ${selectedIds.length} selected`;
    primaryAction = () => {
      verifyRows(selectedIds);
      clearSelection();
    };
  } else if (draftIds.length > 0) {
    primaryLabel = `Verify ${draftIds.length} new`;
    primaryAction = () => verifyRows(draftIds);
  } else if (failIds.length > 0) {
    primaryLabel = `Re-run failed (${failIds.length})`;
    primaryAction = () => verifyRows(failIds);
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
    replaceRows(entries.map(entryToRow));
    setSelected(new Set());
    setDetailId(null);
    setFilter("all");
    notify(
      `Loaded ${entries.length} sample label${entries.length === 1 ? "" : "s"} as drafts — edit any field, then verify.`,
    );
  }

  function importRows(importedRows: LabelRow[], summary: string) {
    replaceRows(importedRows);
    setSelected(new Set());
    setDetailId(null);
    setFilter("all");
    setImportOpen(false);
    notify(summary);
  }

  const filters: { key: Filter; label: string; count: number }[] = [
    { key: "all", label: "All", count: statusCounts.total },
    { key: "pass", label: "Pass", count: statusCounts.pass },
    { key: "fail", label: "Fail", count: statusCounts.fail },
    { key: "draft", label: "Not run", count: statusCounts.notRun },
  ];

  return (
    <>
      <div className="app-shell">
        <Sidebar
          counts={statusCounts}
          onAddLabel={openAddLabel}
          onBatchUpload={() => setImportOpen(true)}
          onUseSamples={() => setPickerOpen(true)}
        />

        <main className="main">
          <div className="main-top">
            <div className="main-top-row">
              <button
                type="button"
                className="primary-action"
                disabled={!primaryAction}
                onClick={() => primaryAction?.()}
              >
                {primaryLabel}
              </button>
            </div>

            <div className="toolbar">
              <div className="filter-pills">
                {filters.map((pill) => (
                  <button
                    key={pill.key}
                    type="button"
                    className={`filter-pill${filter === pill.key ? " active" : ""}`}
                    onClick={() => setFilter(pill.key)}
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
                <div className="view-toggle">
                  <button
                    type="button"
                    className={`view-seg${view === "list" ? " active" : ""}`}
                    onClick={() => setView("list")}
                  >
                    List
                  </button>
                  <button
                    type="button"
                    className={`view-seg${view === "grid" ? " active" : ""}`}
                    onClick={() => setView("grid")}
                  >
                    Spreadsheet
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div className="table-region">
            {view === "list" ? (
              <LabelListView
                rows={visibleRows}
                selected={selected}
                allSelected={allSelected}
                onToggleAll={toggleSelectAll}
                onToggle={toggleSelect}
                onOpen={setDetailId}
              />
            ) : (
              <LabelGridView
                rows={visibleRows}
                onEdit={editRow}
                onRerun={(id) => verifyRows([id])}
                onAddRow={() => addBlankRow()}
              />
            )}
          </div>
        </main>
      </div>

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

      {importOpen ? (
        <BatchUploadModal
          onClose={() => setImportOpen(false)}
          onImport={importRows}
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
