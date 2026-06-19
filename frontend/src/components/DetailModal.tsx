import { useEffect } from "react";
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

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <section
        className="detail-modal"
        role="dialog"
        aria-modal="true"
        aria-label="Verification details"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="detail-header">
          <div>
            <p className="eyebrow">
              File {currentIndex + 1} of {totalItems}
            </p>
            <h2>{item.fileName}</h2>
          </div>
          <div className="detail-actions">
            <button
              type="button"
              className="secondary-button"
              onClick={() => onMove(-1)}
              disabled={currentIndex === 0}
            >
              Previous
            </button>
            <button
              type="button"
              className="secondary-button"
              onClick={() => onMove(1)}
              disabled={currentIndex === totalItems - 1}
            >
              Next
            </button>
          </div>
        </header>

        <div className="detail-grid">
          <FilePreview item={item} />
          <FieldSummaryList item={item} />
        </div>
        <footer className="detail-footer">
          <button type="button" className="secondary-button" onClick={onClose}>
            Close
          </button>
        </footer>
      </section>
    </div>
  );
}
