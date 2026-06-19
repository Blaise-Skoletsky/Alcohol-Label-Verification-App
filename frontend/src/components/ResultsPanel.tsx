import { useRef, useState } from "react";
import type { AppConfig } from "../types/config";
import type { BatchItem, UiStatus } from "../types/verification";
import { DemoInfoModal } from "./DemoInfoModal";
import { ResultsList } from "./ResultsList";

export type ResultFilter = "all" | "pass" | "needs-review" | "fail";

export function matchesFilter(item: BatchItem, filter: ResultFilter) {
  if (filter === "all") return true;
  if (filter === "fail") return item.status === "fail" || item.status === "processing-error";
  return item.status === filter;
}

type ResultsPanelProps = {
  items: BatchItem[];
  filteredItems: BatchItem[];
  statusCounts: Record<UiStatus, number>;
  activeFilter: ResultFilter;
  onFilterChange: (filter: ResultFilter) => void;
  onOpenDetails: (index: number) => void;
  config: AppConfig;
  isSubmitting: boolean;
  onFilesChosen: (files: File[]) => { accepted: boolean; addedCount: number };
  onAcceptedFiles: (count: number) => void;
};

export function ResultsPanel({ items, filteredItems, statusCounts, activeFilter, onFilterChange, onOpenDetails, config, isSubmitting, onFilesChosen, onAcceptedFiles }: ResultsPanelProps) {
  const uploadInputRef = useRef<HTMLInputElement | null>(null);

  function handleUploadChange(event: React.ChangeEvent<HTMLInputElement>) {
    const fileList = event.target.files;
    if (!fileList || fileList.length === 0) return;
    const result = onFilesChosen(Array.from(fileList));
    if (result.accepted) onAcceptedFiles(result.addedCount);
    event.target.value = "";
  }
  const [infoOpen, setInfoOpen] = useState(false);

  const failedCount = statusCounts.fail + statusCounts["processing-error"];
  const reviewCount = statusCounts["needs-review"];

  return (
    <section className="results-panel">
      <header className="main-header">
        <div className="main-header-row">
          <div>
            <h1>Open Applications</h1>
            <p className="main-subtitle">
              Every application you&apos;ve submitted and where it stands. Click a row to see the
              evidence.
            </p>
          </div>
          <button type="button" className="info-button" onClick={() => setInfoOpen(true)}>
            <span className="info-button-icon" aria-hidden="true">
              i
            </span>
            Demo info
          </button>
        </div>
      </header>

      <div className="stats-row">
        <StatCard label="Total" value={items.length} />
        <StatCard label="Passed" value={statusCounts.pass} tone="pass" />
        <StatCard label="Needs review" value={reviewCount} tone="review" />
        <StatCard label="Failed" value={failedCount} tone="fail" />
      </div>

      <div className="filter-pills" aria-label="Filter results by status">
        <FilterPill
          label="All"
          count={items.length}
          filter="all"
          activeFilter={activeFilter}
          onSelect={onFilterChange}
        />
        <FilterPill
          label="Passed"
          count={statusCounts.pass}
          filter="pass"
          activeFilter={activeFilter}
          onSelect={onFilterChange}
        />
        <FilterPill
          label="Needs review"
          count={reviewCount}
          filter="needs-review"
          activeFilter={activeFilter}
          onSelect={onFilterChange}
        />
        <FilterPill
          label="Failed"
          count={failedCount}
          filter="fail"
          activeFilter={activeFilter}
          onSelect={onFilterChange}
        />
      </div>

      <div className="table-region">
        {items.length === 0 ? (
          <div className="empty-state">
            <h3>No open applications</h3>
            <p>Upload your own labels, or try the demo with sample labels from the data set.</p>
            <input
              ref={uploadInputRef}
              type="file"
              accept={config.allowedFileTypes.join(",")}
              multiple
              className="sr-only"
              onChange={handleUploadChange}
              disabled={isSubmitting}
            />
            <button
              type="button"
              className="empty-state-sample-btn"
              onClick={() => uploadInputRef.current?.click()}
              disabled={isSubmitting}
            >
              Upload labels
            </button>
          </div>
        ) : filteredItems.length === 0 ? (
          <div className="empty-state">
            <h3>No results match this filter</h3>
            <p>Choose another status above to see more results.</p>
          </div>
        ) : (
          <ResultsList
            items={filteredItems}
            onOpenDetails={(index) => {
              const originalIndex = items.findIndex(
                (item) => item.localId === filteredItems[index].localId,
              );
              if (originalIndex >= 0) {
                onOpenDetails(originalIndex);
              }
            }}
          />
        )}
      </div>

      <DemoInfoModal open={infoOpen} onClose={() => setInfoOpen(false)} />
    </section>
  );
}

type StatCardProps = {
  label: string;
  value: number;
  tone?: "pass" | "review" | "fail";
};

function StatCard({ label, value, tone }: StatCardProps) {
  return (
    <div className="stat-card">
      <div className="stat-label">
        {tone ? <span className={`stat-dot tone-${tone}`} aria-hidden="true" /> : null}
        {label}
      </div>
      <div className={`stat-number${tone ? ` tone-${tone}` : ""}`}>{value}</div>
    </div>
  );
}

type FilterPillProps = {
  label: string;
  count: number;
  filter: ResultFilter;
  activeFilter: ResultFilter;
  onSelect: (filter: ResultFilter) => void;
};

function FilterPill({ label, count, filter, activeFilter, onSelect }: FilterPillProps) {
  const isActive = activeFilter === filter;
  return (
    <button
      type="button"
      className={`filter-pill${isActive ? " active" : ""}`}
      aria-pressed={isActive}
      onClick={() => onSelect(filter)}
    >
      {label}
      <span className="filter-pill-count">{count}</span>
    </button>
  );
}
