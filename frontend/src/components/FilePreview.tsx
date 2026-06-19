import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import type { BatchItem } from "../types/verification";

type FilePreviewProps = {
  item: BatchItem;
};

export function FilePreview({ item }: FilePreviewProps) {
  const [zoomed, setZoomed] = useState(false);

  // Close the zoom lightbox on Escape. Capture phase + stopPropagation keeps the
  // key from also closing the whole slide-over.
  useEffect(() => {
    if (!zoomed) {
      return;
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.stopPropagation();
        setZoomed(false);
      }
    }
    window.addEventListener("keydown", onKeyDown, true);
    return () => window.removeEventListener("keydown", onKeyDown, true);
  }, [zoomed]);

  return (
    <div className="slideover-figure-media">
      <img src={item.previewUrl} alt={item.fileName} className="slideover-figure-img" />
      <button
        type="button"
        className="figure-zoom-btn"
        onClick={() => setZoomed(true)}
        aria-label="Zoom in on the label"
      >
        <ZoomIcon />
        Zoom
      </button>

      {zoomed
        ? createPortal(
            <div
              className="lightbox"
              role="dialog"
              aria-modal="true"
              aria-label="Label zoomed view"
              onClick={(event) => {
                event.stopPropagation();
                setZoomed(false);
              }}
            >
              <img
                src={item.previewUrl}
                alt={item.fileName}
                className="lightbox-img"
                onClick={(event) => event.stopPropagation()}
              />
              <button
                type="button"
                className="lightbox-close"
                onClick={(event) => {
                  event.stopPropagation();
                  setZoomed(false);
                }}
                aria-label="Close zoomed view"
              >
                ✕
              </button>
            </div>,
            document.body,
          )
        : null}
    </div>
  );
}

function ZoomIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="2" />
      <line x1="11" y1="8" x2="11" y2="14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      <line x1="8" y1="11" x2="14" y2="11" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      <line x1="16.5" y1="16.5" x2="21" y2="21" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}
