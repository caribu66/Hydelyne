import React from 'react';
import { FilterState } from '../types';
import { FILTER_PRESETS } from '../data/mockProfiles';
import { Sparkles, Shield, Anchor, Wind, Waves, Award, RotateCcw, CheckCircle2 } from 'lucide-react';

interface QuickFilterBarProps {
  activePresetId?: string;
  onSelectPreset?: (presetId: string) => void;
  filters?: FilterState;
  onUpdateFilters?: React.Dispatch<React.SetStateAction<FilterState>>;
  totalResultsCount?: number;
}

export const QuickFilterBar: React.FC<QuickFilterBarProps> = ({
  activePresetId = 'all',
  onSelectPreset,
  filters,
  onUpdateFilters,
  totalResultsCount,
}) => {
  // If activePresetId and onSelectPreset are provided (Preset Mode)
  if (onSelectPreset) {
    const presets = [
      { id: 'all', label: 'All Specialists', icon: Sparkles, color: 'text-blue-400' },
      { id: 'preset-available-offshore', label: 'Ready for Mobilisation', icon: CheckCircle2, color: 'text-emerald-400' },
      { id: 'preset-geophys-rep', label: 'Geophysics & Seismic QC', icon: Anchor, color: 'text-blue-400' },
      { id: 'preset-mmo-pam', label: 'MMO & PAM Operators', icon: Waves, color: 'text-cyan-400' },
      { id: 'preset-wind-geotech', label: 'Offshore Wind & Geotech', icon: Wind, color: 'text-amber-400' },
      { id: 'preset-hse-flo', label: 'HSE Advisors & FLO', icon: Award, color: 'text-purple-400' },
    ];

    return (
      <div className="w-full flex items-center gap-2 overflow-x-auto scrollbar-none py-1.5 px-0.5 text-xs select-none">
        <span className="text-[11px] font-mono text-zinc-400 font-medium uppercase tracking-wider shrink-0 flex items-center gap-1 mr-1">
          <Sparkles className="w-3 h-3 text-blue-400" />
          Filter Presets:
        </span>

        {presets.map((preset) => {
          const Icon = preset.icon;
          const isActive = activePresetId === preset.id;

          return (
            <button
              key={preset.id}
              type="button"
              onClick={() => onSelectPreset(preset.id)}
              className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-xl border font-medium transition-all shrink-0 cursor-pointer text-xs ${
                isActive
                  ? 'bg-blue-950/80 border-blue-600 text-blue-100 shadow-xs'
                  : 'bg-zinc-900/90 border-zinc-800 text-zinc-400 hover:text-zinc-200 hover:border-zinc-700'
              }`}
            >
              <Icon className={`w-3 h-3 ${isActive ? 'text-blue-300' : preset.color}`} />
              <span>{preset.label}</span>
            </button>
          );
        })}

        {activePresetId !== 'all' && (
          <button
            type="button"
            onClick={() => onSelectPreset('all')}
            className="inline-flex items-center gap-1 px-2 py-1 rounded-xl text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 transition-colors shrink-0 cursor-pointer text-[11px]"
            title="Reset preset"
          >
            <RotateCcw className="w-3 h-3" />
            <span>Reset</span>
          </button>
        )}
      </div>
    );
  }

  // Safe fallback if raw filters are passed
  const safeFilters: FilterState = filters || {
    keyword: '',
    locations: [],
    remoteTypes: [],
    selectedSkills: [],
    skillMatchMode: 'ANY',
    minExperience: 0,
    maxExperience: 30,
    companies: [],
    availability: [],
    departments: [],
    sortBy: 'relevance',
  };

  const isAvailableOnly = safeFilters.availability?.includes('Available immediately') ?? false;
  const isNorthSeaHubs = (safeFilters.locations || []).some((l) =>
    ['Aberdeen', 'Bergen', 'Dorset', 'Great Yarmouth', 'Stavanger'].some((city) => l.includes(city))
  );
  const isGeophysicsOnly = (safeFilters.departments || []).includes('Geophysical & Survey QC');
  const isEnvironmentalOnly = (safeFilters.departments || []).includes('Marine Environmental');
  const isWindGeotechOnly = (safeFilters.departments || []).includes('Geotechnical & Subsea');
  const isSeniorOnly = (safeFilters.minExperience || 0) >= 10;

  return (
    <div className="w-full flex items-center gap-2 overflow-x-auto scrollbar-none py-1.5 px-0.5 text-xs select-none">
      <span className="text-[11px] font-mono text-zinc-400 font-medium uppercase tracking-wider shrink-0 flex items-center gap-1 mr-1">
        <Sparkles className="w-3 h-3 text-blue-400" />
        Quick Filters:
      </span>

      <button
        type="button"
        onClick={() => {
          if (onUpdateFilters) {
            onUpdateFilters((prev) => ({
              ...prev,
              availability: isAvailableOnly
                ? (prev.availability || []).filter((a) => a !== 'Available immediately')
                : ['Available immediately'],
            }));
          }
        }}
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-xl border font-medium transition-all shrink-0 cursor-pointer ${
          isAvailableOnly
            ? 'bg-emerald-950/60 border-emerald-700 text-emerald-200 shadow-xs'
            : 'bg-zinc-900/90 border-zinc-800 text-zinc-400 hover:text-zinc-200 hover:border-zinc-700'
        }`}
      >
        <span className={`w-1.5 h-1.5 rounded-full ${isAvailableNow(safeFilters) ? 'bg-emerald-400' : 'bg-zinc-600'}`} />
        <span>Available Immediately</span>
      </button>
    </div>
  );
};

function isAvailableNow(filters: FilterState) {
  return filters.availability?.includes('Available immediately') ?? false;
}
