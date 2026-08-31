import React, { useState, useEffect } from 'react';
import { UserProfile, SpecialistDocument } from '../types';
import { CertificationBadge } from './CertificationBadge';
import { DocumentVault } from './DocumentVault';
import {
  X,
  MapPin,
  Mail,
  Bookmark,
  BookmarkCheck,
  Copy,
  Check,
  Linkedin,
  BadgeCheck,
  Compass,
  Building,
  GraduationCap,
  Calendar,
  ShieldCheck,
  Scale,
  Send,
  Printer,
  FileCheck,
} from 'lucide-react';

interface ProfileDetailModalProps {
  profile: UserProfile | null;
  onClose: () => void;
  isBookmarked: boolean;
  onToggleBookmark: (profileId: string) => void;
  onShowToast?: (message: string) => void;
  isCompared?: boolean;
  onToggleCompare?: (profile: UserProfile) => void;
  onRequestMobilization?: (profile: UserProfile) => void;
  onPrintDossier?: (profile: UserProfile) => void;
  documents?: SpecialistDocument[];
  onAddDocument?: (doc: Omit<SpecialistDocument, 'id' | 'uploadedAt'>) => void;
  onRemoveDocument?: (docId: string) => void;
}

export const ProfileDetailModal: React.FC<ProfileDetailModalProps> = ({
  profile,
  onClose,
  isBookmarked,
  onToggleBookmark,
  onShowToast,
  isCompared = false,
  onToggleCompare,
  onRequestMobilization,
  onPrintDossier,
  documents = [],
  onAddDocument,
  onRemoveDocument,
}) => {
  const [copiedEmail, setCopiedEmail] = useState(false);
  const [activeTab, setActiveTab] = useState<'profile' | 'documents'>('profile');

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  if (!profile) return null;

  const handleCopyEmail = () => {
    navigator.clipboard?.writeText(profile.email);
    setCopiedEmail(true);
    if (onShowToast) onShowToast(`Copied ${profile.email}`);
    setTimeout(() => setCopiedEmail(false), 2000);
  };

  const isAvailableNow = profile.availability?.toLowerCase().includes('immediately');

  return (
    <div
      className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-3 sm:p-4 animate-in fade-in duration-150"
      onClick={onClose}
    >
      <div
        className="w-full max-w-2xl bg-zinc-900 border border-zinc-800 rounded-2xl text-zinc-100 shadow-2xl animate-in zoom-in-95 duration-150 max-h-[92vh] flex flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="profile-modal-name"
      >
        {/* Header Hero Area */}
        <div className="p-5 sm:p-6 bg-zinc-950 border-b border-zinc-800">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-4 min-w-0">
              <div className="relative shrink-0">
                <img
                  src={profile.avatar}
                  alt={profile.name}
                  referrerPolicy="no-referrer"
                  className="w-16 h-16 rounded-2xl object-cover border border-zinc-700 shadow-md"
                />
                {isAvailableNow && (
                  <span
                    className="absolute -bottom-1 -right-1 w-4 h-4 rounded-full bg-emerald-500 border-2 border-zinc-900 shadow-xs"
                    title="Available for immediate deployment"
                  />
                )}
              </div>

              <div className="min-w-0 space-y-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <h2 id="profile-modal-name" className="text-lg font-bold text-zinc-100">
                    {profile.name}
                  </h2>
                  {profile.isHighlyRecommended && (
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-blue-950/80 border border-blue-800/60 text-xs text-blue-300 font-medium">
                      <BadgeCheck className="w-3.5 h-3.5 text-blue-400" />
                      <span>Verified Consultant</span>
                    </span>
                  )}
                </div>
                <p className="text-xs sm:text-sm text-zinc-300 font-medium">
                  {profile.title}
                </p>
                <div className="flex items-center gap-2 text-xs text-zinc-400 pt-0.5 flex-wrap">
                  <span className="flex items-center gap-1">
                    <MapPin className="w-3.5 h-3.5 text-zinc-400 shrink-0" />
                    <span>{profile.location}</span>
                  </span>
                  <span>•</span>
                  <span className="text-blue-400 font-medium">{profile.department}</span>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-1.5 shrink-0">
              {onToggleCompare && (
                <button
                  type="button"
                  onClick={() => onToggleCompare(profile)}
                  className={`p-2 rounded-xl border transition-colors cursor-pointer ${
                    isCompared
                      ? 'bg-blue-950/70 border-blue-700 text-blue-300'
                      : 'bg-zinc-800/80 border-zinc-700 text-zinc-400 hover:text-white'
                  }`}
                  title={isCompared ? 'Remove from compare' : 'Add to compare'}
                >
                  <Scale className="w-4 h-4" />
                </button>
              )}

              {onPrintDossier && (
                <button
                  type="button"
                  onClick={() => onPrintDossier(profile)}
                  className="p-2 rounded-xl bg-zinc-800/80 border border-zinc-700 text-zinc-400 hover:text-white transition-colors cursor-pointer"
                  title="Print candidate profile"
                >
                  <Printer className="w-4 h-4" />
                </button>
              )}

              <button
                type="button"
                onClick={() => onToggleBookmark(profile.id)}
                className={`p-2 rounded-xl border transition-colors cursor-pointer ${
                  isBookmarked
                    ? 'bg-blue-600 text-white border-blue-500'
                    : 'bg-zinc-800/80 border-zinc-700 text-zinc-400 hover:text-white'
                }`}
                title={isBookmarked ? 'Remove from shortlist' : 'Save to shortlist'}
              >
                {isBookmarked ? (
                  <BookmarkCheck className="w-4 h-4 fill-white" />
                ) : (
                  <Bookmark className="w-4 h-4" />
                )}
              </button>

              <button
                type="button"
                onClick={onClose}
                className="p-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200 transition-colors cursor-pointer"
                title="Close"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Quick Metrics Bar */}
          <div className="grid grid-cols-3 gap-3 mt-4 pt-3 border-t border-zinc-850">
            <div>
              <span className="text-[10px] text-zinc-400 block uppercase font-mono">Mobilization</span>
              <span
                className={`inline-flex items-center gap-1.5 text-xs font-semibold mt-0.5 ${
                  isAvailableNow ? 'text-emerald-400' : 'text-zinc-300'
                }`}
              >
                <span className={`w-2 h-2 rounded-full ${isAvailableNow ? 'bg-emerald-400' : 'bg-zinc-500'}`} />
                <span>{profile.availability}</span>
              </span>
            </div>

            <div>
              <span className="text-[10px] text-zinc-400 block uppercase font-mono">Day Rate</span>
              <span className="font-semibold text-xs text-emerald-400 block mt-0.5 font-mono">
                {profile.dayRate ? `£${profile.dayRate}/day` : 'Upon Request'}
              </span>
            </div>

            <div>
              <span className="text-[10px] text-zinc-400 block uppercase font-mono">Experience</span>
              <span className="font-semibold text-xs text-zinc-200 block mt-0.5 font-mono">
                {profile.yearsOfExperience} years
              </span>
            </div>
          </div>

          {/* Subtabs */}
          <div className="flex items-center gap-2 mt-4 pt-3 border-t border-zinc-800">
            <button
              type="button"
              onClick={() => setActiveTab('profile')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors cursor-pointer ${
                activeTab === 'profile'
                  ? 'bg-zinc-800 text-white shadow-xs'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              <span>Profile & History</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('documents')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors cursor-pointer flex items-center gap-1.5 ${
                activeTab === 'documents'
                  ? 'bg-blue-950/80 border border-blue-700 text-blue-200 shadow-xs'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              <FileCheck className="w-3.5 h-3.5 text-blue-400" />
              <span>Compliance Documents</span>
              <span className="px-1.5 py-0.2 rounded-full bg-blue-900/60 text-blue-300 font-mono text-[10px]">
                {documents.length}
              </span>
            </button>
          </div>
        </div>

        {/* Scrollable Body */}
        <div className="flex-1 overflow-y-auto p-5 sm:p-6 space-y-4 text-xs">
          {activeTab === 'documents' ? (
            <DocumentVault
              profile={profile}
              documents={documents}
              onAddDocument={(doc) => onAddDocument?.(doc)}
              onRemoveDocument={(docId) => onRemoveDocument?.(docId)}
              onShowToast={onShowToast || (() => {})}
            />
          ) : (
            <>
              {/* Bio Overview */}
              <div className="space-y-1.5">
                <h3 className="text-zinc-400 font-semibold uppercase tracking-wider text-[11px]">
                  Specialist Overview
                </h3>
                <p className="text-zinc-300 leading-relaxed">{profile.bio}</p>
              </div>

              {/* Survey Disciplines */}
              {profile.surveyTypes && profile.surveyTypes.length > 0 && (
                <div className="space-y-1.5">
                  <h3 className="text-zinc-400 font-semibold uppercase tracking-wider text-[11px] flex items-center gap-1.5">
                    <Compass className="w-3.5 h-3.5 text-blue-400" />
                    <span>Survey & Operations Disciplines</span>
                  </h3>
                  <div className="flex flex-wrap gap-1.5">
                    {profile.surveyTypes.map((type) => (
                      <span
                        key={type}
                        className="px-2.5 py-1 rounded-lg bg-blue-950/40 border border-blue-800/40 text-blue-200 font-medium text-xs"
                      >
                        {type}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Offshore Certifications with Tooltips */}
              {profile.certifications && profile.certifications.length > 0 && (
                <div className="space-y-1.5">
                  <h3 className="text-zinc-400 font-semibold uppercase tracking-wider text-[11px] flex items-center gap-1.5">
                    <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                    <span>Offshore Safety & Marine Tickets</span>
                  </h3>
                  <div className="flex flex-wrap gap-1.5">
                    {profile.certifications.map((cert) => (
                      <CertificationBadge key={cert} certification={cert} size="md" />
                    ))}
                  </div>
                </div>
              )}

              {/* Skills */}
              {profile.skills && profile.skills.length > 0 && (
                <div className="space-y-1.5">
                  <h3 className="text-zinc-400 font-semibold uppercase tracking-wider text-[11px]">
                    Skills & Equipment Competencies
                  </h3>
                  <div className="flex flex-wrap gap-1.5">
                    {profile.skills.map((skill) => (
                      <span
                        key={skill}
                        className="px-2.5 py-1 rounded-lg bg-zinc-800 text-zinc-200 border border-zinc-700/60 text-xs"
                      >
                        {skill}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Featured Projects */}
              {profile.featuredProjects && profile.featuredProjects.length > 0 && (
                <div className="space-y-1.5">
                  <h3 className="text-zinc-400 font-semibold uppercase tracking-wider text-[11px] flex items-center gap-1.5">
                    <Calendar className="w-3.5 h-3.5 text-purple-400" />
                    <span>Featured Campaigns & Surveys</span>
                  </h3>
                  <div className="space-y-1">
                    {profile.featuredProjects.map((project) => (
                      <div
                        key={project}
                        className="p-2 rounded-lg bg-zinc-950/70 border border-zinc-850 text-zinc-300 text-xs flex items-center gap-2"
                      >
                        <span className="w-1.5 h-1.5 rounded-full bg-blue-400 shrink-0" />
                        <span>{project}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Past Operators / Clients & Education */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
                {profile.pastCompanies && profile.pastCompanies.length > 0 && (
                  <div className="p-3 bg-zinc-950/60 rounded-xl border border-zinc-800/60 space-y-1.5">
                    <div className="text-zinc-400 font-semibold flex items-center gap-1.5">
                      <Building className="w-3.5 h-3.5 text-blue-400" />
                      <span>Past Operators & Clients</span>
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {profile.pastCompanies.map((comp) => (
                        <span
                          key={comp}
                          className="px-2 py-0.5 rounded bg-zinc-900 text-zinc-400 text-[11px] border border-zinc-800"
                        >
                          {comp}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {profile.education && (
                  <div className="p-3 bg-zinc-950/60 rounded-xl border border-zinc-800/60 space-y-1.5">
                    <div className="text-zinc-400 font-semibold flex items-center gap-1.5">
                      <GraduationCap className="w-3.5 h-3.5 text-amber-400" />
                      <span>Education & Academics</span>
                    </div>
                    <p className="text-zinc-300 text-xs">{profile.education}</p>
                  </div>
                )}
              </div>
            </>
          )}
        </div>

        {/* Modal Footer Actions */}
        <div className="p-4 sm:p-5 bg-zinc-950 border-t border-zinc-800 flex items-center justify-between gap-3">
          <div className="min-w-0">
            <span className="text-xs text-zinc-400 font-mono block truncate">{profile.email}</span>
            <span className="text-[10px] text-zinc-400">Hydenlyne Verified Specialist Network</span>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <a
              href={
                profile.linkedinUrl ||
                `https://www.linkedin.com/search/results/all/?keywords=${encodeURIComponent(
                  `${profile.name} Hydenlyne`
                )}`
              }
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-300 hover:text-white text-xs font-medium transition-colors cursor-pointer"
              title="Open LinkedIn Profile (new tab)"
            >
              <Linkedin className="w-3.5 h-3.5 text-[#0a66c2]" />
              <span className="hidden sm:inline">LinkedIn</span>
            </a>

            <button
              type="button"
              onClick={handleCopyEmail}
              className="px-3 py-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-medium flex items-center gap-1.5 transition-colors cursor-pointer"
            >
              {copiedEmail ? (
                <>
                  <Check className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Copied</span>
                </>
              ) : (
                <>
                  <Copy className="w-3.5 h-3.5" />
                  <span>Copy Email</span>
                </>
              )}
            </button>

            {onRequestMobilization ? (
              <button
                type="button"
                onClick={() => onRequestMobilization(profile)}
                className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer shadow-md"
              >
                <Send className="w-3.5 h-3.5" />
                <span>Mobilize Specialist</span>
              </button>
            ) : (
              <a
                href={`mailto:${profile.email}?subject=Hydenlyne%20Survey%20Deployment%20Inquiry%20-%20${encodeURIComponent(
                  profile.title
                )}`}
                className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer shadow-md"
              >
                <Mail className="w-3.5 h-3.5" />
                <span>Mobilize</span>
              </a>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
