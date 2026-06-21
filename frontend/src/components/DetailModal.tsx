import { useEffect, useRef } from "react";
import { STATUS_LABELS, STATUS_TONES } from "../lib/status";
import { detailFieldCards } from "../lib/rowView";
import { BEVERAGE_CLASS_LABELS, rowReady, type NewRowInput } from "../hooks/useLabelRows";
import type { BeverageClass, FieldKey, LabelRow } from "../types/verification";
import { RerunIconLight } from "./icons";

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

type FieldCheckInfo = {
  key: FieldKey;
  tone: string;
  statusLabel: string;
  labelVal: string;
  reason: string;
  isFail: boolean;
  isEdited: boolean;
};

function summaryFor(row: LabelRow, stale: boolean): string {
  if (stale) return "You edited a field since the last run. Re-run to update the result.";
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

  const isDraft = row.status === "draft";
  const processing = row.status === "processing";
  const abvOptional =
    row.beverageClass === "malt"
      ? !row.maltAddedNonbeverageAlcohol
      : row.beverageClass === "wine" && /\b(table|light)\s+wine\b/i.test(row.classType);
  const showMaltFlags = row.beverageClass === "malt";
  const showChecks = row.status === "pass" || row.status === "fail";
  const stale = showChecks && row.edited;
  const tone = stale ? "edited" : STATUS_TONES[row.status];
  const cards = detailFieldCards(row);
  const cardsByKey = new Map(cards.map((card) => [card.key, card]));
  const readyToVerify = rowReady(row);
  const actionDisabled = processing || !readyToVerify;

  const actionLabel = isDraft
    ? "Verify this label"
    : processing
      ? "Verifying..."
      : stale
        ? "Re-run to update"
        : "Re-run this label";

  function checkFor(key: FieldKey): FieldCheckInfo | undefined {
    if (!showChecks) return undefined;
    if ((row.dirtyFields ?? []).includes(key)) {
      return {
        key,
        tone: "edited",
        statusLabel: "Edited · not checked",
        labelVal: "",
        reason: "",
        isFail: false,
        isEdited: true,
      };
    }
    const card = cardsByKey.get(key);
    if (!card) return undefined;
    return {
      key,
      tone: card.tone,
      statusLabel: card.statusLabel,
      labelVal: card.labelVal,
      reason: card.reason,
      isFail: card.isFail,
      isEdited: false,
    };
  }

  function handleFile(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) onAttachImage(row.localId, file);
    event.target.value = "";
  }

  return (
    <>
      <div className="slideover-backdrop" role="presentation" onClick={onClose} />
      <section
        className="slideover"
        role="dialog"
        aria-modal="true"
        aria-label="Label and application entry details"
      >
        <div className="slideover-figure">
          <div className="figure-head">
            <div className="panel-eyebrow">Label</div>
            <div className="figure-title-row">
              <div className="figure-title" title={row.brand}>
                {row.brand || "Untitled label"}
              </div>
              <span className={`status-pill tone-${tone}`}>
                <span className={`status-pill-dot tone-${tone}`} aria-hidden="true" />
                {stale ? "Edited" : STATUS_LABELS[row.status]}
              </span>
            </div>
            <div className="figure-summary">{summaryFor(row, stale)}</div>
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
            <div className="slideover-side-title-block">
              <div className="panel-eyebrow">Application Entry</div>
              <div className="slideover-file" title={row.fileName}>
                {row.fileName || "no image"}
              </div>
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
              ×
            </button>
          </header>

          <div className="slideover-body">
            <div className="value-stack">
              <Field
                fieldKey="brand_name"
                label="Brand name"
                value={row.brand}
                placeholder="e.g. Coyam"
                check={checkFor("brand_name")}
                onChange={(value) => onEdit(row.localId, { brand: value })}
              />
              <label className="value-field">
                <span className="value-field-label-row">
                  <span className="value-field-label">Beverage class</span>
                </span>
                <select
                  className="value-input"
                  value={row.beverageClass}
                  onChange={(event) => {
                    const beverageClass = event.target.value as BeverageClass;
                    onEdit(row.localId, {
                      beverageClass,
                      maltAddedNonbeverageAlcohol:
                        beverageClass === "malt" ? row.maltAddedNonbeverageAlcohol : false,
                      maltColorAdditiveApplicable:
                        beverageClass === "malt" ? row.maltColorAdditiveApplicable : false,
                    });
                  }}
                >
                  {(Object.keys(BEVERAGE_CLASS_LABELS) as BeverageClass[]).map((key) => (
                    <option key={key} value={key}>
                      {BEVERAGE_CLASS_LABELS[key]}
                    </option>
                  ))}
                </select>
              </label>
              <Field
                fieldKey="class_type_designation"
                label="Class / type"
                value={row.classType}
                placeholder="e.g. Red Wine"
                check={checkFor("class_type_designation")}
                onChange={(value) => onEdit(row.localId, { classType: value })}
              />
              <Field
                fieldKey="alcohol_content"
                label="Alcohol content"
                badge={abvOptional ? "OPTIONAL" : undefined}
                value={row.abv}
                placeholder="e.g. 40%"
                check={checkFor("alcohol_content")}
                onChange={(value) => onEdit(row.localId, { abv: value })}
              />
              <Field
                fieldKey="net_contents"
                label="Net contents"
                value={row.net}
                placeholder="e.g. 750 mL"
                check={checkFor("net_contents")}
                onChange={(value) => onEdit(row.localId, { net: value })}
              />
              <Field
                fieldKey="country_of_origin"
                label="Country of origin"
                value={row.country}
                placeholder="Domestic or country name"
                check={checkFor("country_of_origin")}
                onChange={(value) => onEdit(row.localId, { country: value })}
              />
              {showMaltFlags ? (
                <>
                  <CheckboxField
                    label="Added nonbeverage alcohol"
                    checked={row.maltAddedNonbeverageAlcohol}
                    onChange={(value) =>
                      onEdit(row.localId, { maltAddedNonbeverageAlcohol: value })
                    }
                  />
                  <CheckboxField
                    label="Color additive applicable"
                    checked={row.maltColorAdditiveApplicable}
                    check={checkFor("color_additive_disclosure")}
                    onChange={(value) =>
                      onEdit(row.localId, { maltColorAdditiveApplicable: value })
                    }
                  />
                </>
              ) : null}
              <Field
                fieldKey="name_address"
                label="Name & address of bottler / producer"
                value={row.nameAddr}
                placeholder="e.g. Banfi Products Corp, Old Brookville, NY"
                check={checkFor("name_address")}
                onChange={(value) => onEdit(row.localId, { nameAddr: value })}
              />
            </div>

            {showChecks ? (
              <>
                <div className="value-divider" />
                <AutoCheckRow label="Artifact legibility" check={checkFor("artifact_legibility")} />
                <AutoCheckRow
                  label="Government warning detected automatically"
                  check={checkFor("government_warning")}
                />
              </>
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
            {!readyToVerify ? (
              <span className="verify-disabled-note">Complete required fields first.</span>
            ) : null}
            <button
              type="button"
              className="btn-action"
              onClick={() => onAction(row.localId)}
              disabled={actionDisabled}
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
  fieldKey: FieldKey;
  label: string;
  value: string;
  placeholder?: string;
  badge?: string;
  check?: FieldCheckInfo;
  onChange: (value: string) => void;
};

function Field({ fieldKey, label, value, placeholder, badge, check, onChange }: FieldProps) {
  return (
    <div className="value-field-group" data-field-key={fieldKey}>
      <label className="value-field">
        <span className="value-field-label-row">
          <span className="value-field-label">
            {label}
            {badge ? <span className="value-badge">{badge}</span> : null}
          </span>
          <FieldStatusBadge check={check} />
        </span>
        <input
          className={`value-input${inputStateClass(check)}`}
          value={value}
          placeholder={placeholder}
          onChange={(event) => onChange(event.target.value)}
        />
      </label>
      <FailureDetail check={check} />
    </div>
  );
}

type CheckboxFieldProps = {
  label: string;
  checked: boolean;
  check?: FieldCheckInfo;
  onChange: (value: boolean) => void;
};

function CheckboxField({ label, checked, check, onChange }: CheckboxFieldProps) {
  return (
    <div className="value-field-group">
      <label className="value-field">
        <span className="value-field-label-row">
          <span className="value-field-label">{label}</span>
          <FieldStatusBadge check={check} />
        </span>
        <span className={`value-checkbox-row${inputStateClass(check)}`}>
          <input
            type="checkbox"
            checked={checked}
            onChange={(event) => onChange(event.target.checked)}
          />
          <span>{checked ? "Yes" : "No"}</span>
        </span>
      </label>
      <FailureDetail check={check} />
    </div>
  );
}

type AutoCheckRowProps = {
  label: string;
  check?: FieldCheckInfo;
};

function AutoCheckRow({ label, check }: AutoCheckRowProps) {
  if (!check) return null;
  return (
    <div className="auto-check-field">
      <div className="auto-check-row">
        <span>{label}</span>
        <FieldStatusBadge check={check} />
      </div>
      <FailureDetail check={check} />
    </div>
  );
}

function FieldStatusBadge({ check }: { check?: FieldCheckInfo }) {
  if (!check) return null;
  return (
    <span className={`field-status-badge tone-${check.tone}`}>
      <span className={`mini-check-dot tone-${check.tone}`} aria-hidden="true" />
      {check.statusLabel}
    </span>
  );
}

function FailureDetail({ check }: { check?: FieldCheckInfo }) {
  if (!check?.isFail) return null;
  const labelValue = check.labelVal.trim();
  const showLabelValue = labelValue.length > 0 && labelValue !== "—";
  return (
    <div className="field-failure-detail">
      {showLabelValue ? (
        <>
          <div className="field-failure-label">On label</div>
          <div className="field-failure-value">{check.labelVal}</div>
        </>
      ) : null}
      {check.reason ? <p className="field-failure-reason">{check.reason}</p> : null}
    </div>
  );
}

function inputStateClass(check?: FieldCheckInfo): string {
  if (check?.isEdited) return " is-edited";
  if (check?.isFail) return " is-fail";
  return "";
}
