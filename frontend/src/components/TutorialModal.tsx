import { useEffect } from "react";

type TutorialModalProps = {
  videoUrl: string;
  onClose: () => void;
};

export function TutorialModal({ videoUrl, onClose }: TutorialModalProps) {
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  return (
    <div
      className="modal-overlay"
      style={{ background: "rgba(10,10,10,0.55)" }}
      onClick={onClose}
      role="presentation"
    >
      <div className="tutorial-modal" onClick={(event) => event.stopPropagation()}>
        <div className="tutorial-header">
          <div>
            <div className="tutorial-header-title">How to use this tool</div>
            <div className="tutorial-header-sub">
              A short walkthrough of uploading and verifying labels.
            </div>
          </div>
          <button type="button" className="modal-close" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>
        <div style={{ background: "#000" }}>
          <video controls playsInline className="tutorial-video">
            <source src={videoUrl} type="video/mp4" />
            Your browser does not support this video.
          </video>
        </div>
      </div>
    </div>
  );
}
