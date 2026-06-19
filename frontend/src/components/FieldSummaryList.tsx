import { isPendingStatus, STATUS_LABELS } from "../lib/status";
import type { BatchItem, UiStatus } from "../types/verification";
import { InlineMessage } from "./InlineMessage";
import { StatusPill } from "./StatusPill";

type FieldSummaryListProps = {
  item: BatchItem;
};

export function FieldSummaryList({ item }: FieldSummaryListProps) {
  const isPending = isPendingStatus(item.status);

  return (
    <section className="detail-panel">
      <div className="detail-section">
        <h3>Field summary</h3>
        {isPending ? (
          <div className="waiting-panel">
            <span className="spinner" aria-hidden="true" />
            <div>
              <strong>{STATUS_LABELS[item.status]}</strong>
              <p>
                This file is still being reviewed. Leave this window open and it will update when
                the result arrives.
              </p>
            </div>
          </div>
        ) : (
          <div className="field-list">
            {item.fields.map((field) => (
              <article key={field.key} className="field-card">
                <div className="field-card-header">
                  <h4>{field.label}</h4>
                  <StatusPill status={displayDecisionStatus(field.status)} />
                </div>
                <dl className="field-grid">
                  <div>
                    <dt>Application value</dt>
                    <dd>{field.applicationValue}</dd>
                  </div>
                  <div>
                    <dt>Label value</dt>
                    <dd>{field.labelValue}</dd>
                  </div>
                </dl>
              </article>
            ))}
          </div>
        )}
      </div>

      {!isPending && item.errorMessage ? (
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
