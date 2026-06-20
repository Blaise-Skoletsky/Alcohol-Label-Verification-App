export function CheckIcon({ size = 11, color = "#fff" }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 14 14" fill="none" aria-hidden="true">
      <path
        d="M11.5 3.5L5.5 10L2.5 7"
        stroke={color}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function UploadIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M12 16V4M12 4L7 9M12 4l5 5"
        stroke="#fff"
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M4 16v3a1 1 0 001 1h14a1 1 0 001-1v-3"
        stroke="#fff"
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function GridIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 15 15" fill="none" aria-hidden="true">
      <rect x="0.5" y="0.5" width="6" height="6" rx="1.5" fill="#1a1a1a" />
      <rect x="8.5" y="0.5" width="6" height="6" rx="1.5" fill="#c2c2bb" />
      <rect x="0.5" y="8.5" width="6" height="6" rx="1.5" fill="#c2c2bb" />
      <rect x="8.5" y="8.5" width="6" height="6" rx="1.5" fill="#1a1a1a" />
    </svg>
  );
}

export function RerunIcon({ spinning = false }: { spinning?: boolean }) {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 14 14"
      fill="none"
      aria-hidden="true"
      className={spinning ? "spin" : undefined}
    >
      <path
        d="M12 7a5 5 0 11-1.46-3.54M12 2v3h-3"
        stroke="#5c5c5c"
        strokeWidth={1.6}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function RerunIconLight({ spinning = false }: { spinning?: boolean }) {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 14 14"
      fill="none"
      aria-hidden="true"
      className={spinning ? "spin" : undefined}
    >
      <path
        d="M12 7a5 5 0 11-1.46-3.54M12 2v3h-3"
        stroke="#fff"
        strokeWidth={1.6}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
