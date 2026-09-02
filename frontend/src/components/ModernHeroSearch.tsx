import { FC, useState, useRef, useEffect, KeyboardEvent } from 'react';
import { Search, ArrowUp, X, Bookmark, Send, Loader2, SlidersHorizontal } from 'lucide-react';
import { useCrewQuery, CrewQueryResult } from '../hooks/useCrewQuery';

interface ModernHeroSearchProps {
  query: string;
  onChange: (val: string) => void;
  onSearch: (val: string) => void;
  onClear: () => void;
  isCalmState: boolean;
  isAuthenticated?: boolean;
  onOpenFilters?: () => void;
  onAIResults?: (data: CrewQueryResult | null, loading: boolean, isActive: boolean, showSummary: boolean) => void;
}

const QUICK_DISCOVERY_CHIPS = [
  { label: 'Hydrography', query: 'Hydrography' },
  { label: 'Client Representative', query: 'Client Rep' },
  { label: 'Medical Ready', query: 'Who has a current offshore medical?' },
  { label: 'Available Immediately', query: 'Available immediately' },
];

export const ModernHeroSearch: FC<ModernHeroSearchProps> = ({
  query,
  onChange,
  onSearch,
  onClear,
  isCalmState,
  isAuthenticated = true,
  onOpenFilters,
  onAIResults,
}) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [isFocused, setIsFocused] = useState(false);

  const { data: aiData, loading: aiLoading, isAIQuery, showSummary } = useCrewQuery(query, isAuthenticated);

  useEffect(() => {
    if (onAIResults) {
      onAIResults(aiData, aiLoading, isAIQuery, showSummary);
    }
  }, [aiData, aiLoading, isAIQuery, showSummary, onAIResults]);

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
    const handleKeyDown = (e: globalThis.KeyboardEvent) => {
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

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
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
        isCalmState ? `${isAuthenticated ? 'min-h-[64vh]' : 'min-h-[calc(100dvh-4rem)]'} py-10 sm:py-14` : 'py-3'
      }`}
    >
      <div className="w-full max-w-2xl px-4 flex flex-col items-center">
        {/* Refined Enterprise Editorial Header & Status (Visible in Calm/Initial State) */}
        {isCalmState && (
          <div className="text-center space-y-4 mb-10 w-full animate-in fade-in slide-in-from-bottom-3 duration-500">
            {/* Editorial Title */}
            <h1 className="mx-auto max-w-xl text-3xl sm:text-4xl lg:text-[2.75rem] lg:leading-[1.08] font-semibold tracking-[-0.025em] text-zinc-100 font-sans">
              Find the right specialist for the next campaign.
            </h1>

            {/* Enterprise Subtitle */}
            <p className="text-sm text-zinc-400 font-normal max-w-md mx-auto leading-6">
              Search the private network by discipline, certification, region, or availability.
            </p>
          </div>
        )}

        {/* Search Bar */}
        <div className="relative w-full">
          {/* Search Box */}
          <div
              className={`relative flex items-center gap-3 min-h-16 px-4 py-3 rounded-2xl bg-zinc-900/70 border shadow-xl shadow-black/10 transition-all duration-150 ${
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
              onClick={() => {
                if (!isAuthenticated) onSearch('');
              }}
              onKeyDown={handleKeyDown}
              rows={1}
              placeholder={isAuthenticated ? 'Ask in plain English — e.g. “Who has medical experience?”' : 'Sign in to search the private network'}
              readOnly={!isAuthenticated}
              aria-label={isAuthenticated ? 'Search specialists' : 'Sign in to search specialists'}
              className="w-full bg-transparent text-zinc-100 placeholder:text-zinc-500 focus:outline-none text-base sm:text-lg font-light resize-none leading-relaxed antialiased"
              spellCheck="false"
            />

            {query && (
              <button
                type="button"
                onClick={onClear}
                className="min-h-11 min-w-11 p-1 rounded-lg text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 transition-colors cursor-pointer shrink-0 inline-flex items-center justify-center"
                title="Clear"
                aria-label="Clear search"
              >
                <X className="w-4 h-4" />
              </button>
            )}

            {aiLoading && (
              <Loader2 className="w-4 h-4 text-blue-400 animate-spin shrink-0" />
            )}

            <button
              type="button"
              onClick={() => onSearch(query)}
              disabled={isAuthenticated && !query.trim()}
              className={`min-h-11 min-w-11 p-2 rounded-xl transition-all cursor-pointer shrink-0 inline-flex items-center justify-center ${
                query.trim() || !isAuthenticated
                  ? 'bg-zinc-100 hover:bg-white text-zinc-950 shadow-sm'
                  : 'bg-zinc-800/80 text-zinc-600 cursor-not-allowed'
              }`}
              title="Search"
              aria-label={isAuthenticated ? 'Search specialists' : 'Sign in to search specialists'}
            >
              <ArrowUp className="w-4 h-4 stroke-[2.5]" />
            </button>
          </div>

          <div className="mt-3 flex min-h-6 items-center justify-center px-1 text-xs text-zinc-400 sm:justify-between">
            <span className={isAuthenticated ? 'hidden sm:inline' : 'inline'}>
              {isAuthenticated ? 'Search by role, qualification, or availability' : 'Private workforce system · Access is monitored'}
            </span>
            {isAuthenticated && <span className="ml-auto inline-flex items-center gap-1.5 text-[11px] text-zinc-500">
              <kbd className="rounded-md border border-zinc-800 bg-zinc-900 px-1.5 py-0.5 font-mono text-[10px] text-zinc-400">↵</kbd>
              <span>to search</span>
              <span className="mx-1 text-zinc-700">·</span>
              <kbd className="rounded-md border border-zinc-800 bg-zinc-900 px-1.5 py-0.5 font-mono text-[10px] text-zinc-400">/</kbd>
              <span>to focus</span>
            </span>}
          </div>

          {/* Suggested searches help discovery before the result workspace opens. */}
          {isCalmState && isAuthenticated && <div className="mt-5 flex items-center justify-center flex-wrap gap-2 px-1">
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
                    if (!isAuthenticated) {
                      onSearch('');
                      return;
                    }
                    if (isActive) {
                      onClear();
                    } else {
                      onChange(chip.query);
                      onSearch(chip.query);
                    }
                  }}
                  className={`inline-flex min-h-11 items-center px-3 py-1 rounded-full text-xs transition-all cursor-pointer border ${
                    isActive
                      ? 'bg-zinc-800 border-zinc-600 text-zinc-100 font-medium shadow-xs'
                        : 'bg-transparent hover:bg-zinc-900/70 border-zinc-800/80 hover:border-zinc-700 text-zinc-400 hover:text-zinc-200 font-normal'
                  }`}
                >
                  {chip.label}
                </button>
              );
            })}
            {isAuthenticated && onOpenFilters && (
              <button
                type="button"
                onClick={onOpenFilters}
                className="inline-flex min-h-11 items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium text-zinc-400 transition-colors hover:bg-zinc-900 hover:text-zinc-100"
              >
                <SlidersHorizontal className="h-3.5 w-3.5" aria-hidden="true" />
                More filters
              </button>
            )}
          </div>}

          {!isCalmState && isAuthenticated && onOpenFilters && (
            <div className="mt-2 flex justify-end px-1">
              <button
                type="button"
                onClick={onOpenFilters}
                className="inline-flex min-h-11 items-center gap-1.5 rounded-lg px-2.5 text-xs font-medium text-zinc-400 transition-colors hover:bg-zinc-900 hover:text-zinc-100"
              >
                <SlidersHorizontal className="h-3.5 w-3.5" aria-hidden="true" />
                Refine filters
              </button>
            </div>
          )}

          {isCalmState && isAuthenticated && (
            <div className="mt-12 grid w-full max-w-xl grid-cols-3 text-center">
              {[
                { icon: Search, label: 'Discover', detail: 'Search the network' },
                { icon: Bookmark, label: 'Shortlist', detail: 'Save your strongest fits' },
                { icon: Send, label: 'Mobilize', detail: 'Send an inquiry' },
              ].map(({ icon: Icon, label, detail }) => (
                <div key={label} className="border-r border-zinc-800/70 px-3 last:border-r-0">
                  <Icon className="mx-auto mb-2 h-4 w-4 text-zinc-500" aria-hidden="true" />
                  <p className="text-xs font-semibold text-zinc-300">{label}</p>
                  <p className="mt-1 text-[11px] leading-4 text-zinc-500">{detail}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
