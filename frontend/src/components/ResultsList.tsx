import type { BatchItem } from "../types/verification";
import { ResultRow } from "./ResultRow";

type ResultsListProps = {
  items: BatchItem[];
  onOpenDetails: (index: number) => void;
};

export function ResultsList({ items, onOpenDetails }: ResultsListProps) {
  return (
    <div className="results-table">
      <div className="table-head" role="presentation">
        <span>Label</span>
        <span>Checks</span>
        <span>Status</span>
        <span className="align-right">Submitted</span>
      </div>
      <div className="table-body" role="list">
        {items.map((item, index) => (
          <ResultRow key={item.localId} item={item} onOpen={() => onOpenDetails(index)} />
        ))}
      </div>
    </div>
  );
}
