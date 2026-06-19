import type { BatchItem } from "../types/verification";
import { getInitials, getItemBrand } from "../lib/itemDisplay";

type LabelThumbnailProps = {
  item: BatchItem;
  size?: "sm" | "lg";
};

// Shows the real label image when available, falling back to mono initials on
// a gradient (matching the design's placeholder treatment).
export function LabelThumbnail({ item, size = "sm" }: LabelThumbnailProps) {
  const brand = getItemBrand(item);

  return (
    <span className={`label-thumb label-thumb-${size}`} aria-hidden="true">
      {item.previewUrl ? (
        <img src={item.previewUrl} alt="" className="label-thumb-img" />
      ) : (
        <span className="label-thumb-initials">{getInitials(brand)}</span>
      )}
    </span>
  );
}
