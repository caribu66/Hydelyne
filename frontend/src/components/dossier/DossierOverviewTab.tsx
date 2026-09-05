import { FC } from 'react';
import { UserProfile, SpecialistDocument } from '../../types';
import { HighlightText } from '../HighlightText';
import { CertificationBadge } from '../CertificationBadge';
import {
  Sparkles,
  Compass,
  ShieldCheck,
  MapPin,
  Layers,
  GraduationCap,
  Building,
  Loader2,
} from 'lucide-react';

interface DossierOverviewTabProps {
  profile: UserProfile;
  isFocusMode: boolean;
  searchQuery?: string;
  summary?: string;
  summaryLoading?: boolean;
  documents?: SpecialistDocument[];
  onSelectTab: (tab: 'experience' | 'expertise' | 'credentials') => void;
}

export const DossierOverviewTab: FC<DossierOverviewTabProps> = ({
  profile,
  isFocusMode,
  searchQuery = '',
  summary,
  summaryLoading = false,
  documents = [],
  onSelectTab,
}) => {
  const isAvailableNow = profile.availability?.toLowerCase().includes('immediately');
  const readableSummary = summary?.trim();
  const hasReadableSummary = Boolean(
    readableSummary && !readableSummary.startsWith('{') && !readableSummary.startsWith('['),
  );
  const profileSkills = Array.from(new Set([...(profile.skills ?? []), ...(profile.expertise ?? [])]));
  const credentialCount = profile.certificationDetails?.length ?? profile.certifications?.length ?? 0;
  const indexedDocumentCount = documents.filter((doc) => doc.extractionStatus === 'extracted').length;
  const latestProject = [...(profile.workHistory ?? [])].sort((left, right) =>
    (right.startDate ?? '').localeCompare(left.startDate ?? ''),
  )[0];
  const highlightedSkills = profileSkills.slice(0, 3);

  return (
    <div className={isFocusMode ? 'grid grid-cols-1 lg:grid-cols-2 gap-2.5' : 'space-y-3'}>
      {/* Quick Context Strip */}
      <div
        className={`fit-summary flex items-start gap-3 rounded-[12px] p-3 border border-border-subtle/80 bg-surface-raised/30 ${
          isFocusMode ? 'lg:col-span-2' : ''
        }`}
      >
        <div className="p-1.5 rounded-lg bg-surface-raised text-primary shrink-0 mt-0.5">
          <Sparkles className="h-3.5 w-3.5 text-accent" aria-hidden="true" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold uppercase tracking-wider font-mono text-secondary">
            Why this contractor
          </p>
          <p className="mt-1 text-xs leading-relaxed text-secondary">
            {profile.name} brings{' '}
            <strong className="font-semibold text-primary">
              {profile.yearsOfExperience} years
            </strong>{' '}
            of offshore experience in {profile.department.toLowerCase()} and is{' '}
            {isAvailableNow ? 'available for immediate mobilization' : profile.availability.toLowerCase()}.
          </p>
        </div>
      </div>

      {/* AI Summary — generated on first profile view, cached after that */}
      {(summaryLoading || hasReadableSummary) && (
        <div
          className={`space-y-1.5 bg-canvas/40 rounded-[10px] border border-border-subtle/60 ${
            isFocusMode ? 'p-2 lg:col-span-2' : 'p-3'
          }`}
        >
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
      <div
        className={`space-y-1.5 bg-canvas/40 rounded-[10px] border border-border-subtle/60 ${
          isFocusMode ? 'p-2 lg:col-span-2' : 'p-3'
        }`}
      >
        <h4 className="text-xs font-semibold text-secondary uppercase tracking-wider font-mono">
          Overview & Track Record
        </h4>
        <p className="text-secondary leading-relaxed">
          <HighlightText text={profile.bio} query={searchQuery} />
        </p>
      </div>

      {/* At a glance cards */}
      <section
        aria-label="At a glance"
        className={`grid grid-cols-1 gap-2.5 sm:grid-cols-3 ${isFocusMode ? 'lg:col-span-2' : ''}`}
      >
        <button
          type="button"
          onClick={() => onSelectTab('credentials')}
          className="group rounded-[12px] border border-border-subtle bg-surface-raised/40 p-3.5 text-left transition-all duration-200 hover:bg-surface-raised/80 hover:border-border-strong focus:outline-hidden focus:ring-2 focus:ring-focus cursor-pointer"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-muted font-mono">
              Deployment
            </span>
            <span
              className={`w-2 h-2 rounded-full ${isAvailableNow ? 'bg-positive' : 'bg-surface-selected'}`}
            />
          </div>
          <span
            className={`mt-2 block text-sm font-semibold tracking-tight ${
              isAvailableNow ? 'text-positive' : 'text-primary'
            }`}
          >
            {profile.availability}
          </span>
          <span className="mt-1 block text-xs text-secondary">
            {credentialCount} credentials · {documents.length} docs
            {indexedDocumentCount > 0 ? ` · ${indexedDocumentCount} verified` : ''}
          </span>
        </button>

        <button
          type="button"
          onClick={() => onSelectTab('expertise')}
          className="group rounded-[12px] border border-border-subtle bg-surface-raised/40 p-3.5 text-left transition-all duration-200 hover:bg-surface-raised/80 hover:border-border-strong focus:outline-hidden focus:ring-2 focus:ring-focus cursor-pointer"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-muted font-mono">
              Strengths
            </span>
            <span className="text-xs font-mono text-muted">{profileSkills.length}</span>
          </div>
          <span className="mt-2 block text-sm font-semibold tracking-tight text-primary">
            {profileSkills.length} Core Skills
          </span>
          <span className="mt-1 line-clamp-2 block text-xs leading-relaxed text-secondary">
            {highlightedSkills.length > 0 ? highlightedSkills.join(' · ') : 'No skills extracted yet'}
          </span>
        </button>

        <button
          type="button"
          onClick={() => onSelectTab('experience')}
          className="group rounded-[12px] border border-border-subtle bg-surface-raised/40 p-3.5 text-left transition-all duration-200 hover:bg-surface-raised/80 hover:border-border-strong focus:outline-hidden focus:ring-2 focus:ring-focus cursor-pointer"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-muted font-mono">
              Track Record
            </span>
            <span className="text-xs font-mono text-muted">{profile.workHistory?.length ?? 0}</span>
          </div>
          <span className="mt-2 block text-sm font-semibold tracking-tight text-primary">
            {profile.workHistory?.length ?? 0} Projects · {profile.geographicalExperience?.length ?? 0} Regions
          </span>
          <span className="mt-1 block truncate text-xs text-secondary">
            {latestProject
              ? `${latestProject.clientName ?? 'Recent project'} · ${
                  latestProject.role ?? latestProject.projectType ?? 'Role recorded'
                }`
              : 'No project history extracted yet'}
          </span>
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
              <span
                key={place}
                className="px-2.5 py-1 rounded-md bg-surface-raised/60 border border-border-subtle text-secondary font-medium text-xs hover:border-border-strong transition-colors"
              >
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
              <span
                key={system}
                className="px-2.5 py-1 rounded-md bg-surface-raised/60 border border-border-subtle text-secondary font-medium text-xs hover:border-border-strong transition-colors"
              >
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
              <span
                key={item}
                className="px-2.5 py-1 rounded-md bg-surface-raised/60 border border-border-subtle text-secondary font-medium text-xs hover:border-border-strong transition-colors"
              >
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
  );
};
