import { FC, useState, useMemo } from 'react';
import {
  FilterState,
  RemoteType,
  AvailabilityStatus,
  FilterPreset,
} from '../types';
import {
  SKILL_CATEGORIES,
  FILTER_PRESETS,
} from '../data/mockProfiles';
import { UserProfile } from '../types';
import { ExperienceRangeSlider } from './ExperienceRangeSlider';
import {
  MapPin,
  Layers,
  GraduationCap,
  Building2,
  Clock,
  ChevronDown,
  ChevronUp,
  RotateCcw,
  Check,
  Search,
  Zap,
  SlidersHorizontal,
} from 'lucide-react';

interface FilterSidebarProps {
  profiles: UserProfile[];
  filters: FilterState;
  onUpdateFilters: (updater: (prev: FilterState) => FilterState) => void;
  onResetFilters: () => void;
  onApplyPreset: (preset: FilterPreset) => void;
  totalFilteredCount: number;
  totalCount: number;
}

export const FilterSidebar: FC<FilterSidebarProps> = ({
  profiles,
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

  // Unused: no department filter chips are rendered in this sidebar yet
  // (ALL_DEPARTMENTS is imported but unused too). FilterState.departments
  // still exists — kept pending a decision to wire this up or remove it.
  const _toggleDepartment = (dept: string) => {
    onUpdateFilters((prev) => ({
      ...prev,
      departments: prev.departments.includes(dept)
        ? prev.departments.filter((d) => d !== dept)
        : [...prev.departments, dept],
    }));
  };

  const availableSkills = useMemo(
    () => Array.from(new Set(profiles.flatMap((profile) => profile.skills))).sort(),
    [profiles],
  );
  const availableLocations = useMemo(
    () =>
      Array.from(
        new Set(
          profiles
            .map((profile) => profile.location)
            .filter((location) => location && location !== 'Location not recorded'),
        ),
      ).sort(),
    [profiles],
  );
  const availableCompanies = useMemo(
    () =>
      Array.from(
        new Set(
          profiles
            .map((profile) => profile.company)
            .filter((company) => company && company !== 'Company not recorded'),
        ),
      ).sort(),
    [profiles],
  );

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
    let pool = availableSkills;
    if (selectedSkillCategory !== 'All') {
      const cat = SKILL_CATEGORIES.find((c) => c.name === selectedSkillCategory);
      if (cat) {
        const categorySkills = new Set(cat.skills);
        pool = availableSkills.filter((skill) => categorySkills.has(skill));
      }
    }
    if (!skillSearchQuery.trim()) return pool;
    return pool.filter((s) =>
      s.toLowerCase().includes(skillSearchQuery.toLowerCase().trim())
    );
  }, [availableSkills, skillSearchQuery, selectedSkillCategory]);

  const filteredLocations = useMemo(() => {
    if (!locationSearchQuery.trim()) return availableLocations;
    return availableLocations.filter((l) =>
      l.toLowerCase().includes(locationSearchQuery.toLowerCase().trim())
    );
  }, [availableLocations, locationSearchQuery]);

  const filteredCompanies = useMemo(() => {
    if (!companySearchQuery.trim()) return availableCompanies;
    return availableCompanies.filter((c) =>
      c.toLowerCase().includes(companySearchQuery.toLowerCase().trim())
    );
  }, [availableCompanies, companySearchQuery]);

  const remoteOptions: { type: RemoteType; label: string; icon: string }[] = [
    { type: 'Remote', label: 'Remote', icon: '🌐' },
    { type: 'Hybrid', label: 'Hybrid', icon: '🏢' },
    { type: 'On-site', label: 'On-site', icon: '📍' },
  ];

  const availabilityOptions: { status: AvailabilityStatus; dotColor: string }[] = [
    { status: 'Available immediately', dotColor: 'bg-positive ring-positive/20' },
    { status: 'Open to offers', dotColor: 'bg-focus ring-focus/20' },
    { status: 'Contract / Freelance', dotColor: 'bg-warning ring-warning/20' },
    { status: 'Employed (Not looking)', dotColor: 'bg-surface-selected ring-focus/20' },
  ];

  return (
    <div
      id="filter-sidebar"
      className="w-full bg-surface/80 backdrop-blur-xl border border-border-subtle/90 rounded-[14px] p-4.5 shadow-xl space-y-5"
    >
      {/* Sidebar Header with Results Counter & Clear Action */}
      <div className="flex items-center justify-between pb-3.5 border-b border-border-subtle/80">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-surface-raised text-secondary border border-border-strong">
            <SlidersHorizontal className="w-4 h-4" />
          </div>
          <div>
            <h3 className="font-bold text-sm text-primary">Contractor filters</h3>
            <p className="text-xs text-secondary font-mono">
              <span className="text-primary font-semibold">{totalFilteredCount}</span> of {totalCount} contractors match
            </p>
          </div>
        </div>

        <button
          type="button"
          id="reset-all-filters-btn"
          onClick={onResetFilters}
          className="inline-flex min-h-11 items-center gap-1 text-xs font-semibold text-secondary hover:text-primary transition-colors cursor-pointer py-1 px-2 rounded-lg hover:bg-surface-raised/60"
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
          className="min-h-11 w-full flex items-center justify-between text-xs font-bold text-secondary hover:text-primary uppercase tracking-wider cursor-pointer"
        >
          <span className="flex items-center gap-1.5">
            <Zap className="w-3.5 h-3.5 text-secondary" />
            Quick Presets
          </span>
          {expandedSections.presets ? (
            <ChevronUp className="w-3.5 h-3.5 text-secondary" />
          ) : (
            <ChevronDown className="w-3.5 h-3.5 text-secondary" />
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
                className="p-2.5 rounded-[10px] text-left bg-canvas/60 hover:bg-surface-raised/80 border border-border-subtle hover:border-border-strong transition-all duration-150 group cursor-pointer"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-primary group-hover:text-primary">
                    {preset.name}
                  </span>
                  <Zap className="w-3 h-3 text-muted group-hover:text-secondary" />
                </div>
                <p className="text-xs text-secondary line-clamp-1 mt-0.5">
                  {preset.description}
                </p>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* 2. Skills Filter with Category Tabs & Match Logic Toggle */}
      <div className="space-y-3 pt-1 border-t border-border-subtle/60">
        <div className="flex items-center justify-between">
          <button
            type="button"
            onClick={() => toggleSection('skills')}
            className="min-h-11 flex items-center gap-1.5 text-xs font-bold text-primary uppercase tracking-wider cursor-pointer"
          >
            <Layers className="w-3.5 h-3.5 text-secondary" />
            Skills & Stack
            {filters.selectedSkills.length > 0 && (
              <span className="px-1.5 py-0.5 rounded-full bg-surface-raised text-secondary text-xs font-mono font-bold border border-border-strong">
                {filters.selectedSkills.length}
              </span>
            )}
          </button>

          {/* ANY vs ALL Match Mode Switch */}
          <div className="flex items-center gap-1 bg-canvas/80 p-0.5 rounded-lg border border-border-subtle">
            <button
              type="button"
              id="skill-mode-any"
              onClick={() => onUpdateFilters((prev) => ({ ...prev, skillMatchMode: 'ANY' }))}
              className={`min-h-11 px-2 text-xs font-semibold rounded-md transition-all cursor-pointer ${
                filters.skillMatchMode === 'ANY'
                  ? 'bg-surface-selected text-primary shadow-xs'
                  : 'text-secondary hover:text-primary'
              }`}
              title="Match ANY selected skill (OR mode)"
            >
              ANY
            </button>
            <button
              type="button"
              id="skill-mode-all"
              onClick={() => onUpdateFilters((prev) => ({ ...prev, skillMatchMode: 'ALL' }))}
              className={`min-h-11 px-2 text-xs font-semibold rounded-md transition-all cursor-pointer ${
                filters.skillMatchMode === 'ALL'
                  ? 'bg-surface-selected text-primary shadow-xs'
                  : 'text-secondary hover:text-primary'
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
              <Search className="w-3.5 h-3.5 text-secondary absolute left-2.5 top-2.5" />
              <input
                type="text"
                value={skillSearchQuery}
                onChange={(e) => setSkillSearchQuery(e.target.value)}
                placeholder="Search contractor skills…"
                aria-label="Search contractor skills"
                className="min-h-11 w-full pl-8 pr-3 py-1.5 bg-canvas/80 border border-border-subtle rounded-[10px] text-sm text-primary placeholder:text-muted focus:outline-none focus:border-border-strong"
              />
            </div>

            {/* Category Quick Filter */}
            <div className="flex items-center gap-1 overflow-x-auto pb-1 no-scrollbar text-xs">
              {['All', ...SKILL_CATEGORIES.map((c) => c.name)].map((cat) => (
                <button
                  key={cat}
                  type="button"
                  onClick={() => setSelectedSkillCategory(cat)}
                    className={`min-h-11 px-2 rounded-md whitespace-nowrap transition-colors cursor-pointer ${
                    selectedSkillCategory === cat
                      ? 'bg-surface-raised text-primary font-semibold border border-border-strong'
                      : 'text-secondary hover:text-primary'
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
                    className={`min-h-11 px-2.5 py-1 text-xs font-medium rounded-lg border transition-all duration-150 cursor-pointer flex items-center gap-1.5 ${
                      isSelected
                        ? 'bg-surface-raised text-primary border-border-strong shadow-xs font-semibold'
                        : 'bg-canvas/60 border-border-subtle text-secondary hover:border-border-strong hover:text-primary'
                    }`}
                  >
                    {isSelected && <Check className="w-3 h-3 text-primary" />}
                    <span>{skill}</span>
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* 3. Years of Experience Dual Slider */}
      <div className="space-y-3 pt-1 border-t border-border-subtle/60">
        <button
          type="button"
          onClick={() => toggleSection('experience')}
          className="min-h-11 w-full flex items-center justify-between text-xs font-bold text-primary uppercase tracking-wider cursor-pointer"
        >
          <span className="flex items-center gap-1.5">
            <GraduationCap className="w-3.5 h-3.5 text-secondary" />
            Experience Range
          </span>
          {expandedSections.experience ? (
            <ChevronUp className="w-3.5 h-3.5 text-secondary" />
          ) : (
            <ChevronDown className="w-3.5 h-3.5 text-secondary" />
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
      <div className="space-y-3 pt-1 border-t border-border-subtle/60">
        <button
          type="button"
          onClick={() => toggleSection('location')}
          className="min-h-11 w-full flex items-center justify-between text-xs font-bold text-primary uppercase tracking-wider cursor-pointer"
        >
          <span className="flex items-center gap-1.5">
            <MapPin className="w-3.5 h-3.5 text-secondary" />
            Work Mode & Location
            {(filters.locations.length > 0 || filters.remoteTypes.length > 0) && (
              <span className="px-1.5 py-0.5 rounded-full bg-surface-raised text-secondary text-xs font-mono font-bold border border-border-strong">
                {filters.locations.length + filters.remoteTypes.length}
              </span>
            )}
          </span>
          {expandedSections.location ? (
            <ChevronUp className="w-3.5 h-3.5 text-secondary" />
          ) : (
            <ChevronDown className="w-3.5 h-3.5 text-secondary" />
          )}
        </button>

        {expandedSections.location && (
          <div className="space-y-3">
            {/* 3-way Segmented Remote Pills */}
            <div className="grid grid-cols-3 gap-1.5 p-1 bg-canvas/80 rounded-[10px] border border-border-subtle">
              {remoteOptions.map(({ type, label, icon }) => {
                const isSelected = filters.remoteTypes.includes(type);
                return (
                  <button
                    key={type}
                    type="button"
                    id={`remote-toggle-${type.toLowerCase()}`}
                    onClick={() => toggleRemoteType(type)}
                    className={`min-h-11 py-1.5 px-2 rounded-lg text-xs font-medium transition-all duration-150 flex items-center justify-center gap-1.5 cursor-pointer ${
                      isSelected
                        ? 'bg-surface-raised text-primary font-semibold shadow-xs'
                        : 'text-secondary hover:text-primary hover:bg-surface-raised/50'
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
                <Search className="w-3.5 h-3.5 text-secondary absolute left-2.5 top-2.5" />
                <input
                  type="text"
                  value={locationSearchQuery}
                  onChange={(e) => setLocationSearchQuery(e.target.value)}
                  placeholder="Filter locations…"
                  aria-label="Filter locations"
                  className="min-h-11 w-full pl-8 pr-3 py-1.5 bg-canvas/80 border border-border-subtle rounded-[10px] text-sm text-primary placeholder:text-muted focus:outline-none focus:border-border-strong"
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
                      className={`min-h-11 px-2.5 py-1 text-xs rounded-lg border transition-all cursor-pointer flex items-center gap-1 ${
                        isSelected
                          ? 'bg-surface-raised text-primary border-border-strong font-semibold'
                          : 'bg-canvas/60 border-border-subtle text-secondary hover:border-border-strong hover:text-primary'
                      }`}
                    >
                      {isSelected && <Check className="w-3 h-3 text-primary" />}
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
      <div className="space-y-3 pt-1 border-t border-border-subtle/60">
        <button
          type="button"
          onClick={() => toggleSection('company')}
          className="min-h-11 w-full flex items-center justify-between text-xs font-bold text-primary uppercase tracking-wider cursor-pointer"
        >
          <span className="flex items-center gap-1.5">
            <Building2 className="w-3.5 h-3.5 text-secondary" />
            Company & Alumni
            {filters.companies.length > 0 && (
              <span className="px-1.5 py-0.5 rounded-full bg-surface-raised text-secondary text-xs font-mono font-bold border border-border-strong">
                {filters.companies.length}
              </span>
            )}
          </span>
          {expandedSections.company ? (
            <ChevronUp className="w-3.5 h-3.5 text-secondary" />
          ) : (
            <ChevronDown className="w-3.5 h-3.5 text-secondary" />
          )}
        </button>

        {expandedSections.company && (
          <div className="space-y-2">
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-secondary absolute left-2.5 top-2.5" />
              <input
                type="text"
                value={companySearchQuery}
                onChange={(e) => setCompanySearchQuery(e.target.value)}
                placeholder="Search companies…"
                aria-label="Search companies"
                className="min-h-11 w-full pl-8 pr-3 py-1.5 bg-canvas/80 border border-border-subtle rounded-[10px] text-sm text-primary placeholder:text-muted focus:outline-none focus:border-border-strong"
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
                    className={`min-h-11 px-2.5 py-1 text-xs rounded-lg border transition-all cursor-pointer flex items-center gap-1 ${
                      isSelected
                        ? 'bg-surface-raised text-primary border-border-strong font-semibold'
                        : 'bg-canvas/60 border-border-subtle text-secondary hover:border-border-strong hover:text-primary'
                    }`}
                  >
                    {isSelected && <Check className="w-3 h-3 text-primary" />}
                    <span>{company}</span>
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* 6. Availability Status */}
      <div className="space-y-3 pt-1 border-t border-border-subtle/60">
        <button
          type="button"
          onClick={() => toggleSection('availability')}
          className="min-h-11 w-full flex items-center justify-between text-xs font-bold text-primary uppercase tracking-wider cursor-pointer"
        >
          <span className="flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5 text-secondary" />
            Availability Status
            {filters.availability.length > 0 && (
              <span className="px-1.5 py-0.5 rounded-full bg-surface-raised text-secondary text-xs font-mono font-bold border border-border-strong">
                {filters.availability.length}
              </span>
            )}
          </span>
          {expandedSections.availability ? (
            <ChevronUp className="w-3.5 h-3.5 text-secondary" />
          ) : (
            <ChevronDown className="w-3.5 h-3.5 text-secondary" />
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
                  className={`min-h-11 w-full px-3 py-2 rounded-[10px] text-xs flex items-center justify-between border transition-all cursor-pointer ${
                    isSelected
                      ? 'bg-surface-raised border-border-strong text-primary font-semibold'
                      : 'bg-canvas/60 border-border-subtle text-secondary hover:border-border-strong hover:text-primary'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ring-2 ${dotColor}`} />
                    <span>{status}</span>
                  </div>
                  {isSelected && <Check className="w-3.5 h-3.5 text-primary" />}
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
