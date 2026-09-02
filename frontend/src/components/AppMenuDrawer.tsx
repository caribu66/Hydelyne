import { FC, useRef } from 'react';
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

  if (!isOpen) return null;

  const closeAfter = (action: () => void) => {
    action();
    onClose();
  };

  return (
    <div className="ui-overlay-enter fixed inset-0 z-50" aria-hidden={!isOpen}>
      <button type="button" className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} aria-label="Close menu" />
      <aside
        ref={drawerRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="app-menu-title"
        className="ui-drawer-enter absolute right-0 top-0 flex h-full w-[min(100%,360px)] flex-col border-l border-zinc-800 bg-zinc-950 p-5 shadow-2xl"
      >
        <div className="flex items-center justify-between border-b border-zinc-800 pb-4">
          <div>
            <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-zinc-500">Workspace</p>
            <h2 id="app-menu-title" className="mt-1 text-base font-semibold text-zinc-100">Menu</h2>
          </div>
          <button type="button" onClick={onClose} className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-xl border border-zinc-800 bg-zinc-900 text-zinc-400 hover:text-zinc-100 cursor-pointer" aria-label="Close menu">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto py-5">
          <p className="mb-2 text-[10px] font-mono uppercase tracking-[0.18em] text-zinc-500">Workspace actions</p>
          <div className="space-y-1">
            {isAuthenticated && (
              <button type="button" onClick={() => closeAfter(onOpenAddSpecialist)} className="menu-drawer-action menu-drawer-action-primary">
                <UserPlus className="h-4 w-4" aria-hidden="true" />
                <span>Add Specialist</span>
              </button>
            )}
            {compareCount > 0 && isAuthenticated && (
              <button type="button" onClick={() => closeAfter(onOpenCompare)} className="menu-drawer-action">
                <Scale className="h-4 w-4" aria-hidden="true" />
                <span>Compare specialists</span>
                <span className="menu-drawer-count">{compareCount}</span>
              </button>
            )}
            {shortlistCount > 0 && (
              <button type="button" onClick={() => closeAfter(onExportShortlist)} className="menu-drawer-action">
                <Download className="h-4 w-4" aria-hidden="true" />
                <span>Export shortlist</span>
              </button>
            )}
            {isSearchActive && isAuthenticated && (
              <div className="mt-4 border-t border-zinc-800 pt-4">
                <p className="mb-2 text-[10px] font-mono uppercase tracking-[0.18em] text-zinc-500">Result view</p>
                <div className="grid grid-cols-3 gap-1 rounded-xl border border-zinc-800 bg-zinc-900 p-1">
                  {([
                    ['split', Columns, 'Split'],
                    ['grid', LayoutGrid, 'Cards'],
                    ['table', Table, 'Matrix'],
                  ] as const).map(([mode, Icon, label]) => (
                    <button key={mode} type="button" onClick={() => onViewModeChange(mode)} className={`flex min-h-11 flex-col items-center justify-center gap-1 rounded-lg text-xs cursor-pointer ${viewMode === mode ? 'bg-zinc-100 text-zinc-950 font-semibold' : 'text-zinc-500 hover:bg-zinc-800 hover:text-zinc-200'}`} aria-pressed={viewMode === mode}>
                      <Icon className="h-3.5 w-3.5" aria-hidden="true" />
                      {label}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          <p className="mb-2 mt-6 text-[10px] font-mono uppercase tracking-[0.18em] text-zinc-500">Preferences</p>
          <div className="space-y-1">
            <button type="button" onClick={() => closeAfter(onToggleTheme)} className="menu-drawer-action">
              {isDark ? <Sun className="h-4 w-4" aria-hidden="true" /> : <Moon className="h-4 w-4" aria-hidden="true" />}
              <span>Use {isDark ? 'light' : 'dark'} theme</span>
            </button>
            <button type="button" onClick={() => closeAfter(onOpenShortcuts)} className="menu-drawer-action">
              <SlidersHorizontal className="h-4 w-4" aria-hidden="true" />
              <span>Keyboard shortcuts</span>
              <kbd className="ml-auto rounded border border-zinc-700 px-1.5 py-0.5 text-[10px] text-zinc-500">?</kbd>
            </button>
          </div>
        </div>

        <div className="border-t border-zinc-800 pt-4">
          {isAuthenticated ? (
            <div className="flex items-center justify-between gap-3 rounded-xl border border-zinc-800 bg-zinc-900/60 p-3">
              <span className="min-w-0 truncate text-xs text-zinc-400">{email}</span>
              <button type="button" onClick={() => closeAfter(onLogout)} className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-lg border border-zinc-800 text-zinc-400 hover:border-rose-800/60 hover:text-rose-300 cursor-pointer" aria-label="Sign out">
                <LogOut className="h-4 w-4" />
              </button>
            </div>
          ) : (
            <button type="button" onClick={() => closeAfter(onRequestLogin)} className="menu-drawer-action menu-drawer-action-primary">
              Sign in to the network
            </button>
          )}
        </div>
      </aside>
    </div>
  );
};
