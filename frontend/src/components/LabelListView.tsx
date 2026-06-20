import { STATUS_LABELS, STATUS_TONES } from "../lib/status";
import { miniChecks, rowInitials } from "../lib/rowView";
import type { LabelRow } from "../types/verification";
import { CheckIcon } from "./icons";

type LabelListViewProps = {
  rows: LabelRow[];
  selected: Set<string>;
  allSelected: boolean;
  onToggleAll: () => void;
  onToggle: (id: string) => void;
  onOpen: (id: string) => void;
};

export function LabelListView({
  rows,
  selected,
  allSelected,
  onToggleAll,
  onToggle,
  onOpen,
}: LabelListViewProps) {
  return (
    <div className="label-table-card">
      <div className="label-grid label-table-head">
        <button
          type="button"
          className={`checkbox${allSelected ? " checked" : ""}`}
          aria-label="Select all"
          onClick={onToggleAll}
        >
          {allSelected ? <CheckIcon /> : null}
        </button>
        <div>Label</div>
        <div>Checks</div>
        <div>Result</div>
        <div className="align-right">Updated</div>
      </div>

      {rows.length === 0 ? (
        <div className="empty-state">
          <h3>Nothing here yet</h3>
          <p>Add labels or load the sample set to get started.</p>
        </div>
      ) : (
        rows.map((row) => {
          const isSelected = selected.has(row.localId);
          const isEdited = row.edited && Boolean(row.fields);
          const tone = isEdited ? "edited" : STATUS_TONES[row.status];
          const statusLabel = isEdited ? "Edited" : STATUS_LABELS[row.status];
          return (
            <div
              key={row.localId}
              className={`label-grid label-row${isSelected ? " selected" : ""}`}
              onClick={() => onOpen(row.localId)}
            >
              <button
                type="button"
                className={`checkbox${isSelected ? " checked" : ""}`}
                aria-label="Select label"
                onClick={(event) => {
                  event.stopPropagation();
                  onToggle(row.localId);
                }}
              >
                {isSelected ? <CheckIcon /> : null}
              </button>

              <span className="label-cell">
                <span className="thumb">
                  {row.imageUrl ? (
                    <img src={row.imageUrl} alt="" />
                  ) : (
                    <span className="thumb-initials">{rowInitials(row.brand)}</span>
                  )}
                </span>
                <span className="label-cell-text">
                  <span className="label-brand-row">
                    <span className="label-brand">{row.brand || "Untitled label"}</span>
                    {row.flagged ? <span className="needs-image">Needs image</span> : null}
                  </span>
                  <span className="label-file">{row.fileName || "no image"}</span>
                </span>
              </span>

              <span className="checks-cell">
                {miniChecks(row).map((check) => (
                  <span key={check.key} className="check-item">
                    <span
                      className={`mini-check-dot tone-${isEdited ? "edited" : check.tone}`}
                      aria-hidden="true"
                    />
                    <span className="check-item-label">{check.short}</span>
                  </span>
                ))}
              </span>

              <span>
                <span className={`status-pill tone-${tone}`}>
                  <span className={`status-pill-dot tone-${tone}`} aria-hidden="true" />
                  {statusLabel}
                </span>
              </span>

              <span className="updated-cell">{row.updatedAtLabel}</span>
            </div>
          );
        })
      )}
    </div>
  );
}
