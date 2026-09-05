import { FC, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { UserProfile } from '../../types';
import { Mail, Copy, Check, Linkedin, Send } from 'lucide-react';

interface DossierBottomBarProps {
  profile: UserProfile;
  isFocusMode: boolean;
  onShowToast: (msg: string) => void;
  onRequestMobilization?: (profile: UserProfile) => void;
}

export const DossierBottomBar: FC<DossierBottomBarProps> = ({
  profile,
  isFocusMode,
  onShowToast,
  onRequestMobilization,
}) => {
  const [copiedEmail, setCopiedEmail] = useState(false);

  const handleCopyEmail = () => {
    navigator.clipboard?.writeText(profile.email);
    setCopiedEmail(true);
    onShowToast(`Copied ${profile.email}`);
    setTimeout(() => setCopiedEmail(false), 2000);
  };

  return (
    <div
      className={`bg-canvas border-t border-border-subtle flex flex-wrap items-center justify-between gap-3 ${
        isFocusMode ? 'p-3 sm:p-4' : 'p-4'
      }`}
    >
      <div className="min-w-0 w-full sm:w-auto">
        <span className="text-xs sm:text-sm text-secondary font-mono block truncate">
          {profile.email}
        </span>
        <span className="text-xs text-muted hidden sm:block">
          Press <kbd className="font-mono text-secondary">C</kbd> to copy email •{' '}
          <kbd className="font-mono text-secondary">F</kbd> toggle focus
        </span>
      </div>

      <div className="flex items-center justify-end gap-2 shrink-0 w-full sm:w-auto">
        <a
          href={
            profile.linkedinUrl ||
            `https://www.linkedin.com/search/results/all/?keywords=${encodeURIComponent(
              `${profile.name} Hydenlyne`,
            )}`
          }
          target="_blank"
          rel="noopener noreferrer"
          aria-label={`Open ${profile.name} LinkedIn profile`}
          className="min-h-11 min-w-11 p-2.5 rounded-[10px] bg-surface-raised hover:bg-surface-selected text-secondary hover:text-primary transition-colors inline-flex items-center justify-center"
          title="LinkedIn Profile"
        >
          <Linkedin className="h-4 w-4 text-accent" />
        </a>

        <button
          type="button"
          onClick={handleCopyEmail}
          aria-label={`Copy ${profile.name} email address`}
          className={`relative min-h-11 px-3.5 py-2 rounded-[10px] text-xs sm:text-sm font-medium flex items-center gap-1.5 transition-all duration-200 cursor-pointer overflow-hidden ${
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
                <Copy className="w-3.5 h-3.5 text-secondary group-hover:text-primary" />
                <span>Copy</span>
              </motion.div>
            )}
          </AnimatePresence>
        </button>

        {onRequestMobilization ? (
          <button
            type="button"
            onClick={() => onRequestMobilization(profile)}
            className="min-h-11 px-5 py-2 rounded-[10px] bg-action hover:bg-action-hover text-on-action text-xs sm:text-sm font-semibold flex items-center gap-1.5 transition-colors cursor-pointer shadow-md shadow-black/30"
          >
            <Send className="w-4 h-4" />
            <span>Request mobilization</span>
          </button>
        ) : (
          <a
            href={`mailto:${profile.email}?subject=Hydenlyne%20Mobilization%20Request%20-%20${encodeURIComponent(
              profile.title,
            )}`}
            className="min-h-11 px-5 py-2 rounded-[10px] bg-action hover:bg-action-hover text-on-action text-xs sm:text-sm font-semibold flex items-center gap-1.5 transition-colors cursor-pointer shadow-md shadow-black/30"
          >
            <Mail className="w-4 h-4" />
            <span>Request mobilization</span>
          </a>
        )}
      </div>
    </div>
  );
};
