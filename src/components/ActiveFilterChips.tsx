import React from 'react';
import { FilterState } from '../types';
import { X, RotateCcw, Filter } from 'lucide-react';

interface ActiveFilterChipsProps {
  filters: FilterState;
  onUpdateFilters: (updater: (prev: FilterState) => FilterState) => void;
  onResetFilters: () => void;
}

export const ActiveFilterChips: React.FC<ActiveFilterChipsProps> = ({
  filters,
  onUpdateFilters,
  onResetFilters,
}) => {
  const chips: { id: string; label: string; onRemove: () => void; category: string }[] = [];

  // 1. Keyword
  if (filters.keyword.trim()) {
    chips.push({
      id: 'chip-keyword',
      category: 'Query',
      label: `"${filters.keyword}"`,
      onRemove: () => onUpdateFilters((prev) => ({ ...prev, keyword: '' })),
    });
  }

  // 2. Locations
  filters.locations.forEach((loc) => {
    chips.push({
      id: `chip-loc-${loc}`,
      category: 'Location',
      label: loc,
      onRemove: () =>
        onUpdateFilters((prev) => ({
          ...prev,
          locations: prev.locations.filter((l) => l !== loc),
        })),
    });
  });

  // 3. Remote Types
  filters.remoteTypes.forEach((rt) => {
    chips.push({
      id: `chip-rt-${rt}`,
      category: 'Mode',
      label: rt,
      onRemove: () =>
        onUpdateFilters((prev) => ({
          ...prev,
          remoteTypes: prev.remoteTypes.filter((t) => t !== rt),
        })),
    });
  });

  // 4. Skills
  filters.selectedSkills.forEach((skill) => {
    chips.push({
      id: `chip-skill-${skill}`,
      category: `Skill (${filters.skillMatchMode})`,
      label: skill,
      onRemove: () =>
        onUpdateFilters((prev) => ({
          ...prev,
          selectedSkills: prev.selectedSkills.filter((s) => s !== skill),
        })),
    });
  });

  // 5. Experience
  if (filters.minExperience > 0 || filters.maxExperience < 20) {
    chips.push({
      id: 'chip-exp',
      category: 'Exp',
      label: `${filters.minExperience} - ${
        filters.maxExperience >= 20 ? '20+ yrs' : `${filters.maxExperience} yrs`
      }`,
      onRemove: () =>
        onUpdateFilters((prev) => ({
          ...prev,
          minExperience: 0,
          maxExperience: 20,
        })),
    });
  }

  // 6. Companies
  filters.companies.forEach((comp) => {
    chips.push({
      id: `chip-comp-${comp}`,
      category: 'Company',
      label: comp,
      onRemove: () =>
        onUpdateFilters((prev) => ({
          ...prev,
          companies: prev.companies.filter((c) => c !== comp),
        })),
    });
  });

  // 7. Availability
  filters.availability.forEach((avail) => {
    chips.push({
      id: `chip-avail-${avail}`,
      category: 'Status',
      label: avail,
      onRemove: () =>
        onUpdateFilters((prev) => ({
          ...prev,
          availability: prev.availability.filter((a) => a !== avail),
        })),
    });
  });

  // 8. Departments
  filters.departments.forEach((dept) => {
    chips.push({
      id: `chip-dept-${dept}`,
      category: 'Dept',
      label: dept,
      onRemove: () =>
        onUpdateFilters((prev) => ({
          ...prev,
          departments: prev.departments.filter((d) => d !== dept),
        })),
    });
  });

  if (chips.length === 0) return null;

  return (
    <div id="active-filter-chips-bar" className="flex flex-wrap items-center gap-2 py-2">
      <div className="flex items-center gap-1.5 text-xs font-medium text-zinc-400 uppercase tracking-wider mr-1">
        <Filter className="w-3.5 h-3.5 text-blue-400" />
        <span>Active Filters ({chips.length}):</span>
      </div>

      {chips.map((chip) => (
        <span
          key={chip.id}
          id={chip.id}
          className="inline-flex items-center gap-1.5 pl-2.5 pr-1.5 py-1 rounded-lg text-xs font-medium bg-zinc-900 border border-zinc-800 text-zinc-200 shadow-xs group hover:border-zinc-700 transition-colors"
        >
          <span className="text-blue-400 text-[10px] font-mono font-medium uppercase">{chip.category}:</span>
          <span className="font-medium text-zinc-100">{chip.label}</span>
          <button
            type="button"
            onClick={chip.onRemove}
            className="text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800 rounded-md p-0.5 transition-colors cursor-pointer"
            title={`Remove ${chip.label}`}
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </span>
      ))}

      <button
        id="clear-all-filters-chip-btn"
        type="button"
        onClick={onResetFilters}
        className="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-medium text-zinc-400 hover:text-zinc-100 bg-zinc-900/60 hover:bg-zinc-800/80 rounded-lg border border-zinc-800 transition-colors cursor-pointer ml-auto sm:ml-1"
      >
        <RotateCcw className="w-3 h-3" />
        Clear All
      </button>
    </div>
  );
};
