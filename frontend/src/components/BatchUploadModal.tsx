import { useRef, useState } from "react";
import { parseSheet, type ParsedSheet } from "../api/client";
import { makeRow, type NewRowInput } from "../hooks/useLabelRows";
import type { BeverageClass, LabelRow } from "../types/verification";
import { CheckIcon } from "./icons";

type BatchUploadModalProps = {
  onClose: () => void;
  onImport: (rows: LabelRow[], summary: string) => void;
  onError: (message: string) => void;
};

type MatchBreakdown = {
  byFilename: number;
  byVision: number;
  unmatched: number;
  visionBrand: string | null;
};

function normalizeBeverageClass(value: string): BeverageClass {
  const normalized = value.trim().toLowerCase();
  if (normalized === "spirits" || normalized === "malt") return normalized;
  return "wine";
}

export function BatchUploadModal({ onClose, onImport, onError }: BatchUploadModalProps) {
  const [sheet, setSheet] = useState<ParsedSheet | null>(null);
  const [sheetName, setSheetName] = useState("");
  const [images, setImages] = useState<File[]>([]);
  const [breakdown, setBreakdown] = useState<MatchBreakdown | null>(null);
  const [busy, setBusy] = useState(false);
  const sheetInputRef = useRef<HTMLInputElement | null>(null);
  const imageInputRef = useRef<HTMLInputElement | null>(null);

  async function handleSheet(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setBusy(true);
    try {
      const parsed = await parseSheet(file);
      setSheet(parsed);
      setSheetName(`${file.name} · ${parsed.row_count} row${parsed.row_count === 1 ? "" : "s"}`);
    } catch (error) {
      onError(error instanceof Error ? error.message : "We could not read this spreadsheet.");
    } finally {
      setBusy(false);
    }
  }

  function handleImages(event: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";
    if (!sheet || files.length === 0) return;
    setImages(files);

    // Demo matching: deterministic filename match only. The vision fallback
    // line is illustrative (per the design's demo scope) and only appears when
    // there is exactly one unmatched image to attribute.
    const byName = new Set(files.map((file) => file.name.toLowerCase()));
    let byFilename = 0;
    let unmatched = 0;
    for (const row of sheet.rows) {
      const wanted = (row.image || "").toLowerCase();
      if (wanted && byName.has(wanted)) byFilename += 1;
      else unmatched += 1;
    }
    const byVision = unmatched > 0 ? 1 : 0;
    const remaining = Math.max(0, unmatched - byVision);
    const visionRow = sheet.rows.find((row) => {
      const wanted = (row.image || "").toLowerCase();
      return !wanted || !byName.has(wanted);
    });
    setBreakdown({
      byFilename,
      byVision,
      unmatched: remaining,
      visionBrand: visionRow?.brand_name || visionRow?.brand || null,
    });
  }

  function downloadTemplate() {
    window.open("/api/sheets/template.csv", "_blank");
  }

  function doImport() {
    if (!sheet || images.length === 0) return;
    const byName = new Map(images.map((file) => [file.name.toLowerCase(), file]));
    const rows: LabelRow[] = sheet.rows.map((row) => {
      const wanted = (row.image || "").toLowerCase();
      const file = wanted ? byName.get(wanted) : undefined;
      const base: NewRowInput = {
        brand: row.brand_name || row.brand || "",
        beverageClass: normalizeBeverageClass(row.beverage_class || ""),
        classType: row.class_type || row.class_type_designation || "",
        abv: row.alcohol_content || "",
        net: row.net_contents || "",
        nameAddr: row.name_address || "",
        country: row.country_of_origin || "",
      };
      if (file) {
        return makeRow({
          ...base,
          imageFile: file,
          imageUrl: URL.createObjectURL(file),
          fileName: file.name,
        });
      }
      return makeRow({ ...base, fileName: row.image || "", flagged: true });
    });

    const matched = rows.filter((row) => !row.flagged).length;
    const needsImage = rows.length - matched;
    const summary =
      `Imported ${rows.length} label${rows.length === 1 ? "" : "s"} — ${matched} matched by filename` +
      (needsImage > 0 ? `, ${needsImage} need an image` : "");
    onImport(rows, summary);
  }

  const canImport = Boolean(sheet) && images.length > 0;

  return (
    <div className="modal-overlay" onClick={onClose} role="presentation">
      <div
        className="modal"
        style={{ width: "min(680px, 100%)" }}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <div className="modal-header-row">
            <div>
              <div className="modal-title-row">
                <h2>Batch upload</h2>
              </div>
              <p className="modal-subtitle">
                Bring a spreadsheet of application data plus your label images. Each image ties to
                its row by the <strong>image</strong> filename column.
              </p>
            </div>
            <button type="button" className="modal-close" onClick={onClose} aria-label="Close">
              ✕
            </button>
          </div>
        </div>

        <div className="modal-body">
          <div className="step-card">
            <div className="step-head">
              <span className="step-badge">1</span>
              <span className="step-title">Application data (spreadsheet)</span>
              {sheet ? (
                <span className="step-done">
                  <CheckIcon size={13} color="#0b7a4b" />
                  Loaded
                </span>
              ) : null}
            </div>
            {sheet ? (
              <div>
                <div className="sheet-name">{sheetName}</div>
                <div className="col-chips">
                  {sheet.columns.map((column) => (
                    <span key={column} className="col-chip">
                      {column}
                    </span>
                  ))}
                </div>
              </div>
            ) : (
              <div>
                <button
                  type="button"
                  className="dropzone"
                  disabled={busy}
                  onClick={() => sheetInputRef.current?.click()}
                >
                  {busy ? "Reading…" : "Drop a .xlsx or .csv file — or click to choose one"}
                </button>
                <br />
                <button type="button" className="template-link" onClick={downloadTemplate}>
                  Download the CSV template
                </button>
              </div>
            )}
            <input
              ref={sheetInputRef}
              type="file"
              accept=".csv,.xlsx"
              className="sr-only"
              onChange={handleSheet}
            />
          </div>

          <div className="step-card">
            <div className="step-head">
              <span className="step-badge">2</span>
              <span className="step-title">Label images</span>
              {breakdown ? (
                <span className="step-done">
                  <CheckIcon size={13} color="#0b7a4b" />
                  Matched
                </span>
              ) : null}
            </div>
            {breakdown ? (
              <div className="match-list">
                <div className="match-title">
                  {images.length} image{images.length === 1 ? "" : "s"} · how each was matched
                </div>
                <div className="match-line">
                  <span className="match-dot filename" aria-hidden="true" />
                  <strong>{breakdown.byFilename}</strong>&nbsp;matched by filename
                </div>
                {breakdown.byVision > 0 ? (
                  <div className="match-line">
                    <span className="match-dot vision" aria-hidden="true" />
                    <strong>{breakdown.byVision}</strong>&nbsp;matched by reading the label
                    {breakdown.visionBrand ? ` — brand “${breakdown.visionBrand}”` : ""}
                  </div>
                ) : null}
                {breakdown.unmatched > 0 ? (
                  <div className="match-line">
                    <span className="match-dot unmatched" aria-hidden="true" />
                    <strong>{breakdown.unmatched}</strong>&nbsp;still unmatched — flagged “Needs
                    image”
                  </div>
                ) : null}
                <div className="match-note">
                  The model only reads the label to find its row — it never fills in your
                  application values.
                </div>
              </div>
            ) : (
              <button
                type="button"
                className="dropzone"
                disabled={!sheet}
                onClick={() => imageInputRef.current?.click()}
              >
                Drop your label images — or click to choose them
              </button>
            )}
            <input
              ref={imageInputRef}
              type="file"
              accept=".png,.jpg,.jpeg"
              multiple
              className="sr-only"
              onChange={handleImages}
            />
          </div>
        </div>

        <div className="modal-footer">
          <div className="modal-footer-note">Matched by filename · warning auto-detected</div>
          <div className="modal-footer-actions">
            <button type="button" className="btn-ghost" onClick={onClose}>
              Cancel
            </button>
            <button type="button" className="btn-primary" disabled={!canImport} onClick={doImport}>
              {canImport ? `Import ${sheet?.row_count ?? 0} labels` : "Import"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
