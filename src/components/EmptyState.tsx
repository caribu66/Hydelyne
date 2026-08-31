import React from 'react';
import { FilterState } from '../types';
import { SearchX, RotateCcw, SlidersHorizontal, Sparkles } from 'lucide-react';

interface EmptyStateProps {
  filters: FilterState;
  onResetFilters: () => void;
  onUpdateFilters: (updater: (prev: FilterState) => FilterState) => void;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  filters,
  onResetFilters,
  onUpdateFilters,
}) => {
  return (
    <div
      id="empty-search-results"
      className="bg-zinc-900/80 border border-zinc-800 rounded-2xl p-8 sm:p-12 text-center max-w-xl mx-auto my-8 shadow-xl space-y-5"
    >
      <div className="w-12 h-12 bg-zinc-800 border border-zinc-700/60 rounded-2xl flex items-center justify-center mx-auto text-zinc-400">
        <SearchX className="w-6 h-6 text-blue-400" />
      </div>

      <div className="space-y-1.5">
        <h3 className="text-base font-semibold text-zinc-100">No matching specialists found</h3>
        <p className="text-xs sm:text-sm text-zinc-400 max-w-md mx-auto leading-relaxed">
          No specialists meet all of your selected criteria simultaneously. Try loosening one or two filters below.
        </p>
      </div>

      {/* Suggested Quick Fixes */}
      <div className="pt-4 border-t border-zinc-800 text-xs text-zinc-400 space-y-2.5">
        <span className="font-medium text-zinc-300 block text-[11px] uppercase tracking-wider">
          Suggested Relaxations:
        </span>
        <div className="flex flex-wrap justify-center gap-2">
          {filters.skillMatchMode === 'ALL' && filters.selectedSkills.length > 1 && (
            <button
              type="button"
              onClick={() =>
                onUpdateFilters((prev) => ({ ...prev, skillMatchMode: 'ANY' }))
              }
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl bg-blue-950/60 border border-blue-800/60 text-blue-300 font-medium hover:bg-blue-900/60 transition-colors cursor-pointer"
            >
              <Sparkles className="w-3.5 h-3.5" />
              Switch skill match to ANY
            </button>
          )}

          {(filters.minExperience > 0 || filters.maxExperience < 20) && (
            <button
              type="button"
              onClick={() =>
                onUpdateFilters((prev) => ({
                  ...prev,
                  minExperience: 0,
                  maxExperience: 20,
                }))
              }
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl bg-zinc-800 border border-zinc-700 text-zinc-300 font-medium hover:bg-zinc-700 transition-colors cursor-pointer"
            >
              <SlidersHorizontal className="w-3.5 h-3.5" />
              Expand experience to 0-20+ yrs
            </button>
          )}

          {filters.locations.length > 0 && (
            <button
              type="button"
              onClick={() =>
                onUpdateFilters((prev) => ({ ...prev, locations: [] }))
              }
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl bg-zinc-800 border border-zinc-700 text-zinc-300 font-medium hover:bg-zinc-700 transition-colors cursor-pointer"
            >
              Clear location restrictions
            </button>
          )}

          {filters.companies.length > 0 && (
            <button
              type="button"
              onClick={() =>
                onUpdateFilters((prev) => ({ ...prev, companies: [] }))
              }
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl bg-zinc-800 border border-zinc-700 text-zinc-300 font-medium hover:bg-zinc-700 transition-colors cursor-pointer"
            >
              Clear company constraints
            </button>
          )}
        </div>
      </div>

      <div className="pt-2">
        <button
          type="button"
          id="empty-state-reset-btn"
          onClick={onResetFilters}
          className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs transition-all shadow-xs cursor-pointer"
        >
          <RotateCcw className="w-3.5 h-3.5" />
          Reset All Filters
        </button>
      </div>
    </div>
  );
};
