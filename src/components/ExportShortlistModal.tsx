import React, { useState } from 'react';
import { X, Download, Copy, Check, Trash2, Users } from 'lucide-react';
import { UserProfile } from '../types';

interface ExportShortlistModalProps {
  isOpen: boolean;
  onClose: () => void;
  shortlistedProfiles: UserProfile[];
  onClear: () => void;
  onRemoveProfile: (id: string) => void;
  onSelectProfile: (profile: UserProfile) => void;
}

export const ExportShortlistModal: React.FC<ExportShortlistModalProps> = ({
  isOpen,
  onClose,
  shortlistedProfiles,
  onClear,
  onRemoveProfile,
  onSelectProfile,
}) => {
  const [copied, setCopied] = useState(false);

  if (!isOpen) return null;

  const handleCopy = async () => {
    if (shortlistedProfiles.length === 0) return;
    const text = shortlistedProfiles
      .map(
        (p, idx) =>
          `[${idx + 1}] ${p.name} - ${p.title} (${p.department})\nLocation: ${p.location} | Avail: ${p.availability} | Day Rate: £${p.dayRate || 'On Request'}/day\nEmail: ${p.email}\nBio: ${p.bio}\nKey Skills: ${p.skills.slice(0, 5).join(', ')}`
      )
      .join('\n\n------------------------------------\n\n');

    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback
    }
  };

  const handleDownloadCSV = () => {
    if (shortlistedProfiles.length === 0) return;
    const headers = ['Name', 'Title', 'Discipline', 'Location', 'Availability', 'Day Rate GBP', 'Years Experience', 'Email'];
    const rows = shortlistedProfiles.map((p) => [
      `"${p.name.replace(/"/g, '""')}"`,
      `"${p.title.replace(/"/g, '""')}"`,
      `"${p.department.replace(/"/g, '""')}"`,
      `"${p.location.replace(/"/g, '""')}"`,
      `"${(p.availability || 'Available').replace(/"/g, '""')}"`,
      p.dayRate ? `${p.dayRate}` : 'N/A',
      `${p.yearsOfExperience}`,
      `"${p.email.replace(/"/g, '""')}"`,
    ]);

    const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map((r) => r.join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `Hydenlyne_Shortlist_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-zinc-950/80 backdrop-blur-xs animate-in fade-in duration-150"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="shortlist-title"
    >
      <div
        className="w-full max-w-2xl bg-zinc-900 border border-zinc-800 rounded-2xl flex flex-col max-h-[85vh] overflow-hidden shadow-2xl text-zinc-100 animate-in zoom-in-95 duration-150"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="p-5 border-b border-zinc-800 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-blue-950/60 border border-blue-800/60 text-blue-400">
              <Users className="w-5 h-5" />
            </div>
            <div>
              <h3 id="shortlist-title" className="font-semibold text-base text-zinc-100">
                Shortlisted Specialists ({shortlistedProfiles.length})
              </h3>
              <p className="text-xs text-zinc-400 font-light">
                Candidate review, CSV export, and batch clipboard summary
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 transition-colors cursor-pointer"
            aria-label="Close modal"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content list */}
        <div className="flex-1 overflow-y-auto p-5 space-y-2.5 divide-y divide-zinc-800/40">
          {shortlistedProfiles.length === 0 ? (
            <div className="text-center py-12 text-zinc-500 space-y-2">
              <p className="text-sm">No specialists currently saved to shortlist.</p>
              <p className="text-xs text-zinc-600">
                Click the bookmark icon or press <kbd className="font-mono bg-zinc-950 px-1.5 py-0.5 rounded border border-zinc-800">S</kbd> while viewing any specialist.
              </p>
            </div>
          ) : (
            shortlistedProfiles.map((profile) => (
              <div
                key={profile.id}
                className="pt-2.5 first:pt-0 flex items-center justify-between gap-3 group"
              >
                <div
                  onClick={() => {
                    onSelectProfile(profile);
                    onClose();
                  }}
                  className="flex items-center gap-3 min-w-0 flex-1 cursor-pointer hover:opacity-80 transition-opacity"
                >
                  <img
                    src={profile.avatar}
                    alt={profile.name}
                    referrerPolicy="no-referrer"
                    className="w-10 h-10 rounded-lg object-cover border border-zinc-800 shrink-0"
                  />
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <h4 className="font-semibold text-xs text-zinc-200 group-hover:text-blue-400 transition-colors truncate">
                        {profile.name}
                      </h4>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400 font-mono">
                        {profile.department}
                      </span>
                    </div>
                    <p className="text-[11px] text-zinc-400 truncate">{profile.title}</p>
                    <div className="text-[10px] text-zinc-500 flex items-center gap-2">
                      <span>{profile.location}</span>
                      <span>•</span>
                      <span className="text-emerald-400">{profile.availability}</span>
                      {profile.dayRate && (
                        <>
                          <span>•</span>
                          <span className="font-mono">£{profile.dayRate}/d</span>
                        </>
                      )}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-1.5 shrink-0">
                  <button
                    type="button"
                    onClick={() => onRemoveProfile(profile.id)}
                    className="p-1.5 rounded-lg text-zinc-500 hover:text-red-400 hover:bg-zinc-800 transition-colors cursor-pointer"
                    title="Remove from shortlist"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Footer actions */}
        {shortlistedProfiles.length > 0 && (
          <div className="p-4 border-t border-zinc-800 bg-zinc-950/60 flex items-center justify-between gap-3 flex-wrap">
            <button
              type="button"
              onClick={onClear}
              className="text-xs text-zinc-500 hover:text-red-400 transition-colors cursor-pointer"
            >
              Clear all
            </button>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleCopy}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-medium transition-colors cursor-pointer"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copied ? 'Copied summary!' : 'Copy summary'}</span>
              </button>

              <button
                type="button"
                onClick={handleDownloadCSV}
                className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold transition-colors cursor-pointer shadow-xs"
              >
                <Download className="w-3.5 h-3.5" />
                <span>Export CSV</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
