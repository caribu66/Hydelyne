import React, { useRef, useEffect } from 'react';
import { Search, X, Sparkles, Command, ArrowRight, Zap, Code2, Globe2, Cpu, ShieldCheck } from 'lucide-react';

interface SearchBarProps {
  value: string;
  onChange: (val: string) => void;
  onClear: () => void;
}

const QUICK_TAGS = [
  { label: 'Distributed Systems', icon: Cpu },
  { label: 'PyTorch & LLMs', icon: Zap },
  { label: 'React / TypeScript', icon: Code2 },
  { label: 'Remote Only', icon: Globe2 },
  { label: 'Lead / Staff', icon: ShieldCheck },
];

export const SearchBar: React.FC<SearchBarProps> = ({ value, onChange, onClear }) => {
  const inputRef = useRef<HTMLInputElement>(null);

  // Global '/' or 'cmd+k' shortcut to focus search
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (
        (e.key === '/' || (e.key === 'k' && (e.metaKey || e.ctrlKey))) &&
        document.activeElement?.tagName !== 'INPUT' &&
        document.activeElement?.tagName !== 'TEXTAREA'
      ) {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  return (
    <div className="w-full space-y-3">
      {/* Modern Spotlight Omnibar */}
      <div className="relative group">
        <div className="absolute -inset-0.5 bg-gradient-to-r from-indigo-500/30 via-purple-500/20 to-pink-500/20 rounded-2xl blur-md opacity-40 group-focus-within:opacity-100 group-hover:opacity-75 transition duration-300"></div>

        <div className="relative flex items-center w-full bg-zinc-900/90 border border-zinc-800/90 group-focus-within:border-indigo-500/80 rounded-2xl shadow-2xl transition-all duration-200">
          <div className="pl-4 pr-1 flex items-center pointer-events-none text-zinc-400 group-focus-within:text-indigo-400 transition-colors">
            <Search className="w-5 h-5" />
          </div>

          <input
            ref={inputRef}
            id="global-keyword-search"
            type="text"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder="Search by keywords, title, skills, bio, company, or tech stack (e.g., 'PyTorch', 'Staff Engineer', 'Stripe')..."
            className="w-full py-3.5 pl-2 pr-28 bg-transparent text-zinc-100 placeholder:text-zinc-500 text-sm sm:text-base focus:outline-none font-medium selection:bg-indigo-500/40"
          />

          <div className="pr-3 flex items-center gap-2">
            {value && (
              <button
                id="clear-keyword-btn"
                type="button"
                onClick={onClear}
                className="p-1 text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 rounded-lg transition-colors cursor-pointer"
                title="Clear query"
              >
                <X className="w-4 h-4" />
              </button>
            )}

            <div className="hidden sm:flex items-center gap-1 px-2 py-1 text-[11px] font-mono text-zinc-400 bg-zinc-800/70 border border-zinc-700/60 rounded-md select-none pointer-events-none">
              <Command className="w-3 h-3" />
              <span>K</span>
            </div>
          </div>
        </div>
      </div>

      {/* Suggested Quick Search / Discovery Pills */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1 text-xs no-scrollbar">
        <span className="flex items-center gap-1 text-zinc-400 font-semibold text-[11px] uppercase tracking-wider whitespace-nowrap pl-0.5">
          <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
          Trending:
        </span>
        {QUICK_TAGS.map(({ label, icon: Icon }) => {
          const isActive = value.toLowerCase() === label.toLowerCase();
          return (
            <button
              key={label}
              type="button"
              onClick={() => onChange(isActive ? '' : label)}
              className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-lg border text-xs whitespace-nowrap transition-all duration-150 cursor-pointer ${
                isActive
                  ? 'bg-indigo-500/20 text-indigo-300 border-indigo-500/50 font-medium shadow-sm'
                  : 'bg-zinc-900/60 border-zinc-800 text-zinc-400 hover:bg-zinc-800/80 hover:text-zinc-200 hover:border-zinc-700'
              }`}
            >
              <Icon className="w-3 h-3 text-zinc-400" />
              <span>{label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
};
