import { FC, useRef } from 'react';
import { useAccessibleDialog } from '../hooks/useAccessibleDialog';
import { X, RotateCcw, SlidersHorizontal, Check, Sparkles } from 'lucide-react';
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

  if (!isOpen) return null;

  return (
    <div
      id="filter-modal-backdrop"
      className="ui-overlay-enter fixed inset-0 z-50 bg-zinc-950/80 backdrop-blur-md flex items-center justify-center p-3 sm:p-6 overflow-y-auto"
      onClick={onClose}
    >
      <div
        ref={dialogRef}
        id="filter-modal-container"
        className="ui-surface-enter relative w-full max-w-2xl bg-zinc-900 border border-zinc-800 rounded-3xl shadow-2xl overflow-hidden my-auto max-h-[90vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="filter-modal-title"
        aria-describedby="filter-modal-description"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-800 bg-zinc-900/90 shrink-0">
          <div className="flex items-center gap-2">
            <SlidersHorizontal className="w-5 h-5 text-zinc-400" />
            <div>
            <h2 id="filter-modal-title" className="text-base sm:text-lg font-bold text-zinc-100">
              Filter specialists
            </h2>
            <p id="filter-modal-description" className="text-xs text-zinc-400">Narrow the roster by fit, availability, and credentials.</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close filters"
            className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-xl text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
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
        <div className="px-6 py-4 border-t border-zinc-800 bg-zinc-950/80 flex items-center justify-between shrink-0">
          <button
            type="button"
            onClick={onResetFilters}
            className="inline-flex min-h-11 items-center gap-1.5 px-4 py-2 text-xs font-semibold text-zinc-400 hover:text-white transition-colors cursor-pointer"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            Reset all
          </button>

          <button
            type="button"
            onClick={onClose}
            className="min-h-11 px-6 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-bold text-xs transition-all cursor-pointer"
          >
            Show {totalFilteredCount} specialists
          </button>
        </div>
      </div>
    </div>
  );
};
