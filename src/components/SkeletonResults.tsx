import React from 'react';

interface SkeletonResultsProps {
  viewMode?: 'grid' | 'list';
  count?: number;
}

export const SkeletonGridCard: React.FC = () => {
  return (
    <div className="animate-shimmer bg-slate-900/40 border border-slate-800/60 rounded-xl p-4 flex flex-col justify-between space-y-3 shadow-xs select-none">
      {/* Top Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0 flex-1">
          <div className="w-10 h-10 rounded-lg bg-slate-800 animate-pulse border border-slate-700/50 shrink-0" />
          <div className="min-w-0 flex-1 space-y-1.5">
            <div className="flex items-center gap-2">
              <div className="h-4 w-28 bg-slate-800 rounded animate-pulse" />
              <div className="h-3.5 w-12 bg-slate-800/80 rounded" />
            </div>
            <div className="h-3 w-40 max-w-[80%] bg-slate-800/60 rounded animate-pulse" />
          </div>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <div className="w-6 h-6 rounded bg-slate-800/50 animate-pulse" />
          <div className="w-6 h-6 rounded bg-slate-800/50 animate-pulse" />
        </div>
      </div>

      {/* Bio snippet */}
      <div className="space-y-1.5 py-0.5">
        <div className="h-3 w-full bg-slate-800/50 rounded animate-pulse" />
        <div className="h-3 w-4/5 bg-slate-800/40 rounded animate-pulse" />
      </div>

      {/* Skills tags */}
      <div className="flex items-center gap-1.5 flex-wrap">
        <div className="h-5 w-14 bg-slate-800/60 rounded animate-pulse" />
        <div className="h-5 w-16 bg-slate-800/60 rounded animate-pulse" />
        <div className="h-5 w-12 bg-slate-800/60 rounded animate-pulse" />
      </div>

      {/* Footer */}
      <div className="pt-2 border-t border-slate-800/40 flex items-center justify-between">
        <div className="h-3 w-28 bg-slate-800/60 rounded animate-pulse" />
        <div className="h-3 w-16 bg-cyan-950/40 rounded animate-pulse" />
      </div>
    </div>
  );
};

export const SkeletonListItem: React.FC = () => {
  return (
    <div className="animate-shimmer p-3 sm:p-3.5 flex items-center justify-between gap-3 select-none">
      <div className="flex items-center gap-3 min-w-0 flex-1">
        <div className="w-8 h-8 rounded-lg bg-slate-800 animate-pulse border border-slate-700/50 shrink-0" />
        <div className="min-w-0 space-y-1 flex-1">
          <div className="flex items-center gap-2">
            <div className="h-3.5 w-24 bg-slate-800 rounded animate-pulse" />
            <div className="h-3 w-36 bg-slate-800/60 rounded hidden sm:block animate-pulse" />
          </div>
          <div className="flex items-center gap-2">
            <div className="h-2.5 w-16 bg-slate-800/70 rounded" />
            <div className="h-2.5 w-20 bg-slate-800/50 rounded" />
          </div>
        </div>
      </div>
      <div className="flex items-center gap-1 shrink-0">
        <div className="w-7 h-7 rounded bg-slate-800/50 animate-pulse" />
        <div className="w-7 h-7 rounded bg-slate-800/50 animate-pulse" />
      </div>
    </div>
  );
};

export const SkeletonResults: React.FC<SkeletonResultsProps> = ({
  viewMode = 'grid',
  count = 4,
}) => {
  const items = Array.from({ length: count });

  if (viewMode === 'list') {
    return (
      <div className="divide-y divide-slate-800/60 border border-slate-800/60 rounded-xl bg-slate-900/30 overflow-hidden">
        {items.map((_, index) => (
          <SkeletonListItem key={`skeleton-list-${index}`} />
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
      {items.map((_, index) => (
        <SkeletonGridCard key={`skeleton-grid-${index}`} />
      ))}
    </div>
  );
};
