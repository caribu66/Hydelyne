import { FC } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { FilterState } from '../types';
import { X, RotateCcw, Filter } from 'lucide-react';

interface ActiveFilterChipsProps {
  filters: FilterState;
  onUpdateFilters: (updater: (prev: FilterState) => FilterState) => void;
  onResetFilters: () => void;
}

export const ActiveFilterChips: FC<ActiveFilterChipsProps> = ({
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
    <div id="active-filter-chips-bar" className="flex flex-wrap items-center gap-2 py-3" aria-label="Active contractor filters">
      <div className="flex items-center gap-1.5 text-xs font-semibold text-secondary uppercase tracking-wider mr-1">
        <Filter className="w-3.5 h-3.5 text-accent" />
        <span>Active Filters ({chips.length}):</span>
      </div>

      <AnimatePresence>
        {chips.map((chip) => (
          <motion.span
            layout
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.85 }}
            transition={{ duration: 0.15, ease: 'easeOut' }}
            key={chip.id}
            id={chip.id}
            className="inline-flex min-h-11 items-center gap-1.5 pl-2.5 pr-1 py-1 rounded-lg text-xs font-medium bg-surface border border-border-subtle text-primary shadow-xs group hover:border-border-strong transition-colors"
          >
            <span className="text-accent text-xs font-mono font-medium uppercase">{chip.category}:</span>
            <span className="font-medium text-primary">{chip.label}</span>
            <button
              type="button"
              onClick={chip.onRemove}
              className="inline-flex min-h-9 min-w-9 items-center justify-center text-muted hover:text-primary hover:bg-surface-raised rounded-md transition-colors cursor-pointer"
              title={`Remove ${chip.label}`}
              aria-label={`Remove ${chip.category} filter: ${chip.label}`}
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </motion.span>
        ))}
      </AnimatePresence>

      <button
        id="clear-all-filters-chip-btn"
        type="button"
        onClick={onResetFilters}
        className="inline-flex min-h-11 items-center gap-1.5 px-3 py-1 text-xs font-medium text-secondary hover:text-primary bg-surface/60 hover:bg-surface-raised/80 rounded-lg border border-border-subtle transition-colors cursor-pointer ml-auto sm:ml-1"
      >
        <RotateCcw className="w-3 h-3" />
        Clear all
      </button>
    </div>
  );
};
