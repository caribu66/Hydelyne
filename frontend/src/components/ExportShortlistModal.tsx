import { FC, useEffect, useState, useRef } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { useAccessibleDialog } from '../hooks/useAccessibleDialog';
import { X, Download, Copy, Check, Trash2, Users } from 'lucide-react';
import { UserProfile } from '../types';
import { csvDocument } from '../utils/csv';
import { copyTextToClipboard } from '../utils/clipboard';
import { isoDateAfterDays } from '../utils/operationsHome';
import { formatExperience } from '../utils/experience';
import { availabilityLabel } from '../utils/profileLabels';

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
  const [copyFailed, setCopyFailed] = useState(false);
  const dialogRef = useRef<HTMLDivElement>(null);
  const copyFeedbackTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  useAccessibleDialog(isOpen, dialogRef, onClose);

  useEffect(() => {
    setCopied(false);
    setCopyFailed(false);
    return () => {
      if (copyFeedbackTimerRef.current !== null) clearTimeout(copyFeedbackTimerRef.current);
    };
  }, [isOpen]);

  const handleCopy = async () => {
    if (shortlistedProfiles.length === 0) return;
    const text = shortlistedProfiles
      .map(
        (p, idx) =>
          `[${idx + 1}] ${p.name} - ${p.title} (${p.department})\nLocation: ${p.location} | Avail: ${p.availability} | Day Rate: ${p.dayRate != null ? `£${p.dayRate}/day` : 'Rate on request'}\nEmail: ${p.email}\nBio: ${p.bio}\nKey Skills: ${p.skills.slice(0, 5).join(', ')}`
      )
      .join('\n\n------------------------------------\n\n');

    try {
      if (await copyTextToClipboard(text)) {
        setCopied(true);
        setCopyFailed(false);
        if (copyFeedbackTimerRef.current !== null) clearTimeout(copyFeedbackTimerRef.current);
        copyFeedbackTimerRef.current = setTimeout(() => {
          copyFeedbackTimerRef.current = null;
          setCopied(false);
        }, 2000);
      } else {
        setCopyFailed(true);
      }
    } catch {
      setCopyFailed(true);
    }
  };

  const handleDownloadCSV = () => {
    if (shortlistedProfiles.length === 0) return;
    const headers = ['Name', 'Title', 'Discipline', 'Location', 'Availability', 'Day Rate GBP', 'Years Experience', 'Email'];
    const rows = shortlistedProfiles.map((p) => [
      p.name,
      p.title,
      p.department,
      p.location,
      p.availability || 'Availability not recorded',
      p.dayRate != null ? p.dayRate : 'N/A',
      formatExperience(p.yearsOfExperience),
      p.email,
    ]);

    const csvContent = csvDocument([headers, ...rows]);
    const blobUrl = URL.createObjectURL(new Blob([csvContent], { type: 'text/csv;charset=utf-8;' }));
    const link = document.createElement('a');
    link.setAttribute('href', blobUrl);
    link.setAttribute('download', `Hydenlyne_Shortlist_${isoDateAfterDays(0)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    // Retain the object URL briefly: Firefox/Safari consume the anchor
    // navigation asynchronously, so a 0ms revocation can cancel the download.
    window.setTimeout(() => URL.revokeObjectURL(blobUrl), 5000);
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="shortlist-title"
        >
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="fixed inset-0 bg-canvas/80 backdrop-blur-xs"
            onClick={onClose}
          />

          {/* Modal Container */}
          <motion.div
            ref={dialogRef}
            initial={{ opacity: 0, scale: 0.96, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 8 }}
            transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
            className="w-full max-w-2xl bg-surface border border-border-subtle rounded-[14px] flex flex-col max-h-[85vh] overflow-hidden shadow-2xl text-primary z-10"
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
                    Shortlisted contractors ({shortlistedProfiles.length})
                  </h3>
                  <p className="text-xs text-secondary font-light">
                    Contractor review, CSV export, and batch clipboard summary
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={onClose}
                className="inline-flex min-h-9 min-w-9 items-center justify-center rounded-lg border border-border-subtle hover:border-border-strong text-secondary hover:text-primary hover:bg-surface-raised transition-colors cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                aria-label="Close modal"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Content list */}
            <div className="flex-1 overflow-y-auto p-5 space-y-2.5 divide-y divide-border-subtle">
              {shortlistedProfiles.length === 0 ? (
                <div className="text-center py-12 text-muted space-y-2">
                  <p className="text-sm">No contractors currently saved to shortlist.</p>
                  <p className="text-xs text-muted">
                    Use “Save to shortlist” or press <kbd className="rounded border border-border-subtle bg-canvas px-1.5 py-0.5 font-mono">S</kbd> while viewing a contractor.
                  </p>
                </div>
              ) : (
                shortlistedProfiles.map((profile) => (
                  <div
                    key={profile.id}
                    role="button"
                    tabIndex={0}
                    className="pt-2.5 first:pt-0 flex items-center justify-between gap-3 group rounded-lg hover:bg-surface-raised/40 p-1.5 transition-colors"
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
                    <span className="flex items-center gap-3 min-w-0 flex-1 text-left">
                      <img
                        src={profile.avatar}
                        alt={profile.name}
                        referrerPolicy="no-referrer"
                        className="w-10 h-10 rounded-[10px] object-cover border border-border-subtle shrink-0"
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
                          <span className="text-positive">{availabilityLabel(profile.availability)}</span>
                          {profile.dayRate != null && (
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
                        className="inline-flex min-h-9 min-w-9 items-center justify-center rounded-lg text-muted hover:text-danger hover:bg-surface transition-colors cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-focus"
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
              <div className="p-4 border-t border-border-subtle bg-canvas/60 space-y-2">
                {copyFailed && (
                  <p role="alert" className="text-xs text-danger">
                    Could not copy the summary. Clipboard is unavailable or denied — use Export CSV instead.
                  </p>
                )}
                <div className="flex items-center justify-between gap-3 flex-wrap">
                <button
                  type="button"
                  onClick={onClear}
                  className="inline-flex min-h-9 items-center px-3 text-xs text-muted hover:text-danger transition-colors cursor-pointer rounded-lg hover:bg-surface focus:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                >
                  Clear all
                </button>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={handleCopy}
                    className="inline-flex min-h-9 items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-raised hover:bg-surface-selected border border-border-subtle text-primary text-xs font-medium transition-colors cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                  >
                    {copied ? <Check className="w-3.5 h-3.5 text-positive" /> : <Copy className="w-3.5 h-3.5" />}
                    <span>{copied ? 'Copied summary!' : 'Copy summary'}</span>
                  </button>

                  <button
                    type="button"
                    onClick={handleDownloadCSV}
                    className="inline-flex min-h-9 items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-action hover:bg-action-hover text-on-action text-xs font-semibold transition-colors cursor-pointer shadow-xs focus:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                  >
                    <Download className="w-3.5 h-3.5" />
                    <span>Export CSV</span>
                  </button>
                </div>
                </div>
              </div>
            )}
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
};
