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
      <div className="console">
        <aside className="sidebar">
          <div className="brand-block">
            <div className="brand-name">Alcohol Label Verification</div>
            <div className="brand-note">Not affiliated with TTB</div>
          </div>

          <nav className="sidebar-nav">
            <span className="nav-item active">
              <span className="nav-marker" aria-hidden="true" />
              Open Applications
            </span>
            <span className="nav-item" aria-disabled="true">
              <span className="nav-marker" aria-hidden="true" />
              History
              <span className="nav-badge">SOON</span>
            </span>
          </nav>

          <div className="sidebar-upload">
            <UploadPanel
              config={config}
              configError={configError}
              formError={formError}
              isSubmitting={isSubmitting}
              onFilesChosen={handleFiles}
              onAcceptedFiles={shiftSelectionForNewFiles}
            />
          </div>
        </aside>

        <main className="main-area">
          <ResultsPanel items={items} statusCounts={statusCounts} onOpenDetails={openDetails} />
        </main>
      </div>

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
