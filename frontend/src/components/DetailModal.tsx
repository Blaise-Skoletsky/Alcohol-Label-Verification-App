import { useEffect } from "react";
import { STATUS_TONES } from "../lib/status";
import { getItemBrand, verdictTitle } from "../lib/itemDisplay";
import type { BatchItem } from "../types/verification";
import { FieldSummaryList } from "./FieldSummaryList";
import { FilePreview } from "./FilePreview";

type DetailModalProps = {
  item: BatchItem;
  currentIndex: number;
  totalItems: number;
  onClose: () => void;
  onMove: (direction: -1 | 1) => void;
};

export function DetailModal({
  item,
  currentIndex,
  totalItems,
  onClose,
  onMove,
}: DetailModalProps) {
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
      if (event.key === "ArrowLeft") {
        onMove(-1);
      }
      if (event.key === "ArrowRight") {
        onMove(1);
      }
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose, onMove]);

  const brand = getItemBrand(item);
  const tone = STATUS_TONES[item.status];

  return (
    <div className="slideover-backdrop" role="presentation" onClick={onClose}>
      <section
        className="slideover"
        role="dialog"
        aria-modal="true"
        aria-label="Verification details"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="slideover-figure">
          <div className="figure-header">
            <div className="figure-title-row">
              <div className="figure-title" title={brand}>
                {brand}
              </div>
              <span className={`status-pill verdict-chip tone-${tone}`}>
                <span className={`status-pill-dot tone-${tone}`} aria-hidden="true" />
                {verdictTitle(item.status)}
              </span>
            </div>
            <div className="figure-summary">{item.summary}</div>
          </div>
          <FilePreview item={item} />
        </div>

        <div className="slideover-content">
          <header className="slideover-header">
            <div className="slideover-file" title={item.fileName}>
              {item.fileName}
            </div>
            <button
              type="button"
              className="slideover-close"
              onClick={onClose}
              aria-label="Close details"
            >
              ✕
            </button>
          </header>

          <div className="slideover-body">
            <FieldSummaryList item={item} />
          </div>

          <footer className="slideover-footer">
            <button
              type="button"
              className="slideover-prev"
              onClick={() => onMove(-1)}
              disabled={currentIndex === 0}
            >
              Previous
            </button>
            <button
              type="button"
              className="slideover-next"
              onClick={() => onMove(1)}
              disabled={currentIndex === totalItems - 1}
            >
              Next label
            </button>
          </footer>
        </div>
      </section>
    </div>
  );
}
