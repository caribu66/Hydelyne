import React, { useState, useMemo } from 'react';
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
  Linkedin,
  BadgeCheck,
  ArrowUpRight,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Scale,
  Send,
  SlidersHorizontal,
  Eye,
} from 'lucide-react';

interface SpecialistTableViewProps {
  profiles: UserProfile[];
  searchQuery: string;
  selectedId: string | null;
  onSelectProfile: (profile: UserProfile) => void;
  isBookmarked: (id: string) => boolean;
  onToggleBookmark: (id: string, e?: React.MouseEvent) => void;
  onShowToast: (msg: string) => void;
  compareIds?: string[];
  onToggleCompare?: (profile: UserProfile) => void;
  onRequestMobilization?: (profile: UserProfile) => void;
}

type SortField = 'name' | 'department' | 'experience' | 'dayRate' | 'rating' | 'availability';
type SortDirection = 'asc' | 'desc';

interface ColumnVisibility {
  discipline: boolean;
  mobilization: boolean;
  location: boolean;
  experience: boolean;
  certifications: boolean;
  dayRate: boolean;
  rating: boolean;
}

export const SpecialistTableView: React.FC<SpecialistTableViewProps> = ({
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
      let valA: any = a[sortField === 'experience' ? 'yearsOfExperience' : sortField];
      let valB: any = b[sortField === 'experience' ? 'yearsOfExperience' : sortField];

      if (typeof valA === 'string') {
        valA = valA.toLowerCase();
        valB = (valB || '').toLowerCase();
        return sortDirection === 'asc' ? valA.localeCompare(valB) : valB.localeCompare(valA);
      }
      valA = valA || 0;
      valB = valB || 0;
      return sortDirection === 'asc' ? valA - valB : valB - valA;
    });
  }, [profiles, sortField, sortDirection]);

  const handleCopyEmail = (profile: UserProfile, e: React.MouseEvent) => {
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
      <ArrowUp className="w-3 h-3 text-blue-400" />
    ) : (
      <ArrowDown className="w-3 h-3 text-blue-400" />
    );
  };

  return (
    <div className="w-full space-y-2">
      {/* Table Toolbar Controls */}
      <div className="flex items-center justify-between px-1 text-xs text-zinc-400">
        <div className="flex items-center gap-2">
          <span>Showing {sortedProfiles.length} specialists in table matrix</span>
          {sortField && (
            <span className="text-[11px] font-mono text-blue-400">
              (Sorted by {sortField} {sortDirection})
            </span>
          )}
        </div>

        <div className="relative">
          <button
            type="button"
            onClick={() => setShowColSettings(!showColSettings)}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-xl bg-zinc-900 border border-zinc-800 hover:border-zinc-700 text-zinc-300 text-xs font-medium cursor-pointer transition-colors"
          >
            <SlidersHorizontal className="w-3 h-3 text-zinc-400" />
            <span>Columns</span>
          </button>

          {showColSettings && (
            <div className="absolute right-0 top-full mt-1.5 z-40 w-48 p-2.5 rounded-xl bg-zinc-900 border border-zinc-750 shadow-2xl space-y-1.5 text-xs text-zinc-200">
              <span className="font-semibold text-[11px] text-zinc-400 uppercase font-mono block pb-1 border-b border-zinc-800">
                Toggle Columns
              </span>
              {Object.keys(colVisibility).map((key) => {
                const colKey = key as keyof ColumnVisibility;
                return (
                  <label key={colKey} className="flex items-center gap-2 cursor-pointer py-0.5 hover:text-white">
                    <input
                      type="checkbox"
                      checked={colVisibility[colKey]}
                      onChange={(e) =>
                        setColVisibility((prev) => ({ ...prev, [colKey]: e.target.checked }))
                      }
                      className="rounded border-zinc-700 bg-zinc-800 text-blue-500 accent-blue-500"
                    />
                    <span className="capitalize">{colKey.replace(/([A-Z])/g, ' $1')}</span>
                  </label>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Main Table Structure */}
      <div className="w-full overflow-x-auto border border-zinc-800 rounded-2xl bg-zinc-900/40 shadow-xs">
        <table className="w-full text-left text-xs text-zinc-300 border-collapse">
          <thead className="bg-zinc-950/80 text-[11px] text-zinc-400 uppercase font-semibold border-b border-zinc-800 tracking-wider select-none">
            <tr>
              {onToggleCompare && <th className="py-3 px-3 w-10 text-center">Cmp</th>}
              <th
                onClick={() => handleSort('name')}
                className="py-3 px-4 cursor-pointer hover:text-white group transition-colors"
              >
                <div className="flex items-center gap-1.5">
                  <span>Specialist</span>
                  {renderSortIndicator('name')}
                </div>
              </th>

              {colVisibility.discipline && (
                <th
                  onClick={() => handleSort('department')}
                  className="py-3 px-3 cursor-pointer hover:text-white group transition-colors"
                >
                  <div className="flex items-center gap-1.5">
                    <span>Discipline</span>
                    {renderSortIndicator('department')}
                  </div>
                </th>
              )}

              {colVisibility.mobilization && (
                <th
                  onClick={() => handleSort('availability')}
                  className="py-3 px-3 cursor-pointer hover:text-white group transition-colors"
                >
                  <div className="flex items-center gap-1.5">
                    <span>Mobilization</span>
                    {renderSortIndicator('availability')}
                  </div>
                </th>
              )}

              {colVisibility.location && <th className="py-3 px-3">Location</th>}

              {colVisibility.experience && (
                <th
                  onClick={() => handleSort('experience')}
                  className="py-3 px-3 cursor-pointer hover:text-white group transition-colors"
                >
                  <div className="flex items-center gap-1.5">
                    <span>Exp</span>
                    {renderSortIndicator('experience')}
                  </div>
                </th>
              )}

              {colVisibility.certifications && <th className="py-3 px-3">Accreditations</th>}

              {colVisibility.dayRate && (
                <th
                  onClick={() => handleSort('dayRate')}
                  className="py-3 px-3 cursor-pointer hover:text-white group transition-colors"
                >
                  <div className="flex items-center gap-1.5">
                    <span>Day Rate</span>
                    {renderSortIndicator('dayRate')}
                  </div>
                </th>
              )}

              {colVisibility.rating && (
                <th
                  onClick={() => handleSort('rating')}
                  className="py-3 px-3 cursor-pointer hover:text-white group transition-colors"
                >
                  <div className="flex items-center gap-1.5">
                    <span>Rating</span>
                    {renderSortIndicator('rating')}
                  </div>
                </th>
              )}

              <th className="py-3 px-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/60">
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
                        ? 'bg-zinc-800/80 hover:bg-zinc-800'
                        : 'hover:bg-zinc-800/40'
                    }`}
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
                          className="rounded border-zinc-700 bg-zinc-800 text-blue-500 accent-blue-500 cursor-pointer"
                          title="Select to compare"
                        />
                      </td>
                    )}

                    {/* Specialist Name & Title */}
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-3">
                        <img
                          src={profile.avatar}
                          alt={profile.name}
                          className="w-8 h-8 rounded-xl object-cover border border-zinc-700 shrink-0"
                        />
                        <div className="min-w-0">
                          <div className="flex items-center gap-1.5 font-medium text-zinc-100 group-hover:text-blue-400 transition-colors">
                            <span className="truncate max-w-[170px]">
                              <HighlightText text={profile.name} highlight={searchQuery} />
                            </span>
                            {profile.isHighlyRecommended && (
                              <BadgeCheck className="w-3.5 h-3.5 text-blue-400 shrink-0" />
                            )}
                          </div>
                          <p className="text-[11px] text-zinc-400 truncate max-w-[200px]">
                            <HighlightText text={profile.title} highlight={searchQuery} />
                          </p>
                        </div>
                      </div>
                    </td>

                    {/* Discipline / Department */}
                    {colVisibility.discipline && (
                      <td className="py-3 px-3 whitespace-nowrap">
                        <span className="px-2 py-0.5 rounded-lg text-[11px] font-medium bg-zinc-800 border border-zinc-700/60 text-zinc-300">
                          {profile.department}
                        </span>
                      </td>
                    )}

                    {/* Mobilization Status */}
                    {colVisibility.mobilization && (
                      <td className="py-3 px-3 whitespace-nowrap">
                        <span
                          className={`inline-flex items-center gap-1.5 text-[11px] font-medium ${
                            isAvailableNow ? 'text-emerald-400' : 'text-zinc-400'
                          }`}
                        >
                          <span
                            className={`w-1.5 h-1.5 rounded-full ${
                              isAvailableNow ? 'bg-emerald-400' : 'bg-zinc-600'
                            }`}
                          />
                          <span>{profile.availability}</span>
                        </span>
                      </td>
                    )}

                    {/* Location */}
                    {colVisibility.location && (
                      <td className="py-3 px-3 whitespace-nowrap text-zinc-400">
                        <div className="flex items-center gap-1">
                          <MapPin className="w-3 h-3 text-zinc-500 shrink-0" />
                          <span className="truncate max-w-[130px]">{profile.location}</span>
                        </div>
                      </td>
                    )}

                    {/* Offshore Exp */}
                    {colVisibility.experience && (
                      <td className="py-3 px-3 whitespace-nowrap font-mono text-zinc-200">
                        <span className="font-semibold text-zinc-100">{profile.yearsOfExperience}</span> yrs
                      </td>
                    )}

                    {/* Certifications with Tooltips */}
                    {colVisibility.certifications && (
                      <td className="py-3 px-3" onClick={(e) => e.stopPropagation()}>
                        <div className="flex flex-wrap gap-1 max-w-[220px]">
                          {profile.certifications && profile.certifications.length > 0 ? (
                            profile.certifications.slice(0, 2).map((cert) => (
                              <CertificationBadge key={cert} certification={cert} size="sm" />
                            ))
                          ) : (
                            <span className="text-zinc-500 font-mono text-[10px]">—</span>
                          )}
                          {profile.certifications && profile.certifications.length > 2 && (
                            <span className="text-[10px] text-zinc-500 font-mono self-center">
                              +{profile.certifications.length - 2}
                            </span>
                          )}
                        </div>
                      </td>
                    )}

                    {/* Day Rate */}
                    {colVisibility.dayRate && (
                      <td className="py-3 px-3 whitespace-nowrap font-mono font-medium text-zinc-100">
                        {profile.dayRate ? `£${profile.dayRate}/d` : 'Negotiable'}
                      </td>
                    )}

                    {/* Rating */}
                    {colVisibility.rating && (
                      <td className="py-3 px-3 whitespace-nowrap font-mono text-amber-400">
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
                            className="p-1.5 rounded-lg text-zinc-400 hover:text-blue-400 hover:bg-zinc-800 transition-colors"
                            title="Inquire Mobilization"
                          >
                            <Send className="w-3.5 h-3.5" />
                          </button>
                        )}

                        <button
                          type="button"
                          onClick={(e) => handleCopyEmail(profile, e)}
                          className="p-1.5 rounded-lg text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 transition-colors"
                          title="Copy Email"
                        >
                          {copiedId === profile.id ? (
                            <Check className="w-3.5 h-3.5 text-emerald-400" />
                          ) : (
                            <Copy className="w-3.5 h-3.5" />
                          )}
                        </button>

                        <button
                          type="button"
                          onClick={(e) => onToggleBookmark(profile.id, e)}
                          className={`p-1.5 rounded-lg transition-colors cursor-pointer ${
                            isProfileBookmarked ? 'text-blue-400' : 'text-zinc-500 hover:text-zinc-300'
                          }`}
                          title={isProfileBookmarked ? 'Shortlisted' : 'Shortlist'}
                        >
                          {isProfileBookmarked ? (
                            <BookmarkCheck className="w-3.5 h-3.5 fill-blue-400" />
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
