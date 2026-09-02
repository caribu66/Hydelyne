import { FC, ChangeEvent } from 'react';
import { Clock } from 'lucide-react';

interface ExperienceRangeSliderProps {
  min: number;
  max: number;
  onChange: (min: number, max: number) => void;
}

export const ExperienceRangeSlider: FC<ExperienceRangeSliderProps> = ({
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

  const handleMinChange = (e: ChangeEvent<HTMLInputElement>) => {
    const val = Math.min(Number(e.target.value), max - 1);
    onChange(Math.max(0, val), max);
  };

  const handleMaxChange = (e: ChangeEvent<HTMLInputElement>) => {
    const val = Math.max(Number(e.target.value), min + 1);
    onChange(min, Math.min(20, val));
  };

  const minPercent = (min / 20) * 100;
  const maxPercent = (max / 20) * 100;

  return (
    <div id="experience-slider-container" className="space-y-3.5">
      {/* Visual Badge Display */}
      <div className="flex items-center justify-between text-xs">
        <span className="text-secondary font-medium flex items-center gap-1.5">
          <Clock className="w-3.5 h-3.5 text-secondary" />
          Experience Span
        </span>
        <span className="font-mono font-semibold text-primary bg-surface-raised border border-border-strong px-2.5 py-1 rounded-lg">
          {min} {min === 1 ? 'yr' : 'yrs'} — {max >= 20 ? '20+ yrs' : `${max} yrs`}
        </span>
      </div>

      {/* Dual Slider Track */}
      <div className="relative pt-2 pb-2 px-1">
        <div className="h-2 w-full bg-surface-raised rounded-full relative overflow-hidden">
          <div
            className="absolute h-2 bg-action rounded-full shadow-sm"
            style={{
              left: `${minPercent}%`,
              width: `${Math.max(0, maxPercent - minPercent)}%`,
            }}
          />
        </div>

        <input
          id="exp-min-slider"
          aria-label="Minimum years of experience"
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
          aria-label="Maximum years of experience"
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
              className={`min-h-11 px-2.5 py-1.5 text-xs font-medium rounded-lg border transition-all duration-150 text-left truncate cursor-pointer ${
                isActive
                  ? 'bg-action/15 border-border-strong/40 text-accent font-semibold shadow-sm'
                  : 'bg-surface/60 border-border-subtle text-secondary hover:bg-surface-raised/80 hover:text-primary hover:border-border-strong'
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
