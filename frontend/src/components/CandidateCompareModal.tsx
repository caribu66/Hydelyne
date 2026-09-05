import { FC, useRef } from 'react';
import { useAccessibleDialog } from '../hooks/useAccessibleDialog';
import { UserProfile } from '../types';
import { AnimatePresence, motion } from 'motion/react';
import {
  X,
  Scale,
  Check,
  MapPin,
  Calendar,
  Briefcase,
  GraduationCap,
  ShieldCheck,
  Download,
  Printer,
  Send,
  Trash2,
} from 'lucide-react';
import { CertificationBadge } from './CertificationBadge';

interface CandidateCompareModalProps {
  isOpen: boolean;
  onClose: () => void;
  compareProfiles: UserProfile[];
  allProfiles: UserProfile[];
  onRemoveProfile: (id: string) => void;
  onAddProfile: (profile: UserProfile) => void;
  onRequestMobilization: (profile: UserProfile) => void;
  onSelectProfileDetail: (profile: UserProfile) => void;
}

export const CandidateCompareModal: FC<CandidateCompareModalProps> = ({
  isOpen,
  onClose,
  compareProfiles,
  allProfiles,
  onRemoveProfile,
  onAddProfile,
  onRequestMobilization,
  onSelectProfileDetail,
}) => {
  const modalRef = useRef<HTMLDivElement>(null);

  useAccessibleDialog(isOpen, modalRef, onClose);

  // Calculate common vs unique skills
  const allSkillsInCohort = Array.from(
    new Set(compareProfiles.flatMap((p) => p.skills))
  );

  const sharedSkills = allSkillsInCohort.filter((skill) =>
    compareProfiles.every((p) => p.skills.includes(skill))
  );

  // Available profiles to add (not currently in compare)
  const availableToAdd = allProfiles.filter(
    (p) => !compareProfiles.some((cp) => cp.id === p.id)
  );

  // Export comparison table as CSV
  const handleExportCSV = () => {
    if (compareProfiles.length === 0) return;
    const headers = ['Metric', ...compareProfiles.map((p) => p.name)];
    const rows = [
      ['Title', ...compareProfiles.map((p) => `"${p.title}"`)],
      ['Location', ...compareProfiles.map((p) => `"${p.location}"`)],
      ['Availability', ...compareProfiles.map((p) => `"${p.availability || 'Available'}"`)],
      ['Day Rate (GBP)', ...compareProfiles.map((p) => `£${p.dayRate || 'N/A'}`)],
      ['Experience (Years)', ...compareProfiles.map((p) => `${p.yearsOfExperience} yrs`)],
      ['Rating', ...compareProfiles.map((p) => `${p.rating || 4.9}/5.0`)],
      ['Certifications', ...compareProfiles.map((p) => `"${(p.certifications || []).join(', ')}"`)],
      ['Core Skills', ...compareProfiles.map((p) => `"${p.skills.join(', ')}"`)],
      ['Survey Types', ...compareProfiles.map((p) => `"${(p.surveyTypes || []).join(', ')}"`)],
      ['Past Clients', ...compareProfiles.map((p) => `"${(p.pastCompanies || []).join(', ')}"`)],
      ['Email', ...compareProfiles.map((p) => p.email)],
    ];

    const csvContent = [headers.join(','), ...rows.map((r) => r.join(','))].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `Hydenlyne_Contractor_Comparison_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handlePrint = () => {
    window.print();
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.18, ease: 'easeOut' }}
          className="fixed inset-0 z-50 flex items-center justify-center p-2 sm:p-4 bg-canvas/80 backdrop-blur-xs"
        >
          <motion.div
            ref={modalRef}
            initial={{ opacity: 0, scale: 0.96, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 8 }}
            transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
            className="w-full max-w-6xl max-h-[92vh] flex flex-col bg-surface border border-border-subtle rounded-[14px] shadow-2xl overflow-hidden"
            role="dialog"
            aria-modal="true"
            aria-labelledby="compare-modal-title"
          >
        {/* Header */}
        <div className="sticky top-0 z-10 flex items-center justify-between px-5 sm:px-6 py-4 border-b border-border-subtle bg-surface/95 backdrop-blur-sm shrink-0">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-surface-raised border border-border-subtle text-secondary">
              <Scale className="w-4 h-4" />
            </div>
            <div>
              <h2 id="compare-modal-title" className="text-sm sm:text-base font-semibold text-primary flex items-center gap-2">
                Compare specialists
                <span className="text-xs font-mono font-normal px-2 py-0.5 rounded-full bg-surface-raised border border-border-subtle text-secondary">
                  {compareProfiles.length} of 4 selected
                </span>
              </h2>
              <p className="text-xs text-secondary">
                Review rates, credentials, and survey history side by side.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handlePrint}
              aria-label="Print specialist comparison"
              className="inline-flex min-h-9 items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface hover:bg-surface-raised border border-border-subtle hover:border-border-strong text-xs font-medium text-secondary hover:text-primary transition-colors cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-focus"
              title="Print comparison table"
            >
              <Printer className="w-3.5 h-3.5 text-secondary" />
              <span className="hidden sm:inline">Print</span>
            </button>
            <button
              type="button"
              onClick={handleExportCSV}
              aria-label="Export specialist comparison as CSV"
              className="inline-flex min-h-9 items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface hover:bg-surface-raised border border-border-subtle hover:border-border-strong text-xs font-medium text-secondary hover:text-primary transition-colors cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-focus"
              title="Download CSV report"
            >
              <Download className="w-3.5 h-3.5 text-secondary" />
              <span className="hidden sm:inline">Export CSV</span>
            </button>
            <button
              type="button"
              onClick={onClose}
              className="inline-flex min-h-9 min-w-9 items-center justify-center rounded-lg bg-surface hover:bg-surface-raised border border-border-subtle hover:border-border-strong text-secondary hover:text-primary transition-colors cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-focus"
              aria-label="Close comparison"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Content Body */}
        {compareProfiles.length === 0 ? (
          <div className="p-12 text-center text-secondary space-y-3">
            <Scale className="w-10 h-10 text-muted mx-auto" />
            <h3 className="text-sm font-semibold text-primary">No specialists selected for comparison</h3>
            <p className="text-xs text-muted max-w-sm mx-auto">
              Select 2 to 4 specialists from the search workspace or shortlist to compare their credentials side-by-side.
            </p>
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto overflow-x-auto p-4 sm:p-6 space-y-6">
            {/* Guidance banner when only 1 specialist is currently added */}
            {compareProfiles.length === 1 && (
              <div className="p-3.5 rounded-lg bg-surface-raised border border-border-subtle flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs">
                <div className="flex items-center gap-2.5 text-secondary">
                  <Scale className="w-4 h-4 text-accent shrink-0" />
                  <span>
                    <strong className="text-primary font-medium">Select a second specialist</strong> to unlock side-by-side comparison metrics.
                  </span>
                </div>
                {availableToAdd.length > 0 && (
                  <div className="flex items-center gap-2 w-full sm:w-auto">
                    <label htmlFor="quick-add-compare-top" className="sr-only">Add another specialist</label>
                    <select
                      id="quick-add-compare-top"
                      className="w-full sm:w-auto min-h-9 px-3 py-1.5 rounded-lg bg-surface border border-border-subtle hover:border-border-strong text-xs text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-focus cursor-pointer"
                      onChange={(e) => {
                        const selected = availableToAdd.find((p) => p.id === e.target.value);
                        if (selected) {
                          onAddProfile(selected);
                          e.target.value = '';
                        }
                      }}
                      defaultValue=""
                    >
                      <option value="" disabled>Choose specialist to compare with {compareProfiles[0]?.name.split(' ')[0]}...</option>
                      {availableToAdd.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name} — {p.title.slice(0, 30)} (Day rate: £{p.dayRate || 'N/A'})
                        </option>
                      ))}
                    </select>
                  </div>
                )}
              </div>
            )}

            {/* Candidate Column Cards */}
            <div
              className="grid gap-4"
              style={{
                gridTemplateColumns: `repeat(${Math.max(compareProfiles.length, 1)}, minmax(240px, 1fr))`,
              }}
            >
              {compareProfiles.map((p) => {
                const isAvailableNow = (p.availability || '').toLowerCase().includes('immediately');
                return (
                  <div
                    key={p.id}
                    className="p-4 rounded-[14px] bg-surface-raised/40 border border-border-subtle flex flex-col justify-between space-y-3 relative group hover:border-border-strong transition-colors"
                  >
                    <button
                      type="button"
                      onClick={() => onRemoveProfile(p.id)}
                      className="absolute top-2.5 right-2.5 inline-flex min-h-8 min-w-8 items-center justify-center rounded-lg text-muted hover:text-danger hover:bg-surface transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-focus cursor-pointer"
                      title="Remove from comparison"
                      aria-label={`Remove ${p.name} from comparison`}
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>

                    <div className="flex items-start gap-3">
                      <div className="relative shrink-0">
                        {p.avatar ? (
                          <img
                            src={p.avatar}
                            alt={p.name}
                            referrerPolicy="no-referrer"
                            className="w-11 h-11 rounded-[10px] object-cover border border-border-subtle"
                            onError={(e) => {
                              // If image fails to load, hide image and show initials
                              e.currentTarget.style.display = 'none';
                              const fallback = e.currentTarget.nextElementSibling;
                              if (fallback) (fallback as HTMLElement).style.display = 'flex';
                            }}
                          />
                        ) : null}
                        <div
                          className={`w-11 h-11 rounded-[10px] bg-surface-raised border border-border-subtle items-center justify-center font-bold text-xs text-primary shrink-0 tracking-wider ${
                            p.avatar ? 'hidden' : 'flex'
                          }`}
                        >
                          {p.name
                            .split(' ')
                            .map((n) => n[0])
                            .join('')
                            .slice(0, 2)}
                        </div>
                        {isAvailableNow && (
                          <span
                            className="absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full bg-positive border-2 border-surface"
                            title="Available immediately"
                          />
                        )}
                      </div>
                      <div className="min-w-0 pr-6">
                        <button
                          type="button"
                          onClick={() => onSelectProfileDetail(p)}
                          className="font-semibold text-sm text-primary hover:text-primary transition-colors truncate block text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-focus rounded-sm"
                        >
                          {p.name}
                        </button>
                        <p className="text-xs text-secondary truncate">{p.title}</p>
                        <div className="flex items-center gap-1.5 text-xs text-muted mt-1">
                          <MapPin className="w-3 h-3 shrink-0" />
                          <span className="truncate">{p.location.split(',')[0]}</span>
                        </div>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-2 pt-2 border-t border-border-subtle text-xs">
                      <div>
                        <span className="text-xs text-muted block font-mono">Day Rate</span>
                        <span className="font-semibold text-primary font-mono">
                          {p.dayRate ? `£${p.dayRate}/d` : 'Negotiable'}
                        </span>
                      </div>
                      <div>
                        <span className="text-xs text-muted block font-mono">Status</span>
                        <span className={`inline-flex items-center gap-1 font-medium ${isAvailableNow ? 'text-positive' : 'text-secondary'}`}>
                          <span className={`w-1.5 h-1.5 rounded-full ${isAvailableNow ? 'bg-positive' : 'bg-surface-selected'}`} />
                          <span className="truncate">{(p.availability || 'Available').replace('Available ', '')}</span>
                        </span>
                      </div>
                    </div>

                    <div className="pt-2 flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => onRequestMobilization(p)}
                        className="w-full inline-flex min-h-9 items-center justify-center gap-1.5 px-3 rounded-lg bg-action hover:bg-action-hover text-on-action font-semibold text-xs transition-colors cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                      >
                        <Send className="w-3.5 h-3.5" />
                        <span>Request Mobilization</span>
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Matrix Rows */}
            <div className="space-y-4 pt-1">
              {/* Row: Experience & Seniority */}
              <div className="border border-border-subtle rounded-[14px] overflow-hidden bg-surface-raised/20">
                <div className="px-4 py-2.5 bg-surface-raised/60 border-b border-border-subtle font-mono text-xs font-semibold text-secondary flex items-center gap-2">
                  <Briefcase className="w-3.5 h-3.5 text-accent" />
                  <span>Experience & Operational Seniority</span>
                </div>
                <div
                  className="grid p-4 gap-4 divide-x divide-border-subtle"
                  style={{
                    gridTemplateColumns: `repeat(${compareProfiles.length}, minmax(240px, 1fr))`,
                  }}
                >
                  {compareProfiles.map((p) => (
                    <div key={p.id} className="first:pl-0 pl-4 space-y-1.5">
                      <div className="flex items-baseline gap-2">
                        <span className="text-base font-bold text-primary font-mono">{p.yearsOfExperience}</span>
                        <span className="text-xs text-muted">years offshore experience</span>
                      </div>
                      <p className="text-xs text-secondary leading-relaxed line-clamp-3">{p.bio}</p>
                    </div>
                  ))}
                </div>
              </div>

              {/* Row: Mandatory Offshore Certifications */}
              <div className="border border-border-subtle rounded-[14px] overflow-hidden bg-surface-raised/20">
                <div className="px-4 py-2.5 bg-surface-raised/60 border-b border-border-subtle font-mono text-xs font-semibold text-secondary flex items-center gap-2">
                  <ShieldCheck className="w-3.5 h-3.5 text-positive" />
                  <span>Accreditations & Offshore Safety Tickets</span>
                </div>
                <div
                  className="grid p-4 gap-4 divide-x divide-border-subtle"
                  style={{
                    gridTemplateColumns: `repeat(${compareProfiles.length}, minmax(240px, 1fr))`,
                  }}
                >
                  {compareProfiles.map((p) => (
                    <div key={p.id} className="first:pl-0 pl-4">
                      {p.certifications && p.certifications.length > 0 ? (
                        <div className="flex flex-wrap gap-1.5">
                          {p.certifications.map((cert) => (
                            <CertificationBadge key={cert} certification={cert} size="sm" />
                          ))}
                        </div>
                      ) : (
                        <span className="text-xs text-muted italic">No formal certifications listed</span>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* Row: Core Technical Competencies & Software */}
              <div className="border border-border-subtle rounded-[14px] overflow-hidden bg-surface-raised/20">
                <div className="px-4 py-2.5 bg-surface-raised/60 border-b border-border-subtle font-mono text-xs font-semibold text-secondary flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Check className="w-3.5 h-3.5 text-accent" />
                    <span>Technical Competencies & Specialized Tools</span>
                  </div>
                  {sharedSkills.length > 0 && (
                    <span className="text-xs text-muted font-normal font-mono">
                      ({sharedSkills.length} competencies shared)
                    </span>
                  )}
                </div>
                <div
                  className="grid p-4 gap-4 divide-x divide-border-subtle"
                  style={{
                    gridTemplateColumns: `repeat(${compareProfiles.length}, minmax(240px, 1fr))`,
                  }}
                >
                  {compareProfiles.map((p) => (
                    <div key={p.id} className="first:pl-0 pl-4">
                      <div className="flex flex-wrap gap-1.5">
                        {p.skills.map((skill) => {
                          const isShared = sharedSkills.includes(skill);
                          return (
                            <span
                              key={skill}
                              className={`px-2 py-0.5 rounded-md text-xs font-medium border ${
                                isShared
                                  ? 'badge-accent'
                                  : 'bg-surface border-border-subtle text-secondary'
                              }`}
                            >
                              {skill}
                            </span>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Row: Survey Disciplines & Track Record */}
              <div className="border border-border-subtle rounded-[14px] overflow-hidden bg-surface-raised/20">
                <div className="px-4 py-2.5 bg-surface-raised/60 border-b border-border-subtle font-mono text-xs font-semibold text-secondary flex items-center gap-2">
                  <Calendar className="w-3.5 h-3.5 text-secondary" />
                  <span>Survey Types & Major Project Track Record</span>
                </div>
                <div
                  className="grid p-4 gap-4 divide-x divide-border-subtle"
                  style={{
                    gridTemplateColumns: `repeat(${compareProfiles.length}, minmax(240px, 1fr))`,
                  }}
                >
                  {compareProfiles.map((p) => (
                    <div key={p.id} className="first:pl-0 pl-4 space-y-2 text-xs">
                      <div>
                        <span className="text-xs text-muted font-mono block">Survey Types</span>
                        <p className="text-secondary font-medium">{p.surveyTypes?.join(' • ') || 'General Marine'}</p>
                      </div>
                      <div>
                        <span className="text-xs text-muted font-mono block">Past Operators / Clients</span>
                        <p className="text-secondary">{p.pastCompanies?.join(', ') || 'N/A'}</p>
                      </div>
                      <div>
                        <span className="text-xs text-muted font-mono block">Featured Campaigns</span>
                        <p className="text-secondary">{p.featuredProjects?.join(' | ') || 'N/A'}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Row: Academic Credentials */}
              <div className="border border-border-subtle rounded-[14px] overflow-hidden bg-surface-raised/20">
                <div className="px-4 py-2.5 bg-surface-raised/60 border-b border-border-subtle font-mono text-xs font-semibold text-secondary flex items-center gap-2">
                  <GraduationCap className="w-3.5 h-3.5 text-warning" />
                  <span>Education & Academic Background</span>
                </div>
                <div
                  className="grid p-4 gap-4 divide-x divide-border-subtle"
                  style={{
                    gridTemplateColumns: `repeat(${compareProfiles.length}, minmax(240px, 1fr))`,
                  }}
                >
                  {compareProfiles.map((p) => (
                    <div key={p.id} className="first:pl-0 pl-4 text-xs text-secondary">
                      {p.education}
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Quick Add more candidates selector */}
            {compareProfiles.length < 4 && availableToAdd.length > 0 && (
              <div className="p-4 rounded-[14px] bg-surface-raised/40 border border-dashed border-border-subtle flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                <div className="text-xs text-secondary">
                  <span className="font-semibold text-primary block">Add another specialist to this comparison</span>
                  Compare up to 4 specialists simultaneously.
                </div>
                <div className="flex items-center gap-2 w-full sm:w-auto">
                  <select
                    className="w-full sm:w-auto px-3 py-1.5 rounded-lg bg-surface border border-border-subtle hover:border-border-strong text-xs text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-focus cursor-pointer"
                    onChange={(e) => {
                      const selected = availableToAdd.find((p) => p.id === e.target.value);
                      if (selected) {
                        onAddProfile(selected);
                        e.target.value = '';
                      }
                    }}
                    defaultValue=""
                  >
                    <option value="" disabled>Select a specialist to add...</option>
                    {availableToAdd.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name} ({p.title.slice(0, 30)}... - £{p.dayRate || 800}/d)
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            )}
          </div>
        )}
      </motion.div>
    </motion.div>
    )}
  </AnimatePresence>
  );
};
