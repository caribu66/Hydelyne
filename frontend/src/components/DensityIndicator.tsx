import { FC } from 'react';

interface DensityIndicatorProps {
  matchedCount: number;
  totalCount: number;
  className?: string;
}

export const DensityIndicator: FC<DensityIndicatorProps> = ({
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
    if (percentage >= 15) return 'Targeted Contractors';
    return 'Niche Discipline';
  };

  return (
    <div
      id="visual-density-indicator"
      className={`inline-flex items-center gap-2 px-2.5 py-0.5 rounded-lg bg-surface/90 border border-border-subtle text-xs text-secondary select-none ${className}`}
      title={`${matchedCount} of ${totalCount} active contractors (${percentage}% of contractor roster - ${getDensityTier()})`}
    >
      <span className="text-muted font-medium hidden xs:inline">Roster</span>
      
      {/* 5-segment micro density meter */}
      <div role="img" className="flex items-center gap-0.5" aria-label={`Density: ${percentage}%`}>
        {Array.from({ length: totalBlocks }).map((_, i) => {
          const isActive = i < activeBlocks;
          return (
            <span
              key={i}
              className={`w-1.5 h-2.5 rounded-xs transition-all duration-300 ${
                isActive
                  ? 'bg-accent'
                  : 'bg-surface-raised'
              }`}
            />
          );
        })}
      </div>

      <span className="font-mono text-secondary font-medium text-xs">
        {percentage}%
      </span>
    </div>
  );
};
