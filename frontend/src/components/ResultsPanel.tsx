import { useMemo, useState } from "react";
import type { BatchItem, UiStatus } from "../types/verification";
import { ResultsList } from "./ResultsList";

type ResultFilter = "all" | "pass" | "needs-review" | "fail";

type ResultsPanelProps = {
  items: BatchItem[];
  statusCounts: Record<UiStatus, number>;
  onOpenDetails: (index: number) => void;
};

export function ResultsPanel({ items, statusCounts, onOpenDetails }: ResultsPanelProps) {
  const [activeFilter, setActiveFilter] = useState<ResultFilter>("all");

  const failedCount = statusCounts.fail + statusCounts["processing-error"];
  const reviewCount = statusCounts["needs-review"];

  const filteredItems = useMemo(
    () => items.filter((item) => matchesFilter(item, activeFilter)),
    [activeFilter, items],
  );

  return (
    <section className="results-panel">
      <header className="main-header">
        <h1>Open Applications</h1>
        <p className="main-subtitle">
          Every application you&apos;ve submitted and where it stands. Click a row to see the
          evidence.
        </p>
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
          onSelect={setActiveFilter}
        />
        <FilterPill
          label="Passed"
          count={statusCounts.pass}
          filter="pass"
          activeFilter={activeFilter}
          onSelect={setActiveFilter}
        />
        <FilterPill
          label="Needs review"
          count={reviewCount}
          filter="needs-review"
          activeFilter={activeFilter}
          onSelect={setActiveFilter}
        />
        <FilterPill
          label="Failed"
          count={failedCount}
          filter="fail"
          activeFilter={activeFilter}
          onSelect={setActiveFilter}
        />
      </div>

      <div className="table-region">
        {items.length === 0 ? (
          <div className="empty-state">
            <h3>No open applications</h3>
            <p>
              Use &ldquo;Upload labels&rdquo; to add a batch. Each label is checked independently.
            </p>
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

function matchesFilter(item: BatchItem, filter: ResultFilter) {
  if (filter === "all") {
    return true;
  }
  if (filter === "fail") {
    return item.status === "fail" || item.status === "processing-error";
  }
  return item.status === filter;
}
