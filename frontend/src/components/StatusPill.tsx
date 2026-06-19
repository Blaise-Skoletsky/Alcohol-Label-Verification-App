import { STATUS_LABELS, STATUS_TONES } from "../lib/status";
import type { UiStatus } from "../types/verification";

type StatusPillProps = {
  status: UiStatus;
  label?: string;
};

export function StatusPill({ status, label = STATUS_LABELS[status] }: StatusPillProps) {
  return <span className={`status-pill ${STATUS_TONES[status]}`}>{label}</span>;
}
