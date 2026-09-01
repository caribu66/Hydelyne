import React, { useEffect } from 'react';
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
  { key: '↓ / ↑', description: 'Navigate specialists up/down', category: 'Navigation' },
  { key: 'J / K', description: 'Vim navigation next/previous', category: 'Navigation' },
  { key: 'Enter', description: 'Open full inspection dossier modal', category: 'Actions' },
  { key: 'S', description: 'Toggle candidate bookmark/shortlist', category: 'Actions' },
  { key: 'C', description: 'Copy specialist email to clipboard', category: 'Actions' },
  { key: 'T', description: 'Toggle Deep Zinc / Light theme', category: 'General' },
  { key: 'Esc', description: 'Clear search / Close modal', category: 'General' },
  { key: '?', description: 'Open keyboard shortcuts sheet', category: 'General' },
];

export const ShortcutsModal: React.FC<ShortcutsModalProps> = ({ isOpen, onClose }) => {
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-zinc-950/80 backdrop-blur-xs animate-in fade-in duration-150"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="shortcuts-title"
    >
      <div
        className="w-full max-w-md bg-zinc-900 border border-zinc-800 rounded-2xl p-5 sm:p-6 shadow-2xl text-zinc-100 animate-in zoom-in-95 duration-150"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between pb-4 border-b border-zinc-800">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-zinc-800 text-zinc-300">
              <Command className="w-4 h-4" />
            </div>
            <div>
              <h3 id="shortcuts-title" className="font-semibold text-sm text-zinc-100">
                Keyboard Shortcuts
              </h3>
              <p className="text-[11px] text-zinc-400">Power user navigation commands</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 transition-colors cursor-pointer"
            aria-label="Close shortcuts modal"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="mt-4 space-y-2 text-xs">
          {SHORTCUTS.map((item) => (
            <div
              key={item.key + item.description}
              className="flex items-center justify-between py-1.5 px-2 rounded-lg hover:bg-zinc-800/50 transition-colors"
            >
              <span className="text-zinc-300 font-light">{item.description}</span>
              <kbd className="px-2 py-1 rounded bg-zinc-950 border border-zinc-800 font-mono text-[11px] text-zinc-400 shadow-xs">
                {item.key}
              </kbd>
            </div>
          ))}
        </div>

        <div className="mt-5 pt-3 border-t border-zinc-800/80 flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="px-3.5 py-1.5 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-medium transition-colors cursor-pointer"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
};
