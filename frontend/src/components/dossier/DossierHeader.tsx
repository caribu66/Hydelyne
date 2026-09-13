import { FC, useRef, useState } from 'react';
import { UserProfile } from '../../types';
import { useMenuKeyboardNav } from '../../hooks/useMenuKeyboardNav';
import { HighlightText } from '../HighlightText';
import { formatExperience } from '../../utils/experience';
import {
  MapPin,
  Bookmark,
  BookmarkCheck,
  BadgeCheck,
  Scale,
  Printer,
  FileCheck,
  Maximize2,
  Minimize2,
  ChevronLeft,
  ChevronRight,
  Activity,
  Layers,
  BriefcaseBusiness,
  GraduationCap,
  Trash2,
  Ellipsis,
} from 'lucide-react';

export type DossierTabType =
  | 'dossier'
  | 'experience'
  | 'expertise'
  | 'systems'
  | 'credentials'
  | 'radar'
  | 'vault';

interface DossierHeaderProps {
  profile: UserProfile;
  isFocusMode: boolean;
  onToggleFocusMode?: () => void;
  onPrevProfile?: () => void;
  onNextProfile?: () => void;
  profileIndex?: number;
  totalProfiles?: number;
  searchQuery?: string;
  isBookmarked: boolean;
  onToggleBookmark: (id: string) => void;
  isCompared?: boolean;
  onToggleCompare?: (profile: UserProfile) => void;
  onPrintDossier?: (profile: UserProfile) => void;
  canDeleteCrew?: boolean;
  onRequestDelete: () => void;
  activeTab: DossierTabType;
  onSelectTab: (tab: DossierTabType) => void;
  profileSkillsCount: number;
  documentsCount: number;
  onOpenRadarModal: () => void;
}

export const DossierHeader: FC<DossierHeaderProps> = ({
  profile,
  isFocusMode,
  onToggleFocusMode,
  onPrevProfile,
  onNextProfile,
  profileIndex,
  totalProfiles,
  searchQuery = '',
  isBookmarked,
  onToggleBookmark,
  isCompared = false,
  onToggleCompare,
  onPrintDossier,
  canDeleteCrew = false,
  onRequestDelete,
  activeTab,
  onSelectTab,
  profileSkillsCount,
  documentsCount,
  onOpenRadarModal,
}) => {
  const [isMoreSectionsOpen, setIsMoreSectionsOpen] = useState(false);
  const [isHeaderActionsOpen, setIsHeaderActionsOpen] = useState(false);
  const sectionMenuRef = useRef<HTMLDivElement>(null);
  const sectionMenuTriggerRef = useRef<HTMLButtonElement>(null);
  const headerActionsRef = useRef<HTMLDivElement>(null);
  const headerActionsTriggerRef = useRef<HTMLButtonElement>(null);

  useMenuKeyboardNav(
    isMoreSectionsOpen,
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

  const isAvailableNow = profile.availability?.toLowerCase().includes('immediately');
  const isSecondarySection = activeTab === 'systems';
  const secondarySectionLabel = activeTab === 'systems' ? 'Systems' : 'More';

  const sectionButtonClass = (isActive: boolean) =>
    `min-h-11 px-3.5 py-1.5 rounded-lg font-medium transition-all duration-150 cursor-pointer flex items-center gap-1.5 ${
      isFocusMode ? 'text-xs sm:text-sm' : 'text-xs'
    } ${
      isActive
        ? 'bg-surface-raised text-primary shadow-xs ring-1 ring-border-strong font-semibold'
        : 'text-secondary hover:text-primary hover:bg-surface-raised/50'
    }`;

  const selectSecondarySection = (section: 'systems') => {
    onSelectTab(section);
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
      <div
        className={`border-b border-border-subtle bg-canvas/70 shrink-0 ${
          isFocusMode ? 'p-3' : 'p-3.5'
        }`}
      >
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
                <h2
                  className={`font-bold text-primary tracking-tight ${
                    isFocusMode ? 'text-lg sm:text-xl' : 'text-base'
                  }`}
                >
                  <HighlightText text={profile.name} query={searchQuery} />
                </h2>
                {profile.isHighlyRecommended && (
                  <span className="badge-accent inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium">
                    <BadgeCheck className="w-3.5 h-3.5 text-accent" />
                    <span>Strong match</span>
                  </span>
                )}
                {profile.dayRate != null && (
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
                  <HighlightText
                    text={profile.location.split(',')[0] ?? profile.location}
                    query={searchQuery}
                  />
                </span>
                <span className="text-muted/60">•</span>
                <span className="text-accent font-medium">{profile.department}</span>
                <span className="text-muted/60">•</span>
                <span className="font-mono text-secondary">{formatExperience(profile.yearsOfExperience)}{profile.yearsOfExperience == null ? '' : 'y exp'}</span>
                {profile.rating != null && (
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
                className={`min-h-11 px-2.5 sm:px-3 py-1.5 rounded-lg border transition-colors cursor-pointer inline-flex items-center gap-1.5 text-xs font-medium shadow-xs ${
                  isFocusMode
                    ? 'bg-action border-border-strong text-on-action'
                    : 'bg-surface-raised/80 border-border-strong text-secondary hover:text-primary hover:bg-surface-raised'
                }`}
                title={
                  isFocusMode
                    ? 'Exit focus mode (Split View)'
                    : 'Open expanded profile modal (Press F)'
                }
                aria-label={
                  isFocusMode ? 'Exit focused contractor view' : 'Open expanded profile modal'
                }
              >
                {isFocusMode ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
                <span className="hidden sm:inline">{isFocusMode ? 'Exit focus' : 'Expand view'}</span>
              </button>
            )}

            <button
              type="button"
              onClick={() => onToggleBookmark(profile.id)}
              aria-label={
                isBookmarked
                  ? `Remove ${profile.name} from shortlist`
                  : `Save ${profile.name} to shortlist`
              }
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

            {(onToggleCompare || onPrintDossier || canDeleteCrew || onToggleFocusMode) && (
              <div ref={headerActionsRef} className="relative">
                <button
                  ref={headerActionsTriggerRef}
                  type="button"
                  aria-label={`More dossier actions for ${profile.name}`}
                  aria-haspopup="menu"
                  aria-expanded={isHeaderActionsOpen}
                  onClick={() => setIsHeaderActionsOpen((open) => !open)}
                  className={`inline-flex min-h-11 min-w-11 items-center justify-center rounded-lg border transition-colors cursor-pointer ${
                    isHeaderActionsOpen
                      ? 'border-border-strong bg-surface-raised text-primary'
                      : 'border-border-strong bg-surface-raised/80 text-secondary hover:text-primary'
                  }`}
                >
                  <Ellipsis className="h-4 w-4" aria-hidden="true" />
                </button>
                {isHeaderActionsOpen && (
                  <div
                    role="menu"
                    aria-label={`Dossier actions for ${profile.name}`}
                    className="absolute right-0 top-11 z-30 w-56 rounded-[14px] border border-border-strong/80 bg-surface/95 p-1.5 shadow-2xl shadow-black/40 backdrop-blur-xl"
                  >
                    {onToggleFocusMode && !isFocusMode && (
                      <button
                        type="button"
                        role="menuitem"
                        onClick={() => runHeaderAction(onToggleFocusMode)}
                        className="flex min-h-10 w-full items-center gap-3 rounded-lg px-3 text-left text-sm text-secondary hover:bg-surface-raised hover:text-primary"
                      >
                        <Maximize2 className="h-4 w-4" /> Open expanded view
                      </button>
                    )}
                    {onToggleCompare && (
                      <button
                        type="button"
                        role="menuitem"
                        onClick={() => runHeaderAction(() => onToggleCompare(profile))}
                        className="flex min-h-10 w-full items-center gap-3 rounded-lg px-3 text-left text-sm text-secondary hover:bg-surface-raised hover:text-primary"
                      >
                        <Scale className={`h-4 w-4 ${isCompared ? 'text-accent' : ''}`} />
                        {isCompared ? 'Remove from compare' : 'Add to compare'}
                      </button>
                    )}
                    {onPrintDossier && (
                      <button
                        type="button"
                        role="menuitem"
                        onClick={() => runHeaderAction(() => onPrintDossier(profile))}
                        className="flex min-h-10 w-full items-center gap-3 rounded-lg px-3 text-left text-sm text-secondary hover:bg-surface-raised hover:text-primary"
                      >
                        <Printer className="h-4 w-4" /> Print dossier
                      </button>
                    )}
                    {canDeleteCrew && (
                      <button
                        type="button"
                        role="menuitem"
                        onClick={() => runHeaderAction(onRequestDelete)}
                        className="flex min-h-10 w-full items-center gap-3 rounded-lg px-3 text-left text-sm text-danger hover:bg-danger-soft/70 hover:text-danger"
                      >
                        <Trash2 className="h-4 w-4" /> Delete contractor
                      </button>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Navigation Tabs Bar */}
        <div className="mt-2.5 pt-2 border-t border-border-subtle/50">
          <div
            role="group"
            aria-label={`${profile.name} dossier sections`}
            className="flex items-center gap-1 flex-wrap"
          >
            <button
              type="button"
              aria-pressed={activeTab === 'dossier'}
              onClick={() => onSelectTab('dossier')}
              className={sectionButtonClass(activeTab === 'dossier')}
            >
              <Layers className="w-3.5 h-3.5 text-secondary" />
              <span>Overview</span>
            </button>

            <button
              type="button"
              aria-pressed={activeTab === 'experience'}
              onClick={() => onSelectTab('experience')}
              className={sectionButtonClass(activeTab === 'experience')}
            >
              <BriefcaseBusiness className="w-3.5 h-3.5 text-secondary" />
              <span>Experience</span>
            </button>

            <button
              type="button"
              aria-pressed={activeTab === 'credentials'}
              onClick={() => onSelectTab('credentials')}
              className={sectionButtonClass(activeTab === 'credentials')}
            >
              <GraduationCap className="w-3.5 h-3.5 text-secondary" />
              <span>Credentials</span>
            </button>

            <button
              type="button"
              aria-pressed={activeTab === 'expertise'}
              onClick={() => onSelectTab('expertise')}
              className={sectionButtonClass(activeTab === 'expertise')}
            >
              <Activity className="w-3.5 h-3.5 text-secondary" />
              <span>Skills</span>
              <span className="px-1.5 py-0.2 rounded-md bg-surface border border-border-subtle text-secondary font-mono text-xs">
                {profileSkillsCount}
              </span>
            </button>

            <button
              type="button"
              aria-pressed={activeTab === 'vault'}
              onClick={() => onSelectTab('vault')}
              className={sectionButtonClass(activeTab === 'vault')}
            >
              <FileCheck className="w-3.5 h-3.5 text-secondary" />
              <span>Documents</span>
              <span className="px-1.5 py-0.2 rounded-md bg-surface border border-border-subtle text-secondary font-mono text-xs">
                {documentsCount}
              </span>
            </button>

            <div ref={sectionMenuRef} className="relative ml-auto">
              <button
                ref={sectionMenuTriggerRef}
                type="button"
                aria-haspopup="menu"
                aria-expanded={isMoreSectionsOpen}
                aria-pressed={isSecondarySection}
                onClick={() => setIsMoreSectionsOpen((open) => !open)}
                className={sectionButtonClass(isSecondarySection)}
              >
                <Ellipsis className="h-4 w-4" aria-hidden="true" />
                <span>{secondarySectionLabel}</span>
              </button>
              {isMoreSectionsOpen && (
                <div
                  role="menu"
                  aria-label="More dossier sections"
                  className="absolute right-0 top-12 z-30 w-52 rounded-[14px] border border-border-strong/80 bg-surface/95 p-1.5 shadow-2xl shadow-black/40 backdrop-blur-xl"
                >
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => selectSecondarySection('systems')}
                    className="flex min-h-11 w-full items-center gap-3 rounded-lg px-3 text-left text-sm text-secondary hover:bg-surface-raised hover:text-primary"
                  >
                    <Layers className="h-4 w-4" /> Systems experience
                  </button>
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      setIsMoreSectionsOpen(false);
                      onOpenRadarModal();
                    }}
                    className="flex min-h-11 w-full items-center gap-3 rounded-lg px-3 text-left text-sm text-secondary hover:bg-surface-raised hover:text-primary"
                  >
                    <Activity className="h-4 w-4" /> Competency radar
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  );
};
