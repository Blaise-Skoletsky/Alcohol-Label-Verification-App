import type { BatchItem } from "../types/verification";
import { ResultRow } from "./ResultRow";

type ResultsListProps = {
  items: BatchItem[];
  onOpenDetails: (index: number) => void;
};

export function ResultsList({ items, onOpenDetails }: ResultsListProps) {
  return (
    <div className="results-list" role="list">
      {items.map((item, index) => (
        <ResultRow key={item.localId} item={item} onOpen={() => onOpenDetails(index)} />
      ))}
    </div>
  );
}
