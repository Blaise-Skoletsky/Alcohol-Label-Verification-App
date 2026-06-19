import { isPendingStatus } from "../lib/status";
import type { BatchItem, UiStatus } from "../types/verification";
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
              <div className="field-value-box">
                <div className="field-value-label">Application</div>
                <div className="field-value">{field.applicationValue}</div>
              </div>
              <div className="field-value-box">
                <div className="field-value-label">On label</div>
                <div className="field-value">{field.labelValue}</div>
              </div>
            </div>
            <p className="field-reason">{field.reason}</p>
            <div className="field-confidence">
              <span className="field-confidence-label">Confidence</span>
              <span className="field-confidence-value">{field.confidence}</span>
            </div>
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

function displayDecisionStatus(status: UiStatus): "pass" | "needs-review" | "fail" {
  if (status === "pass") {
    return "pass";
  }
  if (status === "fail" || status === "processing-error") {
    return "fail";
  }
  return "needs-review";
}
