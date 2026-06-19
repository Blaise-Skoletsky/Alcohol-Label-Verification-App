import { useEffect, useRef, useState } from "react";
import { DetailModal } from "./components/DetailModal";
import { ResultsPanel } from "./components/ResultsPanel";
import { SamplePickerModal } from "./components/SamplePickerModal";
import { UploadPanel } from "./components/UploadPanel";
import { useAppConfig } from "./hooks/useAppConfig";
import { useVerificationQueue } from "./hooks/useVerificationQueue";

export function App() {
  const { config, configError } = useAppConfig();
  const { items, statusCounts, formError, isSubmitting, handleFiles } =
    useVerificationQueue(config);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [samplePickerOpen, setSamplePickerOpen] = useState(false);
  const [toast, setToast] = useState("");
  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (toastTimerRef.current !== null) clearTimeout(toastTimerRef.current);
    };
  }, []);

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

  function handleSampleRun(files: File[]) {
    const result = handleFiles(files);
    if (result.accepted) {
      shiftSelectionForNewFiles(result.addedCount);
      const n = files.length;
      const message = `Sent ${n} sample label${n === 1 ? "" : "s"} to verification`;
      setToast(message);
      if (toastTimerRef.current !== null) clearTimeout(toastTimerRef.current);
      toastTimerRef.current = setTimeout(() => setToast(""), 3200);
    }
  }

  return (
    <>
      <div className="console">
        <aside className="sidebar">
          <div className="brand-block">
            <div className="brand-name">Alcohol Label Verification</div>
            <div className="brand-note">Not affiliated with TTB</div>
          </div>

          <div className="sidebar-upload">
            <UploadPanel
              config={config}
              configError={configError}
              formError={formError}
              isSubmitting={isSubmitting}
              onFilesChosen={handleFiles}
              onAcceptedFiles={shiftSelectionForNewFiles}
              onOpenSamplePicker={() => setSamplePickerOpen(true)}
            />
          </div>
        </aside>

        <main className="main-area">
          <ResultsPanel
            items={items}
            statusCounts={statusCounts}
            onOpenDetails={openDetails}
            onOpenSamplePicker={() => setSamplePickerOpen(true)}
          />
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

      <SamplePickerModal
        open={samplePickerOpen}
        onClose={() => setSamplePickerOpen(false)}
        onRun={handleSampleRun}
      />

      {toast ? (
        <div className="sample-toast">
          <span className="sample-toast-dot" aria-hidden="true" />
          {toast}
        </div>
      ) : null}
    </>
  );
}
