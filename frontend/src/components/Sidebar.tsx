import type { StatusCounts } from "../hooks/useLabelRows";
import { GridIcon, UploadIcon } from "./icons";

type SidebarProps = {
  counts: StatusCounts;
  onAddLabel: () => void;
  onBatchUpload: () => void;
  onUseSamples: () => void;
};

export function Sidebar({ counts, onAddLabel, onBatchUpload, onUseSamples }: SidebarProps) {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="sidebar-title">Alcohol Label Verification</div>
        <div className="sidebar-note">Not affiliated with TTB</div>
      </div>

      <div className="batch-summary">
        <div className="batch-summary-label">This batch</div>
        <SummaryPill label="Passed" value={counts.pass} tone="pass" />
        <SummaryPill label="Failed" value={counts.fail} tone="fail" />
        <SummaryPill label="Not run" value={counts.notRun} tone="neutral" />
      </div>

      <div className="sidebar-actions">
        <button type="button" className="btn-solid" onClick={onAddLabel}>
          <span className="btn-plus">+</span> Add a label
        </button>
        <button type="button" className="btn-solid" onClick={onBatchUpload}>
          <UploadIcon />
          Batch upload
        </button>
        <button type="button" className="btn-outline" onClick={onUseSamples}>
          <GridIcon />
          Use sample labels
          <span className="demo-chip">DEMO</span>
        </button>
      </div>
    </aside>
  );
}

function SummaryPill({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "pass" | "fail" | "neutral";
}) {
  return (
    <div className={`summary-pill tone-${tone}`}>
      <span className="summary-pill-name">
        <span className="summary-pill-dot" aria-hidden="true" />
        {label}
      </span>
      <span className="summary-pill-count">{value}</span>
    </div>
  );
}
