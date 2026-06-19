import { useRef } from "react";
import type { AppConfig } from "../types/config";
import { InlineMessage } from "./InlineMessage";

type UploadPanelProps = {
  config: AppConfig;
  configError: string;
  formError: string;
  isSubmitting: boolean;
  onFilesChosen: (files: File[]) => { accepted: boolean; addedCount: number };
  onAcceptedFiles: (count: number) => void;
  onOpenSamplePicker: () => void;
};

export function UploadPanel({
  config,
  configError,
  formError,
  isSubmitting,
  onFilesChosen,
  onAcceptedFiles,
  onOpenSamplePicker,
}: UploadPanelProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);

  function handleFilesChosen(event: React.ChangeEvent<HTMLInputElement>) {
    const fileList = event.target.files;
    if (!fileList || fileList.length === 0) {
      return;
    }

    const result = onFilesChosen(Array.from(fileList));
    if (result.accepted) {
      onAcceptedFiles(result.addedCount);
    }
    event.target.value = "";
  }

  return (
    <div className="upload-panel">
      <button type="button" className="sample-button" onClick={onOpenSamplePicker}>
        <svg
          width="15"
          height="15"
          viewBox="0 0 15 15"
          fill="none"
          style={{ flexShrink: 0 }}
          aria-hidden="true"
        >
          <rect x="0.5" y="0.5" width="6" height="6" rx="1.5" fill="#1a1a1a" />
          <rect x="8.5" y="0.5" width="6" height="6" rx="1.5" fill="#c2c2bb" />
          <rect x="0.5" y="8.5" width="6" height="6" rx="1.5" fill="#c2c2bb" />
          <rect x="8.5" y="8.5" width="6" height="6" rx="1.5" fill="#1a1a1a" />
        </svg>
        Use sample labels
        <span className="demo-chip">DEMO</span>
      </button>
      <input
        ref={inputRef}
        id="artifact-upload"
        className="sr-only"
        type="file"
        accept={config.allowedFileTypes.join(",")}
        multiple
        onChange={(event) => {
          void handleFilesChosen(event);
        }}
        disabled={isSubmitting}
      />
      <button
        type="button"
        className="upload-button"
        onClick={() => inputRef.current?.click()}
        disabled={isSubmitting}
        aria-describedby="upload-file-help"
      >
        {isSubmitting ? "Starting review..." : "Upload labels"}
      </button>
      <div className="upload-help" id="upload-file-help">
        PNG or JPG - up to {config.maxBatchLabels}
      </div>
      {configError ? <InlineMessage tone="warning">{configError}</InlineMessage> : null}
      {formError ? <InlineMessage tone="error">{formError}</InlineMessage> : null}
    </div>
  );
}
