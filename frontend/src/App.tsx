import { useState } from "react";
import { DetailModal } from "./components/DetailModal";
import { ResultsPanel } from "./components/ResultsPanel";
import { UploadPanel } from "./components/UploadPanel";
import { useAppConfig } from "./hooks/useAppConfig";
import { useVerificationQueue } from "./hooks/useVerificationQueue";

export function App() {
  const { config, configError } = useAppConfig();
  const { items, statusCounts, formError, isSubmitting, handleFiles } =
    useVerificationQueue(config);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);

  const selectedItem = selectedIndex === null ? null : items[selectedIndex] ?? null;

  function openDetails(index: number) {
    setSelectedIndex(index);
  }

  function closeDetails() {
    setSelectedIndex(null);
  }

  function moveSelection(direction: -1 | 1) {
    setSelectedIndex((currentIndex) => {
      if (currentIndex === null) {
        return currentIndex;
      }
      const nextIndex = currentIndex + direction;
      if (nextIndex < 0 || nextIndex >= items.length) {
        return currentIndex;
      }
      return nextIndex;
    });
  }

  function shiftSelectionForNewFiles(count: number) {
    setSelectedIndex((currentIndex) => (currentIndex === null ? null : currentIndex + count));
  }

  return (
    <>
      <main className="app-shell">
        <section className="hero-panel">
          <div className="hero-copy">
            <h1>Alcohol Label Verification</h1>
            <p className="hero-description">
              Upload one or more applications. The system checks the application against the label
              and flags anything that needs your review.
            </p>
            <p className="prototype-notice">
              * This prototype is not an official TTB application and should not be used for final
              label approvals or legal compliance decisions.
            </p>
          </div>

          <UploadPanel
            config={config}
            configError={configError}
            formError={formError}
            isSubmitting={isSubmitting}
            onFilesChosen={handleFiles}
            onAcceptedFiles={shiftSelectionForNewFiles}
          />
        </section>

        <ResultsPanel items={items} statusCounts={statusCounts} onOpenDetails={openDetails} />
      </main>

      {selectedItem ? (
        <DetailModal
          item={selectedItem}
          currentIndex={selectedIndex ?? 0}
          totalItems={items.length}
          onClose={closeDetails}
          onMove={moveSelection}
        />
      ) : null}
    </>
  );
}
