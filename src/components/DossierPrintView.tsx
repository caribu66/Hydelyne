import React, { useEffect } from 'react';
import { UserProfile } from '../types';
import {
  MapPin,
  Mail,
  Building,
  GraduationCap,
  Calendar,
  ShieldCheck,
  Check,
  Compass,
  Printer,
  X,
  Download,
} from 'lucide-react';

interface DossierPrintViewProps {
  profile: UserProfile | null;
  onClose: () => void;
}

export const DossierPrintView: React.FC<DossierPrintViewProps> = ({ profile, onClose }) => {
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
    <div className="fixed inset-0 z-50 bg-zinc-950/90 backdrop-blur-md flex items-center justify-center p-2 sm:p-4 overflow-y-auto">
      <div className="w-full max-w-4xl bg-white text-zinc-900 rounded-2xl shadow-2xl overflow-hidden flex flex-col my-auto border border-zinc-200">
        {/* Screen-only Controls Header */}
        <div className="print:hidden flex items-center justify-between px-6 py-3.5 bg-zinc-900 text-zinc-100 border-b border-zinc-800">
          <div className="flex items-center gap-2 text-xs font-semibold">
            <span className="w-2 h-2 rounded-full bg-emerald-400" />
            <span>Consultant Dossier Preview (Print-Ready)</span>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handlePrint}
              className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs shadow-xs transition-colors cursor-pointer"
            >
              <Printer className="w-3.5 h-3.5" />
              <span>Print / Save as PDF</span>
            </button>
            <button
              type="button"
              onClick={onClose}
              className="p-1.5 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-white transition-colors cursor-pointer"
              aria-label="Close"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Printable Dossier Document Body */}
        <div id="printable-dossier" className="p-8 sm:p-12 space-y-8 bg-white text-zinc-900 font-sans">
          {/* Document Letterhead */}
          <div className="flex items-start justify-between border-b-2 border-zinc-900 pb-6">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs uppercase tracking-widest text-blue-900 font-bold">
                  HYDENLYNE ENERGY & MARINE CONSULTANCY
                </span>
              </div>
              <h1 className="text-2xl sm:text-3xl font-black tracking-tight text-zinc-950">
                {profile.name}
              </h1>
              <p className="text-base font-semibold text-zinc-700">{profile.title}</p>
            </div>

            <div className="text-right space-y-1 text-xs text-zinc-600 font-mono">
              <div className="font-bold text-zinc-900 text-sm">
                £{profile.dayRate || 850}/day <span className="font-normal text-xs text-zinc-500">(Standard Day Rate)</span>
              </div>
              <div>Status: {profile.availability}</div>
              <div>Base: {profile.location}</div>
              <div>Doc Ref: HYD-DOS-{profile.id.slice(0, 8).toUpperCase()}</div>
            </div>
          </div>

          {/* Quick Metrics Grid */}
          <div className="grid grid-cols-4 gap-4 p-4 rounded-xl bg-zinc-100 border border-zinc-300 text-xs">
            <div>
              <span className="text-[10px] uppercase font-bold text-zinc-500 block">Total Experience</span>
              <span className="text-base font-bold text-zinc-900 font-mono">{profile.yearsOfExperience} Years</span>
            </div>
            <div>
              <span className="text-[10px] uppercase font-bold text-zinc-500 block">Discipline</span>
              <span className="text-sm font-semibold text-zinc-900">{profile.department}</span>
            </div>
            <div>
              <span className="text-[10px] uppercase font-bold text-zinc-500 block">Client Satisfaction</span>
              <span className="text-base font-bold text-zinc-900 font-mono">{profile.rating || 4.9} / 5.0</span>
            </div>
            <div>
              <span className="text-[10px] uppercase font-bold text-zinc-500 block">Accreditation</span>
              <span className="text-sm font-semibold text-emerald-800">Verified Offshore</span>
            </div>
          </div>

          {/* Executive Summary */}
          <div className="space-y-2">
            <h2 className="text-xs font-bold uppercase tracking-wider text-zinc-500 border-b border-zinc-200 pb-1">
              Executive Profile & Technical Summary
            </h2>
            <p className="text-sm leading-relaxed text-zinc-800">{profile.bio}</p>
          </div>

          {/* Survey Disciplines & Operations */}
          {profile.surveyTypes && profile.surveyTypes.length > 0 && (
            <div className="space-y-2">
              <h2 className="text-xs font-bold uppercase tracking-wider text-zinc-500 border-b border-zinc-200 pb-1">
                Survey Disciplines & Focus Areas
              </h2>
              <div className="flex flex-wrap gap-2">
                {profile.surveyTypes.map((type) => (
                  <span
                    key={type}
                    className="px-3 py-1 rounded-md bg-blue-50 text-blue-900 border border-blue-200 text-xs font-semibold"
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
              <h2 className="text-xs font-bold uppercase tracking-wider text-zinc-500 border-b border-zinc-200 pb-1">
                Active Offshore Safety & Marine Certifications
              </h2>
              <div className="grid grid-cols-2 gap-2 text-xs">
                {profile.certifications.map((cert) => (
                  <div key={cert} className="p-2 rounded bg-zinc-50 border border-zinc-200 flex items-center gap-2">
                    <Check className="w-3.5 h-3.5 text-emerald-700" />
                    <span className="font-medium text-zinc-900">{cert}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Technical Skills & Systems */}
          {profile.skills && profile.skills.length > 0 && (
            <div className="space-y-2">
              <h2 className="text-xs font-bold uppercase tracking-wider text-zinc-500 border-b border-zinc-200 pb-1">
                Technical Skills & Specialist Software / Equipment
              </h2>
              <div className="flex flex-wrap gap-1.5">
                {profile.skills.map((skill) => (
                  <span
                    key={skill}
                    className="px-2.5 py-1 rounded bg-zinc-100 text-zinc-800 border border-zinc-300 text-xs font-medium"
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
                <h2 className="text-xs font-bold uppercase tracking-wider text-zinc-500 border-b border-zinc-200 pb-1">
                  Past Operators & Energy Clients
                </h2>
                <div className="flex flex-wrap gap-1.5">
                  {profile.pastCompanies.map((c) => (
                    <span key={c} className="px-2.5 py-0.5 rounded bg-zinc-100 text-zinc-800 text-xs border border-zinc-300">
                      {c}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {profile.education && (
              <div className="space-y-2">
                <h2 className="text-xs font-bold uppercase tracking-wider text-zinc-500 border-b border-zinc-200 pb-1">
                  Academic Background
                </h2>
                <p className="text-xs text-zinc-800">{profile.education}</p>
              </div>
            )}
          </div>

          {/* Footer Notice */}
          <div className="pt-6 border-t border-zinc-300 flex items-center justify-between text-[11px] text-zinc-500 font-mono">
            <span>Verified by Hydenlyne Quality Assurance & Compliance</span>
            <span>https://hydenlyne.com • operations@hydenlyne.com</span>
          </div>
        </div>
      </div>
    </div>
  );
};
