import React, { useState, useRef, useEffect } from 'react';
import { Search, X, ArrowRight, History, Trash2, ArrowUpRight } from 'lucide-react';

interface CleanSearchBarProps {
  query: string;
  onChange: (val: string) => void;
  onSearch: (val: string) => void;
  onClear: () => void;
  autoFocus?: boolean;
}

const STORAGE_KEY = 'hydenlyne_recent_searches';
const DEFAULT_RECENT = ['MMO & PAM', 'Aberdeen', 'OBN Seismic QC', 'Geotechnical'];

export const CleanSearchBar: React.FC<CleanSearchBarProps> = ({
  query,
  onChange,
  onSearch,
  onClear,
  autoFocus = false,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [isFocused, setIsFocused] = useState(false);

  // Load recent searches from localStorage
  const [recentSearches, setRecentSearches] = useState<string[]>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) return parsed.slice(0, 4);
      }
    } catch {
      // ignore
    }
    return DEFAULT_RECENT;
  });

  const saveRecent = (items: string[]) => {
    setRecentSearches(items);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
    } catch {
      // ignore
    }
  };

  const addRecentSearch = (term: string) => {
    const trimmed = term.trim();
    if (!trimmed) return;
    const filtered = recentSearches.filter((item) => item.toLowerCase() !== trimmed.toLowerCase());
    const updated = [trimmed, ...filtered].slice(0, 4);
    saveRecent(updated);
  };

  const removeRecentSearch = (term: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const updated = recentSearches.filter((item) => item !== term);
    saveRecent(updated);
  };

  const clearAllRecent = (e: React.MouseEvent) => {
    e.stopPropagation();
    saveRecent([]);
  };

  useEffect(() => {
    if (autoFocus) {
      inputRef.current?.focus();
    }
  }, [autoFocus]);

  // Click outside to close dropdown
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsFocused(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleExecuteSearch = (val: string) => {
    if (val.trim()) {
      addRecentSearch(val.trim());
    }
    onSearch(val);
    setIsFocused(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleExecuteSearch(query);
    } else if (e.key === 'Escape') {
      if (isFocused && recentSearches.length > 0) {
        setIsFocused(false);
      } else if (query) {
        onClear();
      } else {
        inputRef.current?.blur();
        setIsFocused(false);
      }
    }
  };

  const handleSelectRecent = (term: string) => {
    onChange(term);
    handleExecuteSearch(term);
  };

  const showDropdown = isFocused && recentSearches.length > 0;

  return (
    <div className="w-full relative" ref={containerRef}>
      <div
        className={`relative flex items-center bg-slate-900/90 border rounded-xl px-3.5 py-2.5 transition-colors ${
          isFocused ? 'border-cyan-500/50 ring-1 ring-cyan-500/20' : 'border-slate-800 hover:border-slate-700'
        }`}
      >
        <Search className="w-4 h-4 text-slate-500 mr-2.5 shrink-0" />
        <input
          ref={inputRef}
          type="text"
          value={query}
          onFocus={() => setIsFocused(true)}
          onClick={() => setIsFocused(true)}
          onChange={(e) => {
            onChange(e.target.value);
            if (!isFocused) setIsFocused(true);
          }}
          onKeyDown={handleKeyDown}
          placeholder="Search by specialist name, discipline (e.g. PAM, Seismic QC), location, or skill..."
          className="w-full bg-transparent text-slate-100 placeholder:text-slate-500 focus:outline-none text-sm"
          autoComplete="off"
          spellCheck="false"
        />

        <div className="flex items-center gap-1 shrink-0 ml-2">
          {query && (
            <button
              type="button"
              onClick={() => {
                onClear();
                inputRef.current?.focus();
              }}
              className="p-1 rounded text-slate-500 hover:text-slate-300 transition-colors cursor-pointer"
              title="Clear search"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}

          {query.trim() && (
            <button
              type="button"
              onClick={() => handleExecuteSearch(query)}
              className="p-1.5 rounded-lg bg-cyan-500 text-slate-950 hover:bg-cyan-400 text-xs font-medium transition-colors cursor-pointer ml-1"
              title="Search"
            >
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Clean Recent Searches Dropdown */}
      {showDropdown && (
        <div
          id="recent-searches-dropdown"
          className="absolute top-full left-0 right-0 mt-1.5 z-40 bg-slate-900/95 backdrop-blur-md border border-slate-800 rounded-xl shadow-xl p-1.5"
        >
          <div className="flex items-center justify-between px-2 py-1 text-[11px] text-slate-500 border-b border-slate-800/60 mb-1">
            <span>Recent</span>
            <button
              type="button"
              onClick={clearAllRecent}
              className="hover:text-slate-300 transition-colors cursor-pointer"
            >
              Clear
            </button>
          </div>

          <div className="space-y-0.5">
            {recentSearches.map((term) => (
              <div
                key={term}
                onClick={() => handleSelectRecent(term)}
                className="group flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs text-slate-300 hover:text-white hover:bg-slate-800 transition-colors cursor-pointer"
              >
                <div className="flex items-center gap-2 min-w-0 flex-1">
                  <History className="w-3 h-3 text-slate-500 shrink-0" />
                  <span className="truncate">{term}</span>
                </div>
                <button
                  type="button"
                  onClick={(e) => removeRecentSearch(term, e)}
                  className="p-1 text-slate-600 hover:text-slate-300 transition-colors"
                  title="Remove"
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
