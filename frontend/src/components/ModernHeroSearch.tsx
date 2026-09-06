import { FC, useState, useRef, useEffect, KeyboardEvent } from 'react';
import { Search, ArrowUp, X, Bookmark, Send, Loader2, SlidersHorizontal, History } from 'lucide-react';
import { useCrewQuery, CrewQueryResult } from '../hooks/useCrewQuery';
import { HydenlyneAnimatedLogo } from './HydenlyneAnimatedLogo';

const RECENT_SEARCHES_KEY = 'hydenlyne_recent_searches';

interface ModernHeroSearchProps {
  query: string;
  onChange: (val: string) => void;
  onSearch: (val: string) => void;
  onClear: () => void;
  isCalmState: boolean;
  isAuthenticated?: boolean;
  onOpenFilters?: () => void;
  onAIResults?: (data: CrewQueryResult | null, loading: boolean, isActive: boolean, showSummary: boolean) => void;
  variant?: 'hero' | 'compact';
}

const QUICK_DISCOVERY_CHIPS = [
  { label: 'Hydrography', query: 'Hydrography' },
  { label: 'Client Representative', query: 'Client Rep' },
  { label: 'Medical Ready', query: 'Who has a current offshore medical?' },
  { label: 'Available Immediately', query: 'Available immediately' },
  { label: 'Environmental Lead', query: 'Environmental' },
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
  variant = 'hero',
}) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [isFocused, setIsFocused] = useState(false);
  const [recentSearches, setRecentSearches] = useState<string[]>([]);

  // Load recent searches from localStorage
  useEffect(() => {
    try {
      const saved = localStorage.getItem(RECENT_SEARCHES_KEY);
      if (saved) {
        setRecentSearches(JSON.parse(saved).slice(0, 5));
      }
    } catch {
      // ignore storage errors
    }
  }, []);

  const saveRecentSearch = (term: string) => {
    const trimmed = term.trim();
    if (!trimmed || trimmed.length < 2) return;
    try {
      const updated = [trimmed, ...recentSearches.filter((s) => s.toLowerCase() !== trimmed.toLowerCase())].slice(0, 5);
      setRecentSearches(updated);
      localStorage.setItem(RECENT_SEARCHES_KEY, JSON.stringify(updated));
    } catch {
      // ignore storage errors
    }
  };

  const clearRecentSearches = () => {
    setRecentSearches([]);
    try {
      localStorage.removeItem(RECENT_SEARCHES_KEY);
    } catch {
      // ignore
    }
  };

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
        saveRecentSearch(query);
        onSearch(query.trim());
        setIsFocused(false);
      }
    } else if (e.key === 'Escape') {
      setIsFocused(false);
    }
  };

  const handleSelectRecent = (term: string) => {
    onChange(term);
    saveRecentSearch(term);
    onSearch(term);
    setIsFocused(false);
  };

  return (
    <div
      ref={containerRef}
      className={`w-full flex flex-col items-center justify-center transition-all duration-300 ease-out ${
        isCalmState
          ? variant === 'compact'
            ? 'py-0'
            : `${isAuthenticated ? 'min-h-[44vh]' : 'min-h-[calc(100dvh-4rem)]'} py-8 sm:py-12`
          : 'py-1'
      }`}
    >
      <div className={`w-full flex flex-col items-center ${variant === 'compact' ? 'max-w-none px-0' : 'max-w-2xl px-4'}`}>
        {/* Public hero — plain-language value proposition for the logged-out shell */}
        {isCalmState && !isAuthenticated && (
          <div className="text-center space-y-3 mb-9 w-full flex flex-col items-center justify-center animate-in fade-in slide-in-from-bottom-3 duration-300">
            <HydenlyneAnimatedLogo isFocused={isFocused} />
            <h1 className="mx-auto max-w-xl text-3xl sm:text-4xl lg:text-[2.65rem] lg:leading-[1.12] font-semibold tracking-[-0.03em] text-primary font-sans">
              Find the right contractor for the next campaign.
            </h1>
            <p className="text-sm text-secondary font-normal max-w-md mx-auto leading-relaxed">
              Search Hydenlyne&apos;s private specialist network by discipline, certification, region, and availability.
            </p>
          </div>
        )}

        {/* Search Bar - Pristine and Clean */}
        <div className="relative w-full">
          {/* Search Box */}
          <div
            className={`relative flex min-h-14 sm:min-h-16 items-center gap-2.5 sm:gap-3 rounded-[14px] border px-3 sm:px-4 py-2.5 sm:py-3 shadow-sm transition-all duration-200 ${
              isFocused
                ? 'border-border-strong ring-2 ring-focus/25 bg-surface shadow-md'
                : 'border-border-subtle hover:border-border-strong bg-surface/90 backdrop-blur-sm hover:bg-surface'
            }`}
          >
            <Search
              className={`w-4 h-4 sm:w-5 sm:h-5 shrink-0 transition-colors ${
                isFocused ? 'text-primary' : 'text-muted'
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
              aria-label={isAuthenticated ? 'Search contractors' : 'Sign in to search contractors'}
              className="min-w-0 flex-1 w-full bg-transparent text-primary placeholder:text-muted/70 focus:outline-none text-sm sm:text-base lg:text-lg font-normal tracking-tight resize-none leading-relaxed antialiased"
              spellCheck="false"
            />

            {query && (
              <button
                type="button"
                onClick={onClear}
                className="min-h-9 min-w-9 sm:min-h-11 sm:min-w-11 p-1 rounded-lg text-muted hover:text-secondary hover:bg-surface-raised transition-colors cursor-pointer shrink-0 inline-flex items-center justify-center"
                title="Clear"
                aria-label="Clear search"
              >
                <X className="w-4 h-4" />
              </button>
            )}

            {aiLoading && (
              <Loader2 className="w-4 h-4 text-accent animate-spin shrink-0" />
            )}

            <button
              type="button"
              onClick={() => {
                if (query.trim()) {
                  saveRecentSearch(query);
                  onSearch(query.trim());
                  setIsFocused(false);
                }
              }}
              disabled={isAuthenticated && !query.trim()}
              className={`min-h-9 min-w-9 sm:min-h-11 sm:min-w-11 p-2 rounded-xl transition-all cursor-pointer shrink-0 inline-flex items-center justify-center ${
                query.trim() || !isAuthenticated
                  ? 'bg-action hover:bg-action-hover text-on-action shadow-xs active:scale-95'
                  : 'bg-surface-raised/80 text-muted cursor-not-allowed'
              }`}
              title="Search"
              aria-label={isAuthenticated ? 'Search contractors' : 'Sign in to search contractors'}
            >
              <ArrowUp className="w-4 h-4 stroke-[2.5]" />
            </button>
          </div>

          {/* Interactive Recent Searches Dropdown Menu */}
          {isFocused && recentSearches.length > 0 && (
            <div
              onMouseDown={(e) => e.preventDefault()}
              className="absolute left-0 right-0 top-full mt-2 z-50 rounded-[14px] border border-border-strong/80 bg-surface/95 p-2 shadow-2xl shadow-black/50 backdrop-blur-xl animate-in fade-in zoom-in-95 duration-150"
            >
              <div className="flex items-center justify-between px-2.5 py-1 text-xs text-muted font-medium border-b border-border-subtle/60 pb-1.5 mb-1">
                <span className="flex items-center gap-1.5 font-mono uppercase tracking-wider text-xs">
                  <History className="w-3 h-3 text-secondary" />
                  Recent Searches
                </span>
                <button
                  type="button"
                  onClick={clearRecentSearches}
                  className="text-xs text-muted hover:text-secondary transition-colors cursor-pointer"
                >
                  Clear history
                </button>
              </div>
              <div className="space-y-0.5">
                {recentSearches.map((term) => (
                  <button
                    key={term}
                    type="button"
                    onClick={() => handleSelectRecent(term)}
                    className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-xs text-secondary hover:bg-surface-raised hover:text-primary transition-colors cursor-pointer group"
                  >
                    <Search className="w-3.5 h-3.5 text-muted group-hover:text-primary transition-colors shrink-0" />
                    <span className="truncate flex-1 font-medium">{term}</span>
                    <span className="text-xs font-mono text-muted opacity-0 group-hover:opacity-100 transition-opacity">↵ Jump</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="mt-3 flex min-h-6 items-center justify-between px-1 text-xs text-secondary">
            <span className={isAuthenticated ? 'hidden sm:inline text-muted' : 'inline text-muted'}>
              {isAuthenticated ? 'Search by role, qualification, or availability' : 'Private workforce network. Access is protected.'}
            </span>
            {isAuthenticated && (
              <span className="ml-auto inline-flex items-center gap-1.5 text-xs text-muted">
                <kbd className="rounded-md border border-border-subtle bg-surface-raised px-1.5 py-0.5 font-mono text-xs text-secondary">↵</kbd>
                <span>to search</span>
                <span className="mx-1 text-muted/60">·</span>
                <kbd className="rounded-md border border-border-subtle bg-surface-raised px-1.5 py-0.5 font-mono text-xs text-secondary">/</kbd>
                <span>to focus</span>
              </span>
            )}
          </div>

          {/* Suggested searches help discovery before the result workspace opens. */}
          {isCalmState && isAuthenticated && (
            <div className="mt-5 flex items-center justify-center flex-wrap gap-2 px-1">
              <span className="text-xs text-muted font-medium mr-1 hidden sm:inline">
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
                    className={`inline-flex min-h-11 items-center px-3.5 py-1.5 rounded-full text-xs transition-all cursor-pointer border ${
                      isActive
                        ? 'bg-surface-raised border-border-strong text-primary font-semibold shadow-xs ring-1 ring-border-strong/40'
                        : 'bg-surface/70 hover:bg-surface-raised border-border-subtle/80 hover:border-border-strong text-secondary hover:text-primary font-medium'
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
                  className="inline-flex min-h-11 items-center gap-1.5 rounded-full px-3.5 py-1.5 text-xs font-medium text-secondary border border-border-subtle/80 hover:border-border-strong bg-surface/70 hover:bg-surface-raised hover:text-primary transition-all cursor-pointer"
                >
                  <SlidersHorizontal className="h-3.5 w-3.5" aria-hidden="true" />
                  <span>More filters</span>
                </button>
              )}
            </div>
          )}

          {!isCalmState && isAuthenticated && onOpenFilters && (
            <div className="mt-2 flex justify-end px-1">
              <button
                type="button"
                onClick={onOpenFilters}
                className="inline-flex min-h-11 items-center gap-1.5 rounded-lg border border-border-subtle/80 bg-surface/70 hover:bg-surface-raised px-3 text-xs font-medium text-secondary hover:text-primary transition-all cursor-pointer"
              >
                <SlidersHorizontal className="h-3.5 w-3.5" aria-hidden="true" />
                <span>Refine filters</span>
              </button>
            </div>
          )}

          {isCalmState && !isAuthenticated && (
            <div className="mt-12 grid w-full max-w-xl grid-cols-3 gap-2 text-center" aria-label="How it works">
              {[
                { icon: Search, label: 'Discover', detail: 'Search the private network' },
                { icon: Bookmark, label: 'Shortlist', detail: 'Save strongest fits' },
                { icon: Send, label: 'Mobilize', detail: 'Plan mobilization' },
              ].map(({ icon: Icon, label, detail }) => (
                <div
                  key={label}
                  className="rounded-xl border border-border-subtle/60 bg-surface/40 p-4 transition-all hover:border-border-subtle hover:bg-surface/70"
                >
                  <div className="mx-auto mb-2.5 flex h-8 w-8 items-center justify-center rounded-lg bg-surface-raised text-secondary">
                    <Icon className="h-4 w-4" aria-hidden="true" />
                  </div>
                  <p className="text-xs font-semibold text-primary">{label}</p>
                  <p className="mt-1 text-xs leading-4 text-muted">{detail}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
