import { FC, useState, useRef } from 'react';
import { useAccessibleDialog } from '../hooks/useAccessibleDialog';
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

export const ExportShortlistModal: FC<ExportShortlistModalProps> = ({
  isOpen,
  onClose,
  shortlistedProfiles,
  onClear,
  onRemoveProfile,
  onSelectProfile,
}) => {
  const [copied, setCopied] = useState(false);
  const dialogRef = useRef<HTMLDivElement>(null);
  useAccessibleDialog(isOpen, dialogRef, onClose);

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
      className="ui-overlay-enter fixed inset-0 z-50 flex items-center justify-center p-4 bg-canvas/80 backdrop-blur-xs"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="shortlist-title"
    >
      <div
        ref={dialogRef}
        className="ui-surface-enter w-full max-w-2xl bg-surface border border-border-subtle rounded-[14px] flex flex-col max-h-[85vh] overflow-hidden shadow-2xl text-primary"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="p-5 border-b border-border-subtle flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-[10px] bg-accent-soft/60 border border-border-strong/60 text-accent">
              <Users className="w-5 h-5" />
            </div>
            <div>
              <h3 id="shortlist-title" className="font-semibold text-base text-primary">
                Shortlisted specialists ({shortlistedProfiles.length})
              </h3>
              <p className="text-xs text-secondary font-light">
                Specialist review, CSV export, and batch clipboard summary
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="min-h-10 min-w-10 p-1.5 rounded-lg text-secondary hover:text-primary hover:bg-surface-raised transition-colors cursor-pointer inline-flex items-center justify-center"
            aria-label="Close modal"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content list */}
        <div className="flex-1 overflow-y-auto p-5 space-y-2.5 divide-y divide-zinc-800/40">
          {shortlistedProfiles.length === 0 ? (
            <div className="text-center py-12 text-muted space-y-2">
              <p className="text-sm">No specialists currently saved to shortlist.</p>
              <p className="text-xs text-muted">
                Use “Save to shortlist” or press <kbd className="rounded border border-border-subtle bg-canvas px-1.5 py-0.5 font-mono">S</kbd> while viewing a specialist.
              </p>
            </div>
          ) : (
            shortlistedProfiles.map((profile) => (
                <div
                  key={profile.id}
                  role="button"
                  tabIndex={0}
                  className="pt-2.5 first:pt-0 flex items-center justify-between gap-3 group"
                  onClick={() => {
                    onSelectProfile(profile);
                    onClose();
                  }}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      onSelectProfile(profile);
                      onClose();
                    }
                  }}
                >
                <span className="flex items-center gap-3 min-w-0 flex-1 text-left hover:opacity-80 transition-opacity">
                  <img
                    src={profile.avatar}
                    alt={profile.name}
                    referrerPolicy="no-referrer"
                    className="w-10 h-10 rounded-lg object-cover border border-border-subtle shrink-0"
                  />
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <h4 className="font-semibold text-xs text-primary group-hover:text-accent transition-colors truncate">
                        {profile.name}
                      </h4>
                      <span className="text-xs px-1.5 py-0.5 rounded bg-surface-raised text-secondary font-mono">
                        {profile.department}
                      </span>
                    </div>
                    <p className="text-xs text-secondary truncate">{profile.title}</p>
                    <div className="text-xs text-muted flex items-center gap-2">
                      <span>{profile.location}</span>
                      <span>•</span>
                      <span className="text-positive">{profile.availability}</span>
                      {profile.dayRate && (
                        <>
                          <span>•</span>
                          <span className="font-mono">£{profile.dayRate}/d</span>
                        </>
                      )}
                    </div>
                  </div>
                </span>
                <div className="flex items-center gap-1.5 shrink-0">
                  <button
                    type="button"
                    onClick={(event) => {
                      event.stopPropagation();
                      onRemoveProfile(profile.id);
                    }}
                    className="min-h-10 min-w-10 p-1.5 rounded-lg text-muted hover:text-danger hover:bg-surface-raised transition-colors cursor-pointer inline-flex items-center justify-center"
                    title="Remove from shortlist"
                    aria-label={`Remove ${profile.name} from shortlist`}
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
          <div className="p-4 border-t border-border-subtle bg-canvas/60 flex items-center justify-between gap-3 flex-wrap">
            <button
              type="button"
              onClick={onClear}
              className="min-h-10 px-2 text-xs text-muted hover:text-danger transition-colors cursor-pointer"
            >
              Clear all
            </button>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleCopy}
                className="inline-flex min-h-10 items-center gap-1.5 px-3 py-1.5 rounded-[10px] bg-surface-raised hover:bg-surface-selected text-primary text-xs font-medium transition-colors cursor-pointer"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-positive" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copied ? 'Copied summary!' : 'Copy summary'}</span>
              </button>

              <button
                type="button"
                onClick={handleDownloadCSV}
                className="inline-flex min-h-10 items-center gap-1.5 px-3.5 py-1.5 rounded-[10px] bg-action hover:bg-action-hover text-on-action text-xs font-semibold transition-colors cursor-pointer shadow-xs"
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
