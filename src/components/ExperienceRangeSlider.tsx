import React from 'react';
import { Clock, Zap } from 'lucide-react';

interface ExperienceRangeSliderProps {
  min: number;
  max: number;
  onChange: (min: number, max: number) => void;
}

export const ExperienceRangeSlider: React.FC<ExperienceRangeSliderProps> = ({
  min,
  max,
  onChange,
}) => {
  const quickRanges = [
    { label: 'All Levels (0-20+ yrs)', minVal: 0, maxVal: 20 },
    { label: 'Entry (0-2 yrs)', minVal: 0, maxVal: 2 },
    { label: 'Mid-Level (3-6 yrs)', minVal: 3, maxVal: 6 },
    { label: 'Senior (7-10 yrs)', minVal: 7, maxVal: 10 },
    { label: 'Staff / Principal (11+ yrs)', minVal: 11, maxVal: 20 },
  ];

  const handleMinChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = Math.min(Number(e.target.value), max - 1);
    onChange(Math.max(0, val), max);
  };

  const handleMaxChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = Math.max(Number(e.target.value), min + 1);
    onChange(min, Math.min(20, val));
  };

  const minPercent = (min / 20) * 100;
  const maxPercent = (max / 20) * 100;

  return (
    <div id="experience-slider-container" className="space-y-3.5">
      {/* Visual Badge Display */}
      <div className="flex items-center justify-between text-xs">
        <span className="text-zinc-400 font-medium flex items-center gap-1.5">
          <Clock className="w-3.5 h-3.5 text-indigo-400" />
          Experience Span
        </span>
        <span className="font-mono font-semibold text-indigo-300 bg-indigo-500/10 border border-indigo-500/20 px-2.5 py-1 rounded-lg">
          {min} {min === 1 ? 'yr' : 'yrs'} — {max >= 20 ? '20+ yrs' : `${max} yrs`}
        </span>
      </div>

      {/* Dual Slider Track */}
      <div className="relative pt-2 pb-2 px-1">
        <div className="h-2 w-full bg-zinc-800 rounded-full relative overflow-hidden">
          <div
            className="absolute h-2 bg-gradient-to-r from-indigo-500 via-purple-500 to-indigo-400 rounded-full shadow-sm"
            style={{
              left: `${minPercent}%`,
              width: `${Math.max(0, maxPercent - minPercent)}%`,
            }}
          />
        </div>

        <input
          id="exp-min-slider"
          type="range"
          min="0"
          max="20"
          value={min}
          onChange={handleMinChange}
          className="absolute top-0.5 left-0 w-full h-5 appearance-none bg-transparent pointer-events-auto cursor-pointer"
          style={{ zIndex: min > 15 ? 5 : 3 }}
        />
        <input
          id="exp-max-slider"
          type="range"
          min="0"
          max="20"
          value={max}
          onChange={handleMaxChange}
          className="absolute top-0.5 left-0 w-full h-5 appearance-none bg-transparent pointer-events-auto cursor-pointer"
          style={{ zIndex: 4 }}
        />
      </div>

      {/* Quick Tier Selection Chips */}
      <div className="grid grid-cols-2 gap-1.5 pt-1">
        {quickRanges.map((r) => {
          const isActive = min === r.minVal && max === r.maxVal;
          return (
            <button
              key={r.label}
              type="button"
              id={`quick-exp-${r.minVal}-${r.maxVal}`}
              onClick={() => onChange(r.minVal, r.maxVal)}
              className={`px-2.5 py-1.5 text-[11px] font-medium rounded-lg border transition-all duration-150 text-left truncate cursor-pointer ${
                isActive
                  ? 'bg-indigo-500/20 border-indigo-500/60 text-indigo-200 font-semibold shadow-sm'
                  : 'bg-zinc-900/60 border-zinc-800 text-zinc-400 hover:bg-zinc-800/80 hover:text-zinc-200 hover:border-zinc-700'
              }`}
            >
              {r.label}
            </button>
          );
        })}
      </div>
    </div>
  );
};
