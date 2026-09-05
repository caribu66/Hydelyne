import { KeyboardEvent, PointerEvent, RefObject, useCallback, useRef, useState } from 'react';

const SPLIT_RATIO_STORAGE_KEY = 'hydenlyne_split_pane_ratio';
const DEFAULT_SPLIT_RATIO = 35;
const MIN_SPLIT_RATIO = 25;
const MAX_SPLIT_RATIO = 60;
const SNAP_RATIOS = [35, 50, 28];

interface UseSplitPaneResizeResult {
  splitRatio: number;
  minRatio: number;
  maxRatio: number;
  isDraggingSplitter: boolean;
  splitContainerRef: RefObject<HTMLDivElement | null>;
  handleSplitterPointerDown: (e: PointerEvent) => void;
  handleSplitterDoubleClick: () => void;
  handleSplitterKeyDown: (e: KeyboardEvent<HTMLDivElement>) => void;
}

/** Draggable, keyboard-adjustable, localStorage-persisted split ratio for the results/dossier panes. */
export function useSplitPaneResize(): UseSplitPaneResizeResult {
  const [splitRatio, setSplitRatio] = useState<number>(() => {
    try {
      const saved = localStorage.getItem(SPLIT_RATIO_STORAGE_KEY);
      if (saved) {
        const parsed = parseFloat(saved);
        if (!Number.isNaN(parsed) && parsed >= MIN_SPLIT_RATIO && parsed <= MAX_SPLIT_RATIO) {
          return parsed;
        }
      }
    } catch {
      // Ignore localStorage availability issues
    }
    return DEFAULT_SPLIT_RATIO;
  });

  const [isDraggingSplitter, setIsDraggingSplitter] = useState(false);
  const splitContainerRef = useRef<HTMLDivElement>(null);

  const updateSplitRatio = useCallback((newRatio: number) => {
    const clamped = Math.min(MAX_SPLIT_RATIO, Math.max(MIN_SPLIT_RATIO, Math.round(newRatio * 10) / 10));
    setSplitRatio(clamped);
    try {
      localStorage.setItem(SPLIT_RATIO_STORAGE_KEY, clamped.toString());
    } catch {
      // Ignore storage write errors
    }
  }, []);

  const handleSplitterPointerDown = useCallback((e: PointerEvent) => {
    if (e.button !== 0) return;
    e.preventDefault();
    setIsDraggingSplitter(true);

    const container = splitContainerRef.current;
    if (!container) return;

    const handlePointerMove = (moveEvent: globalThis.PointerEvent) => {
      const rect = container.getBoundingClientRect();
      if (rect.width <= 0) return;
      const relativeX = moveEvent.clientX - rect.left;
      const percentage = (relativeX / rect.width) * 100;
      const clamped = Math.min(MAX_SPLIT_RATIO, Math.max(MIN_SPLIT_RATIO, Math.round(percentage * 10) / 10));
      setSplitRatio(clamped);
    };

    const handlePointerUp = (upEvent: globalThis.PointerEvent) => {
      window.removeEventListener('pointermove', handlePointerMove);
      window.removeEventListener('pointerup', handlePointerUp);
      window.removeEventListener('pointercancel', handlePointerUp);
      document.body.style.removeProperty('cursor');
      document.body.style.removeProperty('user-select');
      setIsDraggingSplitter(false);

      const rect = container.getBoundingClientRect();
      if (rect.width > 0) {
        const relativeX = upEvent.clientX - rect.left;
        const percentage = (relativeX / rect.width) * 100;
        updateSplitRatio(percentage);
      }
    };

    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    window.addEventListener('pointermove', handlePointerMove);
    window.addEventListener('pointerup', handlePointerUp);
    window.addEventListener('pointercancel', handlePointerUp);
  }, [updateSplitRatio]);

  const handleSplitterDoubleClick = useCallback(() => {
    // Cycle between snap presets: 35% -> 50% -> 28% -> 35%
    const currentRounded = Math.round(splitRatio);
    const currentIndex = SNAP_RATIOS.findIndex((ratio) => Math.abs(ratio - currentRounded) <= 2);
    const nextRatio = (currentIndex >= 0 && SNAP_RATIOS[(currentIndex + 1) % SNAP_RATIOS.length] !== undefined)
      ? (SNAP_RATIOS[(currentIndex + 1) % SNAP_RATIOS.length] ?? DEFAULT_SPLIT_RATIO)
      : DEFAULT_SPLIT_RATIO;
    updateSplitRatio(nextRatio);
  }, [splitRatio, updateSplitRatio]);

  const handleSplitterKeyDown = useCallback((e: KeyboardEvent<HTMLDivElement>) => {
    // Home/End/arrow keys are also global result-list navigation shortcuts
    // (useKeyboardNavigation.ts), whose guard excludes INPUT/TEXTAREA/SELECT/
    // BUTTON/A but not a custom role="separator" div. Without stopping
    // propagation here, that window-level handler fires too and moves focus
    // to a result row via requestAnimationFrame — invisible under light load,
    // but a real race that reliably steals focus off the separator under
    // heavier load (see the regression test this guards).
    if (e.key === 'ArrowLeft') {
      e.preventDefault();
      e.stopPropagation();
      updateSplitRatio(splitRatio - 2);
    } else if (e.key === 'ArrowRight') {
      e.preventDefault();
      e.stopPropagation();
      updateSplitRatio(splitRatio + 2);
    } else if (e.key === 'Home') {
      e.preventDefault();
      e.stopPropagation();
      updateSplitRatio(MIN_SPLIT_RATIO);
    } else if (e.key === 'End') {
      e.preventDefault();
      e.stopPropagation();
      updateSplitRatio(MAX_SPLIT_RATIO);
    } else if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      e.stopPropagation();
      handleSplitterDoubleClick();
    }
  }, [splitRatio, updateSplitRatio, handleSplitterDoubleClick]);

  return {
    splitRatio,
    minRatio: MIN_SPLIT_RATIO,
    maxRatio: MAX_SPLIT_RATIO,
    isDraggingSplitter,
    splitContainerRef,
    handleSplitterPointerDown,
    handleSplitterDoubleClick,
    handleSplitterKeyDown,
  };
}
