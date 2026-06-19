import { STATUS_TONES } from "../lib/status";
import type { BatchItem } from "../types/verification";
import { StatusPill } from "./StatusPill";

type ResultRowProps = {
  item: BatchItem;
  onOpen: () => void;
};

export function ResultRow({ item, onOpen }: ResultRowProps) {
  return (
    <button type="button" className="result-row" role="listitem" onClick={onOpen}>
      <span className={`status-dot ${STATUS_TONES[item.status]}`} aria-hidden="true" />
      <span className="row-main">
        <span className="row-title">{item.fileName}</span>
        <span className="row-subtitle">{item.summary}</span>
      </span>
      <span className="row-meta">
        <StatusPill status={item.status} label={item.overallLabel} />
        <span className="row-time">{item.updatedAtLabel}</span>
      </span>
    </button>
  );
}
