import { FC, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useAccessibleDialog } from '../hooks/useAccessibleDialog';
import { motion, AnimatePresence } from 'motion/react';
import { UserProfile, SpecialistDocument } from '../types';
import { HighlightText } from './HighlightText';
import { CertificationBadge } from './CertificationBadge';
import { DocumentVault } from './DocumentVault';
import { CandidateSkillRadarChart } from './CandidateSkillRadarChart';
import { ConfirmDialog } from './ConfirmDialog';
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
  X,
  Sparkles,
  Activity,
  Layers,
  BriefcaseBusiness,
  Trash2,
  Ellipsis,
  Loader2,
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
  summary?: string;
  summaryLoading?: boolean;
  onAddDocument?: () => void;
  onRemoveDocument?: (docId: string) => void | Promise<void>;
  canManageDocuments?: boolean;
  canDeleteCrew?: boolean;
  onDeleteCrew?: (profile: UserProfile) => Promise<void>;
  isFocusMode?: boolean;
  onToggleFocusMode?: () => void;
  onPrevProfile?: () => void;
  onNextProfile?: () => void;
  profileIndex?: number;
  totalProfiles?: number;
}

export const SpecialistDossierPane: FC<SpecialistDossierPaneProps> = ({
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
  summary,
  summaryLoading = false,
  onAddDocument,
  onRemoveDocument,
  canManageDocuments = false,
  canDeleteCrew = false,
  onDeleteCrew,
  isFocusMode = false,
  onToggleFocusMode,
  onPrevProfile,
  onNextProfile,
  profileIndex,
  totalProfiles,
}) => {
  const [copiedEmail, setCopiedEmail] = useState(false);
  const [activeTab, setActiveTab] = useState<'dossier' | 'experience' | 'expertise' | 'systems' | 'credentials' | 'radar' | 'vault'>('dossier');
  const [isRadarModalOpen, setIsRadarModalOpen] = useState(false);
  const [isMoreSectionsOpen, setIsMoreSectionsOpen] = useState(false);
  const [isHeaderActionsOpen, setIsHeaderActionsOpen] = useState(false);
  const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);
  const sectionMenuRef = useRef<HTMLDivElement>(null);
  const sectionMenuTriggerRef = useRef<HTMLButtonElement>(null);
  const headerActionsRef = useRef<HTMLDivElement>(null);
  const headerActionsTriggerRef = useRef<HTMLButtonElement>(null);
  const radarCloseRef = useRef<HTMLButtonElement>(null);
  const radarDialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    contentRef.current?.scrollTo({ top: 0, behavior: 'auto' });
  }, [profile?.id, activeTab, isFocusMode]);

  useEffect(() => {
    setIsMoreSectionsOpen(false);
    setIsHeaderActionsOpen(false);
  }, [profile?.id]);

  useEffect(() => {
    if (!isMoreSectionsOpen || isRadarModalOpen) return;

    const handlePointerDown = (event: PointerEvent) => {
      if (!sectionMenuRef.current?.contains(event.target as Node)) setIsMoreSectionsOpen(false);
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsMoreSectionsOpen(false);
        sectionMenuTriggerRef.current?.focus();
        return;
      }
      if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return;
      const items = Array.from(sectionMenuRef.current?.querySelectorAll('[role="menuitem"]') ?? []) as HTMLButtonElement[];
      if (items.length === 0) return;
      event.preventDefault();
      const currentIndex = items.indexOf(document.activeElement as HTMLButtonElement);
      const nextIndex = event.key === 'Home'
        ? 0
        : event.key === 'End'
          ? items.length - 1
          : event.key === 'ArrowDown'
            ? (currentIndex + 1) % items.length
            : (currentIndex - 1 + items.length) % items.length;
      items[nextIndex]?.focus();
    };

    document.addEventListener('pointerdown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isMoreSectionsOpen, isRadarModalOpen]);

  useEffect(() => {
    if (!isHeaderActionsOpen) return;

    const handlePointerDown = (event: PointerEvent) => {
      if (!headerActionsRef.current?.contains(event.target as Node)) setIsHeaderActionsOpen(false);
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsHeaderActionsOpen(false);
        headerActionsTriggerRef.current?.focus();
        return;
      }
      if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return;
      const items = Array.from(headerActionsRef.current?.querySelectorAll('[role="menuitem"]') ?? []) as HTMLButtonElement[];
      if (items.length === 0) return;
      event.preventDefault();
      const currentIndex = items.indexOf(document.activeElement as HTMLButtonElement);
      const nextIndex = event.key === 'Home'
        ? 0
        : event.key === 'End'
          ? items.length - 1
          : event.key === 'ArrowDown'
            ? (currentIndex + 1) % items.length
            : (currentIndex - 1 + items.length) % items.length;
      items[nextIndex]?.focus();
    };

    document.addEventListener('pointerdown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    requestAnimationFrame(() => headerActionsRef.current?.querySelector<HTMLButtonElement>('[role="menuitem"]')?.focus());
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isHeaderActionsOpen]);

  useAccessibleDialog(isRadarModalOpen, radarDialogRef, () => setIsRadarModalOpen(false));

  if (!profile) {
    return (
      <div className="h-full min-h-[460px] flex flex-col items-center justify-center p-8 text-center bg-zinc-900/30 border border-zinc-800/60 rounded-2xl">
        <div className="w-14 h-14 rounded-2xl bg-zinc-900 border border-zinc-800 flex items-center justify-center text-zinc-500 mb-3 shadow-inner">
          <Compass className="w-7 h-7 text-zinc-500" />
        </div>
        <h3 className="text-sm font-semibold text-zinc-300">No Specialist Selected</h3>
        <p className="text-xs text-zinc-500 max-w-xs mt-1">
          Select a specialist from the list or press <kbd className="px-1.5 py-0.5 rounded bg-zinc-800 border border-zinc-700 text-[10px] text-zinc-400 font-mono">↑</kbd> <kbd className="px-1.5 py-0.5 rounded bg-zinc-800 border border-zinc-700 text-[10px] text-zinc-400 font-mono">↓</kbd> to review their dossier, skills radar, and compliance documents.
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

  const handleDeleteCrew = async () => {
    if (!onDeleteCrew) return;
    setIsDeleting(true);
    try {
      await onDeleteCrew(profile);
      setIsDeleteConfirmOpen(false);
    } catch (error) {
      onShowToast(error instanceof Error ? error.message : `Could not delete ${profile.name}`);
    } finally {
      setIsDeleting(false);
    }
  };

  const isAvailableNow = profile.availability?.toLowerCase().includes('immediately');
  const isSecondarySection = activeTab === 'systems' || activeTab === 'expertise';
  const secondarySectionLabel = activeTab === 'systems' ? 'Systems' : activeTab === 'expertise' ? 'Expertise' : 'More';
  const sectionButtonClass = (isActive: boolean) => `min-h-11 px-3.5 py-1.5 rounded-xl font-semibold transition-colors cursor-pointer flex items-center gap-1.5 ${
    isFocusMode ? 'text-xs sm:text-sm' : 'text-xs'
  } ${isActive ? 'bg-zinc-800 text-white shadow-xs' : 'text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200'}`;

  const selectSecondarySection = (section: 'systems' | 'expertise') => {
    setActiveTab(section);
    setIsMoreSectionsOpen(false);
    requestAnimationFrame(() => sectionMenuTriggerRef.current?.focus());
  };

  const runHeaderAction = (action: () => void) => {
    action();
    setIsHeaderActionsOpen(false);
    requestAnimationFrame(() => headerActionsTriggerRef.current?.focus());
  };

  return (
    <>
    <div
      id="specialist-focused-card"
      className={`bg-zinc-900 border border-zinc-800 rounded-2xl text-zinc-100 flex flex-col overflow-hidden shadow-2xl transition-all duration-300 ${
        isFocusMode
          ? 'w-full h-full max-w-6xl mx-auto ring-1 ring-zinc-700 shadow-zinc-950/80 my-2'
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
                className="min-h-11 px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 text-zinc-200 hover:text-white flex items-center gap-1 font-medium transition-colors cursor-pointer"
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
                className="min-h-11 px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 text-zinc-200 hover:text-white flex items-center gap-1 font-medium transition-colors cursor-pointer"
                title="Next Specialist (Press Right Arrow)"
              >
                <span>Next</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            )}
            {onToggleFocusMode && !isFocusMode && (
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
      <div className={`border-b border-zinc-800 bg-zinc-950/70 ${isFocusMode ? 'p-3 sm:p-4' : 'p-4 sm:p-5'}`}>
        <div className="flex flex-col items-stretch gap-3 lg:flex-row lg:items-start lg:justify-between lg:gap-4">
          <div className="flex min-w-0 items-start gap-3 sm:gap-4">
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
                  <span className="badge-accent inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-medium">
                    <BadgeCheck className="w-3.5 h-3.5 text-blue-400" />
                    <span>Verified Specialist</span>
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

          <div className="flex w-full flex-wrap items-center justify-end gap-2 lg:w-auto lg:shrink-0">
            {onToggleFocusMode && (
              <button
                type="button"
                onClick={onToggleFocusMode}
                className={`min-h-11 min-w-11 p-2 rounded-xl border transition-colors cursor-pointer inline-flex items-center justify-center ${
                  isFocusMode
                    ? 'bg-blue-600 border-blue-500 text-white shadow-xs'
                    : 'bg-zinc-800/80 border-zinc-700 text-zinc-400 hover:text-white'
                }`}
                title={isFocusMode ? 'Exit focus mode (Split View)' : 'Open focused specialist view (Press F)'}
                aria-label={isFocusMode ? 'Exit focused specialist view' : 'Open focused specialist view'}
              >
                {isFocusMode ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
              </button>
            )}

            <button
              type="button"
              onClick={() => onToggleBookmark(profile.id)}
              aria-label={isBookmarked ? `Remove ${profile.name} from shortlist` : `Save ${profile.name} to shortlist`}
              className={`min-h-11 min-w-11 p-2 rounded-xl border transition-colors cursor-pointer inline-flex items-center justify-center ${
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

            {(onToggleCompare || onPrintDossier || (canDeleteCrew && onDeleteCrew)) && (
              <div ref={headerActionsRef} className="relative">
                <button
                  ref={headerActionsTriggerRef}
                  type="button"
                  aria-label={`More dossier actions for ${profile.name}`}
                  aria-haspopup="menu"
                  aria-expanded={isHeaderActionsOpen}
                  onClick={() => setIsHeaderActionsOpen((open) => !open)}
                  className={`inline-flex min-h-11 min-w-11 items-center justify-center rounded-xl border transition-colors ${isHeaderActionsOpen ? 'border-zinc-600 bg-zinc-800 text-white' : 'border-zinc-700 bg-zinc-800/80 text-zinc-400 hover:text-white'}`}
                >
                  <Ellipsis className="h-4 w-4" aria-hidden="true" />
                </button>
                {isHeaderActionsOpen && (
                  <div role="menu" aria-label={`Dossier actions for ${profile.name}`} className="absolute right-0 top-12 z-30 w-56 rounded-2xl border border-zinc-700/80 bg-zinc-900/95 p-1.5 shadow-2xl shadow-black/40 backdrop-blur-xl">
                    {onToggleCompare && (
                      <button type="button" role="menuitem" onClick={() => runHeaderAction(() => onToggleCompare(profile))} className="flex min-h-11 w-full items-center gap-3 rounded-lg px-3 text-left text-sm text-zinc-300 hover:bg-zinc-800 hover:text-white">
                        <Scale className={`h-4 w-4 ${isCompared ? 'text-blue-400' : ''}`} />
                        {isCompared ? 'Remove from compare' : 'Add to compare'}
                      </button>
                    )}
                    {onPrintDossier && (
                      <button type="button" role="menuitem" onClick={() => runHeaderAction(() => onPrintDossier(profile))} className="flex min-h-11 w-full items-center gap-3 rounded-lg px-3 text-left text-sm text-zinc-300 hover:bg-zinc-800 hover:text-white">
                        <Printer className="h-4 w-4" /> Print dossier
                      </button>
                    )}
                    {canDeleteCrew && onDeleteCrew && (
                      <button type="button" role="menuitem" onClick={() => runHeaderAction(() => setIsDeleteConfirmOpen(true))} className="flex min-h-11 w-full items-center gap-3 rounded-lg px-3 text-left text-sm text-rose-300 hover:bg-rose-950/70 hover:text-rose-200">
                        <Trash2 className="h-4 w-4" /> Delete specialist
                      </button>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Quick Spec Strip */}
        <div className={`grid grid-cols-2 sm:grid-cols-4 border-y border-zinc-800/70 ${isFocusMode ? 'mt-4 py-3 text-xs' : 'mt-5 py-3 text-xs'}`}>
          <div className="px-3 py-1 sm:border-r sm:border-zinc-800/70 first:pl-0">
            <span className="text-[10px] text-zinc-400 block uppercase font-mono font-medium">Mobilization</span>
            <span className={`font-semibold truncate flex items-center gap-1.5 mt-1 ${isAvailableNow ? 'text-emerald-400' : 'text-zinc-300'} ${isFocusMode ? 'text-sm' : 'text-xs'}`}>
              <span className={`w-2 h-2 rounded-full ${isAvailableNow ? 'bg-emerald-400' : 'bg-zinc-500'}`} />
              {profile.availability}
            </span>
          </div>

          <div className="border-l border-zinc-800/70 px-3 py-1 sm:border-l-0 sm:border-r">
            <span className="text-[10px] text-zinc-400 block uppercase font-mono font-medium">Day Rate</span>
            <span className={`font-semibold text-emerald-400 block mt-1 font-mono ${isFocusMode ? 'text-sm' : 'text-xs'}`}>
              {profile.dayRate ? `£${profile.dayRate}/day` : 'Negotiable'}
            </span>
          </div>

          <div className="mt-3 border-t border-zinc-800/70 px-3 pt-3 pb-1 sm:mt-0 sm:border-t-0 sm:border-r sm:py-1">
            <span className="text-[10px] text-zinc-400 block uppercase font-mono font-medium">Experience</span>
            <span className={`font-semibold text-zinc-200 block mt-1 font-mono ${isFocusMode ? 'text-sm' : 'text-xs'}`}>
              {profile.yearsOfExperience} yrs offshore
            </span>
          </div>

          <div className="mt-3 border-l border-t border-zinc-800/70 px-3 pt-3 pb-1 sm:mt-0 sm:border-t-0 sm:py-1 sm:pr-0">
            <span className="text-[10px] text-zinc-400 block uppercase font-mono font-medium">Rating</span>
            <span className={`font-semibold text-amber-300 block mt-1 font-mono ${isFocusMode ? 'text-sm' : 'text-xs'}`}>
              ★ {profile.rating ? profile.rating.toFixed(1) : '—'}
              {profile.reviewCount ? <span className="ml-1 text-zinc-500 font-normal">({profile.reviewCount})</span> : null}
            </span>
          </div>
        </div>

        {/* Decision summary: orient the reader before the detailed dossier. */}
        <div className="fit-summary mt-4 flex items-start gap-3 rounded-xl px-3 py-3">
          <Sparkles className="fit-summary-label mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <div className="min-w-0">
            <p className="fit-summary-label text-[10px] font-semibold uppercase tracking-wider font-mono">
              Why this specialist
            </p>
            <p className="mt-1 text-xs leading-5">
              {profile.name} brings <strong className="font-semibold text-zinc-100">{profile.yearsOfExperience} years</strong> of offshore experience in {profile.department.toLowerCase()} and is {isAvailableNow ? 'available for immediate mobilization' : profile.availability.toLowerCase()}.
            </p>
          </div>
        </div>

        {/* Primary sections remain visible; specialist detail is progressively disclosed. */}
        <div role="group" aria-label={`${profile.name} dossier sections`} className="flex items-center gap-2 mt-3 pt-2 border-t border-zinc-800/80 flex-wrap">
          <button
            type="button"
            aria-pressed={activeTab === 'dossier'}
            onClick={() => setActiveTab('dossier')}
            className={sectionButtonClass(activeTab === 'dossier')}
          >
            <Layers className="w-3.5 h-3.5 text-zinc-400" />
            <span>Overview</span>
          </button>

          <button
            type="button"
            aria-pressed={activeTab === 'experience'}
            onClick={() => setActiveTab('experience')}
            className={sectionButtonClass(activeTab === 'experience')}
          >
            <BriefcaseBusiness className="w-3.5 h-3.5 text-zinc-400" />
            <span>Experience</span>
          </button>

          <button
            type="button"
            aria-pressed={activeTab === 'credentials'}
            onClick={() => setActiveTab('credentials')}
            className={sectionButtonClass(activeTab === 'credentials')}
          >
            <GraduationCap className="w-3.5 h-3.5 text-zinc-400" />
            <span>Credentials</span>
          </button>

          <button
            type="button"
            aria-pressed={activeTab === 'vault'}
            onClick={() => setActiveTab('vault')}
            className={sectionButtonClass(activeTab === 'vault')}
          >
            <FileCheck className="w-3.5 h-3.5 text-zinc-400" />
            <span>Documents</span>
            <span className="px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-300 font-mono text-[10px]">
              {documents.length}
            </span>
          </button>

          <div ref={sectionMenuRef} className="relative">
            <button
              ref={sectionMenuTriggerRef}
              type="button"
              aria-haspopup="menu"
              aria-expanded={isMoreSectionsOpen}
              aria-pressed={isSecondarySection || isRadarModalOpen}
              onClick={() => setIsMoreSectionsOpen((open) => !open)}
              className={sectionButtonClass(isSecondarySection || isRadarModalOpen)}
            >
              <Ellipsis className="h-4 w-4" aria-hidden="true" />
              <span>{secondarySectionLabel}</span>
            </button>
            {isMoreSectionsOpen && (
              <div role="menu" aria-label="More dossier sections" className="absolute right-0 top-12 z-30 w-52 rounded-2xl border border-zinc-700/80 bg-zinc-900/95 p-1.5 shadow-2xl shadow-black/40 backdrop-blur-xl">
                <button type="button" role="menuitem" onClick={() => selectSecondarySection('systems')} className="flex min-h-11 w-full items-center gap-3 rounded-lg px-3 text-left text-sm text-zinc-300 hover:bg-zinc-800 hover:text-white">
                  <Layers className="h-4 w-4" /> Systems experience
                </button>
                <button type="button" role="menuitem" onClick={() => selectSecondarySection('expertise')} className="flex min-h-11 w-full items-center gap-3 rounded-lg px-3 text-left text-sm text-zinc-300 hover:bg-zinc-800 hover:text-white">
                  <Activity className="h-4 w-4" /> Technical expertise
                </button>
                <button type="button" role="menuitem" onClick={() => setIsRadarModalOpen(true)} className="flex min-h-11 w-full items-center gap-3 rounded-lg px-3 text-left text-sm text-zinc-300 hover:bg-zinc-800 hover:text-white">
                  <Activity className="h-4 w-4" /> Competency radar
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Scrollable Dossier Content */}
      <div ref={contentRef} className={`${isFocusMode ? 'focus-dossier-content overflow-y-auto p-2 sm:p-3 flex-1 text-xs' : 'overflow-y-auto p-5 flex-1 text-xs'} text-zinc-200 min-h-0`}>
        {activeTab === 'vault' ? (
          <DocumentVault
            profile={profile}
            documents={documents}
            onAddDocument={() => onAddDocument?.()}
            onRemoveDocument={(docId) => onRemoveDocument?.(docId)}
            canManageDocuments={canManageDocuments}
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
        ) : activeTab === 'experience' ? (
          <div className="space-y-4">
            <section className="space-y-2">
              <h3 className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider font-mono">Track Record & Clients</h3>
              <p className="text-zinc-300 leading-relaxed">{profile.yearsOfExperience} years of offshore experience.</p>
              {profile.pastCompanies && profile.pastCompanies.length > 0 && <div className="flex flex-wrap gap-2">{profile.pastCompanies.map((company) => <span key={company} className="px-3 py-1.5 rounded-xl bg-zinc-900 border border-zinc-800 text-zinc-300">{company}</span>)}</div>}
            </section>
            {profile.workHistory && profile.workHistory.length > 0 && (
              <section className="space-y-2">
                <h3 className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider font-mono">Recent Projects</h3>
                <div className="overflow-x-auto rounded-xl border border-zinc-800">
                  <table className="min-w-full text-sm">
                    <thead className="bg-zinc-950/60 text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">
                      <tr><th className="px-3 py-2 text-left">Year</th><th className="px-3 py-2 text-left">Client</th><th className="px-3 py-2 text-left">Country</th><th className="px-3 py-2 text-left">Survey Type</th><th className="px-3 py-2 text-left">Position</th></tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-800">
                      {profile.workHistory.map((row, idx) => (
                        <tr key={row.id ?? idx} className="text-zinc-200">
                          <td className="px-3 py-2 whitespace-nowrap">{row.startDate ? row.startDate.slice(0, 4) : ''}</td>
                          <td className="px-3 py-2">{row.clientName}</td>
                          <td className="px-3 py-2">{row.country}</td>
                          <td className="px-3 py-2">{row.projectType}</td>
                          <td className="px-3 py-2">{row.role}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            )}
            {profile.geographicalExperience && profile.geographicalExperience.length > 0 && <section className="space-y-2"><h3 className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider font-mono">Geographical Experience</h3><div className="flex flex-wrap gap-2">{profile.geographicalExperience.map((place) => <span key={place} className="px-3 py-1.5 rounded-xl bg-zinc-900 border border-zinc-800 text-zinc-300"><HighlightText text={place} query={searchQuery} /></span>)}</div></section>}
            {profile.surveyTypes && profile.surveyTypes.length > 0 && <section className="space-y-2"><h3 className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider font-mono">Survey Focus</h3><div className="flex flex-wrap gap-2">{profile.surveyTypes.map((type) => <span key={type} className="px-3 py-1.5 rounded-xl bg-zinc-900 border border-zinc-800 text-zinc-300">{type}</span>)}</div></section>}
          </div>
        ) : activeTab === 'systems' ? (
          <div className="space-y-4">
            {profile.systemsCategories ? (Object.entries(profile.systemsCategories) as [string, string[]][]).map(([category, items]) => items.length > 0 && <section key={category} className="space-y-2"><h3 className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider font-mono">{category}</h3><div className="flex flex-wrap gap-2">{items.map((system) => <span key={system} className="px-3 py-1.5 rounded-xl bg-zinc-900 border border-zinc-800 text-zinc-300 font-medium text-xs">{system}</span>)}</div></section>) : <p className="text-zinc-500">No systems experience was found in the CV.</p>}
          </div>
        ) : activeTab === 'expertise' ? (
          <div className="space-y-4">
            {profile.expertise && profile.expertise.length > 0 && <section className="space-y-2"><h3 className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider font-mono">Expertise</h3><div className="flex flex-wrap gap-2">{profile.expertise.map((item) => <span key={item} className="px-3 py-1.5 rounded-xl bg-zinc-900 border border-zinc-800 text-zinc-300 font-medium text-xs">{item}</span>)}</div></section>}
            {(!profile.expertise || profile.expertise.length === 0) && <p className="text-zinc-500">No explicit expertise section was found in the CV.</p>}
          </div>
        ) : activeTab === 'credentials' ? (
          <div className="space-y-4">
            {(profile.countryOfResidence || profile.dateOfBirth || profile.gender || (profile.languages && profile.languages.length > 0) || profile.flyingPoint || profile.nationality) && (
              <section className="space-y-2">
                <h3 className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider font-mono">Personal Information</h3>
                <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-2 text-sm">
                  {profile.nationality && <div className="flex justify-between gap-2"><dt className="text-zinc-500">Nationality</dt><dd className="text-zinc-200 text-right">{profile.nationality}</dd></div>}
                  {profile.countryOfResidence && <div className="flex justify-between gap-2"><dt className="text-zinc-500">Country of residence</dt><dd className="text-zinc-200 text-right">{profile.countryOfResidence}</dd></div>}
                  {profile.dateOfBirth && <div className="flex justify-between gap-2"><dt className="text-zinc-500">Date of birth</dt><dd className="text-zinc-200 text-right">{profile.dateOfBirth}</dd></div>}
                  {profile.gender && <div className="flex justify-between gap-2"><dt className="text-zinc-500">Gender</dt><dd className="text-zinc-200 text-right">{profile.gender}</dd></div>}
                  {profile.flyingPoint && <div className="flex justify-between gap-2"><dt className="text-zinc-500">Flying point</dt><dd className="text-zinc-200 text-right">{profile.flyingPoint}</dd></div>}
                  {profile.languages && profile.languages.length > 0 && <div className="sm:col-span-2 flex justify-between gap-2"><dt className="text-zinc-500">Languages</dt><dd className="text-zinc-200 text-right">{profile.languages.join(', ')}</dd></div>}
                </dl>
              </section>
            )}
            {profile.certifications && profile.certifications.length > 0 && <section className="space-y-2"><h3 className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider font-mono">Certifications & Tickets</h3><div className="flex flex-wrap gap-2">{profile.certifications.map((cert) => <CertificationBadge key={cert} certification={cert} size="md" />)}</div></section>}
            {profile.certificationDetails && profile.certificationDetails.length > 0 && <section className="space-y-2"><h3 className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider font-mono">Completion & Expiry</h3><div className="space-y-2">{profile.certificationDetails.map((cert) => <div key={cert.id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-zinc-800 bg-zinc-950/40 px-3 py-2"><span className="text-zinc-200">{cert.name}</span><span className="text-zinc-500">{cert.issueDate ? `Completed ${cert.issueDate}` : 'Completion date not recorded'}{cert.expiryDate ? ` · Expires ${cert.expiryDate}` : ' · No expiry recorded'}</span></div>)}</div></section>}
            {profile.trainingDetails && profile.trainingDetails.length > 0 && <section className="space-y-2"><h3 className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider font-mono">Training / Qualifications</h3><div className="space-y-2">{profile.trainingDetails.map((item) => <div key={item.id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-zinc-800 bg-zinc-950/40 px-3 py-2"><div className="flex flex-col"><span className="text-zinc-200">{item.name}</span>{item.location && <span className="text-xs text-zinc-500">{item.location}</span>}</div><span className="text-zinc-500 text-sm">{item.completedDate ? `Completed ${item.completedDate.slice(0, 4)}` : 'Completion date not recorded'}{item.expiryDate ? ` · Expires ${item.expiryDate.slice(0, 4)}` : ''}</span></div>)}</div></section>}
            {profile.education && <section><h3 className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider font-mono">Education</h3><p className="mt-1 text-zinc-300">{profile.education}</p></section>}
          </div>
        ) : (
          <div className={isFocusMode ? 'grid grid-cols-1 lg:grid-cols-2 gap-2' : 'space-y-3'}>
            {/* AI Summary — generated on first profile view, cached after
                that (see backend/docs/cv-ingestion-pipeline.md). Distinct
                from "Overview & Track Record" below: this is a synthesized,
                recruiter-facing overview pulling together certs/availability/
                experience, not the consultant's own CV wording. */}
            {(summaryLoading || summary) && (
              <div className={`space-y-1.5 bg-zinc-950/40 rounded-xl border border-zinc-800/60 ${isFocusMode ? 'p-2 lg:col-span-2' : 'p-3'}`}>
                <h4 className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider font-mono flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-zinc-400" aria-hidden="true" />
                  AI Summary
                </h4>
                {summaryLoading ? (
                  <div className="flex items-center gap-2 text-sm text-zinc-500">
                    <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> Generating summary…
                  </div>
                ) : (
                  <p className="text-zinc-300 leading-relaxed">
                    <HighlightText text={summary || ''} query={searchQuery} />
                  </p>
                )}
              </div>
            )}

            {/* Executive Summary */}
            <div className={`space-y-1.5 bg-zinc-950/40 rounded-xl border border-zinc-800/60 ${isFocusMode ? 'p-2 lg:col-span-2' : 'p-3'}`}>
            <h4 className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider font-mono">
              Overview & Track Record
              </h4>
              <p className="text-zinc-300 leading-relaxed">
                <HighlightText text={profile.bio} query={searchQuery} />
              </p>
            </div>

            {/* Survey Disciplines */}
            {profile.surveyTypes && profile.surveyTypes.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5 font-mono">
                  <Compass className="w-3.5 h-3.5 text-zinc-400" />
                  <span>Survey Focus</span>
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
                  <span>Certifications</span>
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
                  Skills
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

            {profile.geographicalExperience && profile.geographicalExperience.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5 font-mono">
                  <MapPin className="w-3.5 h-3.5 text-zinc-400" />
                  <span>Geographical Experience</span>
                </h4>
                <div className="flex flex-wrap gap-2">
                  {profile.geographicalExperience.map((place) => (
                    <span key={place} className="px-3 py-1.5 rounded-xl bg-zinc-900 border border-zinc-800 text-zinc-300 font-medium text-xs">
                      <HighlightText text={place} query={searchQuery} />
                    </span>
                  ))}
                </div>
              </div>
            )}

            {profile.systemsExperience && profile.systemsExperience.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5 font-mono">
                  <Layers className="w-3.5 h-3.5 text-zinc-400" />
                  <span>Systems Experience</span>
                </h4>
                <div className="flex flex-wrap gap-2">
                  {profile.systemsExperience.map((system) => (
                    <span key={system} className="px-3 py-1.5 rounded-xl bg-zinc-900 border border-zinc-800 text-zinc-300 font-medium text-xs">
                      <HighlightText text={system} query={searchQuery} />
                    </span>
                  ))}
                </div>
              </div>
            )}

            {profile.trainingQualifications && profile.trainingQualifications.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5 font-mono">
                  <GraduationCap className="w-3.5 h-3.5 text-zinc-400" />
                  <span>Training / Qualifications</span>
                </h4>
                <div className="flex flex-wrap gap-2">
                  {profile.trainingQualifications.map((item) => (
                    <span key={item} className="px-3 py-1.5 rounded-xl bg-zinc-900 border border-zinc-800 text-zinc-300 font-medium text-xs">
                      <HighlightText text={item} query={searchQuery} />
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
                  <span>Clients</span>
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
                  <span>Education</span>
                </h4>
                <p className="text-xs sm:text-sm text-zinc-300">{profile.education}</p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Sticky Bottom Action Bar */}
      <div className={`bg-zinc-950 border-t border-zinc-800 flex flex-wrap items-center justify-between gap-3 ${isFocusMode ? 'p-3 sm:p-4' : 'p-4'}`}>
        <div className="min-w-0 w-full sm:w-auto">
          <span className="text-xs sm:text-sm text-zinc-300 font-mono block truncate">{profile.email}</span>
          <span className="text-[11px] text-zinc-500 hidden sm:block">
            Press <kbd className="font-mono text-zinc-300">C</kbd> to copy email • <kbd className="font-mono text-zinc-300">F</kbd> toggle focus
          </span>
        </div>

        <div className="flex items-center justify-end gap-2 shrink-0 w-full sm:w-auto">
          <a
            href={
              profile.linkedinUrl ||
              `https://www.linkedin.com/search/results/all/?keywords=${encodeURIComponent(
                `${profile.name} Hydenlyne`
              )}`
            }
            target="_blank"
            rel="noopener noreferrer"
            aria-label={`Open ${profile.name} LinkedIn profile`}
            className="min-h-11 min-w-11 p-2.5 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-300 hover:text-white transition-colors inline-flex items-center justify-center"
            title="LinkedIn Profile"
          >
            <Linkedin className="w-4 h-4 text-[#0a66c2]" />
          </a>

          <button
            type="button"
            onClick={handleCopyEmail}
            aria-label={`Copy ${profile.name} email address`}
            className={`relative min-h-11 px-3.5 py-2 rounded-xl text-xs sm:text-sm font-medium flex items-center gap-1.5 transition-all duration-200 cursor-pointer overflow-hidden ${
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
              className="min-h-11 px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs sm:text-sm font-semibold flex items-center gap-1.5 transition-colors cursor-pointer shadow-md shadow-blue-950/30"
            >
              <Send className="w-4 h-4" />
              <span>Request mobilization</span>
            </button>
          ) : (
            <a
              href={`mailto:${profile.email}?subject=Hydenlyne%20Survey%20Deployment%20Inquiry%20-%20${encodeURIComponent(
                profile.title
              )}`}
              className="min-h-11 px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs sm:text-sm font-semibold flex items-center gap-1.5 transition-colors cursor-pointer shadow-md shadow-blue-950/30"
            >
              <Mail className="w-4 h-4" />
              <span>Request mobilization</span>
            </a>
          )}
        </div>
      </div>
    </div>

    {isRadarModalOpen && createPortal(
      <div
        className="ui-overlay-enter fixed inset-0 z-[100] flex items-center justify-center bg-zinc-950 p-3 sm:p-6"
        onClick={() => setIsRadarModalOpen(false)}
      >
        <div
          ref={radarDialogRef}
          className="ui-surface-enter w-full max-w-4xl max-h-[94vh] overflow-y-auto rounded-2xl border border-zinc-700 bg-zinc-900 p-4 sm:p-6 shadow-2xl"
          onClick={(event) => event.stopPropagation()}
          role="dialog"
          aria-modal="true"
          aria-label={`${profile.name} skills radar`}
        >
          <div className="mb-3 flex items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-semibold text-zinc-100">Skills Radar</h3>
              <p className="text-xs text-zinc-400">{profile.name} · Competency assessment</p>
            </div>
            <button
              type="button"
              onClick={() => setIsRadarModalOpen(false)}
              ref={radarCloseRef}
              className="rounded-xl bg-zinc-800 p-2 text-zinc-400 transition-colors hover:bg-zinc-700 hover:text-white"
              title="Close skills radar"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
          <CandidateSkillRadarChart profile={profile} size="lg" showLegend={true} />
          <div className="mt-4 rounded-xl border border-zinc-800 bg-zinc-950/50 p-4 text-xs text-zinc-400">
            <span className="mb-1 block font-mono text-[11px] font-semibold uppercase text-zinc-200">
              Methodology & Assessment Criteria
            </span>
            <p>
              Calculated dynamically from verified offshore track records, certifications, and technical proficiencies.
            </p>
          </div>
        </div>
      </div>,
      document.body,
    )}
    <ConfirmDialog
      open={isDeleteConfirmOpen}
      title={`Delete ${profile.name}?`}
      description="This permanently removes the specialist, their certifications, work history, and managed documents. This cannot be undone."
      confirmLabel={isDeleting ? 'Deleting…' : 'Delete permanently'}
      onConfirm={() => void handleDeleteCrew()}
      onCancel={() => !isDeleting && setIsDeleteConfirmOpen(false)}
    />
    </>
  );
};
