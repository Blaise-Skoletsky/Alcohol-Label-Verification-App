import { useEffect, useRef } from "react";

type DemoInfoModalProps = {
  open: boolean;
  onClose: () => void;
};

export function DemoInfoModal({ open, onClose }: DemoInfoModalProps) {
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    if (!open) return;

    closeButtonRef.current?.focus();

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="info-overlay"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="demo-info-title"
    >
      <div className="info-dialog" onClick={(event) => event.stopPropagation()}>
        <div className="info-header">
          <div>
            <div className="info-title-row">
              <h2 id="demo-info-title">Demo walkthrough</h2>
              <span className="demo-chip">DEMO ONLY</span>
            </div>
            <p className="info-subtitle">
              This orientation layer is for the demo build and would not appear in the production
              application.
            </p>
          </div>
          <button
            ref={closeButtonRef}
            type="button"
            className="info-close"
            onClick={onClose}
            aria-label="Close demo information"
          >
            X
          </button>
        </div>

        <div className="info-video-shell">
          <video className="info-video" controls preload="metadata">
            <source src="/demo-overview.mp4" type="video/mp4" />
            Your browser cannot play this demo video.
          </video>
          <div className="info-video-note">
            Demo video slot: add the walkthrough at <span>/demo-overview.mp4</span>.
          </div>
        </div>

        <div className="info-copy">
          <p>
            The walkthrough should explain how a reviewer uploads alcohol label applications,
            monitors batch progress, and opens each result to compare application values against
            label evidence.
          </p>
          <p>
            It should also frame the product vision: reduce repetitive manual review, flag likely
            compliance issues earlier, and keep final judgment with the human reviewer.
          </p>
        </div>
      </div>
    </div>
  );
}
