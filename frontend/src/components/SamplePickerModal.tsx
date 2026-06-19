import { useEffect, useRef, useState } from "react";

type SampleCategory = "pass" | "review" | "fail";
type FilterKey = "all" | SampleCategory;

interface SampleEntry {
  id: string;
  brand: string;
  file: string;
  cat: SampleCategory;
  desc: string;
}

const SAMPLES: SampleEntry[] = [
  {
    id: "jd",
    brand: "Jack Daniel's Winter Jack",
    file: "pass/jack_daniel_s_2013-04-24.png",
    cat: "pass",
    desc: "Clean application and label values for a straightforward pass case.",
  },
  {
    id: "casa",
    brand: "Casamigos Tequila",
    file: "pass/casamigos_2014-03-09.png",
    cat: "pass",
    desc: "Spirits label with matching brand, class, warning, and contents.",
  },
  {
    id: "m47b",
    brand: "Monkey 47 Dry Gin",
    file: "pass/monkey_47_2014-03-28.png",
    cat: "pass",
    desc: "Imported gin sample with complete mandatory label details.",
  },
  {
    id: "coyam",
    brand: "Coyam (Chile)",
    file: "pass/coyam_2011-03-30.png",
    cat: "pass",
    desc: "Wine label sample with expected matching application data.",
  },
  {
    id: "nat",
    brand: "Natura Cabernet",
    file: "needs-review/natura_2011-07-25.png",
    cat: "review",
    desc: "Wine label where one or more details should require human review.",
  },
  {
    id: "gek",
    brand: "Gekkeikan Sake",
    file: "needs-review/gekkeikan_2013-01-04.png",
    cat: "review",
    desc: "Imported sake example with fields that may need closer inspection.",
  },
  {
    id: "chick",
    brand: "Chicken Dinner Red",
    file: "needs-review/chicken_dinner_2012-07-30.png",
    cat: "review",
    desc: "Wine sample intended to surface ambiguous or incomplete fields.",
  },
  {
    id: "howl",
    brand: "Howling Moon Moonshine",
    file: "needs-review/howling_moon_2012-01-06.png",
    cat: "review",
    desc: "Spirits sample where the model should avoid over-confident approval.",
  },
  {
    id: "mack",
    brand: "Mackinaw Trail",
    file: "fail/mackinaw_trail_2006-04-14.png",
    cat: "fail",
    desc: "Known mismatch sample for testing failed verification output.",
  },
  {
    id: "mid",
    brand: "Midnight Moon",
    file: "fail/midnight_moon_2008-04-22.png",
    cat: "fail",
    desc: "Spirits label with expected compliance conflicts.",
  },
  {
    id: "gtd",
    brand: "Grand Traverse Distillery",
    file: "fail/grand_traverse_distillery_2012-05-05.png",
    cat: "fail",
    desc: "Distillery sample intended to produce failed checks.",
  },
  {
    id: "found",
    brand: "Founders",
    file: "fail/founders_2026-01-29.png",
    cat: "fail",
    desc: "Malt beverage label with expected verification failures.",
  },
];

const BADGE_LABELS: Record<SampleCategory, string> = {
  pass: "Should pass",
  review: "Needs review",
  fail: "Should fail",
};

const FILTER_DEFS: { key: FilterKey; label: string }[] = [
  { key: "all", label: "All" },
  { key: "pass", label: "Should pass" },
  { key: "review", label: "Needs review" },
  { key: "fail", label: "Should fail" },
];

type Props = {
  open: boolean;
  onClose: () => void;
  onRun: (files: File[]) => void;
};

export function SamplePickerModal({ open, onClose, onRun }: Props) {
  const [selected, setSelected] = useState<string[]>([]);
  const [filter, setFilter] = useState<FilterKey>("all");
  const [isRunning, setIsRunning] = useState(false);
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
    pass: SAMPLES.filter((sample) => sample.cat === "pass").length,
    review: SAMPLES.filter((sample) => sample.cat === "review").length,
    fail: SAMPLES.filter((sample) => sample.cat === "fail").length,
  };

  const visible = filter === "all" ? SAMPLES : SAMPLES.filter((sample) => sample.cat === filter);

  function toggle(id: string) {
    setSelected((prev) => (prev.includes(id) ? prev.filter((entry) => entry !== id) : [...prev, id]));
  }

  async function handleRun() {
    if (selected.length === 0 || isRunning) return;
    setIsRunning(true);
    try {
      const files = await Promise.all(
        selected.map(async (id) => {
          const entry = SAMPLES.find((sample) => sample.id === id);
          if (!entry) {
            throw new Error(`Unknown sample label: ${id}`);
          }
          const response = await fetch(`/sample_labels/${entry.file}`);
          if (!response.ok) {
            throw new Error(`Could not load sample label: ${entry.file}`);
          }
          const blob = await response.blob();
          const filename = entry.file.split("/").pop() ?? entry.file;
          return new File([blob], filename, { type: blob.type || "image/png" });
        }),
      );
      setSelected([]);
      onClose();
      onRun(files);
    } finally {
      setIsRunning(false);
    }
  }

  const n = selected.length;
  const runLabel = isRunning
    ? "Loading..."
    : n === 0
      ? "Run verification"
      : `Run verification on ${n} label${n === 1 ? "" : "s"}`;

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
                Handpicked labels with their expected result after going through the model. These
                run exactly like an upload -- no special treatment applied.
              </p>
            </div>
            <button type="button" className="sample-close" onClick={onClose} aria-label="Close">
              X
            </button>
          </div>

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
        </div>

        <div className="sample-grid-region">
          <div className="sample-grid">
            {visible.map((entry) => {
              const isSelected = selected.includes(entry.id);
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
                      <span className={`sample-cat-badge ${entry.cat}`}>
                        {BADGE_LABELS[entry.cat]}
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
              disabled={n === 0 || isRunning}
              onClick={() => void handleRun()}
            >
              {runLabel}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
