import React from 'react';
import { FilterState } from '../types';
import { ArrowUpDown, Download, Share2, Check, FileSpreadsheet } from 'lucide-react';

interface StatsBarProps {
  totalCount: number;
  filteredCount: number;
  sortBy: FilterState['sortBy'];
  onSortChange: (val: FilterState['sortBy']) => void;
  onExportJSON: () => void;
  onExportCSV?: () => void;
}

export const StatsBar: React.FC<StatsBarProps> = ({
  totalCount,
  filteredCount,
  sortBy,
  onSortChange,
  onExportJSON,
  onExportCSV,
}) => {
  const [copiedShare, setCopiedShare] = React.useState(false);

  const handleShare = () => {
    navigator.clipboard?.writeText(window.location.href);
    setCopiedShare(true);
    setTimeout(() => setCopiedShare(false), 2000);
  };

  return (
    <div
      id="stats-sorting-bar"
      className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 pt-1 pb-1"
    >
      {/* Count readout */}
      <div className="text-xs sm:text-sm font-semibold text-zinc-300 flex items-center gap-2">
        <span>
          Showing <span className="text-zinc-100 font-bold font-mono">{filteredCount}</span> of{' '}
          <span className="text-zinc-400 font-mono">{totalCount}</span> specialists
        </span>
        {filteredCount < totalCount && (
          <span className="text-[11px] font-mono font-medium text-zinc-300 bg-zinc-800 border border-zinc-700 px-2 py-0.5 rounded-full">
            Active Filter
          </span>
        )}
      </div>

      {/* Sort and Export Controls */}
      <div className="flex items-center gap-2 self-stretch sm:self-auto justify-between sm:justify-end">
        {/* Sort Select */}
        <div className="flex items-center gap-1.5 bg-zinc-900 border border-zinc-800 rounded-xl px-3 py-1.5 shadow-sm text-xs">
          <ArrowUpDown className="w-3.5 h-3.5 text-zinc-400" />
          <span className="text-zinc-400 font-medium hidden sm:inline">Sort:</span>
          <select
            id="sort-by-select"
            value={sortBy}
            onChange={(e) => onSortChange(e.target.value as FilterState['sortBy'])}
            className="bg-transparent text-zinc-200 font-semibold focus:outline-none cursor-pointer text-xs"
          >
            <option value="relevance" className="bg-zinc-900 text-zinc-100">Best Match / Rating</option>
            <option value="experience-desc" className="bg-zinc-900 text-zinc-100">Experience: High to Low</option>
            <option value="experience-asc" className="bg-zinc-900 text-zinc-100">Experience: Low to High</option>
            <option value="name-asc" className="bg-zinc-900 text-zinc-100">Name: A to Z</option>
            <option value="name-desc" className="bg-zinc-900 text-zinc-100">Name: Z to A</option>
          </select>
        </div>

        {/* Export JSON Button */}
        <button
          type="button"
          id="export-results-btn"
          onClick={onExportJSON}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-zinc-900 border border-zinc-800 hover:border-zinc-700 hover:bg-zinc-800/80 text-zinc-300 hover:text-white rounded-xl text-xs font-medium transition-colors cursor-pointer shadow-sm"
          title="Export matching profiles as JSON"
        >
          <Download className="w-3.5 h-3.5 text-zinc-400" />
          <span className="hidden md:inline">Export</span>
        </button>

        {/* Share Link */}
        <button
          type="button"
          id="share-link-btn"
          onClick={handleShare}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-zinc-900 border border-zinc-800 hover:border-zinc-700 hover:bg-zinc-800/80 text-zinc-300 hover:text-white rounded-xl text-xs font-medium transition-colors cursor-pointer shadow-sm"
          title="Copy link to clipboard"
        >
          {copiedShare ? (
            <>
              <Check className="w-3.5 h-3.5 text-emerald-400" />
              <span className="text-emerald-400 font-semibold hidden md:inline">Copied!</span>
            </>
          ) : (
            <>
              <Share2 className="w-3.5 h-3.5 text-zinc-400" />
              <span className="hidden md:inline">Share</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
};
