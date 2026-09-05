import { FC, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useMutation } from '@apollo/client';
import { useAccessibleDialog } from '../hooks/useAccessibleDialog';
import { useMenuKeyboardNav } from '../hooks/useMenuKeyboardNav';
import { motion, AnimatePresence } from 'motion/react';
import { UserProfile, SpecialistDocument } from '../types';
import { CREW_MEMBERS_QUERY, VERIFY_CERTIFICATION } from '../lib/queries';
import { HighlightText } from './HighlightText';
import { CertificationBadge } from './CertificationBadge';
import { DocumentVault } from './DocumentVault';
import { DocumentPreviewModal } from './DocumentPreviewModal';
import { CandidateSkillRadarChart } from './CandidateSkillRadarChart';
import { ConfirmDialog } from './ConfirmDialog';
import { DossierCollection } from './DossierCollection';
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
  CheckCircle2,
  XCircle,
  AlertCircle,
  FileText,
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
  onReviewDocument?: (docId: string, action: 'approve' | 'reject') => void | Promise<void>;
  canManageDocuments?: boolean;
  canRequestDocuments?: boolean;
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
  onReviewDocument,
  canManageDocuments = false,
  canRequestDocuments = false,
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
  const [skillsQuery, setSkillsQuery] = useState('');
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

  const [previewDoc, setPreviewDoc] = useState<SpecialistDocument | null>(null);
  const [actionCertId, setActionCertId] = useState<string | null>(null);
  const [localVerificationOverrides, setLocalVerificationOverrides] = useState<
    Record<string, { verificationStatus: string; status?: string }>
  >({});

  const [verifyMutation, { loading: isVerifying }] = useMutation(VERIFY_CERTIFICATION, {
    refetchQueries: [{ query: CREW_MEMBERS_QUERY, variables: { limit: 100, offset: 0 } }],
  });

  const handleVerify = async (certId: string, status: 'VERIFIED' | 'REJECTED') => {
    setActionCertId(certId);
    const newVerificationStatus = status === 'VERIFIED' ? 'verified' : 'rejected';
    const newLifecycleStatus = status === 'VERIFIED' ? 'valid' : 'pending_verification';

    setLocalVerificationOverrides((prev) => ({
      ...prev,
      [certId]: { verificationStatus: newVerificationStatus, status: newLifecycleStatus },
    }));

    try {
      const res = await verifyMutation({
        variables: { id: certId, status },
      });
      if (res.errors && res.errors.length > 0) {
        const firstError = res.errors[0];
        throw new Error(firstError?.message ?? 'Verification mutation returned errors');
      }
      onShowToast(status === 'VERIFIED' ? 'Certification verified' : 'Certification rejected');
    } catch (err: unknown) {
      setLocalVerificationOverrides((prev) => {
        const next = { ...prev };
        delete next[certId];
        return next;
      });
      const message = err instanceof Error ? err.message : 'Action failed';
      onShowToast(`Failed: ${message}`);
    } finally {
      setActionCertId(null);
    }
  };

  useEffect(() => {
    setIsMoreSectionsOpen(false);
    setIsHeaderActionsOpen(false);
    setSkillsQuery('');
    setLocalVerificationOverrides({});
    setPreviewDoc(null);
  }, [profile?.id]);

  useMenuKeyboardNav(
    isMoreSectionsOpen && !isRadarModalOpen,
    sectionMenuRef,
    sectionMenuTriggerRef,
    () => setIsMoreSectionsOpen(false),
  );

  useMenuKeyboardNav(
    isHeaderActionsOpen,
    headerActionsRef,
    headerActionsTriggerRef,
    () => setIsHeaderActionsOpen(false),
    true,
  );

  useAccessibleDialog(isRadarModalOpen, radarDialogRef, () => setIsRadarModalOpen(false));

  if (!profile) {
    return (
      <div className="h-full min-h-[460px] flex flex-col items-center justify-center p-8 text-center bg-surface/30 border border-border-subtle/60 rounded-[14px]">
        <div className="w-14 h-14 rounded-[14px] bg-surface border border-border-subtle flex items-center justify-center text-muted mb-3 shadow-inner">
          <Compass className="w-7 h-7 text-muted" />
        </div>
        <h3 className="text-sm font-semibold text-secondary">No Contractor Selected</h3>
        <p className="text-xs text-muted max-w-xs mt-1">
          Select a contractor from the list or press <kbd className="px-1.5 py-0.5 rounded bg-surface-raised border border-border-strong text-xs text-secondary font-mono">↑</kbd> <kbd className="px-1.5 py-0.5 rounded bg-surface-raised border border-border-strong text-xs text-secondary font-mono">↓</kbd> to review their dossier, skills radar, and compliance documents.
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
  const readableSummary = summary?.trim();
  const hasReadableSummary = Boolean(readableSummary && !readableSummary.startsWith('{') && !readableSummary.startsWith('['));
  const isSecondarySection = activeTab === 'systems';
  const secondarySectionLabel = activeTab === 'systems' ? 'Systems' : 'More';
  const hasSystemsCategories = Boolean(
    profile.systemsCategories &&
    Object.values(profile.systemsCategories).some((items) => items.length > 0)
  );
  const profileSkills = Array.from(new Set([...(profile.skills ?? []), ...(profile.expertise ?? [])]));
  const normalizedSkillsQuery = skillsQuery.trim().toLocaleLowerCase();
  const matchingSkills = normalizedSkillsQuery
    ? profileSkills.filter((skill) => skill.toLocaleLowerCase().includes(normalizedSkillsQuery))
    : profileSkills;
  const credentialCount = profile.certificationDetails?.length ?? profile.certifications?.length ?? 0;
  const indexedDocumentCount = documents.filter((document) => document.extractionStatus === 'extracted').length;
  const latestProject = [...(profile.workHistory ?? [])]
    .sort((left, right) => (right.startDate ?? '').localeCompare(left.startDate ?? ''))[0];
  const highlightedSkills = profileSkills.slice(0, 3);
  const sectionButtonClass = (isActive: boolean) => `min-h-11 px-3.5 py-1.5 rounded-lg font-medium transition-all duration-150 cursor-pointer flex items-center gap-1.5 ${
    isFocusMode ? 'text-xs sm:text-sm' : 'text-xs'
  } ${isActive ? 'bg-surface-raised text-primary shadow-xs ring-1 ring-border-strong font-semibold' : 'text-secondary hover:text-primary hover:bg-surface-raised/50'}`;

  const selectSecondarySection = (section: 'systems') => {
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
      className={`bg-surface border border-border-subtle rounded-[14px] text-primary flex flex-col overflow-hidden shadow-2xl transition-all duration-300 ${
        isFocusMode
          ? 'w-full h-full max-w-6xl mx-auto ring-1 ring-focus shadow-black/80 my-2'
          : 'h-full'
      }`}
    >
      {/* Focus Mode Navigation Banner */}
      {isFocusMode && (
        <div className="bg-canvas/90 border-b border-border-subtle px-6 py-3 flex items-center justify-between text-xs">
          <div className="flex items-center gap-2.5">
            <span className="flex h-2 w-2 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-action"></span>
            </span>
            <span className="font-semibold text-primary uppercase tracking-wider font-mono text-xs">
              Focused Contractor Workspace
            </span>
            {totalProfiles && totalProfiles > 1 && (
              <span className="text-secondary font-mono text-xs">
                ({(profileIndex ?? 0) + 1} of {totalProfiles})
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            {onPrevProfile && (
              <button
                type="button"
                onClick={onPrevProfile}
                className="min-h-11 px-3 py-1.5 rounded-lg bg-surface-raised hover:bg-surface-selected border border-border-strong text-primary hover:text-primary flex items-center gap-1 font-medium transition-colors cursor-pointer"
                title="Previous Contractor (Press Left Arrow)"
              >
                <ChevronLeft className="w-3.5 h-3.5" />
                <span>Prev</span>
              </button>
            )}
            {onNextProfile && (
              <button
                type="button"
                onClick={onNextProfile}
                className="min-h-11 px-3 py-1.5 rounded-lg bg-surface-raised hover:bg-surface-selected border border-border-strong text-primary hover:text-primary flex items-center gap-1 font-medium transition-colors cursor-pointer"
                title="Next Contractor (Press Right Arrow)"
              >
                <span>Next</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            )}
            {onToggleFocusMode && !isFocusMode && (
              <button
                type="button"
                onClick={onToggleFocusMode}
                className="px-3.5 py-1.5 rounded-lg bg-surface-raised hover:bg-surface-selected border border-border-strong text-primary hover:text-primary flex items-center gap-1 font-medium transition-colors cursor-pointer ml-1"
                title="Exit focus mode back to Split-Pane"
              >
                <Minimize2 className="w-3.5 h-3.5" />
                <span>Exit Focus</span>
              </button>
            )}
          </div>
        </div>
      )}

      {/* Compact High-Efficiency Header Profile Section */}
      <div className={`border-b border-border-subtle bg-canvas/70 shrink-0 ${isFocusMode ? 'p-3' : 'p-3.5'}`}>
        <div className="flex flex-col items-stretch gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex min-w-0 items-center gap-3">
            <div className="relative shrink-0">
              <img
                src={profile.avatar}
                alt={profile.name}
                referrerPolicy="no-referrer"
                className={`rounded-xl object-cover ring-1 ring-border-subtle/80 shadow-sm transition-all ${
                  isFocusMode ? 'w-14 h-14 sm:w-16 sm:h-16' : 'w-12 h-12'
                }`}
              />
              {isAvailableNow && (
                <span
                  className="absolute -bottom-1 -right-1 h-3.5 w-3.5 rounded-full bg-positive ring-2 ring-surface shadow-xs"
                  title="Ready for deployment immediately"
                />
              )}
            </div>

            <div className="min-w-0 space-y-1">
              <div className="flex items-center gap-2 flex-wrap">
                <h2 className={`font-bold text-primary tracking-tight ${isFocusMode ? 'text-lg sm:text-xl' : 'text-base'}`}>
                  <HighlightText text={profile.name} query={searchQuery} />
                </h2>
                {profile.isHighlyRecommended && (
                  <span className="badge-accent inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium">
                    <BadgeCheck className="w-3.5 h-3.5 text-accent" />
                    <span>Verified</span>
                  </span>
                )}
                {profile.dayRate && (
                  <span className="font-mono text-xs font-semibold text-positive bg-surface-raised px-2 py-0.5 rounded-md border border-border-subtle">
                    £{profile.dayRate}/d
                  </span>
                )}
              </div>

              <div className="flex items-center gap-2 text-xs text-secondary flex-wrap">
                <span className="font-medium text-primary">{profile.title}</span>
                <span className="text-muted/60">•</span>
                <span className="flex items-center gap-1">
                  <MapPin className="w-3 h-3 text-secondary" />
                  <HighlightText text={profile.location.split(',')[0] ?? profile.location} query={searchQuery} />
                </span>
                <span className="text-muted/60">•</span>
                <span className="text-accent font-medium">{profile.department}</span>
                <span className="text-muted/60">•</span>
                <span className="font-mono text-secondary">{profile.yearsOfExperience}y exp</span>
                {profile.rating && (
                  <>
                    <span className="text-muted/60">•</span>
                    <span className="font-mono text-warning">★ {profile.rating.toFixed(1)}</span>
                  </>
                )}
              </div>
            </div>
          </div>

          <div className="flex items-center justify-end gap-2 shrink-0">
            {onToggleFocusMode && (
              <button
                type="button"
                onClick={onToggleFocusMode}
                className={`min-h-11 min-w-11 p-2 rounded-lg border transition-colors cursor-pointer inline-flex items-center justify-center ${
                  isFocusMode
                    ? 'bg-action border-border-strong text-on-action shadow-xs'
                    : 'bg-surface-raised/80 border-border-strong text-secondary hover:text-primary'
                }`}
                title={isFocusMode ? 'Exit focus mode (Split View)' : 'Open focused contractor view (Press F)'}
                aria-label={isFocusMode ? 'Exit focused contractor view' : 'Open focused contractor view'}
              >
                {isFocusMode ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
              </button>
            )}

            <button
              type="button"
              onClick={() => onToggleBookmark(profile.id)}
              aria-label={isBookmarked ? `Remove ${profile.name} from shortlist` : `Save ${profile.name} to shortlist`}
              className={`min-h-11 px-3 py-1.5 rounded-lg border transition-colors cursor-pointer inline-flex items-center gap-1.5 text-xs font-medium shadow-xs ${
                isBookmarked
                  ? 'bg-action text-on-action border-action'
                  : 'bg-surface-raised/80 border-border-strong text-primary hover:bg-surface-raised'
              }`}
              title={isBookmarked ? 'Saved in shortlist (Press S)' : 'Save to shortlist (Press S)'}
            >
              {isBookmarked ? (
                <>
                  <BookmarkCheck className="w-4 h-4 fill-on-action" />
                  <span>Saved</span>
                </>
              ) : (
                <>
                  <Bookmark className="w-4 h-4" />
                  <span>Shortlist</span>
                </>
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
                  className={`inline-flex min-h-11 min-w-11 items-center justify-center rounded-lg border transition-colors cursor-pointer ${isHeaderActionsOpen ? 'border-border-strong bg-surface-raised text-primary' : 'border-border-strong bg-surface-raised/80 text-secondary hover:text-primary'}`}
                >
                  <Ellipsis className="h-4 w-4" aria-hidden="true" />
                </button>
                {isHeaderActionsOpen && (
                  <div role="menu" aria-label={`Dossier actions for ${profile.name}`} className="absolute right-0 top-11 z-30 w-56 rounded-[14px] border border-border-strong/80 bg-surface/95 p-1.5 shadow-2xl shadow-black/40 backdrop-blur-xl">
                    {onToggleCompare && (
                      <button type="button" role="menuitem" onClick={() => runHeaderAction(() => onToggleCompare(profile))} className="flex min-h-10 w-full items-center gap-3 rounded-lg px-3 text-left text-sm text-secondary hover:bg-surface-raised hover:text-primary">
                        <Scale className={`h-4 w-4 ${isCompared ? 'text-accent' : ''}`} />
                        {isCompared ? 'Remove from compare' : 'Add to compare'}
                      </button>
                    )}
                    {onPrintDossier && (
                      <button type="button" role="menuitem" onClick={() => runHeaderAction(() => onPrintDossier(profile))} className="flex min-h-10 w-full items-center gap-3 rounded-lg px-3 text-left text-sm text-secondary hover:bg-surface-raised hover:text-primary">
                        <Printer className="h-4 w-4" /> Print dossier
                      </button>
                    )}
                    {canDeleteCrew && onDeleteCrew && (
                      <button type="button" role="menuitem" onClick={() => runHeaderAction(() => setIsDeleteConfirmOpen(true))} className="flex min-h-10 w-full items-center gap-3 rounded-lg px-3 text-left text-sm text-danger hover:bg-danger-soft/70 hover:text-danger">
                        <Trash2 className="h-4 w-4" /> Delete contractor
                      </button>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Navigation Tabs Bar - Slim & Flush */}
        <div className="mt-2.5 pt-2 border-t border-border-subtle/50">
          <div role="group" aria-label={`${profile.name} dossier sections`} className="flex items-center gap-1 flex-wrap">
            <button
              type="button"
              aria-pressed={activeTab === 'dossier'}
              onClick={() => setActiveTab('dossier')}
              className={sectionButtonClass(activeTab === 'dossier')}
            >
              <Layers className="w-3.5 h-3.5 text-secondary" />
              <span>Overview</span>
            </button>

            <button
              type="button"
              aria-pressed={activeTab === 'experience'}
              onClick={() => setActiveTab('experience')}
              className={sectionButtonClass(activeTab === 'experience')}
            >
              <BriefcaseBusiness className="w-3.5 h-3.5 text-secondary" />
              <span>Experience</span>
            </button>

            <button
              type="button"
              aria-pressed={activeTab === 'credentials'}
              onClick={() => setActiveTab('credentials')}
              className={sectionButtonClass(activeTab === 'credentials')}
            >
              <GraduationCap className="w-3.5 h-3.5 text-secondary" />
              <span>Credentials</span>
            </button>

            <button
              type="button"
              aria-pressed={activeTab === 'expertise'}
              onClick={() => setActiveTab('expertise')}
              className={sectionButtonClass(activeTab === 'expertise')}
            >
              <Activity className="w-3.5 h-3.5 text-secondary" />
              <span>Skills</span>
              <span className="px-1.5 py-0.2 rounded-md bg-surface border border-border-subtle text-secondary font-mono text-xs">
                {profileSkills.length}
              </span>
            </button>

            <button
              type="button"
              aria-pressed={activeTab === 'vault'}
              onClick={() => setActiveTab('vault')}
              className={sectionButtonClass(activeTab === 'vault')}
            >
              <FileCheck className="w-3.5 h-3.5 text-secondary" />
              <span>Documents</span>
              <span className="px-1.5 py-0.2 rounded-md bg-surface border border-border-subtle text-secondary font-mono text-xs">
                {documents.length}
              </span>
            </button>

            <div ref={sectionMenuRef} className="relative ml-auto">
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
                <div role="menu" aria-label="More dossier sections" className="absolute right-0 top-12 z-30 w-52 rounded-[14px] border border-border-strong/80 bg-surface/95 p-1.5 shadow-2xl shadow-black/40 backdrop-blur-xl">
                  <button type="button" role="menuitem" onClick={() => selectSecondarySection('systems')} className="flex min-h-11 w-full items-center gap-3 rounded-lg px-3 text-left text-sm text-secondary hover:bg-surface-raised hover:text-primary">
                    <Layers className="h-4 w-4" /> Systems experience
                  </button>
                  <button type="button" role="menuitem" onClick={() => setIsRadarModalOpen(true)} className="flex min-h-11 w-full items-center gap-3 rounded-lg px-3 text-left text-sm text-secondary hover:bg-surface-raised hover:text-primary">
                    <Activity className="h-4 w-4" /> Competency radar
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Scrollable Dossier Content */}
      <div ref={contentRef} className={`${isFocusMode ? 'focus-dossier-content overflow-y-auto p-2 sm:p-3 flex-1 text-xs' : 'overflow-y-auto p-5 flex-1 text-xs'} text-primary min-h-0`}>
        {activeTab === 'vault' ? (
          <DocumentVault
            profile={profile}
            documents={documents}
            onAddDocument={() => onAddDocument?.()}
            onRemoveDocument={(docId) => onRemoveDocument?.(docId)}
            onReviewDocument={onReviewDocument}
            canManageDocuments={canManageDocuments}
            canRequestDocuments={canRequestDocuments}
            onShowToast={onShowToast}
          />
        ) : activeTab === 'radar' ? (
          <div className="space-y-4">
            <CandidateSkillRadarChart
              profile={profile}
              size={isFocusMode ? 'lg' : 'md'}
              showLegend={true}
            />
            <div className="bg-canvas/50 p-4 rounded-[10px] border border-border-subtle/70 text-xs text-secondary space-y-1.5">
              <span className="font-semibold text-primary block font-mono text-xs uppercase">
                Methodology & Assessment Criteria
              </span>
              <p>
                Calculated dynamically from verified offshore track records, certifications (BOSIET, GWO, STCW), and technical proficiencies in <strong className="text-secondary">Geotechnical</strong>, <strong className="text-secondary">Environmental</strong>, and <strong className="text-secondary">Data Analysis</strong>.
              </p>
            </div>
          </div>
        ) : activeTab === 'experience' ? (
          <div className="space-y-4">
            <section className="space-y-2">
              <h3 className="text-xs font-semibold text-secondary uppercase tracking-wider font-mono">Track Record & Clients</h3>
              <p className="text-secondary leading-relaxed">{profile.yearsOfExperience} years of offshore experience.</p>
              {profile.pastCompanies && profile.pastCompanies.length > 0 && <DossierCollection items={profile.pastCompanies} itemLabel="clients" initialItems={8} renderItems={(companies) => <div className="flex flex-wrap gap-2">{companies.map((company) => <span key={company} className="px-3 py-1.5 rounded-[10px] bg-surface border border-border-subtle text-secondary">{company}</span>)}</div>} />}
            </section>
            {profile.workHistory && profile.workHistory.length > 0 && (
              <section className="space-y-2">
                <h3 className="text-xs font-semibold text-secondary uppercase tracking-wider font-mono">Recent Projects</h3>
                <DossierCollection
                  items={profile.workHistory}
                  itemLabel="projects"
                  renderItems={(projects) => (
                    <div className="overflow-x-auto rounded-[10px] border border-border-subtle">
                      <table className="min-w-full text-sm">
                        <thead className="bg-canvas/60 text-xs font-semibold text-secondary uppercase tracking-wider">
                          <tr><th className="px-3 py-2 text-left">Year</th><th className="px-3 py-2 text-left">Client</th><th className="px-3 py-2 text-left">Country</th><th className="px-3 py-2 text-left">Survey Type</th><th className="px-3 py-2 text-left">Position</th></tr>
                        </thead>
                        <tbody className="divide-y divide-border-subtle">
                          {projects.map((row, index) => (
                            <tr key={row.id ?? `${row.clientName ?? 'project'}-${index}`} className="text-primary">
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
                  )}
                />
              </section>
            )}
            {profile.geographicalExperience && profile.geographicalExperience.length > 0 && <section className="space-y-2"><h3 className="text-xs font-semibold text-secondary uppercase tracking-wider font-mono">Geographical Experience</h3><DossierCollection items={profile.geographicalExperience} itemLabel="locations" initialItems={8} renderItems={(locations) => <div className="flex flex-wrap gap-2">{locations.map((place) => <span key={place} className="px-3 py-1.5 rounded-[10px] bg-surface border border-border-subtle text-secondary"><HighlightText text={place} query={searchQuery} /></span>)}</div>} /></section>}
            {profile.surveyTypes && profile.surveyTypes.length > 0 && <section className="space-y-2"><h3 className="text-xs font-semibold text-secondary uppercase tracking-wider font-mono">Survey Focus</h3><DossierCollection items={profile.surveyTypes} itemLabel="survey disciplines" initialItems={8} renderItems={(surveyTypes) => <div className="flex flex-wrap gap-2">{surveyTypes.map((type) => <span key={type} className="px-3 py-1.5 rounded-[10px] bg-surface border border-border-subtle text-secondary">{type}</span>)}</div>} /></section>}
          </div>
        ) : activeTab === 'systems' ? (
          <div className="space-y-4">
            {hasSystemsCategories && profile.systemsCategories ? (
              (Object.entries(profile.systemsCategories) as [string, string[]][]).map(
                ([category, items]) => items.length > 0 && (
                  <section key={category} className="space-y-2">
                    <h3 className="text-xs font-semibold text-secondary uppercase tracking-wider font-mono capitalize">{category}</h3>
                    <DossierCollection
                      items={items}
                      itemLabel="systems"
                      initialItems={8}
                      renderItems={(systems) => (
                        <div className="flex flex-wrap gap-2">
                          {systems.map((system) => (
                            <span key={system} className="px-3 py-1.5 rounded-[10px] bg-surface border border-border-subtle text-secondary font-medium text-xs">
                              {system}
                            </span>
                          ))}
                        </div>
                      )}
                    />
                  </section>
                )
              )
            ) : (
              <p className="text-muted">No systems experience was found in the CV.</p>
            )}
          </div>
        ) : activeTab === 'expertise' ? (
          <div className="space-y-4">
            <section className="space-y-3" aria-labelledby="skills-heading">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
                <div>
                  <h3 id="skills-heading" className="text-xs font-semibold uppercase tracking-wider text-secondary font-mono">Skills & technical competencies</h3>
                  <p className="mt-1 text-sm text-secondary">{matchingSkills.length} of {profileSkills.length} skills shown</p>
                </div>
                <label className="block sm:w-72">
                  <span className="sr-only">Find a skill in {profile.name}'s profile</span>
                  <input
                    type="search"
                    value={skillsQuery}
                    onChange={(event) => setSkillsQuery(event.target.value)}
                    placeholder="Find a skill, tool, or competency"
                    className="min-h-11 w-full rounded-[10px] border border-border-strong bg-canvas px-3 text-sm text-primary placeholder:text-muted focus:outline-hidden focus:ring-2 focus:ring-focus"
                  />
                </label>
              </div>

              {matchingSkills.length > 0 ? (
                <DossierCollection
                  items={matchingSkills}
                  itemLabel="skills"
                  initialItems={normalizedSkillsQuery ? matchingSkills.length : 8}
                  renderItems={(skills) => (
                    <ul className="grid grid-cols-1 gap-2 lg:grid-cols-2">
                      {skills.map((skill) => (
                        <li key={skill} className="flex min-h-11 items-start gap-2 rounded-[10px] border border-border-subtle bg-canvas/60 px-3 py-2 text-sm leading-5 text-secondary">
                          <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" aria-hidden="true" />
                          <HighlightText text={skill} query={skillsQuery} />
                        </li>
                      ))}
                    </ul>
                  )}
                />
              ) : (
                <div className="rounded-[10px] border border-border-subtle bg-canvas/60 px-3 py-4 text-sm text-secondary">No skills match “{skillsQuery}”.</div>
              )}
            </section>
          </div>
        ) : activeTab === 'credentials' ? (
          <div className="space-y-4">
            {(profile.countryOfResidence || profile.dateOfBirth || profile.gender || (profile.languages && profile.languages.length > 0) || profile.flyingPoint || profile.nationality) && (
              <section className="space-y-2">
                <h3 className="text-xs font-semibold text-secondary uppercase tracking-wider font-mono">Personal Information</h3>
                <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-2 text-sm">
                  {profile.nationality && <div className="flex justify-between gap-2"><dt className="text-muted">Nationality</dt><dd className="text-primary text-right">{profile.nationality}</dd></div>}
                  {profile.countryOfResidence && <div className="flex justify-between gap-2"><dt className="text-muted">Country of residence</dt><dd className="text-primary text-right">{profile.countryOfResidence}</dd></div>}
                  {profile.dateOfBirth && <div className="flex justify-between gap-2"><dt className="text-muted">Date of birth</dt><dd className="text-primary text-right">{profile.dateOfBirth}</dd></div>}
                  {profile.gender && <div className="flex justify-between gap-2"><dt className="text-muted">Gender</dt><dd className="text-primary text-right">{profile.gender}</dd></div>}
                  {profile.flyingPoint && <div className="flex justify-between gap-2"><dt className="text-muted">Flying point</dt><dd className="text-primary text-right">{profile.flyingPoint}</dd></div>}
                  {profile.languages && profile.languages.length > 0 && <div className="sm:col-span-2 flex justify-between gap-2"><dt className="text-muted">Languages</dt><dd className="text-primary text-right">{profile.languages.join(', ')}</dd></div>}
                </dl>
              </section>
            )}
            {profile.certifications && profile.certifications.length > 0 && <section className="space-y-2"><h3 className="text-xs font-semibold text-secondary uppercase tracking-wider font-mono">Certifications & Tickets</h3><DossierCollection items={profile.certifications} itemLabel="certifications" renderItems={(certifications) => <div className="flex flex-wrap gap-2">{certifications.map((cert) => <CertificationBadge key={cert} certification={cert} size="md" />)}</div>} /></section>}
            {profile.certificationDetails && profile.certificationDetails.length > 0 && (
              <section className="space-y-2.5">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-semibold text-secondary uppercase tracking-wider font-mono">
                    Completion & Expiry
                  </h3>
                  <span className="text-xs text-muted font-mono">
                    {profile.certificationDetails.length} recorded
                  </span>
                </div>
                <DossierCollection
                  items={profile.certificationDetails}
                  itemLabel="credentials"
                  renderItems={(certifications) => (
                    <div className="space-y-2">
                      {certifications.map((cert) => {
                        const effectiveVerification =
                          localVerificationOverrides[cert.id]?.verificationStatus ??
                          cert.verificationStatus ??
                          'unverified';
                        const effectiveStatus =
                          localVerificationOverrides[cert.id]?.status ?? cert.status;

                        const linkedDoc = documents.find(
                          (d) =>
                            d.id === cert.documentRef ||
                            (d.category === 'certificate' &&
                              d.title.toLowerCase().includes(cert.name.toLowerCase())),
                        );

                        return (
                          <div
                            key={cert.id}
                            className="rounded-[10px] border border-border-subtle bg-canvas/40 p-3 transition-colors hover:border-border-strong"
                          >
                            <div className="flex flex-wrap items-start justify-between gap-2.5">
                              <div className="space-y-1 min-w-0 flex-1">
                                <div className="flex items-center gap-2 flex-wrap">
                                  <span className="font-medium text-sm text-primary">
                                    {cert.name}
                                  </span>
                                  {cert.certNumber && (
                                    <span className="font-mono text-xs px-1.5 py-0.5 rounded bg-surface-raised text-secondary border border-border-subtle">
                                      #{cert.certNumber}
                                    </span>
                                  )}
                                  {effectiveVerification === 'verified' ? (
                                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium font-mono bg-positive/10 text-positive border border-positive/20">
                                      <CheckCircle2 className="w-3 h-3" />
                                      Verified
                                    </span>
                                  ) : effectiveVerification === 'rejected' ? (
                                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium font-mono bg-negative/10 text-negative border border-negative/20">
                                      <XCircle className="w-3 h-3" />
                                      Rejected
                                    </span>
                                  ) : (
                                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium font-mono bg-warning/10 text-warning border border-warning/20">
                                      <AlertCircle className="w-3 h-3" />
                                      Pending Verification
                                    </span>
                                  )}
                                  {effectiveStatus === 'expired' && (
                                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium font-mono bg-negative/10 text-negative border border-negative/20">
                                      Expired
                                    </span>
                                  )}
                                  {effectiveStatus === 'expiring_soon' && (
                                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium font-mono bg-warning/10 text-warning border border-warning/20">
                                      Expiring Soon
                                    </span>
                                  )}
                                </div>

                                <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-muted">
                                  {cert.issuingBody && (
                                    <span>
                                      Issued by{' '}
                                      <strong className="text-secondary font-normal">
                                        {cert.issuingBody}
                                      </strong>
                                    </span>
                                  )}
                                  <span>
                                    {cert.issueDate ? `Completed ${cert.issueDate}` : 'Date not recorded'}
                                  </span>
                                  <span>
                                    {cert.expiryDate ? `Expires ${cert.expiryDate}` : 'No expiry recorded'}
                                  </span>
                                </div>
                              </div>

                              <div className="flex items-center gap-2 shrink-0">
                                {linkedDoc && (
                                  <button
                                    type="button"
                                    onClick={() => setPreviewDoc(linkedDoc)}
                                    className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-lg border border-border-subtle bg-surface hover:bg-surface-raised text-secondary hover:text-primary transition-colors focus-visible:ring-2 focus-visible:ring-focus cursor-pointer"
                                    title={`View backing document (${linkedDoc.fileName})`}
                                  >
                                    <FileText className="w-3.5 h-3.5 text-accent" />
                                    <span>View Proof</span>
                                  </button>
                                )}

                                {canManageDocuments && (
                                  <div className="flex items-center gap-1">
                                    {effectiveVerification !== 'verified' && (
                                      <button
                                        type="button"
                                        disabled={isVerifying && actionCertId === cert.id}
                                        onClick={() => void handleVerify(cert.id, 'VERIFIED')}
                                        className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded-lg bg-positive/15 text-positive hover:bg-positive/25 border border-positive/30 transition-colors focus-visible:ring-2 focus-visible:ring-focus disabled:opacity-50 cursor-pointer"
                                        title="Verify this certification"
                                      >
                                        {isVerifying && actionCertId === cert.id ? (
                                          <Loader2 className="w-3 h-3 animate-spin" />
                                        ) : (
                                          <CheckCircle2 className="w-3 h-3" />
                                        )}
                                        <span>Verify</span>
                                      </button>
                                    )}

                                    {effectiveVerification !== 'rejected' && (
                                      <button
                                        type="button"
                                        disabled={isVerifying && actionCertId === cert.id}
                                        onClick={() => void handleVerify(cert.id, 'REJECTED')}
                                        className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded-lg bg-surface hover:bg-negative/10 text-muted hover:text-negative border border-border-subtle hover:border-negative/30 transition-colors focus-visible:ring-2 focus-visible:ring-focus disabled:opacity-50 cursor-pointer"
                                        title="Reject this certification"
                                      >
                                        <XCircle className="w-3 h-3" />
                                        <span>Reject</span>
                                      </button>
                                    )}
                                  </div>
                                )}
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                />
              </section>
            )}
            {profile.trainingDetails && profile.trainingDetails.length > 0 && <section className="space-y-2"><h3 className="text-xs font-semibold text-secondary uppercase tracking-wider font-mono">Training / Qualifications</h3><DossierCollection items={profile.trainingDetails} itemLabel="qualifications" renderItems={(training) => <div className="space-y-2">{training.map((item) => <div key={item.id} className="flex flex-wrap items-center justify-between gap-2 rounded-[10px] border border-border-subtle bg-canvas/40 px-3 py-2"><div className="flex flex-col"><span className="text-primary">{item.name}</span>{item.location && <span className="text-xs text-muted">{item.location}</span>}</div><span className="text-muted text-sm">{item.completedDate ? `Completed ${item.completedDate.slice(0, 4)}` : 'Completion date not recorded'}{item.expiryDate ? ` · Expires ${item.expiryDate.slice(0, 4)}` : ''}</span></div>)}</div>} /></section>}
            {profile.education && <section><h3 className="text-xs font-semibold text-secondary uppercase tracking-wider font-mono">Education</h3><p className="mt-1 text-secondary">{profile.education}</p></section>}
          </div>
        ) : (
          <div className={isFocusMode ? 'grid grid-cols-1 lg:grid-cols-2 gap-2.5' : 'space-y-3'}>
            {/* Quick Context Strip */}
            <div className={`fit-summary flex items-start gap-3 rounded-[12px] p-3 border border-border-subtle/80 bg-surface-raised/30 ${isFocusMode ? 'lg:col-span-2' : ''}`}>
              <div className="p-1.5 rounded-lg bg-surface-raised text-primary shrink-0 mt-0.5">
                <Sparkles className="h-3.5 w-3.5 text-accent" aria-hidden="true" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-xs font-semibold uppercase tracking-wider font-mono text-secondary">
                  Why this contractor
                </p>
                <p className="mt-1 text-xs leading-relaxed text-secondary">
                  {profile.name} brings <strong className="font-semibold text-primary">{profile.yearsOfExperience} years</strong> of offshore experience in {profile.department.toLowerCase()} and is {isAvailableNow ? 'available for immediate mobilization' : profile.availability.toLowerCase()}.
                </p>
              </div>
            </div>

            {/* AI Summary — generated on first profile view, cached after
                that (see backend/docs/cv-ingestion-pipeline.md). Distinct
                from "Overview & Track Record" below: this is a synthesized,
                recruiter-facing overview pulling together certs/availability/
                experience, not the consultant's own CV wording. */}
            {(summaryLoading || hasReadableSummary) && (
              <div className={`space-y-1.5 bg-canvas/40 rounded-[10px] border border-border-subtle/60 ${isFocusMode ? 'p-2 lg:col-span-2' : 'p-3'}`}>
                <h4 className="text-xs font-semibold text-secondary uppercase tracking-wider font-mono flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-secondary" aria-hidden="true" />
                  AI Summary
                </h4>
                {summaryLoading ? (
                  <div className="flex items-center gap-2 text-sm text-muted">
                    <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> Generating summary…
                  </div>
                ) : (
                  <p className="text-secondary leading-relaxed">
                    <HighlightText text={readableSummary || ''} query={searchQuery} />
                  </p>
                )}
              </div>
            )}

            {/* Executive Summary */}
            <div className={`space-y-1.5 bg-canvas/40 rounded-[10px] border border-border-subtle/60 ${isFocusMode ? 'p-2 lg:col-span-2' : 'p-3'}`}>
            <h4 className="text-xs font-semibold text-secondary uppercase tracking-wider font-mono">
              Overview & Track Record
              </h4>
              <p className="text-secondary leading-relaxed">
                <HighlightText text={profile.bio} query={searchQuery} />
              </p>
            </div>

            <section aria-label="At a glance" className={`grid grid-cols-1 gap-2.5 sm:grid-cols-3 ${isFocusMode ? 'lg:col-span-2' : ''}`}>
              <button
                type="button"
                onClick={() => setActiveTab('credentials')}
                className="group rounded-[12px] border border-border-subtle bg-surface-raised/40 p-3.5 text-left transition-all duration-200 hover:bg-surface-raised/80 hover:border-border-strong focus:outline-hidden focus:ring-2 focus:ring-focus cursor-pointer"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold uppercase tracking-wider text-muted font-mono">Deployment</span>
                  <span className={`w-2 h-2 rounded-full ${isAvailableNow ? 'bg-positive' : 'bg-surface-selected'}`} />
                </div>
                <span className={`mt-2 block text-sm font-semibold tracking-tight ${isAvailableNow ? 'text-positive' : 'text-primary'}`}>{profile.availability}</span>
                <span className="mt-1 block text-xs text-secondary">{credentialCount} credentials · {documents.length} docs{indexedDocumentCount > 0 ? ` · ${indexedDocumentCount} verified` : ''}</span>
              </button>

              <button
                type="button"
                onClick={() => setActiveTab('expertise')}
                className="group rounded-[12px] border border-border-subtle bg-surface-raised/40 p-3.5 text-left transition-all duration-200 hover:bg-surface-raised/80 hover:border-border-strong focus:outline-hidden focus:ring-2 focus:ring-focus cursor-pointer"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold uppercase tracking-wider text-muted font-mono">Strengths</span>
                  <span className="text-xs font-mono text-muted">{profileSkills.length}</span>
                </div>
                <span className="mt-2 block text-sm font-semibold tracking-tight text-primary">{profileSkills.length} Core Skills</span>
                <span className="mt-1 line-clamp-2 block text-xs leading-relaxed text-secondary">{highlightedSkills.length > 0 ? highlightedSkills.join(' · ') : 'No skills extracted yet'}</span>
              </button>

              <button
                type="button"
                onClick={() => setActiveTab('experience')}
                className="group rounded-[12px] border border-border-subtle bg-surface-raised/40 p-3.5 text-left transition-all duration-200 hover:bg-surface-raised/80 hover:border-border-strong focus:outline-hidden focus:ring-2 focus:ring-focus cursor-pointer"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold uppercase tracking-wider text-muted font-mono">Track Record</span>
                  <span className="text-xs font-mono text-muted">{profile.workHistory?.length ?? 0}</span>
                </div>
                <span className="mt-2 block text-sm font-semibold tracking-tight text-primary">{profile.workHistory?.length ?? 0} Projects · {profile.geographicalExperience?.length ?? 0} Regions</span>
                <span className="mt-1 block truncate text-xs text-secondary">{latestProject ? `${latestProject.clientName ?? 'Recent project'} · ${latestProject.role ?? latestProject.projectType ?? 'Role recorded'}` : 'No project history extracted yet'}</span>
              </button>
            </section>

            {/* Survey Disciplines */}
            {profile.surveyTypes && profile.surveyTypes.length > 0 && (
              <div className="space-y-2 pt-1">
                <h4 className="text-xs font-semibold text-secondary uppercase tracking-wider flex items-center gap-1.5 font-mono">
                  <Compass className="w-3.5 h-3.5 text-secondary" />
                  <span>Survey Focus</span>
                </h4>
                <div className="flex flex-wrap gap-1.5">
                  {profile.surveyTypes.map((type) => (
                    <span
                      key={type}
                      className="px-2.5 py-1 rounded-md bg-surface-raised/60 border border-border-subtle text-secondary font-medium text-xs hover:border-border-strong transition-colors"
                    >
                      <HighlightText text={type} query={searchQuery} />
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Offshore Safety Certifications with Tooltips */}
            {!isFocusMode && profile.certifications && profile.certifications.length > 0 && (
              <div className="space-y-2 pt-1">
                <h4 className="text-xs font-semibold text-secondary uppercase tracking-wider flex items-center gap-1.5 font-mono">
                  <ShieldCheck className="w-3.5 h-3.5 text-secondary" />
                  <span>Certifications</span>
                </h4>
                <div className="flex flex-wrap gap-2">
                  {profile.certifications.map((cert) => (
                    <CertificationBadge key={cert} certification={cert} size={isFocusMode ? 'lg' : 'md'} />
                  ))}
                </div>
              </div>
            )}

            {!isFocusMode && profile.geographicalExperience && profile.geographicalExperience.length > 0 && (
              <div className="space-y-2 pt-1">
                <h4 className="text-xs font-semibold text-secondary uppercase tracking-wider flex items-center gap-1.5 font-mono">
                  <MapPin className="w-3.5 h-3.5 text-secondary" />
                  <span>Geographical Experience</span>
                </h4>
                <div className="flex flex-wrap gap-1.5">
                  {profile.geographicalExperience.map((place) => (
                    <span key={place} className="px-2.5 py-1 rounded-md bg-surface-raised/60 border border-border-subtle text-secondary font-medium text-xs hover:border-border-strong transition-colors">
                      <HighlightText text={place} query={searchQuery} />
                    </span>
                  ))}
                </div>
              </div>
            )}

            {!isFocusMode && profile.systemsExperience && profile.systemsExperience.length > 0 && (
              <div className="space-y-2 pt-1">
                <h4 className="text-xs font-semibold text-secondary uppercase tracking-wider flex items-center gap-1.5 font-mono">
                  <Layers className="w-3.5 h-3.5 text-secondary" />
                  <span>Systems Experience</span>
                </h4>
                <div className="flex flex-wrap gap-1.5">
                  {profile.systemsExperience.map((system) => (
                    <span key={system} className="px-2.5 py-1 rounded-md bg-surface-raised/60 border border-border-subtle text-secondary font-medium text-xs hover:border-border-strong transition-colors">
                      <HighlightText text={system} query={searchQuery} />
                    </span>
                  ))}
                </div>
              </div>
            )}

            {!isFocusMode && profile.trainingQualifications && profile.trainingQualifications.length > 0 && (
              <div className="space-y-2 pt-1">
                <h4 className="text-xs font-semibold text-secondary uppercase tracking-wider flex items-center gap-1.5 font-mono">
                  <GraduationCap className="w-3.5 h-3.5 text-secondary" />
                  <span>Training / Qualifications</span>
                </h4>
                <div className="flex flex-wrap gap-1.5">
                  {profile.trainingQualifications.map((item) => (
                    <span key={item} className="px-2.5 py-1 rounded-md bg-surface-raised/60 border border-border-subtle text-secondary font-medium text-xs hover:border-border-strong transition-colors">
                      <HighlightText text={item} query={searchQuery} />
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Past Operators / Clients */}
            {!isFocusMode && profile.pastCompanies && profile.pastCompanies.length > 0 && (
              <div className="space-y-2 pt-1">
                <h4 className="text-xs font-semibold text-secondary uppercase tracking-wider flex items-center gap-1.5 font-mono">
                  <Building className="w-3.5 h-3.5 text-secondary" />
                  <span>Clients</span>
                </h4>
                <div className="flex flex-wrap gap-1.5">
                  {profile.pastCompanies.map((comp) => (
                    <span
                      key={comp}
                      className="px-2.5 py-1 rounded-md bg-surface-raised/60 border border-border-subtle text-secondary text-xs hover:border-border-strong transition-colors"
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
                <h4 className="text-xs font-semibold text-secondary uppercase tracking-wider flex items-center gap-1.5 font-mono">
                  <GraduationCap className="w-3.5 h-3.5 text-secondary" />
                  <span>Education</span>
                </h4>
                <p className="text-xs sm:text-sm text-secondary">{profile.education}</p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Sticky Bottom Action Bar */}
      <div className={`bg-canvas border-t border-border-subtle flex flex-wrap items-center justify-between gap-3 ${isFocusMode ? 'p-3 sm:p-4' : 'p-4'}`}>
        <div className="min-w-0 w-full sm:w-auto">
          <span className="text-xs sm:text-sm text-secondary font-mono block truncate">{profile.email}</span>
          <span className="text-xs text-muted hidden sm:block">
            Press <kbd className="font-mono text-secondary">C</kbd> to copy email • <kbd className="font-mono text-secondary">F</kbd> toggle focus
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
            className="min-h-11 min-w-11 p-2.5 rounded-[10px] bg-surface-raised hover:bg-surface-selected text-secondary hover:text-primary transition-colors inline-flex items-center justify-center"
            title="LinkedIn Profile"
          >
            <Linkedin className="h-4 w-4 text-accent" />
          </a>

          <button
            type="button"
            onClick={handleCopyEmail}
            aria-label={`Copy ${profile.name} email address`}
            className={`relative min-h-11 px-3.5 py-2 rounded-[10px] text-xs sm:text-sm font-medium flex items-center gap-1.5 transition-all duration-200 cursor-pointer overflow-hidden ${
              copiedEmail
                ? 'bg-positive-soft/80 border border-positive-border/50 text-positive shadow-xs ring-1 ring-positive/30'
                : 'bg-surface-raised hover:bg-surface-selected border border-border-strong/60 text-primary hover:text-primary'
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
                    <Check className="w-3.5 h-3.5 text-positive" />
                  </motion.span>
                  <span className="font-medium text-positive">Copied!</span>
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
                  <Copy className="w-3.5 h-3.5 text-secondary group-hover:text-primary" />
                  <span>Copy</span>
                </motion.div>
              )}
            </AnimatePresence>
          </button>

          {onRequestMobilization ? (
            <button
              type="button"
              onClick={() => onRequestMobilization(profile)}
              className="min-h-11 px-5 py-2 rounded-[10px] bg-action hover:bg-action-hover text-on-action text-xs sm:text-sm font-semibold flex items-center gap-1.5 transition-colors cursor-pointer shadow-md shadow-black/30"
            >
              <Send className="w-4 h-4" />
              <span>Request mobilization</span>
            </button>
          ) : (
            <a
              href={`mailto:${profile.email}?subject=Hydenlyne%20Mobilization%20Request%20-%20${encodeURIComponent(
                profile.title
              )}`}
              className="min-h-11 px-5 py-2 rounded-[10px] bg-action hover:bg-action-hover text-on-action text-xs sm:text-sm font-semibold flex items-center gap-1.5 transition-colors cursor-pointer shadow-md shadow-black/30"
            >
              <Mail className="w-4 h-4" />
              <span>Request mobilization</span>
            </a>
          )}
        </div>
      </div>
    </div>

    {createPortal(
      <AnimatePresence>
        {isRadarModalOpen && (
          <div className="fixed inset-0 z-[100] flex items-center justify-center p-3 sm:p-6">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.18 }}
              className="fixed inset-0 bg-canvas/80 backdrop-blur-xs"
              onClick={() => setIsRadarModalOpen(false)}
            />
            <motion.div
              ref={radarDialogRef}
              initial={{ opacity: 0, scale: 0.96, y: 8 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.96, y: 8 }}
              transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
              className="relative z-10 w-full max-w-4xl max-h-[94vh] overflow-y-auto rounded-[14px] border border-border-strong bg-surface p-4 sm:p-6 shadow-2xl"
              onClick={(event) => event.stopPropagation()}
              role="dialog"
              aria-modal="true"
              aria-label={`${profile.name} skills radar`}
            >
              <div className="mb-3 flex items-center justify-between gap-3">
                <div>
                  <h3 className="text-sm font-semibold text-primary">Skills Radar</h3>
                  <p className="text-xs text-secondary">{profile.name} · Competency assessment</p>
                </div>
                <button
                  type="button"
                  onClick={() => setIsRadarModalOpen(false)}
                  ref={radarCloseRef}
                  className="rounded-[10px] bg-surface-raised p-2 text-secondary transition-colors hover:bg-surface-selected hover:text-primary cursor-pointer"
                  title="Close skills radar"
                  aria-label="Close dialog"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
              <CandidateSkillRadarChart profile={profile} size="lg" showLegend={true} />
              <div className="mt-4 rounded-[10px] border border-border-subtle bg-canvas/50 p-4 text-xs text-secondary">
                <span className="mb-1 block font-mono text-xs font-semibold uppercase text-primary">
                  Methodology & Assessment Criteria
                </span>
                <p>
                  Calculated dynamically from verified offshore track records, certifications, and technical proficiencies.
                </p>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>,
      document.body,
    )}
    <ConfirmDialog
      open={isDeleteConfirmOpen}
      title={`Delete ${profile.name}?`}
      description="This permanently removes the contractor, their certifications, work history, and managed documents. This cannot be undone."
      confirmLabel={isDeleting ? 'Deleting…' : 'Delete permanently'}
      onConfirm={() => void handleDeleteCrew()}
      onCancel={() => !isDeleting && setIsDeleteConfirmOpen(false)}
    />
    <DocumentPreviewModal
      isOpen={Boolean(previewDoc)}
      onClose={() => setPreviewDoc(null)}
      document={previewDoc}
      profile={profile}
      onShowToast={onShowToast}
      onDelete={canManageDocuments ? onRemoveDocument : undefined}
      onReviewAction={canManageDocuments ? onReviewDocument : undefined}
      canReview={canManageDocuments}
    />
    </>
  );
};
