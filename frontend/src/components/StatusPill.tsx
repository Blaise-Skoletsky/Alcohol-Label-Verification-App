import { STATUS_TONES } from "../lib/status";
import { STATUS_DISPLAY_LABELS } from "../lib/itemDisplay";
import type { UiStatus } from "../types/verification";

type StatusPillProps = {
  status: UiStatus;
  label?: string;
};

export function StatusPill({ status, label = STATUS_DISPLAY_LABELS[status] }: StatusPillProps) {
  const tone = STATUS_TONES[status];
  return (
    <span className={`status-pill tone-${tone}`}>
      <span className={`status-pill-dot tone-${tone}`} aria-hidden="true" />
      {label}
    </span>
  );
}
