import type { BatchItem } from "../types/verification";

type FilePreviewProps = {
  item: BatchItem;
};

export function FilePreview({ item }: FilePreviewProps) {
  const isPdf = item.mimeType === "application/pdf" || item.fileName.toLowerCase().endsWith(".pdf");

  return (
    <section className="label-preview">
      <div className="section-eyebrow">Label</div>
      <div className="label-preview-frame">
        {isPdf ? (
          <iframe title={item.fileName} src={item.previewUrl} className="label-preview-embed" />
        ) : (
          <img src={item.previewUrl} alt={item.fileName} className="label-preview-image" />
        )}
      </div>
    </section>
  );
}
