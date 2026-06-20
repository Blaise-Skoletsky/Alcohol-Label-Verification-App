import { STATUS_LABELS, STATUS_TONES } from "../lib/status";
import type { BeverageClass, LabelRow } from "../types/verification";
import type { NewRowInput } from "../hooks/useLabelRows";
import { RerunIcon } from "./icons";

type LabelGridViewProps = {
  rows: LabelRow[];
  onEdit: (id: string, patch: NewRowInput) => void;
  onRerun: (id: string) => void;
  onAddRow: () => void;
};

const COLUMNS = [
  "Label",
  "Brand name",
  "Class / type",
  "Class",
  "ABV",
  "Net",
  "Name & address",
  "Country",
  "Result",
];

export function LabelGridView({ rows, onEdit, onRerun, onAddRow }: LabelGridViewProps) {
  return (
    <>
      <div className="label-table-card">
        <div className="grid-scroll">
          <div className="grid-inner">
            <div className="grid-cols grid-head">
              {COLUMNS.map((column) => (
                <div key={column}>{column}</div>
              ))}
            </div>
            {rows.map((row) => {
              const tone = STATUS_TONES[row.status];
              const abvOptional = row.beverageClass === "wine" || row.beverageClass === "malt";
              return (
                <div key={row.localId} className="grid-cols grid-row">
                  <div className="grid-label-cell">
                    <span className="grid-thumb">
                      {row.imageUrl ? <img src={row.imageUrl} alt="" /> : null}
                    </span>
                    <span className="grid-file">{row.fileName || "no image"}</span>
                  </div>
                  <input
                    className="grid-input"
                    value={row.brand}
                    placeholder="—"
                    onChange={(event) => onEdit(row.localId, { brand: event.target.value })}
                  />
                  <input
                    className="grid-input"
                    value={row.classType}
                    placeholder="—"
                    onChange={(event) => onEdit(row.localId, { classType: event.target.value })}
                  />
                  <select
                    className="grid-input"
                    value={row.beverageClass}
                    onChange={(event) =>
                      onEdit(row.localId, { beverageClass: event.target.value as BeverageClass })
                    }
                  >
                    <option value="spirits">Spirits</option>
                    <option value="wine">Wine</option>
                    <option value="malt">Malt</option>
                  </select>
                  <input
                    className="grid-input"
                    value={row.abv}
                    placeholder={abvOptional ? "optional" : "—"}
                    onChange={(event) => onEdit(row.localId, { abv: event.target.value })}
                  />
                  <input
                    className="grid-input"
                    value={row.net}
                    placeholder="—"
                    onChange={(event) => onEdit(row.localId, { net: event.target.value })}
                  />
                  <input
                    className="grid-input"
                    value={row.nameAddr}
                    placeholder="—"
                    onChange={(event) => onEdit(row.localId, { nameAddr: event.target.value })}
                  />
                  <input
                    className="grid-input"
                    value={row.country}
                    placeholder="domestic"
                    onChange={(event) => onEdit(row.localId, { country: event.target.value })}
                  />
                  <div className="grid-result">
                    <span className={`mini-check-dot tone-${tone}`} aria-hidden="true" />
                    <span className="grid-result-label" style={{ color: toneColor(tone) }}>
                      {STATUS_LABELS[row.status]}
                    </span>
                    <button
                      type="button"
                      className="rerun-btn"
                      title="Re-run"
                      onClick={() => onRerun(row.localId)}
                    >
                      <RerunIcon spinning={row.status === "processing"} />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
      <div className="grid-footer">
        <button type="button" className="grid-add" onClick={onAddRow}>
          <span className="btn-plus">+</span> Add row
        </button>
        <span className="grid-hint">
          Paste straight from Excel or Google Sheets — columns map automatically. The government
          warning is checked on the label, never typed.
        </span>
      </div>
    </>
  );
}

function toneColor(tone: string): string {
  switch (tone) {
    case "pass":
      return "#0b7a4b";
    case "fail":
    case "error":
      return "#c5362b";
    case "working":
      return "#5a6470";
    default:
      return "#6b7280";
  }
}
