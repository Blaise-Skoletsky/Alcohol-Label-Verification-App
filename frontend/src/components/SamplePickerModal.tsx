import { useEffect, useRef, useState } from "react";
import { SAMPLES, type SampleEntry } from "../generated/sampleLabels";

type SampleCategory = "pass" | "fail";
type FilterKey = "all" | SampleCategory;

const BADGE_LABELS: Record<SampleCategory, string> = {
  pass: "Should pass",
  fail: "Should fail",
};

const FILTER_DEFS: { key: FilterKey; label: string }[] = [
  { key: "all", label: "All" },
  { key: "pass", label: "Should pass" },
  { key: "fail", label: "Should fail" },
];

function getSampleCategory(sample: SampleEntry): SampleCategory {
  const folder = sample.file.split("/", 1)[0];
  if (folder === "pass" || folder === "fail") {
    return folder;
  }
  throw new Error(`Sample label must live under pass/ or fail/: ${sample.file}`);
}

type Props = {
  open: boolean;
  onClose: () => void;
  onLoad: (entries: SampleEntry[]) => void;
};

export function SamplePickerModal({ open, onClose, onLoad }: Props) {
  const [selected, setSelected] = useState<string[]>([]);
  const [filter, setFilter] = useState<FilterKey>("all");
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  const counts: Record<FilterKey, number> = {
    all: SAMPLES.length,
    pass: SAMPLES.filter((sample) => getSampleCategory(sample) === "pass").length,
    fail: SAMPLES.filter((sample) => getSampleCategory(sample) === "fail").length,
  };

  const visible =
    filter === "all" ? SAMPLES : SAMPLES.filter((sample) => getSampleCategory(sample) === filter);

  function toggle(id: string) {
    setSelected((prev) => (prev.includes(id) ? prev.filter((entry) => entry !== id) : [...prev, id]));
  }

  const visibleIds = visible.map((s) => s.id);
  const allVisibleSelected = visibleIds.length > 0 && visibleIds.every((id) => selected.includes(id));

  function toggleSelectAll() {
    if (allVisibleSelected) {
      setSelected((prev) => prev.filter((id) => !visibleIds.includes(id)));
    } else {
      setSelected((prev) => [...new Set([...prev, ...visibleIds])]);
    }
  }

  function handleLoad() {
    if (selected.length === 0) return;
    const entries = selected
      .map((id) => SAMPLES.find((sample) => sample.id === id))
      .filter((entry): entry is SampleEntry => Boolean(entry));
    setSelected([]);
    onClose();
    onLoad(entries);
  }

  const n = selected.length;
  const runLabel = n === 0 ? "Select labels" : `Load ${n} label${n === 1 ? "" : "s"}`;

  return (
    <div
      className="sample-overlay"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="Sample label picker"
    >
      <div ref={dialogRef} className="sample-dialog" onClick={(e) => e.stopPropagation()}>
        <div className="sample-header">
          <div className="sample-header-top">
            <div>
              <div className="sample-title-row">
                <h2>Sample labels</h2>
                <span className="demo-chip">DEMO</span>
              </div>
              <p className="sample-subtitle">
                Handpicked labels that load into the batch with editable application data already
                filled in. Pick the ones you want.
              </p>
            </div>
            <button type="button" className="sample-close" onClick={onClose} aria-label="Close">
              X
            </button>
          </div>

          <div className="sample-filter-bar">
            <div className="sample-filter-pills">
              {FILTER_DEFS.map((pill) => (
                <button
                  key={pill.key}
                  type="button"
                  className={`sample-pill${filter === pill.key ? " active" : ""}`}
                  onClick={() => setFilter(pill.key)}
                >
                  {pill.label}
                  <span className="sample-pill-count">{counts[pill.key]}</span>
                </button>
              ))}
            </div>
            <button type="button" className="sample-select-all-btn" onClick={toggleSelectAll}>
              {allVisibleSelected ? "Deselect all" : "Select all"}
            </button>
          </div>
        </div>

        <div className="sample-grid-region">
          <div className="sample-grid">
            {visible.map((entry) => {
              const isSelected = selected.includes(entry.id);
              const category = getSampleCategory(entry);
              return (
                <button
                  key={entry.id}
                  type="button"
                  className={`sample-card${isSelected ? " selected" : ""}`}
                  onClick={() => toggle(entry.id)}
                >
                  <div className="sample-card-preview">
                    <img src={`/sample_labels/${entry.file}`} alt={entry.brand} />
                    <span className={`sample-check-indicator${isSelected ? " selected" : ""}`}>
                      {isSelected ? (
                        <svg width="13" height="13" viewBox="0 0 14 14" fill="none" aria-hidden="true">
                          <path
                            d="M11.5 3.5L5.5 10L2.5 7"
                            stroke="#fff"
                            strokeWidth={2}
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          />
                        </svg>
                      ) : null}
                    </span>
                  </div>
                  <div className="sample-card-body">
                    <div className="sample-card-title-row">
                      <span className="sample-card-brand">{entry.brand}</span>
                      <span className={`sample-cat-badge ${category}`}>
                        {BADGE_LABELS[category]}
                      </span>
                    </div>
                    <div className="sample-card-file">{entry.file.split("/").pop()}</div>
                    <p className="sample-card-desc">{entry.desc}</p>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        <div className="sample-footer">
          <div className="sample-footer-summary">
            {n === 0 ? "No labels selected" : `${n} label${n === 1 ? "" : "s"} selected`}
          </div>
          <div className="sample-footer-actions">
            <button type="button" className="sample-cancel-btn" onClick={onClose}>
              Cancel
            </button>
            <button
              type="button"
              className="sample-run-btn"
              disabled={n === 0}
              onClick={handleLoad}
            >
              {runLabel}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
