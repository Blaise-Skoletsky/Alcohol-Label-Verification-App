import { useMemo, useState } from "react";
import type { BatchItem, UiStatus } from "../types/verification";
import { ResultsList } from "./ResultsList";

type ResultFilter = "all" | "queued" | "processing" | "pass" | "fail" | "needs-review";

type ResultsPanelProps = {
  items: BatchItem[];
  statusCounts: Record<UiStatus, number>;
  onOpenDetails: (index: number) => void;
};

export function ResultsPanel({ items, statusCounts, onOpenDetails }: ResultsPanelProps) {
  const [activeFilter, setActiveFilter] = useState<ResultFilter>("all");
  const filteredItems = useMemo(
    () => items.filter((item) => matchesFilter(item, activeFilter)),
    [activeFilter, items],
  );

  return (
    <section className="results-panel">
      <div className="results-header">
        <div>
          <h2>Results</h2>
          <p className="supporting-text">
            Click any row to view the file and the verification detail.
          </p>
        </div>
        <div className="status-filter-group" aria-label="Filter results by status">
          {renderFilterButton("all", "All", items.length, activeFilter, setActiveFilter)}
          {renderFilterButton("queued", "Queued", statusCounts.queued, activeFilter, setActiveFilter)}
          {renderFilterButton(
            "processing",
            "Processing",
            statusCounts.processing,
            activeFilter,
            setActiveFilter,
          )}
          {renderFilterButton("pass", "Pass", statusCounts.pass, activeFilter, setActiveFilter)}
          {renderFilterButton(
            "fail",
            "Fail",
            statusCounts.fail + statusCounts["processing-error"],
            activeFilter,
            setActiveFilter,
          )}
          {renderFilterButton(
            "needs-review",
            "Needs review",
            statusCounts["needs-review"],
            activeFilter,
            setActiveFilter,
          )}
        </div>
      </div>

      {items.length === 0 ? (
        <div className="empty-state">
          <h3>No applications uploaded yet</h3>
          <p>Upload applications to begin. Results will appear here as each review finishes.</p>
        </div>
      ) : filteredItems.length === 0 ? (
        <div className="empty-state">
          <h3>No results match this filter</h3>
          <p>Choose another status above to see more results.</p>
        </div>
      ) : (
        <ResultsList items={filteredItems} onOpenDetails={(index) => {
          const originalIndex = items.findIndex((item) => item.localId === filteredItems[index].localId);
          if (originalIndex >= 0) {
            onOpenDetails(originalIndex);
          }
        }} />
      )}
    </section>
  );
}

function renderFilterButton(
  filter: ResultFilter,
  label: string,
  count: number,
  activeFilter: ResultFilter,
  setActiveFilter: (filter: ResultFilter) => void,
) {
  const isActive = activeFilter === filter;
  return (
    <button
      type="button"
      className={`filter-button${isActive ? " active" : ""}`}
      aria-pressed={isActive}
      onClick={() => setActiveFilter(filter)}
    >
      <span>{label}</span>
      <strong>{count}</strong>
    </button>
  );
}

function matchesFilter(item: BatchItem, filter: ResultFilter) {
  if (filter === "all") {
    return true;
  }
  if (filter === "fail") {
    return item.status === "fail" || item.status === "processing-error";
  }
  return item.status === filter;
}
