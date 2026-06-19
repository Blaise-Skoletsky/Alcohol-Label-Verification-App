import { STATUS_TONES, isPendingStatus } from "../lib/status";
import { FIELD_SHORT_LABELS, getItemBrand } from "../lib/itemDisplay";
import type { BatchItem } from "../types/verification";
import { LabelThumbnail } from "./LabelThumbnail";
import { StatusPill } from "./StatusPill";

type ResultRowProps = {
  item: BatchItem;
  onOpen: () => void;
};

export function ResultRow({ item, onOpen }: ResultRowProps) {
  const brand = getItemBrand(item);
  const pending = isPendingStatus(item.status);

  return (
    <button type="button" className="result-row" role="listitem" onClick={onOpen}>
      <span className="row-label">
        <LabelThumbnail item={item} />
        <span className="row-label-text">
          <span className="row-brand" title={brand}>
            {brand}
          </span>
          <span className="row-file" title={item.fileName}>
            {item.fileName}
          </span>
        </span>
      </span>

      <span className="row-checks">
        {item.fields.map((field) => {
          // While a label is still being checked, show the working dot for every
          // mini-check rather than each field's not-yet-computed status.
          const tone = STATUS_TONES[pending ? item.status : field.status];
          return (
            <span key={field.key} className="mini-check">
              <span className={`mini-check-dot tone-${tone}`} aria-hidden="true" />
              <span className="mini-check-label">{FIELD_SHORT_LABELS[field.key]}</span>
            </span>
          );
        })}
      </span>

      <span className="row-status">
        <StatusPill status={item.status} />
      </span>

      <span className="row-time">{item.updatedAtLabel}</span>
    </button>
  );
}
