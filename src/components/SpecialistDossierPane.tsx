import React, { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { UserProfile, SpecialistDocument } from '../types';
import { HighlightText } from './HighlightText';
import { CertificationBadge } from './CertificationBadge';
import { DocumentVault } from './DocumentVault';
import { CandidateSkillRadarChart } from './CandidateSkillRadarChart';
import { computeCandidateSkillScores } from '../utils/skillRadarUtils';
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
  ShieldCheck,
  Scale,
  Send,
  Printer,
  FileCheck,
  Maximize2,
  Minimize2,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  Sparkles,
  Activity,
  Layers,
  Award,
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
  onPrevProfile?: () => void;
  onNextProfile?: () => void;
  profileIndex?: number;
  totalProfiles?: number;
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
  onPrevProfile,
  onNextProfile,
  profileIndex,
  totalProfiles,
}) => {
  const [copiedEmail, setCopiedEmail] = useState(false);
  const [activeTab, setActiveTab] = useState<'dossier' | 'radar' | 'vault'>('dossier');
  const [isRadarExpanded, setIsRadarExpanded] = useState<boolean>(true);

  const skillScores = profile ? computeCandidateSkillScores(profile) : [];
  const avgScore = skillScores.length > 0 ? Math.round(skillScores.reduce((acc, curr) => acc + curr.value, 0) / skillScores.length) : 0;

  if (!profile) {
    return (
      <div className="h-full min-h-[460px] flex flex-col items-center justify-center p-8 text-center bg-zinc-900/30 border border-zinc-800/60 rounded-2xl">
        <div className="w-14 h-14 rounded-2xl bg-zinc-900 border border-zinc-800 flex items-center justify-center text-zinc-500 mb-3 shadow-inner">
          <Compass className="w-7 h-7 text-zinc-500" />
        </div>
        <h3 className="text-sm font-semibold text-zinc-300">No Specialist Selected</h3>
        <p className="text-xs text-zinc-500 max-w-xs mt-1">
          Select any crew member from the list or press <kbd className="px-1.5 py-0.5 rounded bg-zinc-800 border border-zinc-700 text-[10px] text-zinc-400 font-mono">↑</kbd> <kbd className="px-1.5 py-0.5 rounded bg-zinc-800 border border-zinc-700 text-[10px] text-zinc-400 font-mono">↓</kbd> to inspect their dossier, D3 skill radar, and compliance documents in centered focus mode.
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
      id="specialist-focused-card"
      className={`bg-zinc-900 border border-zinc-800 rounded-2xl text-zinc-100 flex flex-col overflow-hidden shadow-2xl transition-all duration-300 ${
        isFocusMode
          ? 'w-full max-w-5xl mx-auto ring-1 ring-zinc-700 shadow-zinc-950/80 my-2'
          : 'h-full'
      }`}
    >
      {/* Focus Mode Navigation Banner */}
      {isFocusMode && (
        <div className="bg-zinc-950/90 border-b border-zinc-800 px-6 py-3 flex items-center justify-between text-xs">
          <div className="flex items-center gap-2.5">
            <span className="flex h-2 w-2 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500"></span>
            </span>
            <span className="font-semibold text-zinc-200 uppercase tracking-wider font-mono text-[11px]">
              Focused Specialist Workspace
            </span>
            {totalProfiles && totalProfiles > 1 && (
              <span className="text-zinc-400 font-mono text-[11px]">
                ({(profileIndex ?? 0) + 1} of {totalProfiles})
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            {onPrevProfile && (
              <button
                type="button"
                onClick={onPrevProfile}
                className="px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 text-zinc-200 hover:text-white flex items-center gap-1 font-medium transition-colors cursor-pointer"
                title="Previous Specialist (Press Left Arrow)"
              >
                <ChevronLeft className="w-3.5 h-3.5" />
                <span>Prev</span>
              </button>
            )}
            {onNextProfile && (
              <button
                type="button"
                onClick={onNextProfile}
                className="px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 text-zinc-200 hover:text-white flex items-center gap-1 font-medium transition-colors cursor-pointer"
                title="Next Specialist (Press Right Arrow)"
              >
                <span>Next</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            )}
            {onToggleFocusMode && (
              <button
                type="button"
                onClick={onToggleFocusMode}
                className="px-3.5 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-750 border border-zinc-700 text-zinc-200 hover:text-white flex items-center gap-1 font-medium transition-colors cursor-pointer ml-1"
                title="Exit focus mode back to Split-Pane"
              >
                <Minimize2 className="w-3.5 h-3.5" />
                <span>Exit Focus</span>
              </button>
            )}
          </div>
        </div>
      )}

      {/* Header Profile Section */}
      <div className={`border-b border-zinc-800 bg-zinc-950/70 ${isFocusMode ? 'p-6 sm:p-7' : 'p-5'}`}>
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-4 min-w-0">
            <div className="relative shrink-0">
              <img
                src={profile.avatar}
                alt={profile.name}
                referrerPolicy="no-referrer"
                className={`rounded-2xl object-cover border border-zinc-700/80 shadow-lg transition-all ${
                  isFocusMode ? 'w-18 h-18 sm:w-22 sm:h-22' : 'w-14 h-14'
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
                <span>•</span>
                <span className="font-mono text-zinc-300">{profile.yearsOfExperience}y offshore exp</span>
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

        {/* Navigation Tabs: Dossier, D3 Radar, Compliance Documents */}
        <div className="flex items-center gap-2 mt-4 pt-3 border-t border-zinc-800/80 flex-wrap">
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
            <Layers className="w-3.5 h-3.5 text-zinc-400" />
            <span>Candidate Dossier</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('radar')}
            className={`px-3.5 py-1.5 rounded-xl font-semibold transition-colors cursor-pointer flex items-center gap-1.5 ${
              isFocusMode ? 'text-xs sm:text-sm' : 'text-xs'
            } ${
              activeTab === 'radar'
                ? 'bg-zinc-800 text-white shadow-xs'
                : 'text-zinc-400 hover:text-zinc-200'
            }`}
          >
            <Activity className="w-3.5 h-3.5 text-zinc-400" />
            <span>Skills Radar</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('vault')}
            className={`px-3.5 py-1.5 rounded-xl font-semibold transition-colors cursor-pointer flex items-center gap-1.5 ${
              isFocusMode ? 'text-xs sm:text-sm' : 'text-xs'
            } ${
              activeTab === 'vault'
                ? 'bg-zinc-800 text-white shadow-xs'
                : 'text-zinc-400 hover:text-zinc-200'
            }`}
          >
            <FileCheck className="w-3.5 h-3.5 text-zinc-400" />
            <span>Compliance & Documents</span>
            <span className="px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-300 font-mono text-[10px]">
              {documents.length}
            </span>
          </button>
        </div>
      </div>

      {/* Scrollable Dossier Content */}
      <div className={`overflow-y-auto space-y-5 text-zinc-200 ${isFocusMode ? 'p-6 sm:p-8 max-h-[720px] text-sm' : 'p-5 flex-1 text-xs'}`}>
        {activeTab === 'vault' ? (
          <DocumentVault
            profile={profile}
            documents={documents}
            onAddDocument={(doc) => onAddDocument?.(doc)}
            onRemoveDocument={(docId) => onRemoveDocument?.(docId)}
            onShowToast={onShowToast}
          />
        ) : activeTab === 'radar' ? (
          <div className="space-y-4">
            <CandidateSkillRadarChart
              profile={profile}
              size={isFocusMode ? 'lg' : 'md'}
              showLegend={true}
            />
            <div className="bg-zinc-950/50 p-4 rounded-xl border border-zinc-800/70 text-xs text-zinc-400 space-y-1.5">
              <span className="font-semibold text-zinc-200 block font-mono text-[11px] uppercase">
                Methodology & Assessment Criteria
              </span>
              <p>
                Calculated dynamically from verified offshore track records, certifications (BOSIET, GWO, STCW), and technical proficiencies in <strong className="text-zinc-300">Geotechnical</strong>, <strong className="text-zinc-300">Environmental</strong>, and <strong className="text-zinc-300">Data Analysis</strong>.
              </p>
            </div>
          </div>
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

            {/* Embedded D3 Radar Preview Card with Expand/Collapse Toggle */}
            <div className="space-y-2">
              <div className="flex items-center justify-between gap-2">
                <h4 className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5 font-mono">
                  <Activity className="w-3.5 h-3.5 text-zinc-400" />
                  <span>Competency Radar Analysis</span>
                </h4>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    id="toggle-radar-collapse-btn"
                    onClick={() => setIsRadarExpanded(!isRadarExpanded)}
                    className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium bg-zinc-950/70 hover:bg-zinc-800 border border-zinc-800 text-zinc-300 hover:text-white transition-colors cursor-pointer shadow-2xs"
                    title={isRadarExpanded ? 'Collapse radar breakdown' : 'Expand radar breakdown'}
                  >
                    <span>{isRadarExpanded ? 'Collapse' : 'Expand'}</span>
                    {isRadarExpanded ? (
                      <ChevronUp className="w-3.5 h-3.5 text-zinc-400" />
                    ) : (
                      <ChevronDown className="w-3.5 h-3.5 text-zinc-400" />
                    )}
                  </button>
                  <button
                    type="button"
                    onClick={() => setActiveTab('radar')}
                    className="text-xs text-blue-400 hover:text-blue-300 font-medium cursor-pointer"
                  >
                    Full Tab →
                  </button>
                </div>
              </div>

              <AnimatePresence initial={false} mode="wait">
                {isRadarExpanded ? (
                  <motion.div
                    key="radar-chart-expanded"
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    transition={{ duration: 0.2, ease: 'easeInOut' }}
                    className="overflow-hidden"
                  >
                    <CandidateSkillRadarChart
                      profile={profile}
                      size={isFocusMode ? 'md' : 'sm'}
                      showLegend={isFocusMode}
                    />
                  </motion.div>
                ) : (
                  <motion.button
                    key="radar-chart-collapsed"
                    type="button"
                    id="expand-collapsed-radar-banner"
                    onClick={() => setIsRadarExpanded(true)}
                    initial={{ opacity: 0, scale: 0.98 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.98 }}
                    transition={{ duration: 0.15 }}
                    className="w-full p-3 rounded-xl bg-zinc-950/60 hover:bg-zinc-900 border border-zinc-800/80 hover:border-zinc-700 flex items-center justify-between text-left transition-colors cursor-pointer group"
                    title="Click to expand D3 competency radar chart"
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <div className="w-7 h-7 rounded-lg bg-zinc-900 border border-zinc-800 flex items-center justify-center text-zinc-400 group-hover:text-zinc-200 shrink-0">
                        <Activity className="w-3.5 h-3.5" />
                      </div>
                      <div className="min-w-0">
                        <p className="text-xs font-semibold text-zinc-300 group-hover:text-white truncate">
                          Radar Breakdown Collapsed
                        </p>
                        <p className="text-[10px] text-zinc-500 font-mono">
                          6 Vector Competency Axes • Click to show
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2.5 shrink-0">
                      <span className="px-2 py-0.5 rounded-full bg-zinc-900 border border-zinc-800 text-zinc-300 font-mono text-[11px] font-medium flex items-center gap-1">
                        <Award className="w-3 h-3 text-zinc-400" />
                        {avgScore}% Composite
                      </span>
                      <span className="text-xs text-blue-400 font-medium group-hover:underline flex items-center gap-0.5">
                        <span>Show Radar</span>
                        <ChevronDown className="w-3.5 h-3.5" />
                      </span>
                    </div>
                  </motion.button>
                )}
              </AnimatePresence>
            </div>

            {/* Survey Disciplines */}
            {profile.surveyTypes && profile.surveyTypes.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5 font-mono">
                  <Compass className="w-3.5 h-3.5 text-zinc-400" />
                  <span>Survey & Operations Focus</span>
                </h4>
                <div className="flex flex-wrap gap-2">
                  {profile.surveyTypes.map((type) => (
                    <span
                      key={type}
                      className="px-3 py-1.5 rounded-xl bg-zinc-900 border border-zinc-800 text-zinc-300 font-medium text-xs"
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
                  <ShieldCheck className="w-3.5 h-3.5 text-zinc-400" />
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
                  <Building className="w-3.5 h-3.5 text-zinc-400" />
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
                  <GraduationCap className="w-3.5 h-3.5 text-zinc-400" />
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
          <span className="text-[11px] text-zinc-500">
            Press <kbd className="font-mono text-zinc-300">C</kbd> to copy email • <kbd className="font-mono text-zinc-300">F</kbd> toggle focus
          </span>
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
            className={`relative px-3.5 py-2 rounded-xl text-xs sm:text-sm font-medium flex items-center gap-1.5 transition-all duration-200 cursor-pointer overflow-hidden ${
              copiedEmail
                ? 'bg-emerald-950/80 border border-emerald-500/50 text-emerald-300 shadow-xs ring-1 ring-emerald-500/30'
                : 'bg-zinc-800 hover:bg-zinc-750 border border-zinc-700/60 text-zinc-200 hover:text-white'
            }`}
            title="Copy email address to clipboard"
          >
            <AnimatePresence mode="wait" initial={false}>
              {copiedEmail ? (
                <motion.div
                  key="copied"
                  initial={{ opacity: 0, scale: 0.85, y: 2 }}
                  animate={{ opacity: 1, scale: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.85, y: -2 }}
                  transition={{ duration: 0.15, ease: 'easeOut' }}
                  className="flex items-center gap-1.5"
                >
                  <motion.span
                    initial={{ scale: 0 }}
                    animate={{ scale: [0, 1.25, 1] }}
                    transition={{ duration: 0.22, ease: 'backOut' }}
                  >
                    <Check className="w-3.5 h-3.5 text-emerald-400" />
                  </motion.span>
                  <span className="font-medium text-emerald-300">Copied!</span>
                </motion.div>
              ) : (
                <motion.div
                  key="copy"
                  initial={{ opacity: 0, scale: 0.85, y: 2 }}
                  animate={{ opacity: 1, scale: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.85, y: -2 }}
                  transition={{ duration: 0.15, ease: 'easeOut' }}
                  className="flex items-center gap-1.5"
                >
                  <Copy className="w-3.5 h-3.5 text-zinc-400 group-hover:text-zinc-200" />
                  <span>Copy</span>
                </motion.div>
              )}
            </AnimatePresence>
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
