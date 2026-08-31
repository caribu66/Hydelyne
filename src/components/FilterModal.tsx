import React from 'react';
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

export const FilterModal: React.FC<FilterModalProps> = ({
  isOpen,
  onClose,
  filters,
  onUpdateFilters,
  onResetFilters,
  onApplyPreset,
  totalFilteredCount,
  totalCount,
}) => {
  if (!isOpen) return null;

  return (
    <div
      id="filter-modal-backdrop"
      className="fixed inset-0 z-50 bg-zinc-950/80 backdrop-blur-md flex items-center justify-center p-3 sm:p-6 overflow-y-auto"
      onClick={onClose}
    >
      <div
        id="filter-modal-container"
        className="relative w-full max-w-2xl bg-zinc-900 border border-zinc-800 rounded-3xl shadow-2xl overflow-hidden my-auto max-h-[90vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-800 bg-zinc-900/90 shrink-0">
          <div className="flex items-center gap-2">
            <SlidersHorizontal className="w-5 h-5 text-indigo-400" />
            <h3 className="text-base sm:text-lg font-bold text-zinc-100">
              Filter Talent Database
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-full text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors cursor-pointer"
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
            className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-zinc-400 hover:text-white transition-colors cursor-pointer"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            Reset all
          </button>

          <button
            type="button"
            onClick={onClose}
            className="px-6 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs shadow-md shadow-indigo-600/30 transition-all cursor-pointer"
          >
            Show {totalFilteredCount} Profiles
          </button>
        </div>
      </div>
    </div>
  );
};
