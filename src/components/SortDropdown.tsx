import React, { useState, useRef, useEffect } from 'react';
import { SortOption } from '../types';
import { ArrowUpDown, Check, ChevronDown } from 'lucide-react';

interface SortDropdownProps {
  value: SortOption;
  onChange: (value: SortOption) => void;
}

interface OptionItem {
  id: SortOption;
  label: string;
  shortLabel: string;
}

const SORT_OPTIONS: OptionItem[] = [
  {
    id: 'relevance',
    label: 'Relevance (Best Match)',
    shortLabel: 'Relevance',
  },
  {
    id: 'experience-desc',
    label: 'Offshore Experience (High to Low)',
    shortLabel: 'Experience: High to Low',
  },
  {
    id: 'recent',
    label: 'Recently Added / Mobilised',
    shortLabel: 'Recently Added',
  },
  {
    id: 'experience-asc',
    label: 'Offshore Experience (Low to High)',
    shortLabel: 'Experience: Low to High',
  },
];

export const SortDropdown: React.FC<SortDropdownProps> = ({ value, onChange }) => {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const currentOption = SORT_OPTIONS.find((opt) => opt.id === value) || SORT_OPTIONS[0];

  // Close on outside click
  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener('mousedown', handleOutsideClick);
    }
    return () => {
      document.removeEventListener('mousedown', handleOutsideClick);
    };
  }, [isOpen]);

  // Close on Escape key
  useEffect(() => {
    const handleKeyDowndirect = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        setIsOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDowndirect);
    return () => window.removeEventListener('keydown', handleKeyDowndirect);
  }, [isOpen]);

  const handleSelect = (optId: SortOption) => {
    onChange(optId);
    setIsOpen(false);
  };

  return (
    <div className="relative inline-block text-left" ref={dropdownRef}>
      <button
        id="sort-dropdown-trigger"
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-xl text-xs font-medium border transition-all cursor-pointer select-none ${
          isOpen || value !== 'relevance'
            ? 'bg-slate-900 border-cyan-500/40 text-slate-100 shadow-sm'
            : 'bg-slate-900/70 border-slate-800 text-slate-400 hover:text-slate-200 hover:border-slate-700'
        }`}
        aria-haspopup="true"
        aria-expanded={isOpen}
        title="Sort consultants"
      >
        <ArrowUpDown className="w-3 h-3 text-slate-400 shrink-0" />
        <span className="text-slate-500 font-normal">Sort:</span>
        <span className="text-slate-200 font-medium">{currentOption.shortLabel}</span>
        <ChevronDown
          className={`w-3 h-3 text-slate-500 transition-transform duration-150 ${
            isOpen ? 'rotate-180 text-cyan-400' : ''
          }`}
        />
      </button>

      {isOpen && (
        <div
          id="sort-dropdown-menu"
          className="absolute right-0 mt-1.5 w-64 rounded-2xl bg-slate-900/95 border border-slate-800 shadow-2xl p-1.5 z-40 backdrop-blur-xl animate-in fade-in zoom-in-95 duration-100 focus:outline-none"
          role="menu"
          aria-orientation="vertical"
        >
          <div className="px-2.5 py-1.5 text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
            Sort specialists by
          </div>
          <div className="space-y-0.5">
            {SORT_OPTIONS.map((option) => {
              const isSelected = option.id === value;
              return (
                <button
                  key={option.id}
                  type="button"
                  onClick={() => handleSelect(option.id)}
                  className={`w-full flex items-center justify-between px-2.5 py-2 rounded-xl text-xs text-left transition-colors cursor-pointer ${
                    isSelected
                      ? 'bg-slate-800 text-cyan-300 font-medium'
                      : 'text-slate-300 hover:bg-slate-800/60 hover:text-white'
                  }`}
                  role="menuitem"
                >
                  <span className="truncate">{option.label}</span>
                  {isSelected && <Check className="w-3.5 h-3.5 text-cyan-400 shrink-0 ml-2" />}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};
