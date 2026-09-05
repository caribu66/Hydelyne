import { FC, useRef } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { useAccessibleDialog } from '../hooks/useAccessibleDialog';
import { X, RotateCcw, SlidersHorizontal } from 'lucide-react';
import { FilterState, FilterPreset } from '../types';
import { FilterSidebar } from './FilterSidebar';

interface FilterModalProps {
  isOpen: boolean;
  onClose: () => void;
  filters: FilterState;
  onUpdateFilters: (updater: (prev: FilterState) => FilterState) => void;
  onResetFilters: () => void;
  onApplyPreset: (preset: FilterPreset) => void;
  totalFilteredCount: number;
  totalCount: number;
}

export const FilterModal: FC<FilterModalProps> = ({
  isOpen,
  onClose,
  filters,
  onUpdateFilters,
  onResetFilters,
  onApplyPreset,
  totalFilteredCount,
  totalCount,
}) => {
  const dialogRef = useRef<HTMLDivElement>(null);
  useAccessibleDialog(isOpen, dialogRef, onClose);

  return (
    <AnimatePresence>
      {isOpen && (
        <div
          id="filter-modal-backdrop"
          className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 overflow-y-auto"
        >
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="fixed inset-0 bg-canvas/80 backdrop-blur-md"
            onClick={onClose}
          />

          {/* Modal Container */}
          <motion.div
            ref={dialogRef}
            id="filter-modal-container"
            initial={{ opacity: 0, scale: 0.96, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 8 }}
            transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
            className="relative w-full max-w-2xl bg-surface border border-border-subtle rounded-[14px] shadow-2xl overflow-hidden my-auto max-h-[90vh] flex flex-col z-10"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-labelledby="filter-modal-title"
            aria-describedby="filter-modal-description"
          >
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-border-subtle bg-surface/90 shrink-0">
              <div className="flex items-center gap-2.5">
                <div className="p-1.5 rounded-lg bg-surface-raised border border-border-subtle text-secondary">
                  <SlidersHorizontal className="w-4 h-4" />
                </div>
                <div>
                  <h2 id="filter-modal-title" className="text-base sm:text-lg font-bold text-primary">
                    Filter contractors
                  </h2>
                  <p id="filter-modal-description" className="text-xs text-secondary">Narrow the roster by fit, availability, and credentials.</p>
                </div>
              </div>
              <button
                type="button"
                onClick={onClose}
                aria-label="Close filters"
                className="inline-flex min-h-9 min-w-9 items-center justify-center rounded-lg border border-border-subtle hover:border-border-strong text-secondary hover:text-primary hover:bg-surface-raised transition-colors cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-focus"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Scrollable Filter Body */}
            <div className="p-6 overflow-y-auto flex-1 space-y-6">
              <FilterSidebar
                filters={filters}
                onUpdateFilters={onUpdateFilters}
                onResetFilters={onResetFilters}
                onApplyPreset={(p) => {
                  onApplyPreset(p);
                  onClose();
                }}
                totalFilteredCount={totalFilteredCount}
                totalCount={totalCount}
              />
            </div>

            {/* Footer */}
            <div className="px-6 py-4 border-t border-border-subtle bg-canvas/80 flex items-center justify-between shrink-0">
              <button
                type="button"
                onClick={onResetFilters}
                className="inline-flex min-h-9 items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border-subtle text-xs font-semibold text-secondary hover:text-primary hover:bg-surface-raised transition-colors cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-focus"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                Reset all
              </button>

              <button
                type="button"
                onClick={onClose}
                className="min-h-9 px-5 py-1.5 rounded-lg bg-action hover:bg-action-hover text-on-action font-semibold text-xs transition-all cursor-pointer shadow-xs focus:outline-none focus-visible:ring-2 focus-visible:ring-focus"
              >
                Show {totalFilteredCount} contractors
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
};
