import React, { useState, useRef, useEffect } from 'react';
import { Search, ArrowUp, X, Activity } from 'lucide-react';

interface ModernHeroSearchProps {
  query: string;
  onChange: (val: string) => void;
  onSearch: (val: string) => void;
  onClear: () => void;
  isCalmState: boolean;
  totalSpecialists?: number;
}

const QUICK_DISCOVERY_CHIPS = [
  { label: 'Client Rep', query: 'Client Rep' },
  { label: 'Hydrography', query: 'Hydrography' },
  { label: 'Subsea Geophysics', query: 'Geophysics' },
  { label: 'Environmental & PAM', query: 'PAM' },
  { label: 'Available Immediately', query: 'Available immediately' },
];

export const ModernHeroSearch: React.FC<ModernHeroSearchProps> = ({
  query,
  onChange,
  onSearch,
  onClear,
  isCalmState,
  totalSpecialists = 240,
}) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [isFocused, setIsFocused] = useState(false);

  // Auto-resize textarea smoothly
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      const scrollH = textareaRef.current.scrollHeight;
      textareaRef.current.style.height = `${Math.min(Math.max(scrollH, 32), 120)}px`;
    }
  }, [query]);

  // Keyboard shortcut '/' or 'Cmd+K' to focus
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (
        (e.key === '/' || ((e.metaKey || e.ctrlKey) && e.key === 'k')) &&
        document.activeElement !== textareaRef.current
      ) {
        e.preventDefault();
        textareaRef.current?.focus();
        textareaRef.current?.select();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (query.trim()) {
        onSearch(query.trim());
      }
    }
  };

  return (
    <div
      className={`w-full flex flex-col items-center justify-center transition-all duration-500 ease-out ${
        isCalmState ? 'min-h-[64vh] py-8 sm:py-12' : 'py-3'
      }`}
    >
      <div className="w-full max-w-2xl px-4 flex flex-col items-center">
        {/* Refined Enterprise Editorial Header & Status (Visible in Calm/Initial State) */}
        {isCalmState && (
          <div className="text-center space-y-3 mb-8 w-full animate-in fade-in slide-in-from-bottom-3 duration-500">
            {/* Live Operational Status Capsule */}
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-zinc-900 border border-zinc-800 text-[11px] text-zinc-300">
              <span className="flex h-2 w-2 rounded-full bg-emerald-500" />
              <span className="font-medium text-zinc-200">Global Network Active</span>
              <span className="text-zinc-600">•</span>
              <span className="text-zinc-400 font-mono">{totalSpecialists}+ Verified Specialists</span>
            </div>

            {/* Editorial Title */}
            <h1 className="text-2xl sm:text-3xl lg:text-4xl font-semibold tracking-tight text-zinc-100 font-sans">
              Offshore Operations & Survey Network
            </h1>

            {/* Enterprise Subtitle */}
            <p className="text-xs sm:text-sm text-zinc-400 font-light max-w-md mx-auto leading-relaxed">
              Direct access to certified hydrographers, geophysicists, client representatives, and subsea crew.
            </p>
          </div>
        )}

        {/* Search Bar */}
        <div className="relative w-full">
          {/* Search Box */}
          <div
            className={`relative flex items-center gap-3 px-4 py-3 rounded-2xl bg-zinc-900/90 border transition-all duration-150 ${
              isFocused
                ? 'border-zinc-500 ring-1 ring-zinc-500/20 bg-zinc-900'
                : 'border-zinc-800 hover:border-zinc-700'
            }`}
          >
            <Search
              className={`w-5 h-5 shrink-0 transition-colors ${
                isFocused ? 'text-zinc-200' : 'text-zinc-500'
              }`}
            />

            <textarea
              ref={textareaRef}
              value={query}
              onChange={(e) => onChange(e.target.value)}
              onFocus={() => setIsFocused(true)}
              onBlur={() => setIsFocused(false)}
              onKeyDown={handleKeyDown}
              rows={1}
              placeholder="Search specialists, skills, certifications, or regions..."
              className="w-full bg-transparent text-zinc-100 placeholder:text-zinc-500 focus:outline-none text-base sm:text-lg font-light resize-none leading-relaxed antialiased"
              spellCheck="false"
            />

            {query && (
              <button
                type="button"
                onClick={onClear}
                className="p-1 rounded-lg text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 transition-colors cursor-pointer shrink-0"
                title="Clear"
              >
                <X className="w-4 h-4" />
              </button>
            )}

            <button
              type="button"
              onClick={() => onSearch(query)}
              disabled={!query.trim()}
              className={`p-2 rounded-xl transition-all cursor-pointer shrink-0 ${
                query.trim()
                  ? 'bg-zinc-100 hover:bg-white text-zinc-950 shadow-sm'
                  : 'bg-zinc-800/80 text-zinc-600 cursor-not-allowed'
              }`}
              title="Search"
            >
              <ArrowUp className="w-4 h-4 stroke-[2.5]" />
            </button>
          </div>

          {/* Discreet Quick-Filter Discovery Chips */}
          <div className="mt-3.5 flex items-center justify-center flex-wrap gap-1.5 sm:gap-2 px-1">
            <span className="text-[11px] text-zinc-500 font-medium mr-1 hidden sm:inline">
              Suggested:
            </span>
            {QUICK_DISCOVERY_CHIPS.map((chip) => {
              const isActive = query.trim().toLowerCase() === chip.query.toLowerCase();
              return (
                <button
                  key={chip.label}
                  type="button"
                  onClick={() => {
                    if (isActive) {
                      onClear();
                    } else {
                      onChange(chip.query);
                      onSearch(chip.query);
                    }
                  }}
                  className={`inline-flex items-center px-2.5 py-1 rounded-lg text-xs transition-all cursor-pointer border ${
                    isActive
                      ? 'bg-zinc-800 border-zinc-600 text-zinc-100 font-medium shadow-xs'
                      : 'bg-zinc-900/60 hover:bg-zinc-800/80 border-zinc-800/80 hover:border-zinc-700 text-zinc-400 hover:text-zinc-200 font-normal'
                  }`}
                >
                  {chip.label}
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};
