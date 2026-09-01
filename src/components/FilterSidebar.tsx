import React, { useState, useMemo } from 'react';
import {
  FilterState,
  RemoteType,
  AvailabilityStatus,
  FilterPreset,
} from '../types';
import {
  ALL_LOCATIONS,
  ALL_COMPANIES,
  ALL_DEPARTMENTS,
  SKILL_CATEGORIES,
  ALL_SKILLS,
  FILTER_PRESETS,
} from '../data/mockProfiles';
import { ExperienceRangeSlider } from './ExperienceRangeSlider';
import {
  MapPin,
  Briefcase,
  Layers,
  GraduationCap,
  Building2,
  Clock,
  Sparkles,
  ChevronDown,
  ChevronUp,
  RotateCcw,
  Check,
  Search,
  Zap,
  Globe2,
  SlidersHorizontal,
  ToggleLeft,
  ToggleRight,
  ShieldCheck,
} from 'lucide-react';

interface FilterSidebarProps {
  filters: FilterState;
  onUpdateFilters: (updater: (prev: FilterState) => FilterState) => void;
  onResetFilters: () => void;
  onApplyPreset: (preset: FilterPreset) => void;
  totalFilteredCount: number;
  totalCount: number;
}

export const FilterSidebar: React.FC<FilterSidebarProps> = ({
  filters,
  onUpdateFilters,
  onResetFilters,
  onApplyPreset,
  totalFilteredCount,
  totalCount,
}) => {
  const [skillSearchQuery, setSkillSearchQuery] = useState('');
  const [selectedSkillCategory, setSelectedSkillCategory] = useState<string>('All');
  const [locationSearchQuery, setLocationSearchQuery] = useState('');
  const [companySearchQuery, setCompanySearchQuery] = useState('');

  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    presets: false,
    skills: true,
    experience: true,
    location: true,
    company: true,
    department: false,
    availability: true,
  });

  const toggleSection = (key: string) => {
    setExpandedSections((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const toggleLocation = (loc: string) => {
    onUpdateFilters((prev) => ({
      ...prev,
      locations: prev.locations.includes(loc)
        ? prev.locations.filter((l) => l !== loc)
        : [...prev.locations, loc],
    }));
  };

  const toggleRemoteType = (rt: RemoteType) => {
    onUpdateFilters((prev) => ({
      ...prev,
      remoteTypes: prev.remoteTypes.includes(rt)
        ? prev.remoteTypes.filter((t) => t !== rt)
        : [...prev.remoteTypes, rt],
    }));
  };

  const toggleSkill = (skill: string) => {
    onUpdateFilters((prev) => ({
      ...prev,
      selectedSkills: prev.selectedSkills.includes(skill)
        ? prev.selectedSkills.filter((s) => s !== skill)
        : [...prev.selectedSkills, skill],
    }));
  };

  const toggleCompany = (company: string) => {
    onUpdateFilters((prev) => ({
      ...prev,
      companies: prev.companies.includes(company)
        ? prev.companies.filter((c) => c !== company)
        : [...prev.companies, company],
    }));
  };

  const toggleDepartment = (dept: string) => {
    onUpdateFilters((prev) => ({
      ...prev,
      departments: prev.departments.includes(dept)
        ? prev.departments.filter((d) => d !== dept)
        : [...prev.departments, dept],
    }));
  };

  const toggleAvailability = (avail: AvailabilityStatus) => {
    onUpdateFilters((prev) => ({
      ...prev,
      availability: prev.availability.includes(avail)
        ? prev.availability.filter((a) => a !== avail)
        : [...prev.availability, avail],
    }));
  };

  // Filter skills by search query and category
  const filteredSkillOptions = useMemo(() => {
    let pool = ALL_SKILLS;
    if (selectedSkillCategory !== 'All') {
      const cat = SKILL_CATEGORIES.find((c) => c.name === selectedSkillCategory);
      if (cat) pool = cat.skills;
    }
    if (!skillSearchQuery.trim()) return pool;
    return pool.filter((s) =>
      s.toLowerCase().includes(skillSearchQuery.toLowerCase().trim())
    );
  }, [skillSearchQuery, selectedSkillCategory]);

  const filteredLocations = useMemo(() => {
    if (!locationSearchQuery.trim()) return ALL_LOCATIONS;
    return ALL_LOCATIONS.filter((l) =>
      l.toLowerCase().includes(locationSearchQuery.toLowerCase().trim())
    );
  }, [locationSearchQuery]);

  const filteredCompanies = useMemo(() => {
    if (!companySearchQuery.trim()) return ALL_COMPANIES;
    return ALL_COMPANIES.filter((c) =>
      c.toLowerCase().includes(companySearchQuery.toLowerCase().trim())
    );
  }, [companySearchQuery]);

  const remoteOptions: { type: RemoteType; label: string; icon: string }[] = [
    { type: 'Remote', label: 'Remote', icon: '🌐' },
    { type: 'Hybrid', label: 'Hybrid', icon: '🏢' },
    { type: 'On-site', label: 'On-site', icon: '📍' },
  ];

  const availabilityOptions: { status: AvailabilityStatus; dotColor: string }[] = [
    { status: 'Available immediately', dotColor: 'bg-emerald-500 ring-emerald-500/20' },
    { status: 'Open to offers', dotColor: 'bg-sky-500 ring-sky-500/20' },
    { status: 'Contract / Freelance', dotColor: 'bg-amber-500 ring-amber-500/20' },
    { status: 'Employed (Not looking)', dotColor: 'bg-zinc-500 ring-zinc-500/20' },
  ];

  return (
    <div
      id="filter-sidebar"
      className="w-full bg-zinc-900/80 backdrop-blur-xl border border-zinc-800/90 rounded-2xl p-4.5 shadow-xl space-y-5"
    >
      {/* Sidebar Header with Results Counter & Clear Action */}
      <div className="flex items-center justify-between pb-3.5 border-b border-zinc-800/80">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-zinc-800 text-zinc-300 border border-zinc-700">
            <SlidersHorizontal className="w-4 h-4" />
          </div>
          <div>
            <h3 className="font-bold text-sm text-zinc-100">Filter Engine</h3>
            <p className="text-[11px] text-zinc-400 font-mono">
              <span className="text-zinc-200 font-semibold">{totalFilteredCount}</span> of {totalCount} profiles match
            </p>
          </div>
        </div>

        <button
          type="button"
          id="reset-all-filters-btn"
          onClick={onResetFilters}
          className="inline-flex items-center gap-1 text-xs font-semibold text-zinc-400 hover:text-zinc-200 transition-colors cursor-pointer py-1 px-2 rounded-lg hover:bg-zinc-800/60"
        >
          <RotateCcw className="w-3.5 h-3.5" />
          Reset
        </button>
      </div>

      {/* 1. Quick Presets Showcase */}
      <div className="space-y-2">
        <button
          type="button"
          onClick={() => toggleSection('presets')}
          className="w-full flex items-center justify-between text-xs font-bold text-zinc-300 hover:text-white uppercase tracking-wider cursor-pointer"
        >
          <span className="flex items-center gap-1.5">
            <Zap className="w-3.5 h-3.5 text-zinc-400" />
            Quick Presets
          </span>
          {expandedSections.presets ? (
            <ChevronUp className="w-3.5 h-3.5 text-zinc-400" />
          ) : (
            <ChevronDown className="w-3.5 h-3.5 text-zinc-400" />
          )}
        </button>

        {expandedSections.presets && (
          <div className="grid grid-cols-1 gap-2 pt-1">
            {FILTER_PRESETS.map((preset) => (
              <button
                key={preset.id}
                type="button"
                id={`preset-${preset.id}`}
                onClick={() => onApplyPreset(preset)}
                className="p-2.5 rounded-xl text-left bg-zinc-950/60 hover:bg-zinc-800/80 border border-zinc-800 hover:border-zinc-600 transition-all duration-150 group cursor-pointer"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-zinc-200 group-hover:text-white">
                    {preset.name}
                  </span>
                  <Zap className="w-3 h-3 text-zinc-600 group-hover:text-zinc-400" />
                </div>
                <p className="text-[11px] text-zinc-400 line-clamp-1 mt-0.5">
                  {preset.description}
                </p>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* 2. Skills Filter with Category Tabs & Match Logic Toggle */}
      <div className="space-y-3 pt-1 border-t border-zinc-800/60">
        <div className="flex items-center justify-between">
          <button
            type="button"
            onClick={() => toggleSection('skills')}
            className="flex items-center gap-1.5 text-xs font-bold text-zinc-200 uppercase tracking-wider cursor-pointer"
          >
            <Layers className="w-3.5 h-3.5 text-zinc-400" />
            Skills & Stack
            {filters.selectedSkills.length > 0 && (
              <span className="px-1.5 py-0.5 rounded-full bg-zinc-800 text-zinc-300 text-[10px] font-mono font-bold border border-zinc-700">
                {filters.selectedSkills.length}
              </span>
            )}
          </button>

          {/* ANY vs ALL Match Mode Switch */}
          <div className="flex items-center gap-1 bg-zinc-950/80 p-0.5 rounded-lg border border-zinc-800">
            <button
              type="button"
              id="skill-mode-any"
              onClick={() => onUpdateFilters((prev) => ({ ...prev, skillMatchMode: 'ANY' }))}
              className={`px-2 py-0.5 text-[10px] font-semibold rounded-md transition-all cursor-pointer ${
                filters.skillMatchMode === 'ANY'
                  ? 'bg-zinc-700 text-white shadow-xs'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
              title="Match ANY selected skill (OR mode)"
            >
              ANY
            </button>
            <button
              type="button"
              id="skill-mode-all"
              onClick={() => onUpdateFilters((prev) => ({ ...prev, skillMatchMode: 'ALL' }))}
              className={`px-2 py-0.5 text-[10px] font-semibold rounded-md transition-all cursor-pointer ${
                filters.skillMatchMode === 'ALL'
                  ? 'bg-zinc-700 text-white shadow-xs'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
              title="Match ALL selected skills simultaneously (AND mode)"
            >
              ALL
            </button>
          </div>
        </div>

        {expandedSections.skills && (
          <div className="space-y-2.5">
            {/* Skill Search Input */}
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-zinc-400 absolute left-2.5 top-2.5" />
              <input
                type="text"
                value={skillSearchQuery}
                onChange={(e) => setSkillSearchQuery(e.target.value)}
                placeholder="Search tech stack..."
                className="w-full pl-8 pr-3 py-1.5 bg-zinc-950/80 border border-zinc-800 rounded-xl text-xs text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-zinc-500"
              />
            </div>

            {/* Category Quick Filter */}
            <div className="flex items-center gap-1 overflow-x-auto pb-1 no-scrollbar text-[11px]">
              {['All', ...SKILL_CATEGORIES.map((c) => c.name)].map((cat) => (
                <button
                  key={cat}
                  type="button"
                  onClick={() => setSelectedSkillCategory(cat)}
                  className={`px-2 py-0.5 rounded-md whitespace-nowrap transition-colors cursor-pointer ${
                    selectedSkillCategory === cat
                      ? 'bg-zinc-800 text-zinc-100 font-semibold border border-zinc-700'
                      : 'text-zinc-400 hover:text-zinc-200'
                  }`}
                >
                  {cat}
                </button>
              ))}
            </div>

            {/* Skill Pills Matrix */}
            <div className="flex flex-wrap gap-1.5 max-h-48 overflow-y-auto pr-1">
              {filteredSkillOptions.map((skill) => {
                const isSelected = filters.selectedSkills.includes(skill);
                return (
                  <button
                    key={skill}
                    type="button"
                    id={`skill-pill-${skill.toLowerCase().replace(/[^a-z0-9]/g, '-')}`}
                    onClick={() => toggleSkill(skill)}
                    className={`px-2.5 py-1 text-xs font-medium rounded-lg border transition-all duration-150 cursor-pointer flex items-center gap-1.5 ${
                      isSelected
                        ? 'bg-zinc-800 text-white border-zinc-600 shadow-xs font-semibold'
                        : 'bg-zinc-950/60 border-zinc-800 text-zinc-300 hover:border-zinc-700 hover:text-white'
                    }`}
                  >
                    {isSelected && <Check className="w-3 h-3 text-white" />}
                    <span>{skill}</span>
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* 3. Years of Experience Dual Slider */}
      <div className="space-y-3 pt-1 border-t border-zinc-800/60">
        <button
          type="button"
          onClick={() => toggleSection('experience')}
          className="w-full flex items-center justify-between text-xs font-bold text-zinc-200 uppercase tracking-wider cursor-pointer"
        >
          <span className="flex items-center gap-1.5">
            <GraduationCap className="w-3.5 h-3.5 text-zinc-400" />
            Experience Range
          </span>
          {expandedSections.experience ? (
            <ChevronUp className="w-3.5 h-3.5 text-zinc-400" />
          ) : (
            <ChevronDown className="w-3.5 h-3.5 text-zinc-400" />
          )}
        </button>

        {expandedSections.experience && (
          <ExperienceRangeSlider
            min={filters.minExperience}
            max={filters.maxExperience}
            onChange={(min, max) =>
              onUpdateFilters((prev) => ({
                ...prev,
                minExperience: min,
                maxExperience: max,
              }))
            }
          />
        )}
      </div>

      {/* 4. Work Mode & Location */}
      <div className="space-y-3 pt-1 border-t border-zinc-800/60">
        <button
          type="button"
          onClick={() => toggleSection('location')}
          className="w-full flex items-center justify-between text-xs font-bold text-zinc-200 uppercase tracking-wider cursor-pointer"
        >
          <span className="flex items-center gap-1.5">
            <MapPin className="w-3.5 h-3.5 text-zinc-400" />
            Work Mode & Location
            {(filters.locations.length > 0 || filters.remoteTypes.length > 0) && (
              <span className="px-1.5 py-0.5 rounded-full bg-zinc-800 text-zinc-300 text-[10px] font-mono font-bold border border-zinc-700">
                {filters.locations.length + filters.remoteTypes.length}
              </span>
            )}
          </span>
          {expandedSections.location ? (
            <ChevronUp className="w-3.5 h-3.5 text-zinc-400" />
          ) : (
            <ChevronDown className="w-3.5 h-3.5 text-zinc-400" />
          )}
        </button>

        {expandedSections.location && (
          <div className="space-y-3">
            {/* 3-way Segmented Remote Pills */}
            <div className="grid grid-cols-3 gap-1.5 p-1 bg-zinc-950/80 rounded-xl border border-zinc-800">
              {remoteOptions.map(({ type, label, icon }) => {
                const isSelected = filters.remoteTypes.includes(type);
                return (
                  <button
                    key={type}
                    type="button"
                    id={`remote-toggle-${type.toLowerCase()}`}
                    onClick={() => toggleRemoteType(type)}
                    className={`py-1.5 px-2 rounded-lg text-xs font-medium transition-all duration-150 flex items-center justify-center gap-1.5 cursor-pointer ${
                      isSelected
                        ? 'bg-zinc-800 text-white font-semibold shadow-xs'
                        : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50'
                    }`}
                  >
                    <span>{icon}</span>
                    <span>{label}</span>
                  </button>
                );
              })}
            </div>

            {/* City / Location Search */}
            <div className="space-y-2">
              <div className="relative">
                <Search className="w-3.5 h-3.5 text-zinc-400 absolute left-2.5 top-2.5" />
                <input
                  type="text"
                  value={locationSearchQuery}
                  onChange={(e) => setLocationSearchQuery(e.target.value)}
                  placeholder="Filter locations..."
                  className="w-full pl-8 pr-3 py-1.5 bg-zinc-950/80 border border-zinc-800 rounded-xl text-xs text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-zinc-500"
                />
              </div>

              <div className="flex flex-wrap gap-1.5 max-h-32 overflow-y-auto pr-1">
                {filteredLocations.map((loc) => {
                  const isSelected = filters.locations.includes(loc);
                  return (
                    <button
                      key={loc}
                      type="button"
                      id={`location-pill-${loc.toLowerCase().replace(/[^a-z0-9]/g, '-')}`}
                      onClick={() => toggleLocation(loc)}
                      className={`px-2.5 py-1 text-xs rounded-lg border transition-all cursor-pointer flex items-center gap-1 ${
                        isSelected
                          ? 'bg-zinc-800 text-white border-zinc-600 font-semibold'
                          : 'bg-zinc-950/60 border-zinc-800 text-zinc-400 hover:border-zinc-700 hover:text-zinc-200'
                      }`}
                    >
                      {isSelected && <Check className="w-3 h-3 text-white" />}
                      <span>{loc}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 5. Company Affiliations */}
      <div className="space-y-3 pt-1 border-t border-zinc-800/60">
        <button
          type="button"
          onClick={() => toggleSection('company')}
          className="w-full flex items-center justify-between text-xs font-bold text-zinc-200 uppercase tracking-wider cursor-pointer"
        >
          <span className="flex items-center gap-1.5">
            <Building2 className="w-3.5 h-3.5 text-zinc-400" />
            Company & Alumni
            {filters.companies.length > 0 && (
              <span className="px-1.5 py-0.5 rounded-full bg-zinc-800 text-zinc-300 text-[10px] font-mono font-bold border border-zinc-700">
                {filters.companies.length}
              </span>
            )}
          </span>
          {expandedSections.company ? (
            <ChevronUp className="w-3.5 h-3.5 text-zinc-400" />
          ) : (
            <ChevronDown className="w-3.5 h-3.5 text-zinc-400" />
          )}
        </button>

        {expandedSections.company && (
          <div className="space-y-2">
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-zinc-400 absolute left-2.5 top-2.5" />
              <input
                type="text"
                value={companySearchQuery}
                onChange={(e) => setCompanySearchQuery(e.target.value)}
                placeholder="Search companies (Anthropic, Stripe...)"
                className="w-full pl-8 pr-3 py-1.5 bg-zinc-950/80 border border-zinc-800 rounded-xl text-xs text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-zinc-500"
              />
            </div>

            <div className="flex flex-wrap gap-1.5 max-h-36 overflow-y-auto pr-1">
              {filteredCompanies.map((company) => {
                const isSelected = filters.companies.includes(company);
                return (
                  <button
                    key={company}
                    type="button"
                    id={`company-pill-${company.toLowerCase().replace(/[^a-z0-9]/g, '-')}`}
                    onClick={() => toggleCompany(company)}
                    className={`px-2.5 py-1 text-xs rounded-lg border transition-all cursor-pointer flex items-center gap-1 ${
                      isSelected
                        ? 'bg-zinc-800 text-white border-zinc-600 font-semibold'
                        : 'bg-zinc-950/60 border-zinc-800 text-zinc-400 hover:border-zinc-700 hover:text-zinc-200'
                    }`}
                  >
                    {isSelected && <Check className="w-3 h-3 text-white" />}
                    <span>{company}</span>
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* 6. Availability Status */}
      <div className="space-y-3 pt-1 border-t border-zinc-800/60">
        <button
          type="button"
          onClick={() => toggleSection('availability')}
          className="w-full flex items-center justify-between text-xs font-bold text-zinc-200 uppercase tracking-wider cursor-pointer"
        >
          <span className="flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5 text-zinc-400" />
            Availability Status
            {filters.availability.length > 0 && (
              <span className="px-1.5 py-0.5 rounded-full bg-zinc-800 text-zinc-300 text-[10px] font-mono font-bold border border-zinc-700">
                {filters.availability.length}
              </span>
            )}
          </span>
          {expandedSections.availability ? (
            <ChevronUp className="w-3.5 h-3.5 text-zinc-400" />
          ) : (
            <ChevronDown className="w-3.5 h-3.5 text-zinc-400" />
          )}
        </button>

        {expandedSections.availability && (
          <div className="space-y-1.5">
            {availabilityOptions.map(({ status, dotColor }) => {
              const isSelected = filters.availability.includes(status);
              return (
                <button
                  key={status}
                  type="button"
                  id={`avail-${status.toLowerCase().replace(/[^a-z0-9]/g, '-')}`}
                  onClick={() => toggleAvailability(status)}
                  className={`w-full px-3 py-2 rounded-xl text-xs flex items-center justify-between border transition-all cursor-pointer ${
                    isSelected
                      ? 'bg-zinc-800 border-zinc-600 text-white font-semibold'
                      : 'bg-zinc-950/60 border-zinc-800 text-zinc-400 hover:border-zinc-700 hover:text-zinc-200'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ring-2 ${dotColor}`} />
                    <span>{status}</span>
                  </div>
                  {isSelected && <Check className="w-3.5 h-3.5 text-white" />}
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
