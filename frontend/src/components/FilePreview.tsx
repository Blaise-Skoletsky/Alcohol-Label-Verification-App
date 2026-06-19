import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { BatchItem } from "../types/verification";

type FilePreviewProps = {
  item: BatchItem;
};

const MIN_SCALE = 1;
const MAX_SCALE = 6;
// How much a single click or +/- button press changes the zoom.
const STEP = 1.6;
// Movement (px) beyond which a pointer gesture counts as a drag, not a click.
const CLICK_SLOP = 4;

type Transform = { scale: number; tx: number; ty: number };

const IDENTITY: Transform = { scale: 1, tx: 0, ty: 0 };

export function FilePreview({ item }: FilePreviewProps) {
  const [zoomed, setZoomed] = useState(false);

  return (
    <div className="slideover-figure-media">
      <img src={item.previewUrl} alt={item.fileName} className="slideover-figure-img" />
      <button
        type="button"
        className="figure-zoom-btn"
        onClick={() => setZoomed(true)}
        aria-label="Zoom in on the label"
      >
        <ZoomIcon />
        Zoom
      </button>

      {zoomed
        ? createPortal(
            <Lightbox
              src={item.previewUrl}
              alt={item.fileName}
              onClose={() => setZoomed(false)}
            />,
            document.body,
          )
        : null}
    </div>
  );
}

type LightboxProps = {
  src: string;
  alt: string;
  onClose: () => void;
};

function Lightbox({ src, alt, onClose }: LightboxProps) {
  const stageRef = useRef<HTMLDivElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const [transform, setTransform] = useState<Transform>(IDENTITY);

  // Pointer gesture bookkeeping. Tracks whether the current press has moved far
  // enough to be a pan (vs. a click), and the last pointer position while panning.
  const gesture = useRef({
    pointerId: -1,
    startX: 0,
    startY: 0,
    lastX: 0,
    lastY: 0,
    moved: false,
  });

  // Clamp the pan so at least part of the image always stays inside the stage.
  // Returns a transform with tx/ty corrected for the given scale.
  const clampPan = useCallback((next: Transform): Transform => {
    const stage = stageRef.current;
    const img = imgRef.current;
    if (!stage || !img) return next;

    const stageRect = stage.getBoundingClientRect();
    // Natural (scale-1) rendered size of the contained image.
    const baseW = img.clientWidth;
    const baseH = img.clientHeight;
    const scaledW = baseW * next.scale;
    const scaledH = baseH * next.scale;

    // The image is centered in the stage at rest; transform-origin is the center.
    // Allowed translation keeps the image from being dragged completely away:
    // we let it travel until its edge reaches the stage center.
    const maxX = Math.max(0, (scaledW - stageRect.width) / 2);
    const maxY = Math.max(0, (scaledH - stageRect.height) / 2);

    return {
      scale: next.scale,
      tx: clamp(next.tx, -maxX, maxX),
      ty: clamp(next.ty, -maxY, maxY),
    };
  }, []);

  // Zoom toward a point given in client coordinates, keeping that point visually
  // anchored. Used by both wheel and click-to-zoom.
  const zoomToPoint = useCallback(
    (clientX: number, clientY: number, nextScale: number) => {
      setTransform((prev) => {
        const stage = stageRef.current;
        if (!stage) return prev;
        const scale = clamp(nextScale, MIN_SCALE, MAX_SCALE);
        if (scale === prev.scale) return prev;

        const rect = stage.getBoundingClientRect();
        // Pointer position relative to the stage center (transform-origin).
        const px = clientX - rect.left - rect.width / 2;
        const py = clientY - rect.top - rect.height / 2;

        // Keep the image point under the cursor fixed:
        // screen = center + t + imgPoint * scale  =>  imgPoint = (px - t) / prevScale
        const ratio = scale / prev.scale;
        const tx = px - (px - prev.tx) * ratio;
        const ty = py - (py - prev.ty) * ratio;

        return clampPan({ scale, tx, ty });
      });
    },
    [clampPan],
  );

  const reset = useCallback(() => setTransform(IDENTITY), []);

  // Keep a ref of the current scale so wheel/step handlers read a fresh value
  // without re-subscribing.
  const currentScaleRef = useRef(transform.scale);

  // Step zoom from the stage center, used by the +/- buttons. clampPan zeroes
  // the pan once scale returns to 1, so zooming out fully re-centers.
  const stepZoom = useCallback(
    (factor: number) => {
      const stage = stageRef.current;
      if (!stage) return;
      const rect = stage.getBoundingClientRect();
      zoomToPoint(
        rect.left + rect.width / 2,
        rect.top + rect.height / 2,
        currentScaleRef.current * factor,
      );
    },
    [zoomToPoint],
  );

  useEffect(() => {
    currentScaleRef.current = transform.scale;
  }, [transform.scale]);

  // Escape closes the lightbox. Capture phase + stopPropagation keeps the key
  // from also closing the surrounding slide-over.
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.stopPropagation();
        onClose();
      }
    }
    window.addEventListener("keydown", onKeyDown, true);
    return () => window.removeEventListener("keydown", onKeyDown, true);
  }, [onClose]);

  // Wheel zoom anchored at the cursor. Non-passive so we can preventDefault and
  // stop the page/slide-over from scrolling underneath.
  useEffect(() => {
    const stage = stageRef.current;
    if (!stage) return;
    function onWheel(event: WheelEvent) {
      event.preventDefault();
      const factor = Math.exp(-event.deltaY * 0.0015);
      zoomToPoint(event.clientX, event.clientY, currentScaleRef.current * factor);
    }
    stage.addEventListener("wheel", onWheel, { passive: false });
    return () => stage.removeEventListener("wheel", onWheel);
  }, [zoomToPoint]);

  function onPointerDown(event: React.PointerEvent) {
    if (event.button !== 0) return;
    const g = gesture.current;
    g.pointerId = event.pointerId;
    g.startX = g.lastX = event.clientX;
    g.startY = g.lastY = event.clientY;
    g.moved = false;
    (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
  }

  function onPointerMove(event: React.PointerEvent) {
    const g = gesture.current;
    if (g.pointerId !== event.pointerId) return;

    const dxTotal = event.clientX - g.startX;
    const dyTotal = event.clientY - g.startY;
    if (!g.moved && Math.hypot(dxTotal, dyTotal) > CLICK_SLOP) {
      g.moved = true;
    }
    if (!g.moved || currentScaleRef.current <= MIN_SCALE) {
      g.lastX = event.clientX;
      g.lastY = event.clientY;
      return;
    }

    const dx = event.clientX - g.lastX;
    const dy = event.clientY - g.lastY;
    g.lastX = event.clientX;
    g.lastY = event.clientY;
    setTransform((prev) => clampPan({ ...prev, tx: prev.tx + dx, ty: prev.ty + dy }));
  }

  function onPointerUp(event: React.PointerEvent) {
    const g = gesture.current;
    if (g.pointerId !== event.pointerId) return;
    const wasClick = !g.moved;
    g.pointerId = -1;
    try {
      (event.currentTarget as HTMLElement).releasePointerCapture(event.pointerId);
    } catch {
      // Pointer capture may already be gone; ignore.
    }
    if (wasClick) {
      // Click-to-zoom toward the clicked point. At max zoom, a click resets.
      if (currentScaleRef.current >= MAX_SCALE) {
        reset();
      } else {
        zoomToPoint(event.clientX, event.clientY, currentScaleRef.current * STEP);
      }
    }
  }

  const isZoomed = transform.scale > MIN_SCALE;

  return (
    <div
      className="lightbox"
      role="dialog"
      aria-modal="true"
      aria-label="Label zoomed view"
      onClick={(event) => {
        // Clicking the dark backdrop (outside the stage) closes the lightbox.
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        ref={stageRef}
        className={`lightbox-stage${isZoomed ? " is-zoomed" : ""}`}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onDoubleClick={reset}
      >
        <img
          ref={imgRef}
          src={src}
          alt={alt}
          className="lightbox-img"
          draggable={false}
          style={{
            transform: `translate(${transform.tx}px, ${transform.ty}px) scale(${transform.scale})`,
          }}
        />
      </div>

      <div className="lightbox-controls" onClick={(event) => event.stopPropagation()}>
        <button
          type="button"
          className="lightbox-ctrl"
          onClick={() => stepZoom(1 / STEP)}
          disabled={!isZoomed}
          aria-label="Zoom out"
        >
          –
        </button>
        <button
          type="button"
          className="lightbox-ctrl"
          onClick={reset}
          disabled={!isZoomed}
          aria-label="Reset zoom"
        >
          Reset
        </button>
        <button
          type="button"
          className="lightbox-ctrl"
          onClick={() => stepZoom(STEP)}
          disabled={transform.scale >= MAX_SCALE}
          aria-label="Zoom in"
        >
          +
        </button>
      </div>

      <button
        type="button"
        className="lightbox-close"
        onClick={onClose}
        aria-label="Close zoomed view"
      >
        ✕
      </button>
    </div>
  );
}

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

function ZoomIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="2" />
      <line x1="11" y1="8" x2="11" y2="14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      <line x1="8" y1="11" x2="14" y2="11" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      <line x1="16.5" y1="16.5" x2="21" y2="21" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}
