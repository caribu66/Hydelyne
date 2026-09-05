import { FC, useState, useMemo, MouseEvent } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { UserProfile } from '../types';
import { HighlightText } from './HighlightText';
import { CertificationBadge } from './CertificationBadge';
import {
  MapPin,
  Bookmark,
  BookmarkCheck,
  Copy,
  Check,
  BadgeCheck,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Send,
  SlidersHorizontal,
} from 'lucide-react';

interface SpecialistTableViewProps {
  profiles: UserProfile[];
  searchQuery: string;
  selectedId: string | null;
  onSelectProfile: (profile: UserProfile) => void;
  isBookmarked: (id: string) => boolean;
  onToggleBookmark: (id: string, e?: MouseEvent) => void;
  onShowToast: (msg: string) => void;
  compareIds?: string[];
  onToggleCompare?: (profile: UserProfile) => void;
  onRequestMobilization?: (profile: UserProfile) => void;
}

type SortField = 'name' | 'department' | 'experience' | 'dayRate' | 'rating' | 'availability';
type SortDirection = 'asc' | 'desc';

function sortValue(profile: UserProfile, field: SortField): string | number {
  switch (field) {
    case 'name':
      return profile.name;
    case 'department':
      return profile.department;
    case 'experience':
      return profile.yearsOfExperience;
    case 'dayRate':
      return profile.dayRate ?? 0;
    case 'rating':
      return profile.rating ?? 0;
    case 'availability':
      return profile.availability;
  }
}

interface ColumnVisibility {
  discipline: boolean;
  mobilization: boolean;
  location: boolean;
  experience: boolean;
  certifications: boolean;
  dayRate: boolean;
  rating: boolean;
}

export const SpecialistTableView: FC<SpecialistTableViewProps> = ({
  profiles,
  searchQuery,
  selectedId,
  onSelectProfile,
  isBookmarked,
  onToggleBookmark,
  onShowToast,
  compareIds = [],
  onToggleCompare,
  onRequestMobilization,
}) => {
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [sortField, setSortField] = useState<SortField | null>(null);
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');
  const [showColSettings, setShowColSettings] = useState(false);
  const [colVisibility, setColVisibility] = useState<ColumnVisibility>({
    discipline: true,
    mobilization: true,
    location: true,
    experience: true,
    certifications: true,
    dayRate: true,
    rating: true,
  });

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      if (sortDirection === 'asc') {
        setSortDirection('desc');
      } else {
        setSortField(null);
      }
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  const sortedProfiles = useMemo(() => {
    if (!sortField) return profiles;
    return [...profiles].sort((a, b) => {
      const valA = sortValue(a, sortField);
      const valB = sortValue(b, sortField);

      if (typeof valA === 'string') {
        const strA = valA.toLowerCase();
        const strB = String(valB).toLowerCase();
        return sortDirection === 'asc' ? strA.localeCompare(strB) : strB.localeCompare(strA);
      }
      const numB = typeof valB === 'number' ? valB : 0;
      return sortDirection === 'asc' ? valA - numB : numB - valA;
    });
  }, [profiles, sortField, sortDirection]);

  const handleCopyEmail = (profile: UserProfile, e: MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard?.writeText(profile.email);
    setCopiedId(profile.id);
    onShowToast(`Copied ${profile.email}`);
    setTimeout(() => setCopiedId(null), 1800);
  };

  const renderSortIndicator = (field: SortField) => {
    if (sortField !== field) {
      return <ArrowUpDown className="w-3 h-3 opacity-40 group-hover:opacity-100" />;
    }
    return sortDirection === 'asc' ? (
      <ArrowUp className="w-3 h-3 text-accent" />
    ) : (
      <ArrowDown className="w-3 h-3 text-accent" />
    );
  };

  return (
    <div className="w-full space-y-2.5">
      {/* Table Toolbar Controls */}
      <div className="flex items-center justify-between px-1 text-xs text-secondary">
        <div className="flex items-center gap-2">
          <span>Showing <strong className="font-mono text-primary font-semibold">{sortedProfiles.length}</strong> specialists in matrix</span>
          {sortField && (
            <span className="font-mono text-xs text-muted">
              · sorted by <span className="text-secondary font-medium">{sortField}</span> ({sortDirection})
            </span>
          )}
        </div>

        <div className="relative">
          <button
            type="button"
            onClick={() => setShowColSettings(!showColSettings)}
            aria-expanded={showColSettings}
            aria-label="Toggle visible matrix columns"
            className="inline-flex min-h-9 items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface border border-border-subtle hover:border-border-strong hover:bg-surface-raised text-secondary hover:text-primary text-xs font-medium cursor-pointer transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          >
            <SlidersHorizontal className="w-3.5 h-3.5 text-secondary" />
            <span>Columns</span>
          </button>

          {showColSettings && (
            <div className="absolute right-0 top-full mt-1.5 z-40 w-52 p-3 rounded-[14px] bg-surface border border-border-strong shadow-2xl space-y-2 text-xs text-primary backdrop-blur-xs">
              <span className="font-semibold text-xs text-secondary uppercase font-mono block pb-1.5 border-b border-border-subtle">
                Toggle Columns
              </span>
              <div className="space-y-1">
                {Object.keys(colVisibility).map((key) => {
                  const colKey = key as keyof ColumnVisibility;
                  return (
                    <label key={colKey} className="flex items-center gap-2 cursor-pointer py-1 px-1 rounded-md hover:bg-surface-raised hover:text-primary transition-colors select-none">
                      <input
                        type="checkbox"
                        checked={colVisibility[colKey]}
                        onChange={(e) =>
                          setColVisibility((prev) => ({ ...prev, [colKey]: e.target.checked }))
                        }
                        className="rounded border-border-strong bg-surface-raised text-action focus:ring-focus accent-current cursor-pointer"
                      />
                      <span className="capitalize text-secondary">{colKey.replace(/([A-Z])/g, ' $1')}</span>
                    </label>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Main Table Structure */}
      <div className="scan-matrix-scroll w-full max-h-[min(760px,calc(100vh-250px))] overflow-auto border border-border-subtle rounded-[14px] bg-surface/40 shadow-xs">
        <table className="w-full text-left text-xs text-secondary border-collapse">
          <caption className="sr-only">Contractor screening matrix</caption>
          <thead className="sticky top-0 z-10 bg-canvas/95 text-xs text-secondary uppercase font-semibold border-b border-border-subtle tracking-wider select-none backdrop-blur-sm">
            <tr>
              {onToggleCompare && <th className="py-3 px-3 w-10 text-center">Cmp</th>}
              <th aria-sort={sortField === 'name' ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none'} className="py-3 px-4">
                <button type="button" onClick={() => handleSort('name')} className="flex items-center gap-1.5 cursor-pointer hover:text-primary group transition-colors">
                  <span>Contractor</span>
                  {renderSortIndicator('name')}
                </button>
              </th>

              {colVisibility.discipline && (
                <th aria-sort={sortField === 'department' ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none'} className="py-3 px-3">
                  <button type="button" onClick={() => handleSort('department')} className="flex items-center gap-1.5 cursor-pointer hover:text-primary group transition-colors">
                    <span>Discipline</span>
                    {renderSortIndicator('department')}
                  </button>
                </th>
              )}

              {colVisibility.mobilization && (
                <th aria-sort={sortField === 'availability' ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none'} className="py-3 px-3">
                  <button type="button" onClick={() => handleSort('availability')} className="flex items-center gap-1.5 cursor-pointer hover:text-primary group transition-colors">
                    <span>Mobilization</span>
                    {renderSortIndicator('availability')}
                  </button>
                </th>
              )}

              {colVisibility.location && <th className="py-3 px-3">Location</th>}

              {colVisibility.experience && (
                <th aria-sort={sortField === 'experience' ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none'} className="py-3 px-3">
                  <button type="button" onClick={() => handleSort('experience')} className="flex items-center gap-1.5 cursor-pointer hover:text-primary group transition-colors">
                    <span>Exp</span>
                    {renderSortIndicator('experience')}
                  </button>
                </th>
              )}

              {colVisibility.certifications && <th className="py-3 px-3">Accreditations</th>}

              {colVisibility.dayRate && (
                <th aria-sort={sortField === 'dayRate' ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none'} className="py-3 px-3">
                  <button type="button" onClick={() => handleSort('dayRate')} className="flex items-center gap-1.5 cursor-pointer hover:text-primary group transition-colors">
                    <span>Day Rate</span>
                    {renderSortIndicator('dayRate')}
                  </button>
                </th>
              )}

              {colVisibility.rating && (
                <th aria-sort={sortField === 'rating' ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none'} className="py-3 px-3">
                  <button type="button" onClick={() => handleSort('rating')} className="flex items-center gap-1.5 cursor-pointer hover:text-primary group transition-colors">
                    <span>Rating</span>
                    {renderSortIndicator('rating')}
                  </button>
                </th>
              )}

              <th className="py-3 px-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border-subtle/80">
            <AnimatePresence mode="popLayout">
              {sortedProfiles.map((profile, index) => {
                const isSelected = selectedId === profile.id;
                const isProfileBookmarked = isBookmarked(profile.id);
                const isCompared = compareIds.includes(profile.id);
                const isAvailableNow = profile.availability?.toLowerCase().includes('immediately');

                return (
                  <motion.tr
                    layout
                    key={profile.id}
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, scale: 0.98 }}
                    transition={{ duration: 0.15, delay: Math.min(index * 0.02, 0.2) }}
                    onClick={() => onSelectProfile(profile)}
                    className={`group cursor-pointer transition-colors ${
                      isSelected
                        ? 'bg-surface-raised'
                        : 'hover:bg-surface-raised/50'
                    }`}
                    aria-selected={isSelected}
                    tabIndex={0}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault();
                        onSelectProfile(profile);
                      }
                    }}
                  >
                    {/* Compare Checkbox */}
                    {onToggleCompare && (
                      <td
                        className="py-3 px-3 text-center"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <input
                          type="checkbox"
                          checked={isCompared}
                          onChange={() => onToggleCompare(profile)}
                          className="rounded border-border-strong bg-surface-raised text-action focus:ring-focus accent-current cursor-pointer"
                          title="Select to compare"
                          aria-label={`Compare ${profile.name}`}
                        />
                      </td>
                    )}

                    {/* Specialist Name & Title */}
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-3">
                        <div className="relative shrink-0">
                          {profile.avatar ? (
                            <img
                              src={profile.avatar}
                              alt={profile.name}
                              referrerPolicy="no-referrer"
                              className="w-8 h-8 rounded-[10px] object-cover border border-border-subtle"
                              onError={(e) => {
                                e.currentTarget.style.display = 'none';
                                const fallback = e.currentTarget.nextElementSibling;
                                if (fallback) (fallback as HTMLElement).style.display = 'flex';
                              }}
                            />
                          ) : null}
                          <div
                            className={`w-8 h-8 rounded-[10px] bg-surface-raised border border-border-subtle items-center justify-center font-bold text-xs text-primary shrink-0 ${
                              profile.avatar ? 'hidden' : 'flex'
                            }`}
                          >
                            {profile.name
                              .split(' ')
                              .map((n) => n[0])
                              .join('')
                              .slice(0, 2)}
                          </div>
                          {isAvailableNow && (
                            <span
                              className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-positive border border-surface"
                              title="Available immediately"
                            />
                          )}
                        </div>
                        <div className="min-w-0">
                          <div className="flex items-center gap-1.5 font-medium text-primary group-hover:text-primary transition-colors">
                            <span className="truncate max-w-[170px]">
                              <HighlightText text={profile.name} query={searchQuery} />
                            </span>
                            {profile.isHighlyRecommended && (
                              <BadgeCheck className="w-3.5 h-3.5 text-accent shrink-0" />
                            )}
                          </div>
                          <p className="text-xs text-secondary truncate max-w-[200px]">
                            <HighlightText text={profile.title} query={searchQuery} />
                          </p>
                        </div>
                      </div>
                    </td>

                    {/* Discipline / Department */}
                    {colVisibility.discipline && (
                      <td className="py-3 px-3 whitespace-nowrap">
                        <span className="badge-accent px-2 py-0.5 rounded-md font-medium text-xs">
                          {profile.department}
                        </span>
                      </td>
                    )}

                    {/* Mobilization Status */}
                    {colVisibility.mobilization && (
                      <td className="py-3 px-3 whitespace-nowrap">
                        <span className={`px-2 py-0.5 rounded-md font-medium text-xs ${isAvailableNow ? 'badge-positive' : 'badge-neutral'}`}>
                          {profile.availability.replace('Available ', '')}
                        </span>
                      </td>
                    )}

                    {/* Location */}
                    {colVisibility.location && (
                      <td className="py-3 px-3 whitespace-nowrap text-secondary">
                        <div className="flex items-center gap-1">
                          <MapPin className="w-3 h-3 text-muted shrink-0" />
                          <span className="truncate max-w-[130px]">{profile.location.split(',')[0]}</span>
                        </div>
                      </td>
                    )}

                    {/* Offshore Exp */}
                    {colVisibility.experience && (
                      <td className="py-3 px-3 whitespace-nowrap font-mono text-secondary">
                        <span className="font-semibold text-primary">{profile.yearsOfExperience}</span>y exp
                      </td>
                    )}

                    {/* Certifications */}
                    {colVisibility.certifications && (
                      <td className="py-3 px-3" onClick={(e) => e.stopPropagation()}>
                        <div className="flex flex-wrap gap-1 max-w-[220px]">
                          {profile.certifications && profile.certifications.length > 0 ? (
                            profile.certifications.slice(0, 2).map((cert) => (
                              <CertificationBadge key={cert} certification={cert} size="sm" />
                            ))
                          ) : (
                            <span className="text-muted font-mono text-xs">—</span>
                          )}
                          {profile.certifications && profile.certifications.length > 2 && (
                            <span className="text-xs text-muted font-mono self-center">
                              +{profile.certifications.length - 2}
                            </span>
                          )}
                        </div>
                      </td>
                    )}

                    {/* Day Rate */}
                    {colVisibility.dayRate && (
                      <td className="py-3 px-3 whitespace-nowrap font-mono font-medium text-primary">
                        {profile.dayRate ? `£${profile.dayRate}/d` : 'Negotiable'}
                      </td>
                    )}

                    {/* Rating */}
                    {colVisibility.rating && (
                      <td className="py-3 px-3 whitespace-nowrap font-mono text-warning">
                        ★ {profile.rating ? profile.rating.toFixed(1) : '4.9'}
                      </td>
                    )}

                    {/* Actions Column */}
                    <td className="py-3 px-4 text-right whitespace-nowrap" onClick={(e) => e.stopPropagation()}>
                      <div className="flex items-center justify-end gap-1">
                        {onRequestMobilization && (
                          <button
                            type="button"
                            onClick={() => onRequestMobilization(profile)}
                            aria-label={`Request mobilization for ${profile.name}`}
                            className="inline-flex min-h-9 min-w-9 items-center justify-center rounded-lg text-secondary hover:text-primary hover:bg-surface-raised transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                            title="Request mobilization"
                          >
                            <Send className="w-3.5 h-3.5" />
                          </button>
                        )}

                        <button
                          type="button"
                          onClick={(e) => handleCopyEmail(profile, e)}
                          aria-label={`Copy ${profile.name} email address`}
                          className="inline-flex min-h-9 min-w-9 items-center justify-center rounded-lg text-secondary hover:text-primary hover:bg-surface-raised transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                          title="Copy Email"
                        >
                          {copiedId === profile.id ? (
                            <Check className="w-3.5 h-3.5 text-positive" />
                          ) : (
                            <Copy className="w-3.5 h-3.5" />
                          )}
                        </button>

                        <button
                          type="button"
                          onClick={(e) => onToggleBookmark(profile.id, e)}
                          aria-label={isProfileBookmarked ? `Remove ${profile.name} from shortlist` : `Save ${profile.name} to shortlist`}
                          className={`inline-flex min-h-9 min-w-9 items-center justify-center rounded-lg transition-colors cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-focus ${
                            isProfileBookmarked ? 'text-accent bg-accent-soft/40' : 'text-secondary hover:text-primary hover:bg-surface-raised'
                          }`}
                          title={isProfileBookmarked ? 'Shortlisted' : 'Shortlist'}
                        >
                          {isProfileBookmarked ? (
                            <BookmarkCheck className="w-3.5 h-3.5 fill-current" />
                          ) : (
                            <Bookmark className="w-3.5 h-3.5" />
                          )}
                        </button>
                      </div>
                    </td>
                  </motion.tr>
                );
              })}
            </AnimatePresence>
          </tbody>
        </table>
      </div>
    </div>
  );
};
