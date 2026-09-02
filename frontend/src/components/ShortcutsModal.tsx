import { FC, useRef } from 'react';
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
  { key: 'Enter', description: 'Select the focused contractor result', category: 'Actions' },
  { key: 'S', description: 'Toggle contractor shortlist status', category: 'Actions' },
  { key: 'C', description: 'Copy contractor email to clipboard', category: 'Actions' },
  { key: 'T', description: 'Toggle dark / light theme', category: 'General' },
  { key: 'Esc', description: 'Exit focus mode or close the active dialog', category: 'General' },
  { key: '?', description: 'Open keyboard shortcuts sheet', category: 'General' },
];

export const ShortcutsModal: FC<ShortcutsModalProps> = ({ isOpen, onClose }) => {
  const dialogRef = useRef<HTMLDivElement>(null);
  useAccessibleDialog(isOpen, dialogRef, onClose);

  if (!isOpen) return null;

  return (
    <div
      className="ui-overlay-enter fixed inset-0 z-50 flex items-center justify-center p-4 bg-canvas/80 backdrop-blur-xs"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="shortcuts-title"
    >
      <div
        ref={dialogRef}
        className="ui-surface-enter w-full max-w-md bg-surface border border-border-subtle rounded-[14px] p-5 sm:p-6 shadow-2xl text-primary"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between pb-4 border-b border-border-subtle">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-surface-raised text-secondary">
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
            onClick={onClose}
            className="p-1.5 rounded-lg text-secondary hover:text-primary hover:bg-surface-raised transition-colors cursor-pointer"
            aria-label="Close shortcuts modal"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="mt-4 space-y-2 text-xs">
          {SHORTCUTS.map((item) => (
            <div
              key={item.key + item.description}
              className="flex items-center justify-between py-1.5 px-2 rounded-lg hover:bg-surface-raised/50 transition-colors"
            >
              <span className="text-secondary font-light">{item.description}</span>
              <kbd className="px-2 py-1 rounded bg-canvas border border-border-subtle font-mono text-xs text-secondary shadow-xs">
                {item.key}
              </kbd>
            </div>
          ))}
        </div>

        <div className="mt-5 pt-3 border-t border-border-subtle/80 flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="px-3.5 py-1.5 rounded-[10px] bg-surface-raised hover:bg-surface-selected text-primary text-xs font-medium transition-colors cursor-pointer"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
};
