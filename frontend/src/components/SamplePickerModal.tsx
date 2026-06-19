import { useEffect, useRef, useState } from "react";

type SampleCategory = "pass" | "fail";
type FilterKey = "all" | SampleCategory;

interface SampleEntry {
  id: string;
  brand: string;
  file: string;
  desc: string;
}

const SAMPLES: SampleEntry[] = [
  {
    id: "casa",
    brand: "Casamigos Tequila",
    file: "pass/casamigos_glare_readable.png",
    desc: "Expected pass: spirits label with readable brand, class, alcohol content, net contents, origin, and warning text.",
  },
  {
    id: "coyam",
    brand: "Coyam (Chile)",
    file: "pass/coyam.png",
    desc: "Expected pass: wine label with matching brand, origin, contents, and required warning information.",
  },
  {
    id: "nat",
    brand: "Natura Cabernet",
    file: "pass/natura.png",
    desc: "Expected pass: original Natura label includes the required government warning and supporting label details.",
  },
  {
    id: "gek",
    brand: "Gekkeikan Sake",
    file: "pass/gekkeikan_low_light_readable.png",
    desc: "Expected pass: original sake label is readable and includes the expected class, contents, importer, and warning details.",
  },
  {
    id: "chick",
    brand: "Chicken Dinner Red",
    file: "pass/chicken_dinner.png",
    desc: "Expected pass: original Chicken Dinner label includes readable front/back labels and the required warning block.",
  },
  {
    id: "mid",
    brand: "Midnight Moon",
    file: "pass/midnight_moon.png",
    desc: "Expected pass: original spirits label has readable application and label evidence for required checks.",
  },
  {
    id: "casa-glare",
    brand: "Casamigos Tequila",
    file: "pass/casamigos_glare_readable.png",
    desc: "Expected pass: the photo has glare, but the required label text is still readable enough to verify.",
  },
  {
    id: "gekkeikan-lighting",
    brand: "Gekkeikan Sake",
    file: "pass/gekkeikan_low_light_readable.png",
    desc: "Expected pass: lighting is dim, but the label and application values remain readable enough to verify.",
  },
  {
    id: "jd",
    brand: "Jack Daniel's Winter Jack",
    file: "pass/jack_daniels_winter_jack.png",
    desc: "Expected pass: application says distilled spirits; label says Tennessee cider, a blend using Tennessee whiskey.",
  },
  {
    id: "mack",
    brand: "Mackinaw Trail",
    file: "fail/mackinaw_trail.png",
    desc: "Expected fail: the label evidence is missing or unclear for at least one required verification field.",
  },
  {
    id: "chick-warning",
    brand: "Chicken Dinner Red",
    file: "fail/chicken_dinner_fail_incorrect_government_warning.png",
    desc: "Expected fail: the government warning block was changed to incorrect, non-compliant warning language.",
  },
  {
    id: "natura-warning",
    brand: "Natura Cabernet",
    file: "fail/natura_fail_missing_government_warning.png",
    desc: "Expected fail: the government warning paragraph is missing from the label artwork.",
  },
  {
    id: "monkey-rotated",
    brand: "Monkey 47 Dry Gin",
    file: "pass/monkey_47_rotated_label.png",
    desc: "Expected pass: the rotated embedded label images remain readable enough to verify the required application and label evidence.",
  },
];

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
    pass: SAMPLES.filter((sample) => getSampleCategory(sample) === "pass").length,
    fail: SAMPLES.filter((sample) => getSampleCategory(sample) === "fail").length,
  };

  const visible =
    filter === "all" ? SAMPLES : SAMPLES.filter((sample) => getSampleCategory(sample) === filter);

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
