import React from 'react';
import { UserProfile, FilterState } from '../types';
import { CertificationBadge } from './CertificationBadge';
import {
  MapPin,
  Building2,
  GraduationCap,
  Sparkles,
  ExternalLink,
  Mail,
  Bookmark,
  BookmarkCheck,
  Star,
  CheckCircle2,
  ArrowUpRight,
  ShieldCheck,
  Scale,
  Send,
} from 'lucide-react';

interface ProfileCardProps {
  profile: UserProfile;
  activeFilters: FilterState;
  onSelect: (profile: UserProfile) => void;
  isBookmarked: boolean;
  onToggleBookmark: (profileId: string) => void;
  isCompared?: boolean;
  onToggleCompare?: (profile: UserProfile) => void;
  onRequestMobilization?: (profile: UserProfile) => void;
}

export const ProfileCard: React.FC<ProfileCardProps> = ({
  profile,
  activeFilters,
  onSelect,
  isBookmarked,
  onToggleBookmark,
  isCompared = false,
  onToggleCompare,
  onRequestMobilization,
}) => {
  const isAvailableNow = profile.availability?.toLowerCase().includes('immediately');

  return (
    <div
      id={`profile-card-${profile.id}`}
      className="group relative bg-zinc-900/70 hover:bg-zinc-900 border border-zinc-800 hover:border-zinc-700 rounded-2xl p-5 transition-colors duration-150 flex flex-col justify-between"
    >
      <div>
        {/* Top Header: Avatar, Name, Role, Actions */}
        <div className="flex items-start justify-between gap-3 mb-3.5">
          <div className="flex items-start gap-3.5 min-w-0">
            <div className="relative shrink-0">
              <img
                src={profile.avatar}
                alt={profile.name}
                referrerPolicy="no-referrer"
                className="w-13 h-13 rounded-2xl object-cover border border-zinc-700/60 transition-all"
              />
              {isAvailableNow && (
                <span className="absolute -bottom-0.5 -right-0.5 w-3.5 h-3.5 bg-emerald-500 border-2 border-zinc-900 rounded-full" />
              )}
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-1.5">
                <h3
                  onClick={() => onSelect(profile)}
                  className="font-bold text-zinc-100 text-base group-hover:text-blue-400 transition-colors cursor-pointer truncate"
                >
                  {profile.name}
                </h3>
                {profile.isHighlyRecommended && (
                  <span title="Verified Hydenlyne Specialist">
                    <CheckCircle2 className="w-4 h-4 text-blue-400 fill-blue-400/20 shrink-0" />
                  </span>
                )}
              </div>
              <p className="text-xs font-medium text-zinc-300 line-clamp-1">{profile.title}</p>
              <div className="flex items-center gap-2 mt-0.5 text-xs text-zinc-400">
                <span className="text-blue-400 font-medium">{profile.department}</span>
                <span>•</span>
                <span className="truncate">{profile.location}</span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-1 shrink-0">
            {onToggleCompare && (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onToggleCompare(profile);
                }}
                className={`p-2 rounded-xl transition-colors cursor-pointer ${
                  isCompared
                    ? 'bg-blue-950 border border-blue-700 text-blue-300'
                    : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800'
                }`}
                title={isCompared ? 'Remove from comparison' : 'Add to compare'}
              >
                <Scale className="w-4 h-4" />
              </button>
            )}

            <button
              type="button"
              id={`bookmark-btn-${profile.id}`}
              onClick={(e) => {
                e.stopPropagation();
                onToggleBookmark(profile.id);
              }}
              className={`p-2 rounded-xl transition-colors cursor-pointer ${
                isBookmarked
                  ? 'bg-blue-600 text-white border border-blue-500'
                  : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800'
              }`}
              title={isBookmarked ? 'Remove bookmark' : 'Bookmark candidate'}
            >
              {isBookmarked ? (
                <BookmarkCheck className="w-4 h-4 text-white fill-white" />
              ) : (
                <Bookmark className="w-4 h-4" />
              )}
            </button>
          </div>
        </div>

        {/* Status & Highlights Row */}
        <div className="flex flex-wrap items-center gap-1.5 mb-3 text-xs">
          <span
            className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold border ${
              isAvailableNow
                ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                : 'bg-zinc-800/80 text-zinc-300 border-zinc-700/50'
            }`}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${isAvailableNow ? 'bg-emerald-400' : 'bg-zinc-500'}`} />
            {profile.availability}
          </span>

          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-zinc-800/80 text-zinc-200 font-semibold font-mono border border-zinc-700/50">
            <GraduationCap className="w-3 h-3 text-zinc-400" />
            {profile.yearsOfExperience}y exp
          </span>

          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full bg-blue-950/40 text-blue-300 font-semibold font-mono border border-blue-800/40">
            {profile.dayRate ? `£${profile.dayRate}/d` : 'Negotiable'}
          </span>
        </div>

        {/* Bio summary */}
        <p className="text-xs text-zinc-400 leading-relaxed line-clamp-2 mb-3">
          {profile.bio}
        </p>

        {/* Offshore Certifications Row with Tooltips */}
        {profile.certifications && profile.certifications.length > 0 && (
          <div className="mb-3">
            <div className="flex flex-wrap gap-1">
              {profile.certifications.slice(0, 3).map((cert) => (
                <CertificationBadge key={cert} certification={cert} size="sm" />
              ))}
              {profile.certifications.length > 3 && (
                <span className="px-1.5 py-0.5 text-[10px] font-mono text-zinc-500 self-center">
                  +{profile.certifications.length - 3}
                </span>
              )}
            </div>
          </div>
        )}

        {/* Skills Tag Matrix */}
        <div className="space-y-1 mb-4">
          <div className="flex flex-wrap gap-1.5">
            {profile.skills.slice(0, 4).map((skill) => {
              const isMatch = activeFilters.selectedSkills.some(
                (sel) => sel.toLowerCase() === skill.toLowerCase()
              );
              return (
                <span
                  key={skill}
                  className={`px-2 py-0.5 text-[11px] font-medium rounded-lg border transition-all ${
                    isMatch
                      ? 'bg-blue-950/80 border-blue-700 text-blue-200 font-semibold'
                      : 'bg-zinc-950/60 border-zinc-800 text-zinc-400'
                  }`}
                >
                  {isMatch && <span className="text-blue-400 mr-1">★</span>}
                  {skill}
                </span>
              );
            })}
            {profile.skills.length > 4 && (
              <span className="px-1.5 py-0.5 text-[11px] font-mono text-zinc-500 self-center">
                +{profile.skills.length - 4}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Card Footer: Rating & Inspection Action */}
      <div className="pt-3.5 border-t border-zinc-800/80 flex items-center justify-between">
        <div className="flex items-center gap-3 text-xs">
          <span className="flex items-center gap-1 font-bold text-zinc-200">
            <Star className="w-3.5 h-3.5 text-amber-400 fill-amber-400" />
            {profile.rating ? profile.rating.toFixed(1) : '4.9'}
          </span>
          <span className="text-zinc-500 font-mono text-[11px]">
            {profile.surveyTypes?.[0] || 'Offshore Marine'}
          </span>
        </div>

        <div className="flex items-center gap-2">
          {onRequestMobilization && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onRequestMobilization(profile);
              }}
              className="inline-flex items-center gap-1 text-xs font-medium text-zinc-300 hover:text-white bg-zinc-800 hover:bg-zinc-750 px-2.5 py-1.5 rounded-xl transition-colors cursor-pointer"
              title="Request Mobilization"
            >
              <Send className="w-3 h-3 text-blue-400" />
              <span>Inquire</span>
            </button>
          )}

          <button
            type="button"
            id={`view-profile-${profile.id}`}
            onClick={() => onSelect(profile)}
            className="inline-flex items-center gap-1 text-xs font-semibold text-white bg-zinc-800 hover:bg-blue-600 px-3 py-1.5 rounded-xl transition-all duration-150 cursor-pointer shadow-xs"
          >
            <span>Inspect</span>
            <ArrowUpRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
          </button>
        </div>
      </div>
    </div>
  );
};
