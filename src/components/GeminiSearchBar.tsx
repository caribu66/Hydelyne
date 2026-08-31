import React, { useState, useRef, useEffect } from 'react';
import {
  Sparkles,
  Search,
  Mic,
  MicOff,
  X,
  ArrowRight,
  SlidersHorizontal,
  MapPin,
  Code2,
  Briefcase,
  Layers,
  Check,
  ChevronDown,
  Globe2,
} from 'lucide-react';
import { FilterState, FilterPreset } from '../types';
import { ALL_LOCATIONS, ALL_SKILLS, FILTER_PRESETS } from '../data/mockProfiles';

interface GeminiSearchBarProps {
  query: string;
  onQueryChange: (query: string) => void;
  onSearchSubmit: (query: string) => void;
  onClear: () => void;
  onApplyPreset: (preset: FilterPreset) => void;
  onOpenFilterModal: () => void;
  activeFilterCount: number;
  isCompact?: boolean;
  filters: FilterState;
  onUpdateFilters: (updater: (prev: FilterState) => FilterState) => void;
}

export const GeminiSearchBar: React.FC<GeminiSearchBarProps> = ({
  query,
  onQueryChange,
  onSearchSubmit,
  onClear,
  onApplyPreset,
  onOpenFilterModal,
  activeFilterCount,
  isCompact = false,
  filters,
  onUpdateFilters,
}) => {
  const [isListening, setIsListening] = useState(false);
  const [activeDropdown, setActiveDropdown] = useState<'location' | 'skills' | 'remote' | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Focus shortcut: press "/"
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === '/' && document.activeElement !== inputRef.current) {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setActiveDropdown(null);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Voice Search Handler with Web Speech API
  const handleToggleVoice = () => {
    if (isListening) {
      setIsListening(false);
      return;
    }

    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      // If browser doesn't support Web Speech API, provide friendly fallback simulation
      setIsListening(true);
      const simulatedPhrases = [
        'Staff AI Engineer with PyTorch in San Francisco',
        'Senior React TypeScript developer remote',
        'Kubernetes DevOps lead available immediately',
        'Staff Product Designer in London',
      ];
      const sample = simulatedPhrases[Math.floor(Math.random() * simulatedPhrases.length)];
      setTimeout(() => {
        onQueryChange(sample);
        onSearchSubmit(sample);
        setIsListening(false);
      }, 1800);
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognition.lang = 'en-US';
      recognition.interimResults = true;

      recognition.onstart = () => {
        setIsListening(true);
      };

      recognition.onresult = (event: any) => {
        const transcript = Array.from(event.results)
          .map((result: any) => result[0].transcript)
          .join('');
        onQueryChange(transcript);
      };

      recognition.onerror = () => {
        setIsListening(false);
      };

      recognition.onend = () => {
        setIsListening(false);
        if (query.trim()) {
          onSearchSubmit(query);
        }
      };

      recognition.start();
    } catch {
      setIsListening(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      onSearchSubmit(query);
    } else if (e.key === 'Escape') {
      onClear();
      inputRef.current?.blur();
    }
  };

  const toggleSkill = (skill: string) => {
    onUpdateFilters((prev) => {
      const exists = prev.selectedSkills.includes(skill);
      return {
        ...prev,
        selectedSkills: exists
          ? prev.selectedSkills.filter((s) => s !== skill)
          : [...prev.selectedSkills, skill],
      };
    });
  };

  const toggleLocation = (loc: string) => {
    onUpdateFilters((prev) => {
      const exists = prev.locations.includes(loc);
      return {
        ...prev,
        locations: exists ? prev.locations.filter((l) => l !== loc) : [...prev.locations, loc],
      };
    });
  };

  const toggleRemote = (type: 'Remote' | 'Hybrid' | 'On-site') => {
    onUpdateFilters((prev) => {
      const exists = prev.remoteTypes.includes(type);
      return {
        ...prev,
        remoteTypes: exists
          ? prev.remoteTypes.filter((t) => t !== type)
          : [...prev.remoteTypes, type],
      };
    });
  };

  return (
    <div
      id="gemini-search-container"
      className={`w-full transition-all duration-300 ${
        isCompact ? 'max-w-4xl mx-auto' : 'max-w-3xl mx-auto'
      }`}
    >
      {/* Search Input Omnibar */}
      <div
        className={`relative group rounded-3xl bg-zinc-900/90 border transition-all duration-300 shadow-2xl backdrop-blur-xl ${
          isListening
            ? 'border-indigo-500 ring-4 ring-indigo-500/20 shadow-indigo-500/10'
            : 'border-zinc-800 hover:border-zinc-700 focus-within:border-indigo-500 focus-within:ring-4 focus-within:ring-indigo-500/20'
        }`}
      >
        <div className="flex items-center px-4 sm:px-6 py-3.5 sm:py-4 gap-3 sm:gap-4">
          {/* Gemini Sparkle Icon */}
          <div className="shrink-0 flex items-center justify-center">
            <div className="w-9 h-9 rounded-2xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-purple-500 flex items-center justify-center shadow-md shadow-indigo-500/20">
              <Sparkles className="w-4 h-4 text-white animate-pulse" />
            </div>
          </div>

          {/* Text Input */}
          <div className="flex-1 min-w-0">
            <input
              ref={inputRef}
              id="gemini-main-search-input"
              type="text"
              value={query}
              onChange={(e) => onQueryChange(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                isListening
                  ? 'Listening... Speak your ideal candidate or skills...'
                  : isCompact
                  ? 'Search talent, skills, companies, or natural prompts...'
                  : 'Ask anything: "Senior PyTorch engineer in SF" or "Remote React dev"...'
              }
              className="w-full bg-transparent text-sm sm:text-base text-zinc-100 placeholder:text-zinc-500 focus:outline-none font-medium leading-relaxed"
              autoComplete="off"
              spellCheck="false"
            />
          </div>

          {/* Right Action Icons */}
          <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
            {/* Clear Button */}
            {query && (
              <button
                type="button"
                id="gemini-clear-btn"
                onClick={onClear}
                className="p-1.5 rounded-full text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors cursor-pointer"
                title="Clear input (Esc)"
              >
                <X className="w-4 h-4" />
              </button>
            )}

            {/* Voice Input Button */}
            <button
              type="button"
              id="gemini-voice-btn"
              onClick={handleToggleVoice}
              className={`p-2 rounded-2xl transition-all cursor-pointer ${
                isListening
                  ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30 animate-pulse'
                  : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800'
              }`}
              title={isListening ? 'Stop listening' : 'Voice Search with Gemini'}
            >
              {isListening ? (
                <Mic className="w-4 h-4 text-rose-400" />
              ) : (
                <Mic className="w-4 h-4" />
              )}
            </button>

            {/* Filter Drawer Toggle Button */}
            <button
              type="button"
              id="gemini-filter-toggle-btn"
              onClick={onOpenFilterModal}
              className={`p-2 rounded-2xl border transition-all cursor-pointer relative ${
                activeFilterCount > 0
                  ? 'bg-indigo-500/20 border-indigo-500/40 text-indigo-300'
                  : 'border-zinc-800 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800'
              }`}
              title="All Filters"
            >
              <SlidersHorizontal className="w-4 h-4" />
              {activeFilterCount > 0 && (
                <span className="absolute -top-1 -right-1 w-4 h-4 bg-indigo-500 text-white rounded-full text-[10px] font-bold flex items-center justify-center">
                  {activeFilterCount}
                </span>
              )}
            </button>

            {/* Submit / Ask Sparkle Button */}
            <button
              type="button"
              id="gemini-submit-btn"
              onClick={() => onSearchSubmit(query)}
              className="p-2 sm:px-4 sm:py-2 rounded-2xl bg-gradient-to-r from-indigo-600 to-indigo-500 hover:from-indigo-500 hover:to-indigo-400 text-white font-semibold text-xs sm:text-sm flex items-center gap-1.5 transition-all shadow-md shadow-indigo-600/30 cursor-pointer active:scale-95"
              title="Search (Enter)"
            >
              <span className="hidden sm:inline">Search</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Listening wave indicator if active */}
        {isListening && (
          <div className="px-6 pb-3 pt-1 flex items-center gap-2 text-xs text-rose-400 border-t border-zinc-800/80">
            <span className="w-2 h-2 rounded-full bg-rose-500 animate-ping" />
            <span className="font-medium">Listening to your voice prompt... Try "Staff Go engineer in London"</span>
          </div>
        )}
      </div>

      {/* Quick Filter Tag Bar directly attached beneath the search bar */}
      <div ref={dropdownRef} className="relative mt-3 flex flex-wrap items-center gap-2 justify-center">
        {/* Quick Location Pill */}
        <div className="relative">
          <button
            type="button"
            onClick={() => setActiveDropdown(activeDropdown === 'location' ? null : 'location')}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium border transition-all cursor-pointer ${
              filters.locations.length > 0
                ? 'bg-indigo-500/20 border-indigo-500/40 text-indigo-300 font-semibold'
                : 'bg-zinc-900/80 border-zinc-800 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/80'
            }`}
          >
            <MapPin className="w-3.5 h-3.5 text-indigo-400" />
            <span>
              {filters.locations.length === 0
                ? 'Location'
                : filters.locations.length === 1
                ? filters.locations[0].split(',')[0]
                : `${filters.locations.length} Locations`}
            </span>
            <ChevronDown className="w-3 h-3 opacity-60" />
          </button>

          {activeDropdown === 'location' && (
            <div className="absolute left-0 mt-2 w-64 bg-zinc-900 border border-zinc-800 rounded-2xl p-2.5 shadow-2xl z-40 space-y-1">
              <div className="text-[11px] font-semibold text-zinc-400 px-2 py-1 uppercase tracking-wider">
                Select Locations
              </div>
              <div className="max-h-48 overflow-y-auto space-y-1 pr-1">
                {ALL_LOCATIONS.map((loc) => {
                  const isSelected = filters.locations.includes(loc);
                  return (
                    <button
                      key={loc}
                      type="button"
                      onClick={() => toggleLocation(loc)}
                      className={`w-full text-left px-2.5 py-1.5 rounded-xl text-xs flex items-center justify-between transition-colors cursor-pointer ${
                        isSelected
                          ? 'bg-indigo-500/20 text-indigo-300 font-semibold'
                          : 'text-zinc-300 hover:bg-zinc-800'
                      }`}
                    >
                      <span className="truncate">{loc}</span>
                      {isSelected && <Check className="w-3.5 h-3.5 text-indigo-400" />}
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* Quick Skills Pill */}
        <div className="relative">
          <button
            type="button"
            onClick={() => setActiveDropdown(activeDropdown === 'skills' ? null : 'skills')}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium border transition-all cursor-pointer ${
              filters.selectedSkills.length > 0
                ? 'bg-indigo-500/20 border-indigo-500/40 text-indigo-300 font-semibold'
                : 'bg-zinc-900/80 border-zinc-800 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/80'
            }`}
          >
            <Code2 className="w-3.5 h-3.5 text-indigo-400" />
            <span>
              {filters.selectedSkills.length === 0
                ? 'Skills'
                : filters.selectedSkills.length === 1
                ? filters.selectedSkills[0]
                : `${filters.selectedSkills.length} Skills`}
            </span>
            <ChevronDown className="w-3 h-3 opacity-60" />
          </button>

          {activeDropdown === 'skills' && (
            <div className="absolute left-0 mt-2 w-72 bg-zinc-900 border border-zinc-800 rounded-2xl p-2.5 shadow-2xl z-40 space-y-1.5">
              <div className="text-[11px] font-semibold text-zinc-400 px-2 py-1 uppercase tracking-wider">
                Top Skills
              </div>
              <div className="max-h-52 overflow-y-auto grid grid-cols-2 gap-1 pr-1">
                {ALL_SKILLS.slice(0, 16).map((skill) => {
                  const isSelected = filters.selectedSkills.includes(skill);
                  return (
                    <button
                      key={skill}
                      type="button"
                      onClick={() => toggleSkill(skill)}
                      className={`text-left px-2 py-1.5 rounded-xl text-xs flex items-center justify-between transition-colors cursor-pointer ${
                        isSelected
                          ? 'bg-indigo-500/20 text-indigo-300 font-semibold'
                          : 'text-zinc-300 hover:bg-zinc-800'
                      }`}
                    >
                      <span className="truncate">{skill}</span>
                      {isSelected && <Check className="w-3 h-3 text-indigo-400" />}
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* Quick Remote Pill */}
        <div className="relative">
          <button
            type="button"
            onClick={() => setActiveDropdown(activeDropdown === 'remote' ? null : 'remote')}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium border transition-all cursor-pointer ${
              filters.remoteTypes.length > 0
                ? 'bg-indigo-500/20 border-indigo-500/40 text-indigo-300 font-semibold'
                : 'bg-zinc-900/80 border-zinc-800 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/80'
            }`}
          >
            <Globe2 className="w-3.5 h-3.5 text-indigo-400" />
            <span>
              {filters.remoteTypes.length === 0
                ? 'Work Mode'
                : filters.remoteTypes.join(', ')}
            </span>
            <ChevronDown className="w-3 h-3 opacity-60" />
          </button>

          {activeDropdown === 'remote' && (
            <div className="absolute left-0 mt-2 w-48 bg-zinc-900 border border-zinc-800 rounded-2xl p-2 shadow-2xl z-40 space-y-1">
              {(['Remote', 'Hybrid', 'On-site'] as const).map((type) => {
                const isSelected = filters.remoteTypes.includes(type);
                return (
                  <button
                    key={type}
                    type="button"
                    onClick={() => toggleRemote(type)}
                    className={`w-full text-left px-3 py-1.5 rounded-xl text-xs flex items-center justify-between transition-colors cursor-pointer ${
                      isSelected
                        ? 'bg-indigo-500/20 text-indigo-300 font-semibold'
                        : 'text-zinc-300 hover:bg-zinc-800'
                    }`}
                  >
                    <span>{type}</span>
                    {isSelected && <Check className="w-3.5 h-3.5 text-indigo-400" />}
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* More Filters Trigger */}
        <button
          type="button"
          onClick={onOpenFilterModal}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium bg-zinc-900/80 border border-zinc-800 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/80 transition-all cursor-pointer"
        >
          <SlidersHorizontal className="w-3 h-3" />
          <span>All Filters ({activeFilterCount})</span>
        </button>
      </div>

      {/* Suggested Natural Prompt Cards (shown when not in compact mode) */}
      {!isCompact && (
        <div className="mt-8 space-y-3">
          <div className="text-center text-xs font-medium text-zinc-400 flex items-center justify-center gap-2">
            <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
            <span>Try natural prompts like Gemini:</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
            {[
              {
                icon: '⚡',
                title: 'Available Immediately Remote',
                query: 'Available immediately React & TypeScript remote engineers',
                desc: 'Fast-hire frontend & full-stack engineers',
              },
              {
                icon: '🧠',
                title: 'Staff AI / ML Systems Architect',
                query: 'PyTorch transformer optimization LLM fine-tuning engineers',
                desc: 'Specialists in CUDA, PyTorch & Large Models',
              },
              {
                icon: '🛡️',
                title: 'Principal Cloud & Platform Lead',
                query: 'Kubernetes Go Terraform AWS distributed systems',
                desc: 'Infrastructure & zero-downtime ledger architects',
              },
              {
                icon: '🎨',
                title: 'Senior Product & Design Systems',
                query: 'Design Systems Figma UX Research UI/UX leads',
                desc: 'Design leads with modular component systems',
              },
            ].map((preset) => (
              <button
                key={preset.title}
                type="button"
                onClick={() => {
                  onQueryChange(preset.query);
                  onSearchSubmit(preset.query);
                }}
                className="group p-3.5 bg-zinc-900/60 hover:bg-zinc-800/80 border border-zinc-800/80 hover:border-indigo-500/40 rounded-2xl text-left transition-all duration-200 cursor-pointer flex items-start gap-3 shadow-md hover:shadow-indigo-500/5"
              >
                <span className="text-xl p-2 rounded-xl bg-zinc-800/80 border border-zinc-700/50 group-hover:scale-110 transition-transform shrink-0">
                  {preset.icon}
                </span>
                <div className="min-w-0">
                  <div className="text-xs font-bold text-zinc-200 group-hover:text-indigo-300 transition-colors truncate">
                    {preset.title}
                  </div>
                  <div className="text-[11px] text-zinc-400 line-clamp-1 mt-0.5">
                    {preset.desc}
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
