import React, { useState, useRef, useEffect } from 'react';
import { Search, X, ArrowRight, History, Sparkles, Command, ShieldCheck, Zap, Compass, Filter } from 'lucide-react';

interface SearchCommandBarProps {
  query: string;
  onChange: (val: string) => void;
  onSearch: (val: string) => void;
  onClear: () => void;
  onSelectQueryPreset?: (preset: string) => void;
  placeholder?: string;
  autoFocus?: boolean;
}

const STORAGE_KEY = 'hydenlyne_recent_searches_v2';
const DEFAULT_RECENT = ['MMO & PAM', 'Aberdeen', 'OBN Seismic QC', 'Geotechnical'];

export const SMART_QUERY_PRESETS = [
  { id: 'mmo-pam', label: 'MMO & PAM Operators', query: 'MMO PAM' },
  { id: 'seismic-qc', label: 'Seismic & OBN QC', query: 'OBN Seismic' },
  { id: 'geotech-wind', label: 'Offshore Wind Geotech', query: 'Geotechnical Wind' },
  { id: 'bosiet-aberdeen', label: 'BOSIET in Aberdeen', query: 'BOSIET Aberdeen' },
  { id: 'client-reps', label: 'Client Representatives', query: 'Client Rep' },
];

export const SearchCommandBar: React.FC<SearchCommandBarProps> = ({
  query,
  onChange,
  onSearch,
  onClear,
  onSelectQueryPreset,
  placeholder = 'Search specialists by name, discipline (e.g. PAM, Seismic QC), location, certifications...',
  autoFocus = false,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [isFocused, setIsFocused] = useState(false);

  // Load recent searches
  const [recentSearches, setRecentSearches] = useState<string[]>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) return parsed.slice(0, 5);
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

  const addRecent = (term: string) => {
    const trimmed = term.trim();
    if (!trimmed) return;
    const filtered = recentSearches.filter((item) => item.toLowerCase() !== trimmed.toLowerCase());
    const updated = [trimmed, ...filtered].slice(0, 5);
    saveRecent(updated);
  };

  const removeRecent = (term: string, e: React.MouseEvent) => {
    e.stopPropagation();
    saveRecent(recentSearches.filter((item) => item !== term));
  };

  const clearRecent = (e: React.MouseEvent) => {
    e.stopPropagation();
    saveRecent([]);
  };

  // Global Keyboard Shortcut: '/' or 'Cmd+K' to focus search
  useEffect(() => {
    const handleGlobalKeyDown = (e: KeyboardEvent) => {
      if ((e.key === '/' || (e.key === 'k' && (e.metaKey || e.ctrlKey))) && document.activeElement !== inputRef.current) {
        e.preventDefault();
        inputRef.current?.focus();
        inputRef.current?.select();
      }
    };
    window.addEventListener('keydown', handleGlobalKeyDown);
    return () => window.removeEventListener('keydown', handleGlobalKeyDown);
  }, []);

  // Close dropdown on click outside
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
      addRecent(val.trim());
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

  const showDropdown = isFocused;

  return (
    <div className="w-full relative" ref={containerRef}>
      {/* Search Input Container */}
      <div
        className={`relative flex items-center bg-slate-900/90 border rounded-2xl px-4 py-3 sm:py-3.5 transition-all shadow-md ${
          isFocused
            ? 'border-cyan-500/70 ring-2 ring-cyan-500/20 shadow-cyan-950/50 bg-slate-900'
            : 'border-slate-800/90 hover:border-slate-700'
        }`}
      >
        <Search
          className={`w-5 h-5 mr-3 shrink-0 transition-colors ${
            isFocused ? 'text-cyan-400' : 'text-slate-500'
          }`}
        />

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
          placeholder={placeholder}
          className="w-full bg-transparent text-slate-100 placeholder:text-slate-500 focus:outline-none text-sm sm:text-base font-normal antialiased"
          autoComplete="off"
          spellCheck="false"
        />

        <div className="flex items-center gap-1.5 shrink-0 ml-2">
          {query ? (
            <button
              type="button"
              onClick={() => {
                onClear();
                inputRef.current?.focus();
              }}
              className="p-1 rounded-lg text-slate-500 hover:text-slate-200 hover:bg-slate-800 transition-colors cursor-pointer"
              title="Clear search"
            >
              <X className="w-4 h-4" />
            </button>
          ) : (
            <div className="hidden sm:flex items-center gap-1 px-2 py-0.5 rounded-md bg-slate-800/80 border border-slate-700/60 text-[11px] text-slate-400 font-mono select-none">
              <span>/</span>
            </div>
          )}

          {query.trim() && (
            <button
              type="button"
              onClick={() => handleExecuteSearch(query)}
              className="p-2 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 text-xs font-semibold transition-all cursor-pointer shadow-xs shadow-cyan-500/30"
              title="Execute search (Enter)"
            >
              <ArrowRight className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Instant Search Suggestions & History Dropdown */}
      {showDropdown && (
        <div
          id="search-command-dropdown"
          className="absolute top-full left-0 right-0 mt-2 z-40 bg-slate-900/95 backdrop-blur-xl border border-slate-800/90 rounded-2xl shadow-2xl p-2.5 space-y-2 animate-in fade-in zoom-in-95 duration-100"
        >
          {/* Quick Intent Missions / Presets */}
          <div className="space-y-1">
            <div className="flex items-center justify-between px-2 py-1 text-[11px] text-slate-500 font-medium uppercase tracking-wider">
              <span className="flex items-center gap-1.5">
                <Sparkles className="w-3 h-3 text-cyan-400" />
                <span>Suggested Search Missions</span>
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-1">
              {SMART_QUERY_PRESETS.map((preset) => (
                <button
                  key={preset.id}
                  type="button"
                  onClick={() => {
                    onChange(preset.query);
                    handleExecuteSearch(preset.query);
                  }}
                  className="flex items-center justify-between px-3 py-2 rounded-xl text-xs text-slate-300 hover:text-white hover:bg-slate-800/80 border border-transparent hover:border-slate-700/60 transition-colors text-left cursor-pointer group"
                >
                  <span className="group-hover:text-cyan-300 font-medium">{preset.label}</span>
                  <span className="text-[10px] text-slate-500 font-mono group-hover:text-slate-400">
                    "{preset.query}"
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* Recent History */}
          {recentSearches.length > 0 && (
            <div className="pt-2 border-t border-slate-800/60 space-y-1">
              <div className="flex items-center justify-between px-2 py-1 text-[11px] text-slate-500 font-medium uppercase tracking-wider">
                <span className="flex items-center gap-1.5">
                  <History className="w-3 h-3 text-slate-400" />
                  <span>Recent Searches</span>
                </span>
                <button
                  type="button"
                  onClick={clearRecent}
                  className="hover:text-slate-300 text-[10px] lowercase transition-colors cursor-pointer"
                >
                  clear history
                </button>
              </div>

              <div className="space-y-0.5">
                {recentSearches.map((term) => (
                  <div
                    key={term}
                    onClick={() => {
                      onChange(term);
                      handleExecuteSearch(term);
                    }}
                    className="flex items-center justify-between px-3 py-1.5 rounded-xl text-xs text-slate-300 hover:text-white hover:bg-slate-800/60 transition-colors cursor-pointer group"
                  >
                    <div className="flex items-center gap-2 min-w-0 flex-1">
                      <Search className="w-3 h-3 text-slate-500 group-hover:text-cyan-400" />
                      <span className="truncate">{term}</span>
                    </div>
                    <button
                      type="button"
                      onClick={(e) => removeRecent(term, e)}
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
      )}
    </div>
  );
};
