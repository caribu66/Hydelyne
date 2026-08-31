import React from 'react';
import { UserProfile, FilterState } from '../types';
import { CertificationBadge } from './CertificationBadge';
import {
  MapPin,
  Building2,
  GraduationCap,
  ArrowUpRight,
  Bookmark,
  BookmarkCheck,
  Star,
  CheckCircle2,
  Scale,
  Send,
} from 'lucide-react';

interface ProfileListViewProps {
  profiles: UserProfile[];
  activeFilters: FilterState;
  onSelect: (profile: UserProfile) => void;
  bookmarkedIds: Set<string> | string[];
  onToggleBookmark: (profileId: string) => void;
  compareIds?: string[];
  onToggleCompare?: (profile: UserProfile) => void;
  onRequestMobilization?: (profile: UserProfile) => void;
}

export const ProfileListView: React.FC<ProfileListViewProps> = ({
  profiles,
  activeFilters,
  onSelect,
  bookmarkedIds,
  onToggleBookmark,
  compareIds = [],
  onToggleCompare,
  onRequestMobilization,
}) => {
  const isBookmarkedCheck = (id: string) => {
    if (!bookmarkedIds) return false;
    if (Array.isArray(bookmarkedIds)) return bookmarkedIds.includes(id);
    if (typeof (bookmarkedIds as unknown as { has?: (val: string) => boolean }).has === 'function') {
      return (bookmarkedIds as unknown as { has: (val: string) => boolean }).has(id);
    }
    return false;
  };

  return (
    <div
      id="profile-list-view"
      className="bg-zinc-900/70 border border-zinc-800 rounded-2xl overflow-hidden shadow-xl divide-y divide-zinc-800/80"
    >
      {profiles.map((profile) => {
        const isBookmarked = isBookmarkedCheck(profile.id);
        const isCompared = compareIds.includes(profile.id);
        const isAvailableNow = profile.availability?.toLowerCase().includes('immediately');

        return (
          <div
            key={profile.id}
            id={`list-row-${profile.id}`}
            onClick={() => onSelect(profile)}
            className="p-4 sm:p-5 hover:bg-zinc-800/50 transition-colors flex flex-col md:flex-row items-start md:items-center justify-between gap-4 cursor-pointer group"
          >
            <div className="flex items-start gap-4 min-w-0 flex-1">
              {/* Compare toggle */}
              {onToggleCompare && (
                <div
                  className="pt-1 shrink-0"
                  onClick={(e) => e.stopPropagation()}
                >
                  <input
                    type="checkbox"
                    checked={isCompared}
                    onChange={() => onToggleCompare(profile)}
                    className="rounded border-zinc-700 bg-zinc-800 text-blue-500 accent-blue-500 cursor-pointer"
                    title="Select to compare"
                  />
                </div>
              )}

              <div className="relative shrink-0">
                <img
                  src={profile.avatar}
                  alt={profile.name}
                  referrerPolicy="no-referrer"
                  className="w-12 h-12 rounded-xl object-cover border border-zinc-700/60 transition-all"
                />
                {isAvailableNow && (
                  <span className="absolute -bottom-0.5 -right-0.5 w-3 h-3 bg-emerald-500 border-2 border-zinc-900 rounded-full" />
                )}
              </div>

              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <h3 className="font-bold text-zinc-100 text-sm sm:text-base group-hover:text-blue-400 transition-colors truncate">
                    {profile.name}
                  </h3>
                  <span className="text-xs text-zinc-300 font-medium">
                    {profile.title}
                  </span>
                  <span
                    className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold border ${
                      isAvailableNow
                        ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                        : 'bg-zinc-800 text-zinc-300 border-zinc-700'
                    }`}
                  >
                    <span className={`w-1 h-1 rounded-full ${isAvailableNow ? 'bg-emerald-400' : 'bg-zinc-500'}`} />
                    {profile.availability}
                  </span>
                </div>

                <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-1 text-xs text-zinc-400">
                  <span className="font-medium text-blue-400">
                    {profile.department}
                  </span>
                  <span>•</span>
                  <span className="flex items-center gap-1">
                    <MapPin className="w-3.5 h-3.5 text-zinc-400" />
                    {profile.location}
                  </span>
                  <span>•</span>
                  <span className="flex items-center gap-1 font-mono">
                    <GraduationCap className="w-3.5 h-3.5 text-zinc-400" />
                    {profile.yearsOfExperience}y exp
                  </span>
                  {profile.rating && (
                    <span className="flex items-center gap-1 font-bold text-amber-400">
                      <Star className="w-3 h-3 fill-amber-400 text-amber-400" />
                      {profile.rating.toFixed(1)}
                    </span>
                  )}
                </div>

                {/* Certifications & Skills row */}
                <div className="flex flex-wrap items-center gap-1.5 mt-2">
                  {profile.certifications?.slice(0, 2).map((cert) => (
                    <div key={cert} onClick={(e) => e.stopPropagation()}>
                      <CertificationBadge certification={cert} size="sm" />
                    </div>
                  ))}
                  {profile.skills.slice(0, 4).map((skill) => {
                    const isMatch = activeFilters.selectedSkills.some(
                      (sel) => sel.toLowerCase() === skill.toLowerCase()
                    );
                    return (
                      <span
                        key={skill}
                        className={`px-2 py-0.5 text-[10px] font-medium rounded-md border ${
                          isMatch
                            ? 'bg-blue-950/80 border-blue-700 text-blue-200 font-bold'
                            : 'bg-zinc-950/60 border-zinc-800 text-zinc-400'
                        }`}
                      >
                        {skill}
                      </span>
                    );
                  })}
                  {profile.skills.length > 4 && (
                    <span className="text-[10px] text-zinc-400 font-mono self-center">
                      +{profile.skills.length - 4} more
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* Right Action buttons */}
            <div className="flex items-center gap-2 self-end md:self-center shrink-0">
              <div className="text-right hidden sm:block mr-2">
                <div className="text-xs font-bold font-mono text-zinc-100">
                  {profile.dayRate ? `£${profile.dayRate}/d` : 'Negotiable'}
                </div>
                <div className="text-[10px] text-zinc-500 font-mono">Day Rate</div>
              </div>

              {onRequestMobilization && (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    onRequestMobilization(profile);
                  }}
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl bg-zinc-800 hover:bg-zinc-750 text-zinc-300 hover:text-white font-medium text-xs transition-colors cursor-pointer"
                  title="Inquire Mobilization"
                >
                  <Send className="w-3 h-3 text-blue-400" />
                  <span className="hidden lg:inline">Inquire</span>
                </button>
              )}

              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onToggleBookmark(profile.id);
                }}
                className={`p-2 rounded-xl border transition-colors cursor-pointer ${
                  isBookmarked
                    ? 'bg-blue-600 text-white border-blue-500'
                    : 'bg-zinc-800/80 border-zinc-700/60 text-zinc-400 hover:text-zinc-200'
                }`}
                title="Bookmark"
              >
                {isBookmarked ? (
                  <BookmarkCheck className="w-4 h-4 text-white fill-white" />
                ) : (
                  <Bookmark className="w-4 h-4" />
                )}
              </button>

              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onSelect(profile);
                }}
                className="inline-flex items-center gap-1 px-3.5 py-1.5 rounded-xl bg-zinc-800 hover:bg-blue-600 text-white font-semibold text-xs transition-colors cursor-pointer shadow-xs"
              >
                <span>View</span>
                <ArrowUpRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
};
