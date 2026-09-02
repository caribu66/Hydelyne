import { FC, useEffect } from 'react';
import { UserProfile } from '../types';
import {
  Check,
  Printer,
  X,
} from 'lucide-react';

interface DossierPrintViewProps {
  profile: UserProfile | null;
  onClose: () => void;
}

export const DossierPrintView: FC<DossierPrintViewProps> = ({ profile, onClose }) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  if (!profile) return null;

  const handlePrint = () => {
    window.print();
  };

  return (
    <div className="fixed inset-0 z-50 bg-canvas/90 backdrop-blur-md flex items-center justify-center p-2 sm:p-4 overflow-y-auto">
      <div className="w-full max-w-4xl bg-white text-on-action rounded-[14px] shadow-2xl overflow-hidden flex flex-col my-auto border border-border-strong">
        {/* Screen-only Controls Header */}
        <div className="print:hidden flex items-center justify-between px-6 py-3.5 bg-surface text-primary border-b border-border-subtle">
          <div className="flex items-center gap-2 text-xs font-semibold">
            <span className="w-2 h-2 rounded-full bg-positive" />
            <span>Specialist Dossier Preview (Print-Ready)</span>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handlePrint}
              className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-[10px] bg-action hover:bg-action-hover text-on-action font-medium text-xs shadow-xs transition-colors cursor-pointer"
            >
              <Printer className="w-3.5 h-3.5" />
              <span>Print / Save as PDF</span>
            </button>
            <button
              type="button"
              onClick={onClose}
              className="p-1.5 rounded-[10px] bg-surface-raised hover:bg-surface-selected text-secondary hover:text-primary transition-colors cursor-pointer"
              aria-label="Close"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Printable Dossier Document Body */}
        <div id="printable-dossier" className="p-8 sm:p-12 space-y-8 bg-white text-on-action font-sans">
          {/* Document Letterhead */}
          <div className="flex items-start justify-between border-b-2 border-border-subtle pb-6">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs uppercase tracking-widest text-accent font-bold">
                  HYDENLYNE ENERGY & MARINE CONSULTANCY
                </span>
              </div>
              <h1 className="text-2xl sm:text-3xl font-black tracking-tight text-on-action">
                {profile.name}
              </h1>
              <p className="text-base font-semibold text-muted">{profile.title}</p>
            </div>

            <div className="text-right space-y-1 text-xs text-muted font-mono">
              <div className="font-bold text-on-action text-sm">
                £{profile.dayRate || 850}/day <span className="font-normal text-xs text-muted">(Standard Day Rate)</span>
              </div>
              <div>Status: {profile.availability}</div>
              <div>Base: {profile.location}</div>
              <div>Doc Ref: HYD-DOS-{profile.id.slice(0, 8).toUpperCase()}</div>
            </div>
          </div>

          {/* Quick Metrics Grid */}
          <div className="grid grid-cols-4 gap-4 p-4 rounded-[10px] bg-action border border-border-strong text-xs">
            <div>
              <span className="text-xs uppercase font-bold text-muted block">Total Experience</span>
              <span className="text-base font-bold text-on-action font-mono">{profile.yearsOfExperience} Years</span>
            </div>
            <div>
              <span className="text-xs uppercase font-bold text-muted block">Discipline</span>
              <span className="text-sm font-semibold text-on-action">{profile.department}</span>
            </div>
            <div>
              <span className="text-xs uppercase font-bold text-muted block">Client Satisfaction</span>
              <span className="text-base font-bold text-on-action font-mono">{profile.rating || 4.9} / 5.0</span>
            </div>
            <div>
              <span className="text-xs uppercase font-bold text-muted block">Accreditation</span>
              <span className="text-sm font-semibold text-positive">Verified Offshore</span>
            </div>
          </div>

          {/* Executive Summary */}
          <div className="space-y-2">
            <h2 className="text-xs font-bold uppercase tracking-wider text-muted border-b border-border-strong pb-1">
              Executive Profile & Technical Summary
            </h2>
            <p className="text-sm leading-relaxed text-muted">{profile.bio}</p>
          </div>

          {/* Survey Disciplines & Operations */}
          {profile.surveyTypes && profile.surveyTypes.length > 0 && (
            <div className="space-y-2">
              <h2 className="text-xs font-bold uppercase tracking-wider text-muted border-b border-border-strong pb-1">
                Survey Disciplines & Focus Areas
              </h2>
              <div className="flex flex-wrap gap-2">
                {profile.surveyTypes.map((type) => (
                  <span
                    key={type}
                    className="px-3 py-1 rounded-md bg-accent-soft text-accent border border-border-strong text-xs font-semibold"
                  >
                    {type}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Mandatory Offshore Certifications */}
          {profile.certifications && profile.certifications.length > 0 && (
            <div className="space-y-2">
              <h2 className="text-xs font-bold uppercase tracking-wider text-muted border-b border-border-strong pb-1">
                Active Offshore Safety & Marine Certifications
              </h2>
              <div className="grid grid-cols-2 gap-2 text-xs">
                {profile.certifications.map((cert) => (
                  <div key={cert} className="p-2 rounded bg-surface border border-border-strong flex items-center gap-2">
                    <Check className="w-3.5 h-3.5 text-positive" />
                    <span className="font-medium text-on-action">{cert}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Technical Skills & Systems */}
          {profile.skills && profile.skills.length > 0 && (
            <div className="space-y-2">
              <h2 className="text-xs font-bold uppercase tracking-wider text-muted border-b border-border-strong pb-1">
                Technical Skills & Specialist Software / Equipment
              </h2>
              <div className="flex flex-wrap gap-1.5">
                {profile.skills.map((skill) => (
                  <span
                    key={skill}
                    className="px-2.5 py-1 rounded bg-action text-muted border border-border-strong text-xs font-medium"
                  >
                    {skill}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Past Operators & Campaigns */}
          <div className="grid grid-cols-2 gap-6 pt-2">
            {profile.pastCompanies && profile.pastCompanies.length > 0 && (
              <div className="space-y-2">
                <h2 className="text-xs font-bold uppercase tracking-wider text-muted border-b border-border-strong pb-1">
                  Past Operators & Energy Clients
                </h2>
                <div className="flex flex-wrap gap-1.5">
                  {profile.pastCompanies.map((c) => (
                    <span key={c} className="px-2.5 py-0.5 rounded bg-action text-muted text-xs border border-border-strong">
                      {c}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {profile.education && (
              <div className="space-y-2">
                <h2 className="text-xs font-bold uppercase tracking-wider text-muted border-b border-border-strong pb-1">
                  Academic Background
                </h2>
                <p className="text-xs text-muted">{profile.education}</p>
              </div>
            )}
          </div>

          {/* Footer Notice */}
          <div className="pt-6 border-t border-border-strong flex items-center justify-between text-xs text-muted font-mono">
            <span>Verified by Hydenlyne Quality Assurance & Compliance</span>
            <span>https://hydenlyne.com • operations@hydenlyne.com</span>
          </div>
        </div>
      </div>
    </div>
  );
};
