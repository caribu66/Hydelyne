import { FC, useRef } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { useAccessibleDialog } from '../hooks/useAccessibleDialog';
import { X, Command } from 'lucide-react';

interface ShortcutsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

interface ShortcutItem {
  key: string;
  description: string;
  category: 'Navigation' | 'Actions' | 'General';
}

const SHORTCUTS: ShortcutItem[] = [
  { key: '/', description: 'Focus search bar', category: 'Navigation' },
  { key: '↓ / ↑', description: 'Navigate contractors up/down', category: 'Navigation' },
  { key: 'J / K', description: 'Vim navigation next/previous', category: 'Navigation' },
  { key: 'Home / End', description: 'Jump to first/last contractor', category: 'Navigation' },
  { key: '1 / 2 / 3', description: 'Switch layout: Split / Cards / Matrix', category: 'Navigation' },
  { key: '← / → (divider)', description: 'Resize split-view list and dossier panes', category: 'Navigation' },
  { key: 'F', description: 'Toggle full focus contractor mode', category: 'Navigation' },
  { key: 'Enter', description: 'Select the focused contractor result', category: 'Actions' },
  { key: 'S', description: 'Toggle contractor shortlist status', category: 'Actions' },
  { key: 'X', description: 'Add or remove contractor from comparison', category: 'Actions' },
  { key: 'C', description: 'Copy contractor email to clipboard', category: 'Actions' },
  { key: 'M', description: 'Send mobilization inquiry for candidate', category: 'Actions' },
  { key: 'T', description: 'Toggle dark / light theme', category: 'General' },
  { key: 'Esc', description: 'Exit focus mode or close the active dialog', category: 'General' },
  { key: '?', description: 'Open keyboard shortcuts sheet', category: 'General' },
];

export const ShortcutsModal: FC<ShortcutsModalProps> = ({ isOpen, onClose }) => {
  const dialogRef = useRef<HTMLDivElement>(null);
  useAccessibleDialog(isOpen, dialogRef, onClose);

  return (
    <AnimatePresence>
      {isOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="shortcuts-title"
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
            className="w-full max-w-md bg-surface border border-border-subtle rounded-[14px] p-5 sm:p-6 shadow-2xl text-primary z-10"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between pb-4 border-b border-border-subtle">
              <div className="flex items-center gap-2">
                <div className="p-1.5 rounded-lg bg-surface-raised border border-border-subtle text-secondary">
                  <Command className="w-4 h-4" />
                </div>
                <div>
                  <h3 id="shortcuts-title" className="font-semibold text-sm text-primary">
                    Keyboard Shortcuts
                  </h3>
                  <p className="text-xs text-secondary">Power user navigation commands</p>
                </div>
              </div>
              <button
                type="button"
                onClick={onClose}
                className="inline-flex min-h-9 min-w-9 items-center justify-center rounded-lg border border-border-subtle hover:border-border-strong text-secondary hover:text-primary hover:bg-surface-raised transition-colors cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                aria-label="Close shortcuts modal"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="mt-4 space-y-1.5 text-xs max-h-[60vh] overflow-y-auto pr-1">
              {SHORTCUTS.map((item) => (
                <div
                  key={item.key + item.description}
                  className="flex items-center justify-between py-1.5 px-2 rounded-lg hover:bg-surface-raised/60 transition-colors"
                >
                  <span className="text-secondary font-light">{item.description}</span>
                  <kbd className="px-2 py-0.5 rounded bg-surface-raised border border-border-subtle font-mono text-xs text-secondary shadow-xs">
                    {item.key}
                  </kbd>
                </div>
              ))}
            </div>

            <div className="mt-5 pt-3 border-t border-border-subtle flex justify-end">
              <button
                type="button"
                onClick={onClose}
                className="min-h-9 px-4 py-1.5 rounded-lg bg-surface-raised hover:bg-surface-selected border border-border-subtle text-primary text-xs font-medium transition-colors cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-focus"
              >
                Done
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
};
