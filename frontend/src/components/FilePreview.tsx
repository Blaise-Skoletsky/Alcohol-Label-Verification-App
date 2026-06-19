import type { BatchItem } from "../types/verification";
import { StatusPill } from "./StatusPill";

type FilePreviewProps = {
  item: BatchItem;
};

export function FilePreview({ item }: FilePreviewProps) {
  const isPdf = item.mimeType === "application/pdf" || item.fileName.toLowerCase().endsWith(".pdf");

  return (
    <section className="preview-panel">
      <div className="preview-header">
        <h3>Submitted file</h3>
        <StatusPill status={item.status} label={item.overallLabel} />
      </div>
      <div className="preview-frame">
        {isPdf ? (
          <iframe title={item.fileName} src={item.previewUrl} className="preview-embed" />
        ) : (
          <img src={item.previewUrl} alt={item.fileName} className="preview-image" />
        )}
      </div>
    </section>
  );
}
