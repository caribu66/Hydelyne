import { FC, useRef } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import {
  Columns,
  Download,
  LayoutGrid,
  LogOut,
  Moon,
  Scale,
  SlidersHorizontal,
  Sun,
  Table,
  UserPlus,
  X,
} from 'lucide-react';
import { useAccessibleDialog } from '../hooks/useAccessibleDialog';

interface AppMenuDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  isAuthenticated: boolean;
  isDark: boolean;
  onToggleTheme: () => void;
  onOpenShortcuts: () => void;
  onOpenAddSpecialist: () => void;
  onOpenCompare: () => void;
  compareCount: number;
  isSearchActive: boolean;
  viewMode: 'split' | 'grid' | 'table';
  onViewModeChange: (mode: 'split' | 'grid' | 'table') => void;
  shortlistCount: number;
  onExportShortlist: () => void;
  email?: string;
  onLogout: () => void;
  onRequestLogin: () => void;
}

export const AppMenuDrawer: FC<AppMenuDrawerProps> = ({
  isOpen,
  onClose,
  isAuthenticated,
  isDark,
  onToggleTheme,
  onOpenShortcuts,
  onOpenAddSpecialist,
  onOpenCompare,
  compareCount,
  isSearchActive,
  viewMode,
  onViewModeChange,
  shortlistCount,
  onExportShortlist,
  email,
  onLogout,
  onRequestLogin,
}) => {
  const drawerRef = useRef<HTMLElement>(null);
  useAccessibleDialog(isOpen, drawerRef, onClose);

  const closeAfter = (action: () => void) => {
    action();
    onClose();
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50">
          {/* Backdrop Overlay with fade */}
          <motion.button
            type="button"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="absolute inset-0 bg-canvas/80 backdrop-blur-sm cursor-pointer w-full h-full border-none outline-none"
            onClick={onClose}
            aria-label="Close menu"
          />

          {/* Slide-over Aside Panel */}
          <motion.aside
            ref={drawerRef}
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
            role="dialog"
            aria-modal="true"
            aria-labelledby="app-menu-title"
            className="absolute right-0 top-0 flex h-full w-[min(100%,360px)] flex-col border-l border-border-subtle bg-surface p-5 shadow-2xl z-10"
          >
            <div className="flex items-center justify-between border-b border-border-subtle pb-4">
              <div>
                <p className="text-xs font-mono uppercase tracking-[0.18em] text-muted">Workspace</p>
                <h2 id="app-menu-title" className="mt-1 text-base font-semibold text-primary">Menu</h2>
              </div>
              <button
                type="button"
                onClick={onClose}
                className="inline-flex min-h-9 min-w-9 items-center justify-center rounded-lg border border-border-subtle bg-surface hover:bg-surface-raised text-secondary hover:text-primary transition-colors cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                aria-label="Close menu"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto py-5 space-y-6">
              <div>
                <p className="mb-2 text-xs font-mono uppercase tracking-[0.18em] text-muted">Workspace actions</p>
                <div className="space-y-1">
                  {isAuthenticated && (
                    <button type="button" onClick={() => closeAfter(onOpenAddSpecialist)} className="menu-drawer-action menu-drawer-action-primary">
                      <UserPlus className="h-4 w-4" aria-hidden="true" />
                      <span>Add contractor</span>
                    </button>
                  )}
                  {compareCount > 0 && isAuthenticated && (
                    <button type="button" onClick={() => closeAfter(onOpenCompare)} className="menu-drawer-action">
                      <Scale className="h-4 w-4" aria-hidden="true" />
                      <span>Compare contractors</span>
                      <span className="menu-drawer-count">{compareCount}</span>
                    </button>
                  )}
                  {shortlistCount > 0 && (
                    <button type="button" onClick={() => closeAfter(onExportShortlist)} className="menu-drawer-action">
                      <Download className="h-4 w-4" aria-hidden="true" />
                      <span>Export shortlist</span>
                    </button>
                  )}
                </div>
              </div>

              {isSearchActive && isAuthenticated && (
                <div className="border-t border-border-subtle pt-4">
                  <p className="mb-2 text-xs font-mono uppercase tracking-[0.18em] text-muted">Result view</p>
                  <div className="grid grid-cols-3 gap-1 rounded-[10px] border border-border-subtle bg-surface-raised/40 p-1">
                    {([
                      ['split', Columns, 'Split'],
                      ['grid', LayoutGrid, 'Cards'],
                      ['table', Table, 'Matrix'],
                    ] as const).map(([mode, Icon, label]) => (
                      <button
                        key={mode}
                        type="button"
                        onClick={() => onViewModeChange(mode)}
                        className={`flex min-h-10 flex-col items-center justify-center gap-1 rounded-lg text-xs cursor-pointer transition-colors ${
                          viewMode === mode
                            ? 'bg-action text-on-action font-semibold shadow-xs'
                            : 'text-muted hover:bg-surface-raised hover:text-primary'
                        }`}
                        aria-pressed={viewMode === mode}
                      >
                        <Icon className="h-3.5 w-3.5" aria-hidden="true" />
                        {label}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <div className="border-t border-border-subtle pt-4">
                <p className="mb-2 text-xs font-mono uppercase tracking-[0.18em] text-muted">Preferences</p>
                <div className="space-y-1">
                  <button type="button" onClick={() => closeAfter(onToggleTheme)} className="menu-drawer-action">
                    {isDark ? <Sun className="h-4 w-4" aria-hidden="true" /> : <Moon className="h-4 w-4" aria-hidden="true" />}
                    <span>Use {isDark ? 'light' : 'dark'} theme</span>
                  </button>
                  <button type="button" onClick={() => closeAfter(onOpenShortcuts)} className="menu-drawer-action">
                    <SlidersHorizontal className="h-4 w-4" aria-hidden="true" />
                    <span>Keyboard shortcuts</span>
                    <kbd className="ml-auto rounded border border-border-strong px-1.5 py-0.5 text-xs text-muted font-mono">?</kbd>
                  </button>
                </div>
              </div>
            </div>

            <div className="border-t border-border-subtle pt-4">
              {isAuthenticated ? (
                <div className="flex items-center justify-between gap-3 rounded-[10px] border border-border-subtle bg-surface-raised/40 p-3">
                  <span className="min-w-0 truncate text-xs text-secondary font-mono">{email}</span>
                  <button
                    type="button"
                    onClick={() => closeAfter(onLogout)}
                    className="inline-flex min-h-9 min-w-9 items-center justify-center rounded-lg border border-border-subtle hover:border-danger hover:bg-surface text-secondary hover:text-danger transition-colors cursor-pointer"
                    aria-label="Sign out"
                  >
                    <LogOut className="h-4 w-4" />
                  </button>
                </div>
              ) : (
                <button type="button" onClick={() => closeAfter(onRequestLogin)} className="menu-drawer-action menu-drawer-action-primary">
                  Sign in to the network
                </button>
              )}
            </div>
          </motion.aside>
        </div>
      )}
    </AnimatePresence>
  );
};
