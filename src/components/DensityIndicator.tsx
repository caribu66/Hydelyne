import React from 'react';

interface DensityIndicatorProps {
  matchedCount: number;
  totalCount: number;
  className?: string;
}

export const DensityIndicator: React.FC<DensityIndicatorProps> = ({
  matchedCount,
  totalCount,
  className = '',
}) => {
  const percentage = totalCount > 0 ? Math.min(100, Math.round((matchedCount / totalCount) * 100)) : 0;

  // 5 discrete density blocks for clean, high-precision visual scanning
  const totalBlocks = 5;
  const activeBlocks = Math.ceil((percentage / 100) * totalBlocks);

  const getDensityTier = () => {
    if (percentage >= 80) return 'Broad Roster';
    if (percentage >= 40) return 'Balanced Match';
    if (percentage >= 15) return 'Targeted Specialists';
    return 'Niche Discipline';
  };

  return (
    <div
      id="visual-density-indicator"
      className={`inline-flex items-center gap-2 px-2.5 py-0.5 rounded-lg bg-slate-900/90 border border-slate-800 text-[11px] text-slate-400 select-none ${className}`}
      title={`${matchedCount} of ${totalCount} active consultants (${percentage}% of consultant roster - ${getDensityTier()})`}
    >
      <span className="text-slate-500 font-medium hidden xs:inline">Roster</span>
      
      {/* 5-segment micro density meter */}
      <div className="flex items-center gap-0.5" aria-label={`Density: ${percentage}%`}>
        {Array.from({ length: totalBlocks }).map((_, i) => {
          const isActive = i < activeBlocks;
          return (
            <span
              key={i}
              className={`w-1.5 h-2.5 rounded-xs transition-all duration-300 ${
                isActive
                  ? 'bg-cyan-400 shadow-[0_0_6px_rgba(34,211,238,0.4)]'
                  : 'bg-slate-800'
              }`}
            />
          );
        })}
      </div>

      <span className="font-mono text-cyan-300 font-medium text-[10px]">
        {percentage}%
      </span>
    </div>
  );
};
