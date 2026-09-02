import { FC, useState, useRef } from 'react';
import { useAccessibleDialog } from '../hooks/useAccessibleDialog';
import { ConfirmDialog } from './ConfirmDialog';
import { motion, AnimatePresence } from 'motion/react';
import { UserProfile, SpecialistDocument } from '../types';
import { CertificationBadge } from './CertificationBadge';
import { DocumentVault } from './DocumentVault';
import { CandidateSkillRadarChart } from './CandidateSkillRadarChart';
import { computeCandidateSkillScores } from '../utils/skillRadarUtils';
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
  ChevronUp,
  Award,
  Trash2,
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
  onAddDocument?: () => void;
  onRemoveDocument?: (docId: string) => void | Promise<void>;
  canManageDocuments?: boolean;
  canDeleteCrew?: boolean;
  onDeleteCrew?: (profile: UserProfile) => Promise<void>;
}

export const ProfileDetailModal: FC<ProfileDetailModalProps> = ({
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
  canManageDocuments = false,
  canDeleteCrew = false,
  onDeleteCrew,
}) => {
  const [copiedEmail, setCopiedEmail] = useState(false);
  const [activeTab, setActiveTab] = useState<'profile' | 'radar' | 'documents'>('profile');
  const [isRadarExpanded, setIsRadarExpanded] = useState<boolean>(true);
  const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const dialogRef = useRef<HTMLDivElement>(null);

  const skillScores = profile ? computeCandidateSkillScores(profile) : [];
  const avgScore = skillScores.length > 0 ? Math.round(skillScores.reduce((acc, curr) => acc + curr.value, 0) / skillScores.length) : 0;

  useAccessibleDialog(Boolean(profile), dialogRef, onClose);

  if (!profile) return null;

  const handleCopyEmail = () => {
    navigator.clipboard?.writeText(profile.email);
    setCopiedEmail(true);
    if (onShowToast) onShowToast(`Copied ${profile.email}`);
    setTimeout(() => setCopiedEmail(false), 2000);
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

  return (
    <div
      className="ui-overlay-enter fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-3 sm:p-4"
      onClick={onClose}
    >
      <div
        ref={dialogRef}
        className="ui-surface-enter flex max-h-[calc(100dvh-1.5rem)] w-full max-w-3xl flex-col overflow-hidden rounded-[14px] border border-border-subtle bg-surface text-primary shadow-2xl sm:max-h-[92vh]"
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
                  className="w-16 h-16 rounded-[14px] object-cover border border-border-strong shadow-md"
                />
                {isAvailableNow && (
                  <span
                    className="absolute -bottom-1 -right-1 w-4 h-4 rounded-full bg-positive border-2 border-border-subtle shadow-xs"
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
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-accent-soft/80 border border-border-strong/60 text-xs text-accent font-medium">
                      <BadgeCheck className="w-3.5 h-3.5 text-accent" />
                      <span>Verified Contractor</span>
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
                  <span>•</span>
                  <span className="text-accent font-medium">{profile.department}</span>
                  <span>•</span>
                  <span className="font-mono text-secondary">{profile.yearsOfExperience} yrs experience</span>
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
                      ? 'bg-accent-soft/70 border-border-strong text-accent'
                      : 'bg-surface-raised/80 border-border-strong text-secondary hover:text-primary'
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
                className={`inline-flex min-h-11 min-w-11 items-center justify-center rounded-[10px] border transition-colors cursor-pointer ${
                  isBookmarked
                    ? 'bg-action text-on-action border-border-strong'
                    : 'bg-surface-raised/80 border-border-strong text-secondary hover:text-primary'
                }`}
                title={isBookmarked ? 'Remove from shortlist' : 'Save to shortlist'}
              >
                {isBookmarked ? (
                  <BookmarkCheck className="w-4 h-4 fill-on-action" />
                ) : (
                  <Bookmark className="w-4 h-4" />
                )}
              </button>

              <button
                type="button"
                onClick={onClose}
                aria-label="Close contractor profile"
                className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-[10px] bg-surface-raised hover:bg-surface-selected text-secondary hover:text-primary transition-colors cursor-pointer"
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
                <span>{profile.availability}</span>
              </span>
            </div>

            <div className="border-l border-border-subtle/70 px-3 sm:border-l-0 sm:border-r">
              <span className="text-xs text-secondary block uppercase font-mono">Rating</span>
              <span className="font-semibold text-xs text-warning block mt-0.5 font-mono">
                ★ {profile.rating ? profile.rating.toFixed(1) : '—'}
                {profile.reviewCount ? <span className="ml-1 text-muted font-normal">({profile.reviewCount})</span> : null}
              </span>
            </div>

            <div className="mt-3 border-t border-border-subtle/70 px-3 pt-3 sm:mt-0 sm:border-t-0 sm:border-r sm:pt-0">
              <span className="text-xs text-secondary block uppercase font-mono">Day Rate</span>
              <span className="font-semibold text-xs text-positive block mt-0.5 font-mono">
                {profile.dayRate ? `£${profile.dayRate}/day` : 'Upon Request'}
              </span>
            </div>

            <div className="mt-3 border-l border-t border-border-subtle/70 px-3 pt-3 sm:mt-0 sm:border-t-0 sm:pr-0 sm:pt-0">
              <span className="text-xs text-secondary block uppercase font-mono">Experience</span>
              <span className="font-semibold text-xs text-primary block mt-0.5 font-mono">
                {profile.yearsOfExperience} years
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
        <div className="flex-1 overflow-y-auto p-5 sm:p-6 space-y-4 text-xs">
          {activeTab === 'documents' ? (
            <DocumentVault
              profile={profile}
              documents={documents}
              onAddDocument={() => onAddDocument?.()}
              onRemoveDocument={(docId) => onRemoveDocument?.(docId)}
              canManageDocuments={canManageDocuments}
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
              {/* Bio Overview */}
              <div className="space-y-1.5">
                <h3 className="text-secondary font-semibold uppercase tracking-wider text-xs">
                  Contractor Overview
                </h3>
                <p className="text-secondary leading-relaxed">{profile.bio}</p>
              </div>

              {/* D3 Radar Chart Summary Card with Expand/Collapse Toggle */}
              <div className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="text-secondary font-semibold uppercase tracking-wider text-xs flex items-center gap-1.5 font-mono">
                    <Activity className="w-3.5 h-3.5 text-secondary" />
                    <span>Competency Radar Analysis</span>
                  </h3>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      id="modal-toggle-radar-collapse-btn"
                      onClick={() => setIsRadarExpanded(!isRadarExpanded)}
                      className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium bg-canvas/70 hover:bg-surface-raised border border-border-subtle text-secondary hover:text-primary transition-colors cursor-pointer shadow-2xs"
                      title={isRadarExpanded ? 'Collapse radar breakdown' : 'Expand radar breakdown'}
                    >
                      <span>{isRadarExpanded ? 'Collapse' : 'Expand'}</span>
                      {isRadarExpanded ? (
                        <ChevronUp className="w-3.5 h-3.5 text-secondary" />
                      ) : (
                        <ChevronDown className="w-3.5 h-3.5 text-secondary" />
                      )}
                    </button>
                    <button
                      type="button"
                      onClick={() => setActiveTab('radar')}
                      className="text-xs text-accent hover:text-accent font-medium cursor-pointer"
                    >
                      Full Radar →
                    </button>
                  </div>
                </div>

                <AnimatePresence initial={false} mode="wait">
                  {isRadarExpanded ? (
                    <motion.div
                      key="modal-radar-chart-expanded"
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      exit={{ opacity: 0, height: 0 }}
                      transition={{ duration: 0.2, ease: 'easeInOut' }}
                      className="overflow-hidden"
                    >
                      <CandidateSkillRadarChart profile={profile} size="sm" showLegend={false} />
                    </motion.div>
                  ) : (
                    <motion.button
                      key="modal-radar-chart-collapsed"
                      type="button"
                      id="modal-expand-collapsed-radar-banner"
                      onClick={() => setIsRadarExpanded(true)}
                      initial={{ opacity: 0, scale: 0.98 }}
                      animate={{ opacity: 1, scale: 1 }}
                      exit={{ opacity: 0, scale: 0.98 }}
                      transition={{ duration: 0.15 }}
                      className="w-full p-3 rounded-[10px] bg-canvas/60 hover:bg-surface border border-border-subtle/80 hover:border-border-strong flex items-center justify-between text-left transition-colors cursor-pointer group"
                      title="Expand competency radar chart"
                    >
                      <div className="flex items-center gap-2.5 min-w-0">
                        <div className="w-7 h-7 rounded-lg bg-surface border border-border-subtle flex items-center justify-center text-secondary group-hover:text-primary shrink-0">
                          <Activity className="w-3.5 h-3.5" />
                        </div>
                        <div className="min-w-0">
                          <p className="text-xs font-semibold text-secondary group-hover:text-primary truncate">
                            Competency overview
                          </p>
                          <p className="text-xs text-muted font-mono">
                            Six measured competency areas
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2.5 shrink-0">
                        <span className="px-2 py-0.5 rounded-full bg-surface border border-border-subtle text-secondary font-mono text-xs font-medium flex items-center gap-1">
                          <Award className="w-3 h-3 text-secondary" />
                          {avgScore}% Composite
                        </span>
                        <span className="text-xs text-accent font-medium group-hover:underline flex items-center gap-0.5">
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
                <div className="space-y-1.5">
                  <h3 className="text-secondary font-semibold uppercase tracking-wider text-xs flex items-center gap-1.5">
                    <Compass className="w-3.5 h-3.5 text-secondary" />
                    <span>Survey & Operations Disciplines</span>
                  </h3>
                  <div className="flex flex-wrap gap-1.5">
                    {profile.surveyTypes.map((type) => (
                      <span
                        key={type}
                        className="px-2.5 py-1 rounded-lg bg-surface border border-border-subtle text-secondary font-medium text-xs"
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
                  <h3 className="text-secondary font-semibold uppercase tracking-wider text-xs flex items-center gap-1.5">
                    <ShieldCheck className="w-3.5 h-3.5 text-secondary" />
                    <span>Offshore Safety & Marine Tickets</span>
                  </h3>
                  <div className="flex flex-wrap gap-1.5">
                    {profile.certifications.map((cert) => (
                      <CertificationBadge key={cert} certification={cert} size="md" />
                    ))}
                  </div>
                </div>
              )}

              {profile.certificationDetails && profile.certificationDetails.length > 0 && (
                <div className="space-y-1.5">
                  <h3 className="text-secondary font-semibold uppercase tracking-wider text-xs">Certification Dates</h3>
                  <div className="space-y-1">
                    {profile.certificationDetails.map((cert) => (
                      <div key={cert.id} className="flex items-center justify-between gap-3 text-xs text-secondary">
                        <span>{cert.name}</span>
                        <span className="text-muted">
                          {cert.issueDate ? `Completed ${cert.issueDate}` : 'Completion date not recorded'}
                          {cert.expiryDate ? ` · Expires ${cert.expiryDate}` : ' · No expiry recorded'}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Skills */}
              {profile.skills && profile.skills.length > 0 && (
                <div className="space-y-1.5">
                  <h3 className="text-secondary font-semibold uppercase tracking-wider text-xs">
                    Skills & Equipment Competencies
                  </h3>
                  <div className="flex flex-wrap gap-1.5">
                    {profile.skills.map((skill) => (
                      <span
                        key={skill}
                        className="px-2.5 py-1 rounded-lg bg-surface-raised text-primary border border-border-strong/60 text-xs"
                      >
                        {skill}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {profile.geographicalExperience && profile.geographicalExperience.length > 0 && (
                <div className="space-y-1.5">
                  <h3 className="text-secondary font-semibold uppercase tracking-wider text-xs flex items-center gap-1.5">
                    <MapPin className="w-3.5 h-3.5 text-secondary" />
                    <span>Geographical Experience</span>
                  </h3>
                  <div className="flex flex-wrap gap-1.5">
                    {profile.geographicalExperience.map((place) => (
                      <span key={place} className="px-2.5 py-1 rounded-lg bg-surface border border-border-subtle text-secondary font-medium text-xs">
                        {place}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {profile.systemsExperience && profile.systemsExperience.length > 0 && (
                <div className="space-y-1.5">
                  <h3 className="text-secondary font-semibold uppercase tracking-wider text-xs flex items-center gap-1.5">
                    <Layers className="w-3.5 h-3.5 text-secondary" />
                    <span>Systems Experience</span>
                  </h3>
                  <div className="flex flex-wrap gap-1.5">
                    {profile.systemsExperience.map((system) => (
                      <span key={system} className="px-2.5 py-1 rounded-lg bg-surface border border-border-subtle text-secondary font-medium text-xs">{system}</span>
                    ))}
                  </div>
                </div>
              )}

              {profile.trainingDetails && profile.trainingDetails.length > 0 && (
                <div className="space-y-1.5">
                  <h3 className="text-secondary font-semibold uppercase tracking-wider text-xs flex items-center gap-1.5">
                    <GraduationCap className="w-3.5 h-3.5 text-secondary" />
                    <span>Training / Qualifications</span>
                  </h3>
                  <div className="space-y-1.5">
                    {profile.trainingDetails.map((item) => (
                      <div key={item.id} className="rounded-lg bg-canvas/70 border border-border-subtle px-2.5 py-2 flex flex-wrap items-center justify-between gap-2">
                        <span className="text-secondary text-xs">{item.name}</span>
                        <span className="text-muted text-xs">{item.completedDate ? `Completed ${item.completedDate.slice(0, 4)}` : 'Date not recorded'}{item.expiryDate ? ` · Expires ${item.expiryDate.slice(0, 4)}` : ''}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Featured Projects */}
              {profile.featuredProjects && profile.featuredProjects.length > 0 && (
                <div className="space-y-1.5">
                  <h3 className="text-secondary font-semibold uppercase tracking-wider text-xs flex items-center gap-1.5">
                    <Calendar className="w-3.5 h-3.5 text-secondary" />
                    <span>Featured Campaigns & Surveys</span>
                  </h3>
                  <div className="space-y-1">
                    {profile.featuredProjects.map((project) => (
                      <div
                        key={project}
                        className="p-2 rounded-lg bg-canvas/70 border border-border-subtle text-secondary text-xs flex items-center gap-2"
                      >
                        <span className="w-1.5 h-1.5 rounded-full bg-accent shrink-0" />
                        <span>{project}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Past Operators / Clients & Education */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
                {profile.pastCompanies && profile.pastCompanies.length > 0 && (
                  <div className="p-3 bg-canvas/60 rounded-[10px] border border-border-subtle/60 space-y-1.5">
                    <div className="text-secondary font-semibold flex items-center gap-1.5">
                      <Building className="w-3.5 h-3.5 text-secondary" />
                      <span>Past Operators & Clients</span>
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {profile.pastCompanies.map((comp) => (
                        <span
                          key={comp}
                          className="px-2 py-0.5 rounded bg-surface text-secondary text-xs border border-border-subtle"
                        >
                          {comp}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {profile.education && (
                  <div className="p-3 bg-canvas/60 rounded-[10px] border border-border-subtle/60 space-y-1.5">
                    <div className="text-secondary font-semibold flex items-center gap-1.5">
                      <GraduationCap className="w-3.5 h-3.5 text-secondary" />
                      <span>Education & Academics</span>
                    </div>
                    <p className="text-secondary text-xs">{profile.education}</p>
                  </div>
                )}
              </div>
            </>
          )}
        </div>

        {/* Modal Footer Actions */}
        <div className="flex flex-col items-stretch gap-3 border-t border-border-subtle bg-canvas p-4 sm:flex-row sm:items-center sm:justify-between sm:p-5">
          <div className="min-w-0">
            <span className="text-xs text-secondary font-mono block truncate">{profile.email}</span>
            <span className="text-xs text-secondary">Hydenlyne Verified Contractor Network</span>
          </div>

          <div className="flex flex-wrap items-center gap-2 sm:shrink-0 sm:justify-end">
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
              className="inline-flex min-h-11 items-center gap-1.5 px-3 py-2 rounded-[10px] bg-surface-raised hover:bg-surface-selected text-secondary hover:text-primary text-xs font-medium transition-colors cursor-pointer"
              title="Open LinkedIn Profile (new tab)"
            >
              <Linkedin className="h-4 w-4 text-accent" />
              <span className="hidden sm:inline">LinkedIn</span>
            </a>

            <button
              type="button"
              onClick={handleCopyEmail}
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
                href={`mailto:${profile.email}?subject=Hydenlyne%20Mobilization%20Request%20-%20${encodeURIComponent(
                  profile.title
                )}`}
                className="px-4 py-2 rounded-[10px] bg-action hover:bg-action-hover text-on-action text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer shadow-md"
              >
                <Mail className="w-3.5 h-3.5" />
                <span>Request mobilization</span>
              </a>
            )}
          </div>
        </div>
      </div>
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
