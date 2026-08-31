import React, { useState } from 'react';
import { UserProfile, SpecialistDocument } from '../types';
import { HighlightText } from './HighlightText';
import { CertificationBadge } from './CertificationBadge';
import { DocumentVault } from './DocumentVault';
import {
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
  Maximize2,
  Minimize2,
} from 'lucide-react';

interface SpecialistDossierPaneProps {
  profile: UserProfile | null;
  searchQuery?: string;
  isBookmarked: boolean;
  onToggleBookmark: (id: string) => void;
  onShowToast: (msg: string) => void;
  isCompared?: boolean;
  onToggleCompare?: (profile: UserProfile) => void;
  onRequestMobilization?: (profile: UserProfile) => void;
  onPrintDossier?: (profile: UserProfile) => void;
  documents?: SpecialistDocument[];
  onAddDocument?: (doc: Omit<SpecialistDocument, 'id' | 'uploadedAt'>) => void;
  onRemoveDocument?: (docId: string) => void;
  isFocusMode?: boolean;
  onToggleFocusMode?: () => void;
}

export const SpecialistDossierPane: React.FC<SpecialistDossierPaneProps> = ({
  profile,
  searchQuery = '',
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
  isFocusMode = false,
  onToggleFocusMode,
}) => {
  const [copiedEmail, setCopiedEmail] = useState(false);
  const [activeTab, setActiveTab] = useState<'dossier' | 'vault'>('dossier');

  if (!profile) {
    return (
      <div className="h-full min-h-[460px] flex flex-col items-center justify-center p-8 text-center bg-zinc-900/30 border border-zinc-800/60 rounded-2xl">
        <div className="w-14 h-14 rounded-2xl bg-zinc-900 border border-zinc-800 flex items-center justify-center text-zinc-500 mb-3 shadow-inner">
          <Compass className="w-7 h-7 text-zinc-500" />
        </div>
        <h3 className="text-sm font-semibold text-zinc-300">No Specialist Selected</h3>
        <p className="text-xs text-zinc-500 max-w-xs mt-1">
          Select any crew member from the list or press <kbd className="px-1.5 py-0.5 rounded bg-zinc-800 border border-zinc-700 text-[10px] text-zinc-400 font-mono">↑</kbd> <kbd className="px-1.5 py-0.5 rounded bg-zinc-800 border border-zinc-700 text-[10px] text-zinc-400 font-mono">↓</kbd> to inspect their dossier and compliance documents in centered focus mode.
        </p>
      </div>
    );
  }

  const handleCopyEmail = () => {
    navigator.clipboard?.writeText(profile.email);
    setCopiedEmail(true);
    onShowToast(`Copied ${profile.email}`);
    setTimeout(() => setCopiedEmail(false), 2000);
  };

  const isAvailableNow = profile.availability?.toLowerCase().includes('immediately');

  return (
    <div
      className={`bg-zinc-900 border border-zinc-800 rounded-2xl text-zinc-100 flex flex-col overflow-hidden shadow-2xl transition-all duration-300 ${
        isFocusMode
          ? 'w-full max-w-4xl mx-auto ring-1 ring-blue-500/20 shadow-blue-950/20'
          : 'h-full'
      }`}
    >
      {/* Header Profile Section */}
      <div className={`border-b border-zinc-800 bg-zinc-950/60 ${isFocusMode ? 'p-6 sm:p-7' : 'p-5'}`}>
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-4 min-w-0">
            <div className="relative shrink-0">
              <img
                src={profile.avatar}
                alt={profile.name}
                referrerPolicy="no-referrer"
                className={`rounded-2xl object-cover border border-zinc-700/80 shadow-lg transition-all ${
                  isFocusMode ? 'w-18 h-18 sm:w-20 sm:h-20' : 'w-14 h-14'
                }`}
              />
              {isAvailableNow && (
                <span
                  className={`absolute -bottom-1 -right-1 rounded-full bg-emerald-500 border-2 border-zinc-950 shadow-xs ${
                    isFocusMode ? 'w-4 h-4' : 'w-3.5 h-3.5'
                  }`}
                  title="Ready for deployment immediately"
                />
              )}
            </div>

            <div className="min-w-0 space-y-1">
              <div className="flex items-center gap-2 flex-wrap">
                <h2 className={`font-bold text-zinc-100 tracking-tight ${isFocusMode ? 'text-xl sm:text-2xl' : 'text-base'}`}>
                  <HighlightText text={profile.name} query={searchQuery} />
                </h2>
                {profile.isHighlyRecommended && (
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-blue-950/80 border border-blue-800/60 text-[11px] text-blue-300 font-medium">
                    <BadgeCheck className="w-3.5 h-3.5 text-blue-400" />
                    <span>Verified Consultant</span>
                  </span>
                )}
                {isFocusMode && (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-zinc-800 text-zinc-400 text-[10px] font-mono">
                    Focus Mode
                  </span>
                )}
              </div>

              <p className={`text-zinc-300 font-medium truncate ${isFocusMode ? 'text-sm sm:text-base' : 'text-xs'}`}>
                <HighlightText text={profile.title} query={searchQuery} />
              </p>

              <div className="flex items-center gap-2 text-xs text-zinc-400 pt-0.5 flex-wrap">
                <span className="flex items-center gap-1">
                  <MapPin className="w-3.5 h-3.5 text-zinc-400" />
                  <HighlightText text={profile.location} query={searchQuery} />
                </span>
                <span>•</span>
                <span className="text-blue-400 font-medium">{profile.department}</span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-1.5 shrink-0">
            {onToggleFocusMode && (
              <button
                type="button"
                onClick={onToggleFocusMode}
                className={`p-2 rounded-xl border transition-colors cursor-pointer ${
                  isFocusMode
                    ? 'bg-blue-600 border-blue-500 text-white shadow-xs'
                    : 'bg-zinc-800/80 border-zinc-700 text-zinc-400 hover:text-white'
                }`}
                title={isFocusMode ? 'Exit focus mode (Split View)' : 'Expand & Center Crew Member Focus (Press F)'}
              >
                {isFocusMode ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
              </button>
            )}

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
                title="Print candidate dossier (PDF)"
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
              title={isBookmarked ? 'Saved in shortlist (Press S)' : 'Save to shortlist (Press S)'}
            >
              {isBookmarked ? (
                <BookmarkCheck className="w-4 h-4 fill-white" />
              ) : (
                <Bookmark className="w-4 h-4" />
              )}
            </button>
          </div>
        </div>

        {/* Quick Spec Strip */}
        <div className={`grid grid-cols-3 gap-3 border-t border-zinc-800/80 ${isFocusMode ? 'mt-5 pt-4 text-sm' : 'mt-4 pt-3 text-xs'}`}>
          <div className="bg-zinc-900/60 p-2.5 rounded-xl border border-zinc-800/60">
            <span className="text-[10px] text-zinc-400 block uppercase font-mono font-medium">Mobilization</span>
            <span className={`font-semibold truncate flex items-center gap-1.5 mt-1 ${isAvailableNow ? 'text-emerald-400' : 'text-zinc-300'} ${isFocusMode ? 'text-sm' : 'text-xs'}`}>
              <span className={`w-2 h-2 rounded-full ${isAvailableNow ? 'bg-emerald-400' : 'bg-zinc-500'}`} />
              {profile.availability}
            </span>
          </div>

          <div className="bg-zinc-900/60 p-2.5 rounded-xl border border-zinc-800/60">
            <span className="text-[10px] text-zinc-400 block uppercase font-mono font-medium">Day Rate</span>
            <span className={`font-semibold text-emerald-400 block mt-1 font-mono ${isFocusMode ? 'text-sm' : 'text-xs'}`}>
              {profile.dayRate ? `£${profile.dayRate}/day` : 'Negotiable'}
            </span>
          </div>

          <div className="bg-zinc-900/60 p-2.5 rounded-xl border border-zinc-800/60">
            <span className="text-[10px] text-zinc-400 block uppercase font-mono font-medium">Experience</span>
            <span className={`font-semibold text-zinc-200 block mt-1 font-mono ${isFocusMode ? 'text-sm' : 'text-xs'}`}>
              {profile.yearsOfExperience} yrs offshore
            </span>
          </div>
        </div>

        {/* Tabs: Dossier vs Compliance Documents */}
        <div className="flex items-center gap-2 mt-4 pt-3 border-t border-zinc-800/80">
          <button
            type="button"
            onClick={() => setActiveTab('dossier')}
            className={`px-3.5 py-1.5 rounded-xl font-semibold transition-colors cursor-pointer flex items-center gap-1.5 ${
              isFocusMode ? 'text-xs sm:text-sm' : 'text-xs'
            } ${
              activeTab === 'dossier'
                ? 'bg-zinc-800 text-white shadow-xs'
                : 'text-zinc-400 hover:text-zinc-200'
            }`}
          >
            <span>Candidate Dossier</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('vault')}
            className={`px-3.5 py-1.5 rounded-xl font-semibold transition-colors cursor-pointer flex items-center gap-1.5 ${
              isFocusMode ? 'text-xs sm:text-sm' : 'text-xs'
            } ${
              activeTab === 'vault'
                ? 'bg-blue-950/80 border border-blue-700 text-blue-200 shadow-xs'
                : 'text-zinc-400 hover:text-zinc-200'
            }`}
          >
            <FileCheck className="w-3.5 h-3.5 text-blue-400" />
            <span>Compliance & Documents</span>
            <span className="px-2 py-0.5 rounded-full bg-blue-900/60 text-blue-300 font-mono text-[10px]">
              {documents.length}
            </span>
          </button>
        </div>
      </div>

      {/* Scrollable Dossier Content */}
      <div className={`overflow-y-auto space-y-5 text-zinc-200 ${isFocusMode ? 'p-6 sm:p-8 max-h-[680px] text-sm' : 'p-5 flex-1 text-xs'}`}>
        {activeTab === 'vault' ? (
          <DocumentVault
            profile={profile}
            documents={documents}
            onAddDocument={(doc) => onAddDocument?.(doc)}
            onRemoveDocument={(docId) => onRemoveDocument?.(docId)}
            onShowToast={onShowToast}
          />
        ) : (
          <>
            {/* Executive Summary */}
            <div className="space-y-1.5 bg-zinc-950/40 p-4 rounded-xl border border-zinc-800/60">
              <h4 className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider font-mono">
                Consultant Overview & Track Record
              </h4>
              <p className="text-zinc-300 leading-relaxed">
                <HighlightText text={profile.bio} query={searchQuery} />
              </p>
            </div>

            {/* Quick Document Snapshot Banner */}
            {documents.length > 0 && (
              <div
                onClick={() => setActiveTab('vault')}
                className="p-3.5 bg-zinc-950/70 hover:bg-zinc-950 border border-zinc-800 rounded-xl flex items-center justify-between cursor-pointer transition-colors group"
              >
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-emerald-950/80 border border-emerald-800/80 flex items-center justify-center text-emerald-400">
                    <FileCheck className="w-4 h-4" />
                  </div>
                  <div>
                    <span className="font-semibold text-zinc-200 text-xs sm:text-sm block group-hover:text-blue-400 transition-colors">
                      {documents.length} Verified Compliance Documents on File
                    </span>
                    <span className="text-xs text-zinc-400">
                      BOSIET, Medical, CV & Marine Accreditations verified
                    </span>
                  </div>
                </div>
                <span className="text-xs text-blue-400 font-semibold flex items-center gap-1">
                  Open Vault →
                </span>
              </div>
            )}

            {/* Survey Disciplines */}
            {profile.surveyTypes && profile.surveyTypes.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5 font-mono">
                  <Compass className="w-3.5 h-3.5 text-blue-400" />
                  <span>Survey & Operations Focus</span>
                </h4>
                <div className="flex flex-wrap gap-2">
                  {profile.surveyTypes.map((type) => (
                    <span
                      key={type}
                      className="px-3 py-1.5 rounded-xl bg-blue-950/40 border border-blue-800/40 text-blue-200 font-medium text-xs"
                    >
                      <HighlightText text={type} query={searchQuery} />
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Offshore Safety Certifications with Tooltips */}
            {profile.certifications && profile.certifications.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5 font-mono">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Valid Safety & Marine Certifications</span>
                </h4>
                <div className="flex flex-wrap gap-2">
                  {profile.certifications.map((cert) => (
                    <CertificationBadge key={cert} certification={cert} size={isFocusMode ? 'lg' : 'md'} />
                  ))}
                </div>
              </div>
            )}

            {/* Technical Skills */}
            {profile.skills && profile.skills.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider font-mono">
                  Skills & Equipment Proficiency
                </h4>
                <div className="flex flex-wrap gap-2">
                  {profile.skills.map((skill) => (
                    <span
                      key={skill}
                      className="px-3 py-1.5 rounded-xl bg-zinc-800 text-zinc-200 border border-zinc-700/60 text-xs"
                    >
                      <HighlightText text={skill} query={searchQuery} />
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Past Operators / Clients */}
            {profile.pastCompanies && profile.pastCompanies.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5 font-mono">
                  <Building className="w-3.5 h-3.5 text-blue-400" />
                  <span>Past Operators & Energy Clients</span>
                </h4>
                <div className="flex flex-wrap gap-1.5">
                  {profile.pastCompanies.map((comp) => (
                    <span
                      key={comp}
                      className="px-2.5 py-1 rounded-lg bg-zinc-950 text-zinc-300 text-xs border border-zinc-800"
                    >
                      <HighlightText text={comp} query={searchQuery} />
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Education */}
            {profile.education && (
              <div className="space-y-1.5 pt-1">
                <h4 className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5 font-mono">
                  <GraduationCap className="w-3.5 h-3.5 text-amber-400" />
                  <span>Academic Credentials</span>
                </h4>
                <p className="text-xs sm:text-sm text-zinc-300">{profile.education}</p>
              </div>
            )}
          </>
        )}
      </div>

      {/* Sticky Bottom Action Bar */}
      <div className={`bg-zinc-950 border-t border-zinc-800 flex items-center justify-between gap-3 ${isFocusMode ? 'p-5 sm:p-6' : 'p-4'}`}>
        <div className="min-w-0">
          <span className="text-xs sm:text-sm text-zinc-300 font-mono block truncate">{profile.email}</span>
          <span className="text-[11px] text-zinc-500">Press <kbd className="font-mono text-zinc-300">C</kbd> to copy email • <kbd className="font-mono text-zinc-300">F</kbd> toggle focus</span>
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
            className="p-2.5 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-300 hover:text-white transition-colors"
            title="LinkedIn Profile"
          >
            <Linkedin className="w-4 h-4 text-[#0a66c2]" />
          </a>

          <button
            type="button"
            onClick={handleCopyEmail}
            className="px-3.5 py-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs sm:text-sm font-medium flex items-center gap-1.5 transition-colors cursor-pointer"
          >
            {copiedEmail ? (
              <>
                <Check className="w-3.5 h-3.5 text-emerald-400" />
                <span>Copied</span>
              </>
            ) : (
              <>
                <Copy className="w-3.5 h-3.5" />
                <span>Copy</span>
              </>
            )}
          </button>

          {onRequestMobilization ? (
            <button
              type="button"
              onClick={() => onRequestMobilization(profile)}
              className="px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs sm:text-sm font-semibold flex items-center gap-1.5 transition-colors cursor-pointer shadow-md"
            >
              <Send className="w-4 h-4" />
              <span>Inquire Mobilization</span>
            </button>
          ) : (
            <a
              href={`mailto:${profile.email}?subject=Hydenlyne%20Survey%20Deployment%20Inquiry%20-%20${encodeURIComponent(
                profile.title
              )}`}
              className="px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs sm:text-sm font-semibold flex items-center gap-1.5 transition-colors cursor-pointer shadow-md"
            >
              <Mail className="w-4 h-4" />
              <span>Mobilize</span>
            </a>
          )}
        </div>
      </div>
    </div>
  );
};
