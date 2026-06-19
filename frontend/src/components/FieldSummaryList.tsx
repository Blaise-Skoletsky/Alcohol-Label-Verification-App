import { isPendingStatus } from "../lib/status";
import type { BatchItem, FieldSummary, UiStatus } from "../types/verification";
import { InlineMessage } from "./InlineMessage";
import { StatusPill } from "./StatusPill";

type FieldSummaryListProps = {
  item: BatchItem;
};

export function FieldSummaryList({ item }: FieldSummaryListProps) {
  if (isPendingStatus(item.status)) {
    return (
      <div className="checking-note">
        <span className="checking-dot" aria-hidden="true" />
        <p>
          This label is still being checked. Leave the panel open and the results will appear as
          soon as the review finishes.
        </p>
      </div>
    );
  }

  return (
    <section className="checks-section">
      <div className="section-eyebrow">Checks</div>
      <div className="field-list">
        {item.fields.map((field) => (
          <article key={field.key} className="field-card">
            <div className="field-card-header">
              <span className="field-title">{field.label}</span>
              <StatusPill status={displayDecisionStatus(field.status)} />
            </div>
            <div className="field-values">
              {field.key !== "government_warning" && (
                <div className="field-value-box">
                  <div className="field-value-label">Application</div>
                  <div className="field-value">
                    {field.key === "artifact_legibility"
                      ? legibilityLabel(field.applicationValue, field.status)
                      : field.applicationValue}
                  </div>
                </div>
              )}
              <div className={`field-value-box${field.key === "government_warning" ? " field-value-box--full" : ""}`}>
                <div className="field-value-label">On label</div>
                <div className="field-value">
                  {field.key === "artifact_legibility"
                    ? legibilityLabel(field.labelValue, field.status)
                    : field.labelValue}
                </div>
              </div>
            </div>
            <p className="field-reason">{field.reason}</p>
          </article>
        ))}
      </div>

      {item.errorMessage ? (
        <InlineMessage tone="error" className="plain-detail">
          {item.errorMessage}
        </InlineMessage>
      ) : null}
    </section>
  );
}

function legibilityLabel(raw: string, status: FieldSummary["status"]): string {
  if (status === "pass") return "Legible";
  if (status === "fail") return "Illegible";
  return "Unclear";
}

function displayDecisionStatus(status: UiStatus): "pass" | "needs-review" | "fail" {
  if (status === "pass") {
    return "pass";
  }
  if (status === "fail" || status === "processing-error") {
    return "fail";
  }
  return "needs-review";
}
