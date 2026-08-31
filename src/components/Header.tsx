import React from 'react';
import {
  Sparkles,
  Bookmark,
  LayoutGrid,
  List,
  SlidersHorizontal,
  Home,
  Sun,
  Moon,
  Zap,
} from 'lucide-react';

interface HeaderProps {
  totalCount: number;
  bookmarkedCount: number;
  viewMode: 'grid' | 'list';
  onToggleViewMode: (mode: 'grid' | 'list') => void;
  onOpenFilters: () => void;
  activeFilterCount: number;
  showOnlyBookmarks: boolean;
  onToggleShowOnlyBookmarks: () => void;
  onGoHome: () => void;
  isSearching: boolean;
  isDark: boolean;
  onToggleTheme: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  totalCount,
  bookmarkedCount,
  viewMode,
  onToggleViewMode,
  onOpenFilters,
  activeFilterCount,
  showOnlyBookmarks,
  onToggleShowOnlyBookmarks,
  onGoHome,
  isSearching,
  isDark,
  onToggleTheme,
}) => {
  return (
    <header className="sticky top-0 z-30 w-full bg-zinc-950/80 backdrop-blur-md border-b border-zinc-800 transition-colors">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-4">
        {/* Brand & Logo */}
        <div
          onClick={onGoHome}
          className="flex items-center gap-3 cursor-pointer group select-none"
        >
          <div className="relative flex items-center justify-center w-8 h-8 rounded-xl bg-zinc-900 border border-zinc-700/80 text-blue-400 shadow-xs group-hover:border-zinc-500 transition-colors">
            <Sparkles className="w-4 h-4" />
          </div>

          <div className="flex items-center gap-2">
            <span className="font-semibold text-base sm:text-lg tracking-tight text-zinc-100">
              Hydenlyne
            </span>
            <span className="text-[10px] font-mono font-medium px-2 py-0.5 rounded-full bg-blue-950/60 text-blue-300 border border-blue-800/60">
              Network
            </span>
          </div>
        </div>

        {/* Right Controls */}
        <div className="flex items-center gap-2 sm:gap-2.5">
          {/* New Search / Home Button if currently searching */}
          {isSearching && (
            <button
              type="button"
              id="header-home-btn"
              onClick={onGoHome}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-zinc-900 border border-zinc-800 hover:border-zinc-700 text-zinc-300 hover:text-white text-xs font-medium transition-colors cursor-pointer"
              title="Return to clean search homepage"
            >
              <Home className="w-3.5 h-3.5 text-zinc-400" />
              <span className="hidden sm:inline">New Search</span>
            </button>
          )}

          {/* Bookmarks Toggle */}
          <button
            type="button"
            id="toggle-bookmarks-btn"
            onClick={onToggleShowOnlyBookmarks}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border text-xs font-semibold transition-all cursor-pointer ${
              showOnlyBookmarks
                ? 'bg-zinc-100 border-white text-zinc-950 shadow-xs'
                : 'bg-zinc-900/80 hover:bg-zinc-800 border-zinc-800 text-zinc-300 hover:text-white'
            }`}
          >
            <Bookmark className={`w-3.5 h-3.5 ${showOnlyBookmarks ? 'fill-zinc-950' : 'text-zinc-400'}`} />
            <span className="hidden sm:inline">Saved</span>
            <span
              className={`px-1.5 py-0.5 rounded-full text-[10px] font-mono leading-none ${
                showOnlyBookmarks
                  ? 'bg-zinc-950 text-white font-bold'
                  : 'bg-zinc-800 text-zinc-300'
              }`}
            >
              {bookmarkedCount}
            </span>
          </button>

          {/* View Mode Toggle (Grid vs List) */}
          {isSearching && (
            <div className="hidden sm:flex items-center bg-zinc-900 p-0.5 rounded-xl border border-zinc-800">
              <button
                type="button"
                id="view-mode-grid"
                onClick={() => onToggleViewMode('grid')}
                className={`p-1.5 rounded-lg transition-all cursor-pointer ${
                  viewMode === 'grid'
                    ? 'bg-zinc-800 text-white shadow-xs'
                    : 'text-zinc-400 hover:text-white'
                }`}
                title="Grid View"
              >
                <LayoutGrid className="w-3.5 h-3.5" />
              </button>
              <button
                type="button"
                id="view-mode-list"
                onClick={() => onToggleViewMode('list')}
                className={`p-1.5 rounded-lg transition-all cursor-pointer ${
                  viewMode === 'list'
                    ? 'bg-zinc-800 text-white shadow-xs'
                    : 'text-zinc-400 hover:text-white'
                }`}
                title="List View"
              >
                <List className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          {/* Filter Drawer Button */}
          <button
            type="button"
            id="header-filters-btn"
            onClick={onOpenFilters}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border text-xs font-semibold cursor-pointer transition-colors ${
              activeFilterCount > 0
                ? 'bg-blue-950/60 border-blue-800/60 text-blue-300'
                : 'bg-zinc-900 border-zinc-800 text-zinc-300 hover:border-zinc-700'
            }`}
          >
            <SlidersHorizontal className="w-3.5 h-3.5 text-zinc-400" />
            <span className="hidden sm:inline">Filters</span>
            {activeFilterCount > 0 && (
              <span className="px-1.5 py-0.2 rounded-full bg-blue-600 text-white text-[10px] font-bold font-mono">
                {activeFilterCount}
              </span>
            )}
          </button>
        </div>
      </div>
    </header>
  );
};
