import { useEffect, useRef } from "react";
import { STATUS_LABELS, STATUS_TONES } from "../lib/status";
import { detailFieldCards } from "../lib/rowView";
import { BEVERAGE_CLASS_LABELS, type NewRowInput } from "../hooks/useLabelRows";
import type { BeverageClass, LabelRow } from "../types/verification";
import { CheckIcon, RerunIconLight } from "./icons";

type DetailModalProps = {
  row: LabelRow;
  index: number;
  total: number;
  onClose: () => void;
  onPrev: () => void;
  onNext: () => void;
  onEdit: (id: string, patch: NewRowInput) => void;
  onAttachImage: (id: string, file: File) => void;
  onAction: (id: string) => void;
};

function summaryFor(row: LabelRow): string {
  switch (row.status) {
    case "pass":
      return "All required fields match the application.";
    case "fail":
      return "One or more checks need attention. Fix the value and re-run.";
    case "processing-error":
      return row.summary;
    case "processing":
      return "Verification in progress.";
    default:
      return "Not verified yet.";
  }
}

export function DetailModal({
  row,
  index,
  total,
  onClose,
  onPrev,
  onNext,
  onEdit,
  onAttachImage,
  onAction,
}: DetailModalProps) {
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
      if (event.key === "ArrowLeft") onPrev();
      if (event.key === "ArrowRight") onNext();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose, onPrev, onNext]);

  const tone = STATUS_TONES[row.status];
  const isDraft = row.status === "draft";
  const processing = row.status === "processing";
  const abvOptional = row.beverageClass === "wine" || row.beverageClass === "malt";
  const showChecks = row.status === "pass" || row.status === "fail";
  const cards = detailFieldCards(row);

  const actionLabel = isDraft
    ? "Verify this label"
    : processing
      ? "Verifying…"
      : "Re-run this label";

  function handleFile(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) onAttachImage(row.localId, file);
    event.target.value = "";
  }

  return (
    <>
      <div className="slideover-backdrop" role="presentation" onClick={onClose} />
      <section className="slideover" role="dialog" aria-modal="true" aria-label="Label details">
        <div className="slideover-figure">
          <div className="figure-head">
            <div className="figure-title-row">
              <div className="figure-title" title={row.brand}>
                {row.brand || "Untitled label"}
              </div>
              <span className={`status-pill tone-${tone}`}>
                <span className={`status-pill-dot tone-${tone}`} aria-hidden="true" />
                {STATUS_LABELS[row.status]}
              </span>
            </div>
            <div className="figure-summary">{summaryFor(row)}</div>
          </div>
          <div className="figure-image">
            {row.imageUrl ? (
              <img src={row.imageUrl} alt="" />
            ) : (
              <button
                type="button"
                className="figure-attach"
                onClick={() => fileInputRef.current?.click()}
              >
                Attach a label image
              </button>
            )}
            <input
              ref={fileInputRef}
              type="file"
              accept=".png,.jpg,.jpeg"
              className="sr-only"
              onChange={handleFile}
            />
          </div>
        </div>

        <div className="slideover-side">
          <header className="slideover-side-head">
            <div className="slideover-file" title={row.fileName}>
              {row.fileName || "no image"}
            </div>
            <button
              type="button"
              className="nav-btn"
              title="Previous"
              onClick={onPrev}
              disabled={index <= 0}
            >
              ‹
            </button>
            <button
              type="button"
              className="nav-btn"
              title="Next"
              onClick={onNext}
              disabled={index >= total - 1}
            >
              ›
            </button>
            <button type="button" className="nav-btn" title="Close" onClick={onClose}>
              ✕
            </button>
          </header>

          <div className="slideover-body">
            <div>
              <div className="section-label">Application values</div>
              <div className="value-grid">
                <Field
                  label="Brand name"
                  value={row.brand}
                  placeholder="e.g. Coyam"
                  onChange={(value) => onEdit(row.localId, { brand: value })}
                />
                <label className="value-field">
                  <span className="value-field-label">Beverage class</span>
                  <select
                    className="value-input"
                    value={row.beverageClass}
                    onChange={(event) =>
                      onEdit(row.localId, { beverageClass: event.target.value as BeverageClass })
                    }
                  >
                    {(Object.keys(BEVERAGE_CLASS_LABELS) as BeverageClass[]).map((key) => (
                      <option key={key} value={key}>
                        {BEVERAGE_CLASS_LABELS[key]}
                      </option>
                    ))}
                  </select>
                </label>
                <Field
                  label="Class / type"
                  value={row.classType}
                  placeholder="e.g. Red Wine"
                  onChange={(value) => onEdit(row.localId, { classType: value })}
                />
                <Field
                  label="Alcohol content"
                  badge={abvOptional ? "OPTIONAL" : undefined}
                  value={row.abv}
                  placeholder="e.g. 40%"
                  onChange={(value) => onEdit(row.localId, { abv: value })}
                />
                <Field
                  label="Net contents"
                  value={row.net}
                  placeholder="e.g. 750 mL"
                  onChange={(value) => onEdit(row.localId, { net: value })}
                />
                <Field
                  label="Country"
                  badge="IMPORTS"
                  value={row.country}
                  placeholder="blank if domestic"
                  onChange={(value) => onEdit(row.localId, { country: value })}
                />
                <Field
                  full
                  label="Name & address of bottler / producer"
                  value={row.nameAddr}
                  placeholder="e.g. Banfi Products Corp — Old Brookville, NY"
                  onChange={(value) => onEdit(row.localId, { nameAddr: value })}
                />
              </div>
              <div className="warning-note">
                <CheckIcon size={13} color="#0b7a4b" />
                Government warning is detected automatically — you never type it.
              </div>
            </div>

            {showChecks ? (
              <div>
                <div className="section-label">
                  Why it {row.status === "fail" ? "failed" : "passed"}
                </div>
                <div className="field-cards">
                  {cards.map((card) => (
                    <div
                      key={card.key}
                      className={`field-card${card.isFail ? " fail has-detail" : ""}`}
                    >
                      <div className="field-card-head">
                        <span className="field-card-name">{card.label}</span>
                        <span className="field-card-status" style={{ color: cardColor(card.tone) }}>
                          <span className={`mini-check-dot tone-${card.tone}`} aria-hidden="true" />
                          {card.statusLabel}
                        </span>
                      </div>
                      {card.isFail ? (
                        <div>
                          {card.key === "government_warning" ? (
                            <div className="field-card-grid single">
                              <div className="field-val">
                                <div className="field-val-label">On label</div>
                                <div className="field-val-text">{card.labelVal}</div>
                              </div>
                            </div>
                          ) : (
                            <div className="field-card-grid">
                              <div className="field-val">
                                <div className="field-val-label">Application</div>
                                <div className="field-val-text">{card.appVal}</div>
                              </div>
                              <div className="field-val">
                                <div className="field-val-label">On label</div>
                                <div className="field-val-text">{card.labelVal}</div>
                              </div>
                            </div>
                          )}
                          <p className="field-reason">{card.reason}</p>
                        </div>
                      ) : null}
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            {isDraft ? (
              <div className="draft-note">
                <span className="draft-note-dot" aria-hidden="true" />
                <p>
                  Not verified yet. Fill in the application values above, then verify this label to
                  see the field-by-field result.
                </p>
              </div>
            ) : null}
          </div>

          <footer className="slideover-footer">
            <button type="button" className="btn-close" onClick={onClose}>
              Close
            </button>
            <button
              type="button"
              className="btn-action"
              onClick={() => onAction(row.localId)}
              disabled={processing}
            >
              <RerunIconLight spinning={processing} />
              {actionLabel}
            </button>
          </footer>
        </div>
      </section>
    </>
  );
}

type FieldProps = {
  label: string;
  value: string;
  placeholder?: string;
  badge?: string;
  full?: boolean;
  onChange: (value: string) => void;
};

function Field({ label, value, placeholder, badge, full, onChange }: FieldProps) {
  return (
    <label className={`value-field${full ? " full" : ""}`}>
      <span className="value-field-label">
        {label}
        {badge ? <span className="value-badge">{badge}</span> : null}
      </span>
      <input
        className="value-input"
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function cardColor(tone: string): string {
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
