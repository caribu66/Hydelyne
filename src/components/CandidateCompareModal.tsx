import React, { useEffect, useRef } from 'react';
import { UserProfile } from '../types';
import { motion, AnimatePresence } from 'motion/react';
import {
  X,
  Scale,
  Check,
  Star,
  MapPin,
  Calendar,
  DollarSign,
  Briefcase,
  GraduationCap,
  ShieldCheck,
  Download,
  Printer,
  Send,
  Trash2,
  Plus,
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

export const CandidateCompareModal: React.FC<CandidateCompareModalProps> = ({
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

  // Close on Escape & trap focus
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

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
    link.setAttribute('download', `Hydenlyne_Candidate_Comparison_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handlePrint = () => {
    window.print();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-2 sm:p-4 bg-zinc-950/80 backdrop-blur-md">
      <motion.div
        ref={modalRef}
        initial={{ opacity: 0, scale: 0.96 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.96 }}
        className="w-full max-w-6xl max-h-[92vh] flex flex-col bg-zinc-900 border border-zinc-800 rounded-2xl shadow-2xl overflow-hidden"
        role="dialog"
        aria-modal="true"
        aria-labelledby="compare-modal-title"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-800 bg-zinc-900/90 shrink-0">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-9 h-9 rounded-xl bg-blue-950/60 border border-blue-800/60 text-blue-400">
              <Scale className="w-4 h-4" />
            </div>
            <div>
              <h2 id="compare-modal-title" className="text-base font-semibold text-zinc-100 flex items-center gap-2">
                Specialist Comparison Matrix
                <span className="text-xs font-mono font-normal px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-300">
                  {compareProfiles.length} of 4 selected
                </span>
              </h2>
              <p className="text-xs text-zinc-400">
                Side-by-side technical evaluation across rates, offshore tickets, and survey track record.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handlePrint}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-zinc-800 hover:bg-zinc-750 border border-zinc-700 text-xs font-medium text-zinc-300 hover:text-white transition-colors cursor-pointer"
              title="Print comparison table"
            >
              <Printer className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Print</span>
            </button>
            <button
              type="button"
              onClick={handleExportCSV}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-zinc-800 hover:bg-zinc-750 border border-zinc-700 text-xs font-medium text-zinc-300 hover:text-white transition-colors cursor-pointer"
              title="Download CSV report"
            >
              <Download className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Export CSV</span>
            </button>
            <button
              type="button"
              onClick={onClose}
              className="p-1.5 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-white transition-colors cursor-pointer"
              aria-label="Close comparison"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Content Body */}
        {compareProfiles.length === 0 ? (
          <div className="p-12 text-center text-zinc-400 space-y-3">
            <Scale className="w-10 h-10 text-zinc-600 mx-auto" />
            <h3 className="text-sm font-medium text-zinc-200">No specialists selected for comparison</h3>
            <p className="text-xs text-zinc-400 max-w-sm mx-auto">
              Select 2 to 4 candidates from the candidate list or shortlist drawer to compare their credentials side-by-side.
            </p>
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto overflow-x-auto p-4 sm:p-6 space-y-6">
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
                    className="p-4 rounded-xl bg-zinc-950/60 border border-zinc-800 flex flex-col justify-between space-y-3 relative group"
                  >
                    <button
                      type="button"
                      onClick={() => onRemoveProfile(p.id)}
                      className="absolute top-2.5 right-2.5 p-1 rounded-lg text-zinc-500 hover:text-red-400 hover:bg-zinc-900 transition-colors"
                      title="Remove from comparison"
                      aria-label={`Remove ${p.name} from comparison`}
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>

                    <div className="flex items-start gap-3">
                      <img
                        src={p.avatar}
                        alt={p.name}
                        className="w-12 h-12 rounded-xl object-cover border border-zinc-700/80 shrink-0"
                      />
                      <div className="min-w-0 pr-4">
                        <button
                          type="button"
                          onClick={() => onSelectProfileDetail(p)}
                          className="font-semibold text-sm text-zinc-100 hover:text-blue-400 text-left transition-colors truncate block"
                        >
                          {p.name}
                        </button>
                        <p className="text-[11px] text-zinc-400 line-clamp-1">{p.title}</p>
                        <div className="flex items-center gap-1.5 text-[11px] text-zinc-500 mt-1">
                          <MapPin className="w-3 h-3 shrink-0" />
                          <span className="truncate">{p.location}</span>
                        </div>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-2 pt-2 border-t border-zinc-850 text-xs">
                      <div>
                        <span className="text-[10px] text-zinc-500 block uppercase font-mono">Day Rate</span>
                        <span className="font-semibold text-zinc-200 font-mono">
                          {p.dayRate ? `£${p.dayRate}/d` : 'Negotiable'}
                        </span>
                      </div>
                      <div>
                        <span className="text-[10px] text-zinc-500 block uppercase font-mono">Status</span>
                        <span
                          className={`inline-flex items-center gap-1 font-medium ${
                            isAvailableNow ? 'text-emerald-400' : 'text-zinc-400'
                          }`}
                        >
                          <span className={`w-1.5 h-1.5 rounded-full ${isAvailableNow ? 'bg-emerald-400' : 'bg-zinc-600'}`} />
                          <span className="truncate">{(p.availability || 'Available').split(' ')[0]}</span>
                        </span>
                      </div>
                    </div>

                    <div className="pt-2 flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => onRequestMobilization(p)}
                        className="w-full py-1.5 px-3 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs flex items-center justify-center gap-1.5 transition-colors cursor-pointer"
                      >
                        <Send className="w-3 h-3" />
                        <span>Inquire</span>
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Matrix Rows */}
            <div className="space-y-4 pt-2">
              {/* Row: Experience & Seniority */}
              <div className="border border-zinc-800 rounded-xl overflow-hidden bg-zinc-950/40">
                <div className="px-4 py-2 bg-zinc-850/60 border-b border-zinc-800 font-mono text-xs font-semibold text-zinc-300 flex items-center gap-2">
                  <Briefcase className="w-3.5 h-3.5 text-blue-400" />
                  <span>Experience & Operational Seniority</span>
                </div>
                <div
                  className="grid p-4 gap-4 divide-x divide-zinc-850"
                  style={{
                    gridTemplateColumns: `repeat(${compareProfiles.length}, minmax(240px, 1fr))`,
                  }}
                >
                  {compareProfiles.map((p) => (
                    <div key={p.id} className="first:pl-0 pl-4 space-y-1.5">
                      <div className="flex items-baseline gap-2">
                        <span className="text-lg font-bold text-zinc-100 font-mono">{p.yearsOfExperience}</span>
                        <span className="text-xs text-zinc-400">years offshore / industry</span>
                      </div>
                      <p className="text-xs text-zinc-300 leading-relaxed line-clamp-3">{p.bio}</p>
                    </div>
                  ))}
                </div>
              </div>

              {/* Row: Mandatory Offshore Certifications */}
              <div className="border border-zinc-800 rounded-xl overflow-hidden bg-zinc-950/40">
                <div className="px-4 py-2 bg-zinc-850/60 border-b border-zinc-800 font-mono text-xs font-semibold text-zinc-300 flex items-center gap-2">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Accreditations & Offshore Safety Tickets</span>
                </div>
                <div
                  className="grid p-4 gap-4 divide-x divide-zinc-850"
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
                        <span className="text-xs text-zinc-500 italic">No formal certifications listed</span>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* Row: Core Technical Competencies & Software */}
              <div className="border border-zinc-800 rounded-xl overflow-hidden bg-zinc-950/40">
                <div className="px-4 py-2 bg-zinc-850/60 border-b border-zinc-800 font-mono text-xs font-semibold text-zinc-300 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Check className="w-3.5 h-3.5 text-cyan-400" />
                    <span>Technical Competencies & Specialized Tools</span>
                  </div>
                  {sharedSkills.length > 0 && (
                    <span className="text-[11px] text-blue-400 font-normal">
                      ({sharedSkills.length} competencies shared across cohort)
                    </span>
                  )}
                </div>
                <div
                  className="grid p-4 gap-4 divide-x divide-zinc-850"
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
                              className={`px-2 py-0.5 rounded-lg text-xs font-medium border ${
                                isShared
                                  ? 'bg-blue-950/50 border-blue-800/60 text-blue-300 font-semibold'
                                  : 'bg-zinc-900 border-zinc-800 text-zinc-300'
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
              <div className="border border-zinc-800 rounded-xl overflow-hidden bg-zinc-950/40">
                <div className="px-4 py-2 bg-zinc-850/60 border-b border-zinc-800 font-mono text-xs font-semibold text-zinc-300 flex items-center gap-2">
                  <Calendar className="w-3.5 h-3.5 text-purple-400" />
                  <span>Survey Types & Major Project Track Record</span>
                </div>
                <div
                  className="grid p-4 gap-4 divide-x divide-zinc-850"
                  style={{
                    gridTemplateColumns: `repeat(${compareProfiles.length}, minmax(240px, 1fr))`,
                  }}
                >
                  {compareProfiles.map((p) => (
                    <div key={p.id} className="first:pl-0 pl-4 space-y-2 text-xs">
                      <div>
                        <span className="text-[10px] text-zinc-500 uppercase font-mono block">Survey Types</span>
                        <p className="text-zinc-300 font-medium">{p.surveyTypes?.join(' • ') || 'General Marine'}</p>
                      </div>
                      <div>
                        <span className="text-[10px] text-zinc-500 uppercase font-mono block">Past Operators / Clients</span>
                        <p className="text-zinc-400">{p.pastCompanies?.join(', ') || 'N/A'}</p>
                      </div>
                      <div>
                        <span className="text-[10px] text-zinc-500 uppercase font-mono block">Featured Campaigns</span>
                        <p className="text-zinc-400">{p.featuredProjects?.join(' | ') || 'N/A'}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Row: Academic Credentials */}
              <div className="border border-zinc-800 rounded-xl overflow-hidden bg-zinc-950/40">
                <div className="px-4 py-2 bg-zinc-850/60 border-b border-zinc-800 font-mono text-xs font-semibold text-zinc-300 flex items-center gap-2">
                  <GraduationCap className="w-3.5 h-3.5 text-amber-400" />
                  <span>Education & Academic Background</span>
                </div>
                <div
                  className="grid p-4 gap-4 divide-x divide-zinc-850"
                  style={{
                    gridTemplateColumns: `repeat(${compareProfiles.length}, minmax(240px, 1fr))`,
                  }}
                >
                  {compareProfiles.map((p) => (
                    <div key={p.id} className="first:pl-0 pl-4 text-xs text-zinc-300">
                      {p.education}
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Quick Add more candidates selector */}
            {compareProfiles.length < 4 && availableToAdd.length > 0 && (
              <div className="p-4 rounded-xl bg-zinc-950/40 border border-dashed border-zinc-800 flex items-center justify-between gap-3">
                <div className="text-xs text-zinc-400">
                  <span className="font-semibold text-zinc-200 block">Add another specialist to this comparison</span>
                  Compare up to 4 candidates simultaneously.
                </div>
                <div className="flex items-center gap-2">
                  <select
                    className="px-3 py-1.5 rounded-xl bg-zinc-900 border border-zinc-750 text-xs text-zinc-200 focus:outline-none focus:border-blue-500"
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
    </div>
  );
};
