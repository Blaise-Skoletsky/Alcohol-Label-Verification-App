import { useEffect } from "react";
import { STATUS_TONES } from "../lib/status";
import { getItemBrand, verdictTitle } from "../lib/itemDisplay";
import type { BatchItem } from "../types/verification";
import { FieldSummaryList } from "./FieldSummaryList";
import { FilePreview } from "./FilePreview";
import { LabelThumbnail } from "./LabelThumbnail";

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
        <header className="slideover-header">
          <div className="slideover-heading">
            <LabelThumbnail item={item} />
            <div className="slideover-titles">
              <div className="slideover-brand" title={brand}>
                {brand}
              </div>
              <div className="slideover-file" title={item.fileName}>
                {item.fileName}
              </div>
            </div>
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
          <div className={`verdict-banner tone-${tone}`}>
            <span className={`verdict-dot tone-${tone}`} aria-hidden="true" />
            <div>
              <div className="verdict-title">{verdictTitle(item.status)}</div>
              <div className="verdict-summary">{item.summary}</div>
            </div>
          </div>

          <FilePreview item={item} />

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
      </section>
    </div>
  );
}
