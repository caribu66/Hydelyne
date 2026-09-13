import { FC, useEffect, useRef, useState } from 'react';
import { useAccessibleDialog } from '../hooks/useAccessibleDialog';
import { ConfirmDialog } from './ConfirmDialog';
import { motion, AnimatePresence } from 'motion/react';
import { UserProfile, SpecialistDocument } from '../types';
import type { DocumentMutationResult } from '../hooks/useSpecialistDocuments';
import { CertificationBadge } from './CertificationBadge';
import { DocumentVault } from './DocumentVault';
import { CandidateSkillRadarChart } from './CandidateSkillRadarChart';
import { computeCandidateSkillScores } from '../utils/skillRadarUtils';
import { DossierCollection } from './DossierCollection';
import { mobilizationMailto, safeLinkedInUrl } from '../utils/externalLinks';
import { formatExperience } from '../utils/experience';
import { availabilityLabel } from '../utils/profileLabels';
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
  Activity,
  Layers,
  ChevronDown,
  Trash2,
} from 'lucide-react';

type ProfileInformationSection = 'summary' | 'credentials' | 'expertise' | 'history';

interface ProfileDetailModalProps {
  profile: UserProfile | null;
  sessionKey?: string | null;
  onClose: () => void;
  isBookmarked: boolean;
  onToggleBookmark: (profileId: string) => void;
  onShowToast?: (message: string) => void;
  isCompared?: boolean;
  onToggleCompare?: (profile: UserProfile) => void;
  onRequestMobilization?: (profile: UserProfile) => void;
  onPrintDossier?: (profile: UserProfile) => void;
  documents?: SpecialistDocument[];
  onAddDocument?: () => void;
  onRemoveDocument?: (docId: string) => void | Promise<void | DocumentMutationResult>;
  onReviewDocument?: (docId: string, action: 'approve' | 'reject') => void | Promise<void | DocumentMutationResult>;
  canManageDocuments?: boolean;
  canRequestDocuments?: boolean;
  canDeleteCrew?: boolean;
  onDeleteCrew?: (profile: UserProfile) => Promise<void>;
}

export const ProfileDetailModal: FC<ProfileDetailModalProps> = ({
  profile,
  sessionKey = null,
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
  onReviewDocument,
  canManageDocuments = false,
  canRequestDocuments = false,
  canDeleteCrew = false,
  onDeleteCrew,
}) => {
  const [copiedEmail, setCopiedEmail] = useState(false);
  const [activeTab, setActiveTab] = useState<'profile' | 'radar' | 'documents'>('profile');
  const [activeProfileSection, setActiveProfileSection] = useState<ProfileInformationSection>('summary');
  const [isRadarExpanded, setIsRadarExpanded] = useState<boolean>(false);
  const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const dialogRef = useRef<HTMLDivElement>(null);
  const bodyRef = useRef<HTMLDivElement>(null);
  const copyFeedbackTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const skillScores = profile ? computeCandidateSkillScores(profile) : [];
  const avgScore = skillScores.length > 0 ? Math.round(skillScores.reduce((acc, curr) => acc + curr.value, 0) / skillScores.length) : 0;

  useAccessibleDialog(Boolean(profile), dialogRef, onClose);

  useEffect(() => {
    if (copyFeedbackTimerRef.current !== null) {
      clearTimeout(copyFeedbackTimerRef.current);
      copyFeedbackTimerRef.current = null;
    }
    setActiveProfileSection('summary');
    setActiveTab('profile');
    setIsRadarExpanded(false);
    setIsDeleteConfirmOpen(false);
    setIsDeleting(false);
    setCopiedEmail(false);
    bodyRef.current?.scrollTo({ top: 0, behavior: 'auto' });
    return () => {
      if (copyFeedbackTimerRef.current !== null) {
        clearTimeout(copyFeedbackTimerRef.current);
        copyFeedbackTimerRef.current = null;
      }
    };
  }, [profile?.id, sessionKey]);

  if (!profile) return null;

  const handleCopyEmail = async () => {
    if (!navigator.clipboard) {
      onShowToast?.('Could not copy the email address in this browser.');
      return;
    }
    try {
      await navigator.clipboard.writeText(profile.email);
      setCopiedEmail(true);
      onShowToast?.(`Copied ${profile.email}`);
      copyFeedbackTimerRef.current = setTimeout(() => {
        copyFeedbackTimerRef.current = null;
        setCopiedEmail(false);
      }, 2000);
    } catch {
      setCopiedEmail(false);
      onShowToast?.('Could not copy the email address. Please try again.');
    }
  };

  const handleDeleteCrew = async () => {
    if (!onDeleteCrew) return;
    setIsDeleting(true);
    try {
      await onDeleteCrew(profile);
      setIsDeleteConfirmOpen(false);
    } catch (error) {
      onShowToast?.(error instanceof Error ? error.message : `Could not delete ${profile.name}`);
    } finally {
      setIsDeleting(false);
    }
  };

  const isAvailableNow = profile.availability?.toLowerCase().includes('immediately');
  const displayedAvailability = availabilityLabel(profile.availability);
  const profileSections: ReadonlyArray<{ value: ProfileInformationSection; label: string }> = [
    { value: 'summary', label: 'Snapshot' },
    { value: 'credentials', label: `Credentials (${profile.certifications?.length ?? 0})` },
    { value: 'expertise', label: `Skills (${profile.skills?.length ?? 0})` },
    { value: 'history', label: `History (${profile.featuredProjects?.length ?? 0})` },
  ];
  const selectProfileSection = (section: ProfileInformationSection) => {
    setActiveProfileSection(section);
    requestAnimationFrame(() => bodyRef.current?.scrollTo({ top: 0, behavior: 'auto' }));
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4"
    >
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.18 }}
        className="fixed inset-0 bg-canvas/80 backdrop-blur-sm"
        onClick={onClose}
      />
      <motion.div
        ref={dialogRef}
        initial={{ opacity: 0, scale: 0.96, y: 8 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.96, y: 8 }}
        transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
        className="relative flex max-h-[calc(100dvh-1.5rem)] w-full max-w-5xl flex-col overflow-hidden rounded-[14px] border border-border-subtle bg-surface text-primary shadow-2xl sm:max-h-[94vh] z-10"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="profile-modal-name"
        aria-describedby="profile-modal-description"
      >
        {/* Header Hero Area */}
        <div className="sticky top-0 z-10 p-4 sm:p-6 bg-canvas/95 border-b border-border-subtle backdrop-blur-sm">
          <div className="flex flex-col items-stretch gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
            <div className="flex items-start gap-4 min-w-0">
              <div className="relative shrink-0">
                <img
                  src={profile.avatar}
                  alt={profile.name}
                  referrerPolicy="no-referrer"
                  className="w-16 h-16 rounded-2xl object-cover ring-1 ring-border-subtle/80 shadow-sm"
                />
                {isAvailableNow && (
                  <span
                    className="absolute -bottom-1 -right-1 w-4 h-4 rounded-full bg-positive ring-2 ring-surface shadow-xs"
                    title="Available for immediate deployment"
                  />
                )}
              </div>

              <div className="min-w-0 space-y-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <h2 id="profile-modal-name" className="text-lg font-bold text-primary">
                    {profile.name}
                  </h2>
                  {profile.isHighlyRecommended && (
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-surface-raised border border-border-strong/60 text-xs text-primary font-medium">
                      <BadgeCheck className="w-3.5 h-3.5 text-accent" />
                      <span>Strong match</span>
                    </span>
                  )}
                  {isCompared && (
                    <span className="inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs font-semibold bg-surface-raised border border-border-strong text-primary shrink-0">
                      <Scale className="w-3 h-3 text-secondary" /> Comparing
                    </span>
                  )}
                </div>
                <p id="profile-modal-description" className="text-xs sm:text-sm text-secondary font-medium">
                  {profile.title}
                </p>
                <div className="flex items-center gap-2 text-xs text-secondary pt-0.5 flex-wrap">
                  <span className="flex items-center gap-1">
                    <MapPin className="w-3.5 h-3.5 text-secondary shrink-0" />
                    <span>{profile.location}</span>
                  </span>
                  <span className="text-muted/60">•</span>
                  <span className="text-accent font-medium">{profile.department}</span>
                  <span className="text-muted/60">•</span>
                <span className="font-mono text-secondary">{formatExperience(profile.yearsOfExperience)} yrs experience</span>
                </div>
              </div>
            </div>

            <div className="flex w-full flex-wrap items-center justify-end gap-2 sm:w-auto sm:shrink-0">
              {onToggleCompare && (
                <button
                  type="button"
                  onClick={() => onToggleCompare(profile)}
                  aria-label={isCompared ? `Remove ${profile.name} from comparison` : `Compare ${profile.name}`}
                  className={`inline-flex min-h-11 min-w-11 items-center justify-center rounded-[10px] border transition-colors cursor-pointer ${
                    isCompared
                      ? 'bg-surface-raised border-border-strong text-primary ring-1 ring-border-strong/40'
                      : 'bg-surface-raised/80 border-border-strong text-secondary hover:text-primary'
                  }`}
                  title={isCompared ? 'Remove from compare' : 'Add to compare'}
                >
                  <Scale className={`w-4 h-4 ${isCompared ? 'stroke-[2.5]' : ''}`} />
                </button>
              )}

              {onPrintDossier && (
                <button
                  type="button"
                  onClick={() => onPrintDossier(profile)}
                  aria-label={`Print ${profile.name} profile`}
                  className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-[10px] bg-surface-raised/80 border border-border-strong text-secondary hover:text-primary transition-colors cursor-pointer"
                  title="Print contractor profile"
                >
                  <Printer className="w-4 h-4" />
                </button>
              )}

              {canDeleteCrew && onDeleteCrew && (
                <button
                  type="button"
                  onClick={() => setIsDeleteConfirmOpen(true)}
                  aria-label={`Delete ${profile.name}`}
                  className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-[10px] border border-danger-border/80 bg-danger-soft/40 text-danger hover:bg-danger-soft/60 hover:text-danger transition-colors cursor-pointer"
                  title="Delete contractor"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              )}

              <button
                type="button"
                onClick={() => onToggleBookmark(profile.id)}
                aria-label={isBookmarked ? `Remove ${profile.name} from shortlist` : `Save ${profile.name} to shortlist`}
                className={`inline-flex min-h-11 px-3.5 py-1.5 rounded-[10px] border transition-colors cursor-pointer items-center gap-1.5 text-xs font-semibold shadow-xs ${
                  isBookmarked
                    ? 'bg-action text-on-action border-action'
                    : 'bg-surface-raised/80 border-border-strong text-primary hover:bg-surface-raised'
                }`}
                title={isBookmarked ? 'Saved in shortlist' : 'Save to shortlist'}
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

              <button
                type="button"
                onClick={onClose}
                aria-label="Close contractor profile"
                className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-[10px] bg-surface-raised hover:bg-surface-selected text-secondary hover:text-primary transition-colors cursor-pointer border border-border-subtle"
                title="Close"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Quick Metrics Bar */}
          <div className="mt-5 grid grid-cols-2 border-y border-border-subtle/70 py-3 sm:grid-cols-4">
            <div className="px-3 sm:border-r sm:border-border-subtle/70 sm:pl-0">
              <span className="text-xs text-secondary block uppercase font-mono">Mobilization</span>
              <span
                className={`inline-flex items-center gap-1.5 text-xs font-semibold mt-0.5 ${
                  isAvailableNow ? 'text-positive' : 'text-secondary'
                }`}
              >
                <span className={`w-2 h-2 rounded-full ${isAvailableNow ? 'bg-positive' : 'bg-surface-selected'}`} />
                <span>{displayedAvailability}</span>
              </span>
            </div>

            <div className="border-l border-border-subtle/70 px-3 sm:border-l-0 sm:border-r">
              <span className="text-xs text-secondary block uppercase font-mono">Rating</span>
              <span className="font-semibold text-xs text-warning block mt-0.5 font-mono">
                ★ {profile.rating != null ? profile.rating.toFixed(1) : '—'}
                {profile.reviewCount ? <span className="ml-1 text-muted font-normal">({profile.reviewCount})</span> : null}
              </span>
            </div>

            <div className="mt-3 border-t border-border-subtle/70 px-3 pt-3 sm:mt-0 sm:border-t-0 sm:border-r sm:pt-0">
              <span className="text-xs text-secondary block uppercase font-mono">Day Rate</span>
              <span className="font-semibold text-xs text-positive block mt-0.5 font-mono">
                {profile.dayRate != null ? `£${profile.dayRate}/day` : 'Upon Request'}
              </span>
            </div>

            <div className="mt-3 border-l border-t border-border-subtle/70 px-3 pt-3 sm:mt-0 sm:border-t-0 sm:pr-0 sm:pt-0">
              <span className="text-xs text-secondary block uppercase font-mono">Experience</span>
              <span className="font-semibold text-xs text-primary block mt-0.5 font-mono">
                {formatExperience(profile.yearsOfExperience)} years
              </span>
            </div>
          </div>

          {/* Subtabs */}
          <div role="group" aria-label={`${profile.name} profile sections`} className="flex items-center gap-2 mt-4 pt-3 border-t border-border-subtle flex-wrap">
            <button
              type="button"
              aria-pressed={activeTab === 'profile'}
              onClick={() => setActiveTab('profile')}
              className={`min-h-11 px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors cursor-pointer flex items-center gap-1.5 ${
                activeTab === 'profile'
                  ? 'bg-surface-raised text-primary shadow-xs'
                  : 'text-secondary hover:text-primary'
              }`}
            >
              <Layers className="w-3.5 h-3.5" />
              <span>Profile & History</span>
            </button>

            <button
              type="button"
              aria-pressed={activeTab === 'radar'}
              onClick={() => setActiveTab('radar')}
              className={`min-h-11 px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors cursor-pointer flex items-center gap-1.5 ${
                activeTab === 'radar'
                  ? 'bg-surface-raised text-primary shadow-xs'
                  : 'text-secondary hover:text-primary'
              }`}
            >
              <Activity className="w-3.5 h-3.5 text-secondary" />
              <span>Skills Radar</span>
            </button>

            <button
              type="button"
              aria-pressed={activeTab === 'documents'}
              onClick={() => setActiveTab('documents')}
              className={`min-h-11 px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors cursor-pointer flex items-center gap-1.5 ${
                activeTab === 'documents'
                  ? 'bg-surface-raised text-primary shadow-xs'
                  : 'text-secondary hover:text-primary'
              }`}
            >
              <FileCheck className="w-3.5 h-3.5 text-secondary" />
              <span>Compliance Documents</span>
              <span className="px-1.5 py-0.2 rounded-full bg-surface-raised text-secondary font-mono text-xs">
                {documents.length}
              </span>
            </button>
          </div>
        </div>

        {/* Scrollable Body */}
        <div ref={bodyRef} className="flex-1 overflow-y-auto p-5 sm:p-6 space-y-4 text-xs">
          {activeTab === 'documents' ? (
            <DocumentVault
              profile={profile}
              documents={documents}
              onAddDocument={() => onAddDocument?.()}
              onRemoveDocument={(docId) => onRemoveDocument?.(docId)}
              onReviewDocument={onReviewDocument}
              canManageDocuments={canManageDocuments}
              canRequestDocuments={canRequestDocuments}
              sessionKey={sessionKey}
              onShowToast={onShowToast || (() => {})}
            />
          ) : activeTab === 'radar' ? (
            <div className="space-y-4">
              <CandidateSkillRadarChart profile={profile} size="lg" showLegend={true} />
              <div className="bg-canvas/50 p-4 rounded-[10px] border border-border-subtle text-xs text-secondary">
                <span className="font-semibold text-primary block mb-1 font-mono text-xs uppercase">
                  Offshore Competency Breakdown
                </span>
                <p>
                  Visualizes normalized scores in <strong>Geotechnical</strong>, <strong>Environmental</strong>, and <strong>Data Analysis</strong>, along with specialized subsea survey, HSE, and Quality Control metrics.
                </p>
              </div>
            </div>
          ) : (
            <>
              <nav aria-label="Profile information" className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                {profileSections.map(({ value, label }) => (
                  <button
                    key={value}
                    type="button"
                    aria-pressed={activeProfileSection === value}
                    onClick={() => selectProfileSection(value)}
                    className={`min-h-11 rounded-[10px] border px-3 text-left text-xs font-semibold transition-colors ${
                      activeProfileSection === value
                        ? 'border-accent bg-accent-soft/70 text-primary'
                        : 'border-border-subtle bg-canvas/60 text-secondary hover:bg-surface-raised hover:text-primary'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </nav>

              {activeProfileSection === 'summary' && (
                <div className="space-y-5">
                  <section className="space-y-1.5" aria-labelledby="profile-overview-heading">
                    <h3 id="profile-overview-heading" className="text-secondary font-semibold uppercase tracking-wider text-xs">Contractor Overview</h3>
                    <p className="text-sm leading-relaxed text-secondary">{profile.bio}</p>
                  </section>

                  <section className="space-y-2" aria-labelledby="profile-radar-summary-heading">
                    <div className="flex items-center justify-between gap-2">
                      <h3 id="profile-radar-summary-heading" className="text-secondary font-semibold uppercase tracking-wider text-xs flex items-center gap-1.5 font-mono">
                        <Activity className="w-3.5 h-3.5 text-secondary" />
                        <span>Competency Radar</span>
                      </h3>
                      <button type="button" onClick={() => setActiveTab('radar')} className="min-h-11 px-2 text-xs font-semibold text-accent hover:underline">Full radar</button>
                    </div>
                    {isRadarExpanded ? (
                      <div className="space-y-2">
                        <CandidateSkillRadarChart profile={profile} size="sm" showLegend={false} />
                        <button type="button" onClick={() => setIsRadarExpanded(false)} className="min-h-11 rounded-lg border border-border-subtle px-3 text-xs font-semibold text-accent hover:bg-accent-soft/60">Hide radar preview</button>
                      </div>
                    ) : (
                      <button type="button" onClick={() => setIsRadarExpanded(true)} className="w-full rounded-[10px] border border-border-subtle bg-canvas/60 p-3 text-left hover:bg-surface-raised">
                        <span className="flex items-center justify-between gap-3">
                          <span><span className="block font-semibold text-primary">{avgScore}% composite competency</span><span className="mt-0.5 block text-xs text-secondary">Six measured offshore disciplines</span></span>
                          <ChevronDown className="h-4 w-4 shrink-0 text-accent" />
                        </span>
                      </button>
                    )}
                  </section>

                  {profile.surveyTypes && profile.surveyTypes.length > 0 && (
                    <section className="space-y-1.5" aria-labelledby="profile-disciplines-heading">
                      <h3 id="profile-disciplines-heading" className="text-secondary font-semibold uppercase tracking-wider text-xs flex items-center gap-1.5"><Compass className="w-3.5 h-3.5" />Survey & operations disciplines</h3>
                      <div className="flex flex-wrap gap-1.5">{profile.surveyTypes.slice(0, 8).map((type) => <span key={type} className="rounded-lg border border-border-subtle bg-surface px-2.5 py-1 text-xs font-medium text-secondary">{type}</span>)}</div>
                    </section>
                  )}
                </div>
              )}

              {activeProfileSection === 'credentials' && (
                <div className="space-y-5">
                  {profile.certifications && profile.certifications.length > 0 && <section className="space-y-1.5"><h3 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-secondary"><ShieldCheck className="w-3.5 h-3.5" />Offshore safety & marine tickets</h3><DossierCollection items={profile.certifications} itemLabel="tickets" renderItems={(certifications) => <div className="flex flex-wrap gap-1.5">{certifications.map((cert) => <CertificationBadge key={cert} certification={cert} size="md" />)}</div>} /></section>}
                  {profile.certificationDetails && profile.certificationDetails.length > 0 && <section className="space-y-1.5"><h3 className="text-xs font-semibold uppercase tracking-wider text-secondary">Certification dates</h3><DossierCollection items={profile.certificationDetails} itemLabel="certifications" renderItems={(certifications) => <div className="space-y-1">{certifications.map((cert) => <div key={cert.id} className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 rounded-lg border border-border-subtle bg-canvas/60 px-3 py-2 text-xs"><span className="font-medium text-primary">{cert.name}</span><span className="text-secondary">{cert.issueDate ? `Completed ${cert.issueDate}` : 'Completion date not recorded'}{cert.expiryDate ? ` · Expires ${cert.expiryDate}` : ' · No expiry recorded'}</span></div>)}</div>} /></section>}
                  {profile.trainingDetails && profile.trainingDetails.length > 0 && <section className="space-y-1.5"><h3 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-secondary"><GraduationCap className="w-3.5 h-3.5" />Training & qualifications</h3><DossierCollection items={profile.trainingDetails} itemLabel="qualifications" renderItems={(training) => <div className="space-y-1.5">{training.map((item) => <div key={item.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border-subtle bg-canvas/70 px-3 py-2"><span className="text-secondary">{item.name}</span><span className="text-muted">{item.completedDate ? `Completed ${item.completedDate.slice(0, 4)}` : 'Date not recorded'}{item.expiryDate ? ` · Expires ${item.expiryDate.slice(0, 4)}` : ''}</span></div>)}</div>} /></section>}
                </div>
              )}

              {activeProfileSection === 'expertise' && (
                <div className="space-y-5">
                  {profile.skills && profile.skills.length > 0 && <section className="space-y-1.5"><h3 className="text-xs font-semibold uppercase tracking-wider text-secondary">Skills & equipment competencies</h3><DossierCollection items={profile.skills} itemLabel="skills" initialItems={8} renderItems={(skills) => <div className="flex flex-wrap gap-1.5">{skills.map((skill) => <span key={skill} className="rounded-lg border border-border-strong/60 bg-surface-raised px-2.5 py-1 text-xs text-primary">{skill}</span>)}</div>} /></section>}
                  {profile.geographicalExperience && profile.geographicalExperience.length > 0 && <section className="space-y-1.5"><h3 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-secondary"><MapPin className="w-3.5 h-3.5" />Geographical experience</h3><DossierCollection items={profile.geographicalExperience} itemLabel="locations" initialItems={8} renderItems={(locations) => <div className="flex flex-wrap gap-1.5">{locations.map((place) => <span key={place} className="rounded-lg border border-border-subtle bg-surface px-2.5 py-1 text-xs font-medium text-secondary">{place}</span>)}</div>} /></section>}
                  {profile.systemsExperience && profile.systemsExperience.length > 0 && <section className="space-y-1.5"><h3 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-secondary"><Layers className="w-3.5 h-3.5" />Systems experience</h3><DossierCollection items={profile.systemsExperience} itemLabel="systems" initialItems={8} renderItems={(systems) => <div className="flex flex-wrap gap-1.5">{systems.map((system) => <span key={system} className="rounded-lg border border-border-subtle bg-surface px-2.5 py-1 text-xs font-medium text-secondary">{system}</span>)}</div>} /></section>}
                </div>
              )}

              {activeProfileSection === 'history' && (
                <div className="space-y-5">
                  {profile.featuredProjects && profile.featuredProjects.length > 0 && <section className="space-y-1.5"><h3 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-secondary"><Calendar className="w-3.5 h-3.5" />Campaigns & surveys</h3><DossierCollection items={profile.featuredProjects} itemLabel="campaigns" renderItems={(projects) => <div className="space-y-1">{projects.map((project) => <div key={project} className="flex items-center gap-2 rounded-lg border border-border-subtle bg-canvas/70 p-2 text-secondary"><span className="h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />{project}</div>)}</div>} /></section>}
                  {profile.pastCompanies && profile.pastCompanies.length > 0 && <section className="space-y-1.5"><h3 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-secondary"><Building className="w-3.5 h-3.5" />Past operators & clients</h3><DossierCollection items={profile.pastCompanies} itemLabel="clients" initialItems={8} renderItems={(companies) => <div className="flex flex-wrap gap-1.5">{companies.map((company) => <span key={company} className="rounded border border-border-subtle bg-surface px-2 py-1 text-xs text-secondary">{company}</span>)}</div>} /></section>}
                  {profile.education && <section className="space-y-1.5 rounded-[10px] border border-border-subtle bg-canvas/60 p-3"><h3 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-secondary"><GraduationCap className="w-3.5 h-3.5" />Education & academics</h3><p className="text-secondary">{profile.education}</p></section>}
                </div>
              )}
            </>
          )}
        </div>

        {/* Modal Footer Actions */}
        <div className="flex flex-col items-stretch gap-3 border-t border-border-subtle bg-canvas p-4 sm:flex-row sm:items-center sm:justify-between sm:p-5">
          <div className="min-w-0">
            <span className="text-xs text-secondary font-mono block truncate">{profile.email}</span>
            <span className="text-xs text-secondary">Hydenlyne Contractor Network</span>
          </div>

          <div className="flex flex-wrap items-center gap-2 sm:shrink-0 sm:justify-end">
            <a
              href={safeLinkedInUrl(profile.linkedinUrl, profile.name)}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={`Open ${profile.name} LinkedIn profile`}
              className="inline-flex min-h-11 items-center gap-1.5 px-3 py-2 rounded-[10px] bg-surface-raised hover:bg-surface-selected text-secondary hover:text-primary text-xs font-medium transition-colors cursor-pointer"
              title="Open LinkedIn Profile (new tab)"
            >
              <Linkedin className="h-4 w-4 text-accent" />
              <span className="hidden sm:inline">LinkedIn</span>
            </a>

            <button
              type="button"
              onClick={() => void handleCopyEmail()}
              aria-label={`Copy ${profile.name} email address`}
              className={`relative min-h-11 px-3.5 py-2 rounded-[10px] text-xs font-medium flex items-center gap-1.5 transition-all duration-200 cursor-pointer overflow-hidden ${
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
                    <Copy className="w-3.5 h-3.5 text-secondary" />
                    <span>Copy Email</span>
                  </motion.div>
                )}
              </AnimatePresence>
            </button>

            {canDeleteCrew && onDeleteCrew && (
              <button
                type="button"
                onClick={() => setIsDeleteConfirmOpen(true)}
                className="min-h-11 px-3.5 py-2 rounded-[10px] border border-danger-border bg-danger-soft/50 hover:bg-danger-soft/70 text-danger hover:text-primary text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span>Delete contractor</span>
              </button>
            )}

            {onRequestMobilization ? (
              <button
                type="button"
                onClick={() => onRequestMobilization(profile)}
                className="min-h-11 px-4 py-2 rounded-[10px] bg-action hover:bg-action-hover text-on-action text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer shadow-md"
              >
                <Send className="w-3.5 h-3.5" />
                <span>Request mobilization</span>
              </button>
            ) : (
              <a
              href={mobilizationMailto(profile.email, profile.title)}
                className="px-4 py-2 rounded-[10px] bg-action hover:bg-action-hover text-on-action text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer shadow-md"
              >
                <Mail className="w-3.5 h-3.5" />
                <span>Request mobilization</span>
              </a>
            )}
          </div>
        </div>
      </motion.div>
      <ConfirmDialog
        open={isDeleteConfirmOpen}
        title={`Delete ${profile.name}?`}
        description="This permanently removes the contractor, their certifications, work history, and managed documents. This cannot be undone."
        confirmLabel={isDeleting ? 'Deleting…' : 'Delete permanently'}
        onConfirm={() => void handleDeleteCrew()}
        onCancel={() => !isDeleting && setIsDeleteConfirmOpen(false)}
      />
    </div>
  );
};
