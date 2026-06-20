import { useAppConfig } from "../hooks/useAppConfig";
import { GridIcon, UploadIcon } from "./icons";

type SidebarProps = {
  onAddLabel: () => void;
  onBatchUpload: (files: File[]) => void;
  onUseSamples: () => void;
  onLoadDemoBatch: (manifestUrl: string) => void;
};

export function Sidebar({
  onAddLabel,
  onBatchUpload,
  onUseSamples,
  onLoadDemoBatch,
}: SidebarProps) {
  const { config } = useAppConfig();
  const acceptedTypes = config.allowedFileTypes.join(",");
  const displayTypes = formatFileTypes(config.allowedFileTypes);
  const batchUploadHint = `Verify up to ${config.maxBatchLabels} labels`;
  const showDemoBatch =
    config.environment.toLowerCase() === "production" && Boolean(config.demoBatchManifestUrl);

  function handleBatchFiles(event: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";
    if (files.length > 0) onBatchUpload(files);
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="sidebar-title">Alcohol Label Verification</div>
        <div className="sidebar-note">Not affiliated with TTB</div>
      </div>

      <div className="sidebar-actions">
        {showDemoBatch ? (
          <button
            type="button"
            className="btn-outline"
            onClick={() => onLoadDemoBatch(config.demoBatchManifestUrl ?? "")}
          >
            <GridIcon />
            Load sample batch
            <span className="demo-chip">DEMO</span>
          </button>
        ) : null}
        <button type="button" className="btn-outline" onClick={onUseSamples}>
          <GridIcon />
          Use sample labels
          <span className="demo-chip">DEMO</span>
        </button>
        <button type="button" className="btn-solid" onClick={onAddLabel}>
          <span className="btn-plus">+</span> Add a label
        </button>
        <label
          className="btn-solid sidebar-file-action"
          title={`You can upload ${displayTypes} files.`}
        >
          <span className="sidebar-upload-title">
            <UploadIcon />
            Batch upload
          </span>
          <span className="sidebar-upload-hint">{batchUploadHint}</span>
          <input
            type="file"
            accept={acceptedTypes}
            multiple
            aria-label={`Batch upload. ${batchUploadHint}.`}
            className="sr-only"
            onChange={handleBatchFiles}
          />
        </label>
      </div>
    </aside>
  );
}

function formatFileTypes(types: string[]): string {
  const clean = types
    .map((type) => type.replace(/^\./, "").trim().toUpperCase())
    .filter(Boolean);
  const unique = [...new Set(clean)];
  if (unique.length === 0) return "PNG, JPG, or JPEG";
  if (unique.length === 1) return unique[0];
  return `${unique.slice(0, -1).join(", ")}, or ${unique[unique.length - 1]}`;
}
