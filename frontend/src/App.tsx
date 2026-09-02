/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { lazy, Suspense, useState, useMemo, useEffect, useCallback, MouseEvent } from 'react';
import { useMutation } from '@apollo/client';
import { motion, AnimatePresence } from 'motion/react';
import { UserProfile, SortOption } from './types';
import { FILTER_PRESETS } from './data/mockProfiles';
import { useShortlist } from './hooks/useShortlist';
import { useURLSync } from './hooks/useURLSync';
import { useSpecialistDocuments } from './hooks/useSpecialistDocuments';
import { useCrewSummary } from './hooks/useCrewSummary';
import { useTheme } from './hooks/useTheme';
import { useCrewProfiles } from './hooks/useCrewProfiles';
import { useAuth } from './hooks/useAuth';
import { useRequireAuth } from './hooks/useRequireAuth';
import { useKeyboardNavigation } from './hooks/useKeyboardNavigation';
import { useSearchWorkspace } from './hooks/useSearchWorkspace';
import { DELETE_CREW_MEMBER } from './lib/queries';
import { CrewQueryResult } from './hooks/useCrewQuery';
import { ModernHeroSearch } from './components/ModernHeroSearch';
import { CrewQuerySummary } from './components/CrewQuerySummary';
import { MatchEvidence } from './components/MatchEvidence';
import { AddCrewMemberModal } from './components/AddCrewMemberModal';
import { AppMenuDrawer } from './components/AppMenuDrawer';
import { ActiveFilterChips } from './components/ActiveFilterChips';
import { FilterModal } from './components/FilterModal';
import { SpecialistActionsMenu } from './components/SpecialistActionsMenu';
import { ComparisonBar } from './components/ComparisonBar';
import { HighlightText } from './components/HighlightText';
import { CertificationBadge } from './components/CertificationBadge';
import { Toast } from './components/Toast';
import { ServiceStatus } from './components/ServiceStatus';
import { DensityIndicator } from './components/DensityIndicator';
import { SkeletonResults } from './components/SkeletonResults';
import {
  MapPin,
  Bookmark,
  Linkedin,
  LayoutGrid,
  Columns,
  Table,
  Compass,
  ArrowUpRight,
  Command,
  BadgeCheck,
  Download,
  Scale,
  Printer,
  Sun,
  Moon,
  LogOut,
  AlertTriangle,
  X,
  UserPlus,
  Menu,
} from 'lucide-react';
import hydenlyneLogoWhite from './assets/hydenlyne-logo-white.png';
import hydenlyneLogoColour from './assets/hydenlyne-logo-colour.png';

const LoginPage = lazy(() => import('./components/LoginPage').then((module) => ({ default: module.LoginPage })));
const ProfileDetailModal = lazy(() => import('./components/ProfileDetailModal').then((module) => ({ default: module.ProfileDetailModal })));
const CandidateCompareModal = lazy(() => import('./components/CandidateCompareModal').then((module) => ({ default: module.CandidateCompareModal })));
const MobilizationInquiryModal = lazy(() => import('./components/MobilizationInquiryModal').then((module) => ({ default: module.MobilizationInquiryModal })));
const DossierPrintView = lazy(() => import('./components/DossierPrintView').then((module) => ({ default: module.DossierPrintView })));
const ShortcutsModal = lazy(() => import('./components/ShortcutsModal').then((module) => ({ default: module.ShortcutsModal })));
const ExportShortlistModal = lazy(() => import('./components/ExportShortlistModal').then((module) => ({ default: module.ExportShortlistModal })));
const SpecialistDossierPane = lazy(() => import('./components/SpecialistDossierPane').then((module) => ({ default: module.SpecialistDossierPane })));
const SpecialistTableView = lazy(() => import('./components/SpecialistTableView').then((module) => ({ default: module.SpecialistTableView })));

const LazySurfaceFallback = () => (
  <div className="fixed inset-0 z-[100] flex items-center justify-center bg-zinc-950/70" role="status" aria-live="polite">
    <span className="rounded-xl border border-zinc-800 bg-zinc-900 px-4 py-3 text-xs text-zinc-300">Loading workspace…</span>
  </div>
);

const DossierFallback = () => (
  <div className="flex h-full min-h-80 items-center justify-center rounded-2xl bg-zinc-900/40" role="status" aria-live="polite">
    <span className="text-sm text-zinc-400">Opening dossier…</span>
  </div>
);

function queryFromCriteria(criteria: Record<string, unknown>): string {
  const parts = ['Find crew'];
  if (criteria.nationality) parts.push(`who are ${String(criteria.nationality)}`);
  if (criteria.medical_valid) parts.push('with a current medical');
  else if (criteria.medical_required) parts.push('with a medical certificate');
  if (Array.isArray(criteria.certification_keywords)) {
    criteria.certification_keywords.forEach((value) => parts.push(`with ${String(value)} certification`));
  }
  if (Array.isArray(criteria.certifications)) {
    criteria.certifications
      .filter((value) => !(criteria.medical_required && /medical/i.test(String(value))))
      .forEach((value) => parts.push(`with ${String(value)} certification`));
  }
  if (criteria.min_experience_years != null) parts.push(`with ${String(criteria.min_experience_years)} years of experience`);
  if (criteria.location) parts.push(`in ${String(criteria.location)}`);
  if (criteria.availability) parts.push(`who are ${String(criteria.availability).replaceAll('_', ' ')}`);
  if (criteria.project_type) parts.push(`with ${String(criteria.project_type)} experience`);
  if (Array.isArray(criteria.skills)) criteria.skills.forEach((value) => parts.push(`with ${String(value)} experience`));
  return parts.join(' ');
}

export default function App() {
  const { theme, isDark, toggleTheme } = useTheme();
  const { initialized: authInitialized, isAuthenticated, user, logout, refreshSession } = useAuth();
  const canManageDocuments = user?.role === 'admin';
  const [deleteCrewMember] = useMutation(DELETE_CREW_MEMBER);
  const [authSessionKey, setAuthSessionKey] = useState(0);
  const [isLoginOpen, setIsLoginOpen] = useState(false);

  const [modalProfile, setModalProfile] = useState<UserProfile | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [isShortcutsOpen, setIsShortcutsOpen] = useState(false);
  const [isExportShortlistOpen, setIsExportShortlistOpen] = useState(false);
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isFilterOpen, setIsFilterOpen] = useState(false);

  // Candidate Comparison state
  const [compareIds, setCompareIds] = useState<string[]>([]);
  const [isCompareModalOpen, setIsCompareModalOpen] = useState(false);

  // Mobilization Inquiry state
  const [inquiryProfile, setInquiryProfile] = useState<UserProfile | null>(null);
  const [isInquiryModalOpen, setIsInquiryModalOpen] = useState(false);

  // Printable Dossier state
  const [printProfile, setPrintProfile] = useState<UserProfile | null>(null);

  // AI Query state
  const [aiQueryData, setAiQueryData] = useState<CrewQueryResult | null>(null);
  const [aiQueryLoading, setAiQueryLoading] = useState(false);
  const [aiQueryActive, setAiQueryActive] = useState(false);
  const [showAISummary, setShowAISummary] = useState(false);

  // Add Crew Member modal state
  const [isAddCrewMemberOpen, setIsAddCrewMemberOpen] = useState(false);

  const handleAIResults = useCallback((data: CrewQueryResult | null, loading: boolean, isActive: boolean, showSummary: boolean) => {
    setAiQueryData(data);
    setAiQueryLoading(loading);
    setAiQueryActive(isActive);
    setShowAISummary(showSummary);
  }, []);

  const handleRemoveSearchCriterion = useCallback((key: string, value?: string) => {
    if (!aiQueryData) return;
    const criteria: Record<string, unknown> = { ...aiQueryData.criteria };
    if (key === 'medical') {
      delete criteria.medical_required;
      delete criteria.medical_valid;
      if (Array.isArray(criteria.certifications)) {
        criteria.certifications = criteria.certifications.filter((item) => !/medical/i.test(String(item)));
      }
    } else if (key === 'experience') {
      delete criteria.min_experience_years;
      delete criteria.max_experience_years;
    } else if (key === 'certifications' || key === 'certification_keywords' || key === 'skills') {
      if (Array.isArray(criteria[key])) {
        criteria[key] = criteria[key].filter((item) => String(item) !== value);
      }
    } else {
      delete criteria[key];
    }
    const nextQuery = queryFromCriteria(criteria);
    setQuery(nextQuery);
    setCommittedQuery(nextQuery);
  }, [aiQueryData]);

  // Live backend profiles (falls back to MOCK_PROFILES only when demo mode enabled)
  const { profiles: liveProfiles, isLive, demoActive, loading: profilesLoading, error: profilesError, refetch: refetchProfiles } = useCrewProfiles({ skip: !isAuthenticated })
  const allProfiles = liveProfiles

  const requestLogin = useCallback(() => {
    setIsLoginOpen(true);
  }, []);

  const requireAuth = useRequireAuth(isAuthenticated, requestLogin);

  // Shortlist Hook - now works on live + mock unified list
  const {
    bookmarkedIds,
    shortlistedProfiles,
    toggleBookmark: rawToggleBookmark,
    isBookmarked,
    clearShortlist,
    shortlistCount,
  } = useShortlist(allProfiles)

  // Specialist Documents & Compliance Hook
  const {
    getDocumentsForProfile,
    removeDocument,
    refreshDocuments,
  } = useSpecialistDocuments();

  // AI consultant summary, shown automatically when a profile opens
  // (see backend/docs/cv-ingestion-pipeline.md).
  const {
    fetchSummary,
    getSummaryForProfile,
    isSummaryLoading,
  } = useCrewSummary();

  // Search Workspace state (query, filters, results, selection)
  const {
    query, setQuery,
    committedQuery, setCommittedQuery,
    activePresetId,
    filters, setFilters, resetFilters, activeFilterCount,
    showSavedOnly, setShowSavedOnly,
    viewMode, setViewMode,
    sortBy, setSortBy,
    selectedProfileId, setSelectedProfileId,
    isResultsUpdating,
    isSearchActive,
    results,
    activeSelectedProfile,
    currentSelectedIdx,
    handleSelectPreset,
    handleResetAll,
    handlePrevProfile,
    handleNextProfile,
  } = useSearchWorkspace({
    allProfiles,
    isBookmarked,
    aiQueryData,
    aiQueryActive,
  });

  // Focused Workspace mode for working comfortably on a crew member
  const [isFocusMode, setIsFocusMode] = useState(false);

  const showToast = useCallback((msg: string) => {
    setToastMessage(msg);
    setTimeout(() => {
      setToastMessage((curr) => (curr === msg ? null : curr));
    }, 2200);
  }, []);

  const handleToggleTheme = useCallback(() => {
    toggleTheme();
    showToast(isDark ? 'Switched to High-Contrast Light Theme' : 'Switched to Deep Zinc Dark Theme');
  }, [toggleTheme, isDark, showToast]);

  const handleDeleteCrewMember = useCallback(async (profile: UserProfile) => {
    const { data } = await deleteCrewMember({ variables: { id: profile.id } });
    if (!data?.deleteCrewMember) {
      throw new Error(`${profile.name} could not be deleted`);
    }
    if (isBookmarked(profile.id)) rawToggleBookmark(profile.id);
    setCompareIds((ids) => ids.filter((id) => id !== profile.id));
    setSelectedProfileId(selectedProfileId === profile.id ? null : selectedProfileId);
    setModalProfile(null);
    await refetchProfiles();
    showToast(`${profile.name} was deleted`);
  }, [deleteCrewMember, isBookmarked, rawToggleBookmark, refetchProfiles, showToast]);

  const toggleBookmark = useCallback((id: string, e?: MouseEvent) => {
    if (e) e.stopPropagation();
    if (!requireAuth()) return;
    const profile = allProfiles.find((p) => p.id === id);
    const name = profile ? profile.name.split(' ')[0] : 'Specialist';
    const currentlyBookmarked = isBookmarked(id);
    rawToggleBookmark(id);
    showToast(currentlyBookmarked ? `Removed ${name} from shortlist` : `Saved ${name} to shortlist`);
  }, [requireAuth, isBookmarked, rawToggleBookmark, showToast, allProfiles]);

  const handleCopyEmail = useCallback((profile: UserProfile, e?: MouseEvent) => {
    e?.stopPropagation();
    if (!requireAuth()) return;
    navigator.clipboard?.writeText(profile.email);
    setCopiedId(profile.id);
    showToast(`Copied ${profile.email}`);
    setTimeout(() => setCopiedId(null), 1800);
  }, [requireAuth, showToast]);

  // Comparison toggle handler
  const handleToggleCompare = useCallback((profile: UserProfile) => {
    if (!requireAuth()) return;
    setCompareIds((prev) => {
      if (prev.includes(profile.id)) {
        return prev.filter((id) => id !== profile.id);
      }
      if (prev.length >= 4) {
        showToast('You can compare up to 4 specialists at once');
        return prev;
      }
      showToast(`Added ${profile.name.split(' ')[0]} to comparison`);
      return [...prev, profile.id];
    });
  }, [requireAuth, showToast]);

  const handleRemoveCompare = useCallback((id: string) => {
    setCompareIds((prev) => prev.filter((i) => i !== id));
  }, []);

  const handleClearCompare = useCallback(() => {
    setCompareIds([]);
    showToast('Comparison cleared');
  }, [showToast]);

  const compareProfiles = useMemo(() => {
    return allProfiles.filter((p) => compareIds.includes(p.id));
  }, [compareIds, allProfiles]);

  // Mobilization Trigger
  const handleRequestMobilization = useCallback((profile: UserProfile) => {
    if (!requireAuth()) return;
    setInquiryProfile(profile);
    setIsInquiryModalOpen(true);
  }, [requireAuth]);

  // Print Trigger
  const handlePrintDossier = useCallback((profile: UserProfile) => {
    if (!requireAuth()) return;
    setPrintProfile(profile);
  }, [requireAuth]);

  // URL Synchronization
  useURLSync({
    query,
    viewMode: viewMode === 'grid' ? 'cards' : viewMode,
    onSyncQuery: useCallback((q: string) => {
      setQuery(q);
      setCommittedQuery(q.trim());
    }, []),
    onSyncViewMode: useCallback((mode: 'split' | 'cards' | 'table') => {
      setViewMode(mode === 'cards' ? 'grid' : mode);
    }, []),
  });

  // Document records live on the backend. Refresh the active/modal dossier
  // whenever its subject changes, including after a successful upload/delete.
  useEffect(() => {
    const profileIds = new Set(
      [activeSelectedProfile?.id, modalProfile?.id].filter((id): id is string => Boolean(id))
    );
    profileIds.forEach((id) => {
      void refreshDocuments(id).catch(() => {
        // The vault remains empty until the authenticated request succeeds.
      });
      void fetchSummary(id);
    });
  }, [activeSelectedProfile?.id, modalProfile?.id, refreshDocuments, fetchSummary]);

  // Global & Split View Keyboard navigation
  useKeyboardNavigation({
    results,
    selectedProfileId,
    setSelectedProfileId,
    activeSelectedProfile,
    isFocusMode,
    setIsFocusMode,
    handleToggleTheme,
    toggleBookmark,
    handleRequestMobilization,
    handlePrevProfile,
    handleNextProfile,
    setIsShortcutsOpen,
    showToast,
  });

  // Auth gate: block until we know session state
  if (!authInitialized) {
    return (
      <div className="min-h-screen bg-zinc-950 text-zinc-100 flex items-center justify-center font-sans antialiased">
        <div className="flex items-center gap-2 text-xs text-zinc-500 font-mono">
          <span className="h-2 w-2 rounded-full bg-blue-500 animate-pulse" />
          Loading session…
        </div>
      </div>
    );
  }

  const handleLogout = async () => {
    await logout();
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col font-sans antialiased selection:bg-blue-600/30 selection:text-blue-100 relative overflow-x-hidden">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[100] focus:rounded-lg focus:bg-zinc-100 focus:px-3 focus:py-2 focus:text-xs focus:font-semibold focus:text-zinc-950"
      >
        Skip to main content
      </a>
      {/* Subtle Ambient Background Layer */}
      <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden" aria-hidden="true">
        <div className="absolute inset-0 bg-radial-ambient" />
        <div
          className="absolute inset-0 bg-grid-subtle opacity-40"
          style={{
            maskImage: 'radial-gradient(ellipse 90% 70% at 50% 30%, black 20%, transparent 85%)',
            WebkitMaskImage: 'radial-gradient(ellipse 90% 70% at 50% 30%, black 20%, transparent 85%)',
          }}
        />
      </div>

      {/* Minimal Top Navbar */}
      <header className="w-full border-b border-zinc-800/60 bg-zinc-950/80 backdrop-blur-xl sticky top-0 z-30">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-5 min-w-0">
          {/* Logo / Brand Name */}
          <button
            type="button"
            onClick={handleResetAll}
            className="flex items-center gap-2.5 cursor-pointer select-none group focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded-lg"
            aria-label="Go to Hydenlyne Talent home"
          >
            <img src={isDark ? hydenlyneLogoWhite : hydenlyneLogoColour} alt="Hydenlyne" className="w-[104px] h-auto" />
            <span className="text-[11px] text-zinc-500 font-mono hidden sm:inline">
              / talent
            </span>
          </button>

          {/* Right Nav */}
          <div className="hidden">
            <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
            {/* Compare Matrix Trigger Button */}
            {compareIds.length > 0 && isAuthenticated && (
              <button
                type="button"
                onClick={() => setIsCompareModalOpen(true)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-blue-950/80 border border-blue-800 text-blue-300 hover:text-white text-xs font-semibold transition-colors cursor-pointer"
                title="Compare specialists side-by-side"
              >
                <Scale className="w-3.5 h-3.5" />
                <span>Compare ({compareIds.length})</span>
              </button>
            )}

            {isSearchActive && isAuthenticated && (
              /* View Mode Switcher */
              <div className="flex items-center bg-zinc-900 border border-zinc-800 p-0.5 rounded-xl text-xs">
                <button
                  type="button"
                  onClick={() => setViewMode('split')}
                  className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg transition-colors cursor-pointer ${
                    viewMode === 'split'
                      ? 'bg-zinc-800 text-white font-medium shadow-xs'
                      : 'text-zinc-500 hover:text-zinc-300'
                  }`}
                  title="Split Command View"
                  aria-label="Split command view"
                  aria-pressed={viewMode === 'split'}
                >
                  <Columns className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">Split</span>
                </button>

                <button
                  type="button"
                  onClick={() => setViewMode('grid')}
                  className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg transition-colors cursor-pointer ${
                    viewMode === 'grid'
                      ? 'bg-zinc-800 text-white font-medium shadow-xs'
                      : 'text-zinc-500 hover:text-zinc-300'
                  }`}
                  title="Cards View"
                  aria-label="Cards view"
                  aria-pressed={viewMode === 'grid'}
                >
                  <LayoutGrid className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">Cards</span>
                </button>

                <button
                  type="button"
                  onClick={() => setViewMode('table')}
                  className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg transition-colors cursor-pointer ${
                    viewMode === 'table'
                      ? 'bg-zinc-800 text-white font-medium shadow-xs'
                      : 'text-zinc-500 hover:text-zinc-300'
                  }`}
                  title="Matrix View"
                  aria-label="Table view"
                  aria-pressed={viewMode === 'table'}
                >
                  <Table className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">Matrix</span>
                </button>
              </div>
            )}

             {/* Shortcuts Guide Button */}
            <button
              type="button"
              onClick={() => setIsShortcutsOpen(true)}
                className="min-h-10 min-w-10 p-2 rounded-xl bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-zinc-200 transition-colors cursor-pointer shrink-0 inline-flex items-center justify-center"
              title="Keyboard shortcuts (?)"
              aria-label="Open keyboard shortcuts"
            >
              <Command className="w-3.5 h-3.5" />
            </button>

            {/* Add Crew Member Button */}
            {isAuthenticated && (
              <button
                type="button"
                onClick={() => setIsAddCrewMemberOpen(true)}
                className="inline-flex min-h-10 items-center gap-1.5 rounded-xl border border-zinc-700 bg-zinc-900 px-2.5 py-1.5 text-xs font-semibold text-zinc-300 transition-colors hover:border-zinc-500 hover:bg-zinc-800 hover:text-zinc-100 cursor-pointer shrink-0"
                title="Add a specialist to the network"
                aria-label="Add specialist"
              >
                <UserPlus className="w-3.5 h-3.5" />
                <span className="hidden md:inline">Add Specialist</span>
              </button>
            )}

            {/* Theme Toggle Button */}
            <button
              type="button"
              id="app-theme-toggle-btn"
              onClick={handleToggleTheme}
              className="inline-flex min-h-10 items-center gap-1.5 px-2.5 py-1.5 rounded-xl bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-zinc-200 transition-colors cursor-pointer text-xs font-medium shrink-0"
              title={isDark ? 'Switch to High-Contrast Light Theme (T)' : 'Switch to Deep Zinc Dark Theme (T)'}
              aria-label={isDark ? 'Switch to light theme' : 'Switch to dark theme'}
            >
              {isDark ? (
                <>
                  <Sun className="w-3.5 h-3.5 text-amber-400" />
                  <span className="hidden md:inline">Light</span>
                </>
              ) : (
                <>
                  <Moon className="w-3.5 h-3.5 text-zinc-600" />
                  <span className="hidden md:inline">Dark</span>
                </>
              )}
            </button>

            {/* Shortlist Filter & Exporter Action */}
            <div className="flex items-center gap-1 bg-zinc-900 border border-zinc-800 p-0.5 rounded-xl shrink-0">
              <button
                type="button"
                onClick={() => isAuthenticated ? setShowSavedOnly(!showSavedOnly) : requestLogin()}
                className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium transition-colors cursor-pointer ${
                  showSavedOnly
                    ? 'bg-zinc-100 text-zinc-950 font-semibold'
                    : 'text-zinc-400 hover:text-zinc-200'
                }`}
                title={showSavedOnly ? 'Show all results' : 'Filter by shortlist'}
              >
                <Bookmark className={`w-3.5 h-3.5 ${showSavedOnly ? 'fill-zinc-950' : ''}`} />
                <span className="hidden xs:inline">Shortlist</span>
                <span className="text-[11px] text-zinc-300 font-mono">({shortlistCount})</span>
              </button>

              {shortlistCount > 0 && (
                <button
                  type="button"
                  onClick={() => setIsExportShortlistOpen(true)}
                  className="p-1 rounded-lg text-zinc-400 hover:text-blue-400 hover:bg-zinc-800 transition-colors cursor-pointer"
                  title="Export / View Shortlist"
                  aria-label="Export or view shortlist"
                >
                  <Download className="w-3.5 h-3.5" />
                </button>
              )}
            </div>

            </div>

            {/* User + Authentication */}
            <div className="flex items-center gap-1.5 ml-1 pl-2 sm:gap-2 sm:ml-0 sm:pl-3 border-l border-zinc-800 shrink-0">
            {isAuthenticated ? <div className="hidden sm:flex items-center gap-2 rounded-xl border border-zinc-800 bg-zinc-900/60 px-2 py-1">
              <span className="text-[11px] text-zinc-400 max-w-[120px] truncate" title={user?.email}>
                {user?.email}
              </span>
              <button
                type="button"
                onClick={handleLogout}
                className="p-2 rounded-xl bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-rose-300 hover:border-rose-800/60 transition-colors cursor-pointer"
                title="Sign out"
                aria-label="Sign out"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div> : (
              <button type="button" onClick={requestLogin} className="inline-flex min-h-11 items-center rounded-xl bg-zinc-100 px-3 py-1.5 text-xs font-semibold text-zinc-950 transition-colors hover:bg-white cursor-pointer">
                Sign in
              </button>
            )}
            {isAuthenticated && (
              <span
                className="sm:hidden max-w-[132px] truncate rounded-lg bg-zinc-900/60 px-2 py-1.5 text-[10px] text-zinc-400"
                title={user?.email || undefined}
              >
                {user?.email}
              </span>
            )}
            </div>
            <span className="hidden" data-auth-session-key={authSessionKey} />
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {isAuthenticated && (
              <span className="hidden max-w-[180px] truncate text-xs text-zinc-400 sm:inline" title={user?.email}>
                {user?.email}
              </span>
            )}
            {!isAuthenticated && (
              <button type="button" onClick={requestLogin} className="inline-flex min-h-11 items-center rounded-xl bg-zinc-100 px-3 py-1.5 text-xs font-semibold text-zinc-950 transition-colors hover:bg-white cursor-pointer">
                Sign in
              </button>
            )}
            {isAuthenticated && (
              <button type="button" onClick={() => setIsAddCrewMemberOpen(true)} className="inline-flex min-h-11 items-center gap-1.5 rounded-xl border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-xs font-semibold text-zinc-300 transition-colors hover:border-zinc-500 hover:bg-zinc-800 hover:text-zinc-100 cursor-pointer" aria-label="Add specialist" title="Add a specialist to the network">
                <UserPlus className="h-3.5 w-3.5" aria-hidden="true" />
                <span className="hidden sm:inline">Add Specialist</span>
              </button>
            )}
            {user?.role === 'admin' && <ServiceStatus />}
            {isAuthenticated && (
              <button type="button" onClick={() => setShowSavedOnly(!showSavedOnly)} className={`inline-flex min-h-11 items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-semibold transition-colors cursor-pointer ${showSavedOnly ? 'border-zinc-500 bg-zinc-100 text-zinc-950' : 'border-zinc-800 bg-zinc-900 text-zinc-300 hover:border-zinc-600 hover:bg-zinc-800 hover:text-zinc-100'}`} aria-pressed={showSavedOnly} title={showSavedOnly ? 'Show all specialists' : 'View shortlist'}>
                <Bookmark className={`h-3.5 w-3.5 ${showSavedOnly ? 'fill-zinc-950' : ''}`} aria-hidden="true" />
                <span className="hidden sm:inline">Shortlist</span>
                <span className="font-mono text-[11px]">({shortlistCount})</span>
              </button>
            )}
            <button type="button" onClick={() => setIsMenuOpen(true)} className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-xl border border-zinc-800 bg-zinc-900 text-zinc-300 transition-colors hover:border-zinc-600 hover:bg-zinc-800 hover:text-zinc-100 cursor-pointer" aria-label="Open workspace menu" aria-expanded={isMenuOpen}>
              <Menu className="h-4 w-4" />
            </button>
          </div>
        </div>
      </header>

      <AppMenuDrawer
        isOpen={isMenuOpen}
        onClose={() => setIsMenuOpen(false)}
        isAuthenticated={isAuthenticated}
        isDark={isDark}
        onToggleTheme={handleToggleTheme}
        onOpenShortcuts={() => setIsShortcutsOpen(true)}
        onOpenAddSpecialist={() => setIsAddCrewMemberOpen(true)}
        onOpenCompare={() => setIsCompareModalOpen(true)}
        compareCount={compareIds.length}
        isSearchActive={isSearchActive}
        viewMode={viewMode}
        onViewModeChange={setViewMode}
        shortlistCount={shortlistCount}
        onExportShortlist={() => setIsExportShortlistOpen(true)}
        email={user?.email}
        onLogout={handleLogout}
        onRequestLogin={requestLogin}
      />

      {/* Main Container */}
      <main id="main-content" className="flex-1 max-w-6xl mx-auto w-full px-4 sm:px-6 flex flex-col justify-start" aria-label="Specialist network workspace">
        {/* Live-data required banner (prod, no demo fallback) */}
        {isAuthenticated && !profilesLoading && !isLive && !demoActive && (
          <div className="mt-4 rounded-2xl border border-rose-800/60 bg-rose-950/30 px-4 py-3 flex items-start gap-3" role="alert">
            <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
            <div className="flex-1">
              <h2 className="text-sm font-semibold text-rose-200">Live specialist data unavailable</h2>
              <p className="text-xs text-rose-300/80 mt-0.5">
                The backend returned no data{profilesError ? ` (${profilesError})` : ''}. Demo profiles
                are disabled in this build — sign in and confirm the API is reachable.
              </p>
            </div>
            <button
              type="button"
              onClick={refetchProfiles}
              className="shrink-0 min-h-11 px-3 py-1.5 rounded-lg bg-rose-950/60 border border-rose-700/60 text-rose-200 hover:bg-rose-900/60 text-xs font-medium transition-colors cursor-pointer"
            >
              Retry
            </button>
          </div>
        )}
        {/* Modern Search Bar: stays available while scanning a long result set. */}
        <div className={isSearchActive ? 'sticky top-16 z-20 -mx-4 px-4 bg-zinc-950/90 backdrop-blur-md sm:-mx-6 sm:px-6' : ''}>
          <ModernHeroSearch
            query={query}
            onChange={(val) => {
              if (isAuthenticated) setQuery(val);
            }}
            onSearch={(val) => {
              setQuery(val);
              setCommittedQuery(val.trim());
              if (!isAuthenticated) requestLogin();
            }}
            onClear={() => {
              setQuery('');
              setCommittedQuery('');
            }}
            isCalmState={!isSearchActive}
            isAuthenticated={isAuthenticated}
            onAIResults={handleAIResults}
            onOpenFilters={() => setIsFilterOpen(true)}
          />
        </div>

        {/* Results Header (Active Search Only) */}
        {isSearchActive && (
          <div className="flex flex-col gap-3 py-2 text-xs text-zinc-400 border-b border-zinc-800/60 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-2 flex-wrap" aria-live="polite">
              <span>
                Found <strong className="text-zinc-100 font-semibold">{results.length}</strong> {results.length === 1 ? 'specialist' : 'specialists'}
              </span>
              {isResultsUpdating && (
                <span className="inline-flex items-center gap-1.5 text-zinc-500">
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-blue-400" aria-hidden="true" />
                  Updating results…
                </span>
              )}
              <DensityIndicator matchedCount={results.length} totalCount={allProfiles.length} />
              <div className="flex items-center gap-1.5 flex-wrap">
                {committedQuery && (
                  <button type="button" onClick={() => { setQuery(''); setCommittedQuery(''); }} className="badge-accent inline-flex min-h-11 items-center gap-1 rounded-lg px-2 py-1 text-xs hover:brightness-95" aria-label="Remove search query filter">
                    <span className="font-mono font-semibold">Query</span> “{committedQuery}” <X className="h-3 w-3 opacity-80" />
                  </button>
                )}
                {activePresetId !== 'all' && (
                  <button type="button" onClick={resetFilters} className="badge-neutral inline-flex min-h-11 items-center gap-1 rounded-lg px-2 py-1 text-xs hover:brightness-95" aria-label="Remove active preset filter">
                    <span className="font-mono font-semibold opacity-80">Preset</span> {FILTER_PRESETS.find((p) => p.id === activePresetId)?.name} <X className="h-3 w-3 opacity-70" />
                  </button>
                )}
                {showSavedOnly && (
                  <button type="button" onClick={() => setShowSavedOnly(false)} className="badge-neutral inline-flex min-h-11 items-center gap-1 rounded-lg px-2 py-1 text-xs hover:brightness-95" aria-label="Remove shortlist-only filter">
                    <span className="font-semibold">Shortlist only</span> <X className="h-3 w-3 opacity-70" />
                  </button>
                )}
              </div>
            </div>

            <div className="flex w-full items-center gap-3 sm:w-auto sm:justify-end">
              {/* Sort Dropdown */}
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as SortOption)}
                aria-label="Sort specialists"
                className="min-h-11 min-w-0 flex-1 bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-zinc-200 text-xs rounded-lg px-2.5 py-1 focus:outline-none focus:border-zinc-700 cursor-pointer font-medium sm:flex-none"
              >
                <option value="relevance">Sort: Relevance & Match</option>
                <option value="experience-desc">Sort: Experience (High to Low)</option>
                <option value="rate-desc">Sort: Day Rate (High to Low)</option>
                <option value="rate-asc">Sort: Day Rate (Low to High)</option>
                <option value="rating-desc">Sort: Rating (★ Highest)</option>
              </select>

              {(query || showSavedOnly || activeFilterCount > 0 || sortBy !== 'relevance') && (
                <button
                  type="button"
                  onClick={handleResetAll}
                  className="min-h-11 shrink-0 text-zinc-400 hover:text-zinc-200 transition-colors cursor-pointer text-xs underline"
                >
                  Clear all
                </button>
              )}
            </div>
          </div>
        )}

        {isSearchActive && activeFilterCount > 0 && (
          <ActiveFilterChips
            filters={filters}
            onUpdateFilters={setFilters}
            onResetFilters={resetFilters}
          />
        )}

        {/* Results Area */}
        {isSearchActive && (
          <div className="pb-16" role="region" aria-busy={profilesLoading || aiQueryLoading} aria-label="Specialist search results">
            {aiQueryActive && showAISummary && (
              <CrewQuerySummary
                data={aiQueryData}
                loading={aiQueryLoading}
                error={null}
                onRemoveCriterion={handleRemoveSearchCriterion}
              />
            )}
            {profilesLoading ? (
              <SkeletonResults viewMode="list" />
            ) : results.length > 0 ? (
              viewMode === 'split' ? (
                isFocusMode ? (
                  /* Focused Specialist Workspace (Enlarged & Centered for comfortable working) */
                  <div className="fixed inset-0 z-40 flex flex-col overflow-hidden bg-zinc-950/95 px-2 py-3 sm:p-4 backdrop-blur-sm">
                    {/* Crew Selector Navigation Strip */}
                    <div className="w-full max-w-6xl mx-auto flex items-center justify-between bg-zinc-900/90 border border-zinc-800 p-2.5 sm:p-3 rounded-2xl backdrop-blur-md shadow-xl gap-3 shrink-0">
                      <div className="flex items-center gap-2 overflow-x-auto py-1 scrollbar-none max-w-2xl">
                        {results.map((profile, idx) => {
                          const isSel = (activeSelectedProfile?.id || selectedProfileId) === profile.id;
                          return (
                            <button
                              key={profile.id}
                              id={`specialist-result-${profile.id}`}
                              type="button"
                              onClick={() => setSelectedProfileId(profile.id)}
                              className={`flex items-center gap-2.5 px-3.5 py-1.5 rounded-xl text-xs font-medium shrink-0 transition-all cursor-pointer ${
                                isSel
                                  ? 'bg-zinc-800 text-white border border-zinc-600 shadow-md font-semibold'
                                  : 'bg-zinc-950/60 border border-zinc-850 text-zinc-400 hover:bg-zinc-800/80 hover:text-zinc-200'
                              }`}
                            >
                              <img
                                src={profile.avatar}
                                alt={profile.name}
                                referrerPolicy="no-referrer"
                                className="w-5 h-5 rounded-full object-cover border border-zinc-700"
                              />
                              <span className="truncate max-w-[110px]">{profile.name}</span>
                              <span className="font-mono text-[10px] opacity-60">#{idx + 1}</span>
                            </button>
                          );
                        })}
                      </div>

                      <div className="flex items-center gap-2 shrink-0">
                        <button
                          type="button"
                          onClick={() => setIsFocusMode(false)}
                          className="px-3.5 py-1.5 rounded-xl bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 text-zinc-200 text-xs font-medium transition-colors cursor-pointer flex items-center gap-1.5 shadow-xs"
                          title="Exit Focus Mode (F / Esc)"
                        >
                          <span>Exit Focus</span>
                          <span className="font-mono text-[10px] text-zinc-400">Esc</span>
                        </button>
                      </div>
                    </div>

                    {/* Centered Enlarged Specialist Dossier Card */}
                    <AnimatePresence mode="wait">
                      <motion.div
                        key={activeSelectedProfile ? activeSelectedProfile.id : 'empty-focus'}
                        initial={{ opacity: 0, scale: 0.98, y: 10 }}
                        animate={{ opacity: 1, scale: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.98, y: -10 }}
                        transition={{ duration: 0.2, ease: 'easeOut' }}
                        className="w-full max-w-6xl mx-auto flex-1 min-h-0 flex justify-center"
                      >
                        <Suspense fallback={<DossierFallback />}>
                        <SpecialistDossierPane
                          profile={activeSelectedProfile}
                          searchQuery={committedQuery}
                          isBookmarked={activeSelectedProfile ? isBookmarked(activeSelectedProfile.id) : false}
                          onToggleBookmark={toggleBookmark}
                          onShowToast={showToast}
                          isCompared={activeSelectedProfile ? compareIds.includes(activeSelectedProfile.id) : false}
                          onToggleCompare={handleToggleCompare}
                          onRequestMobilization={handleRequestMobilization}
                          onPrintDossier={handlePrintDossier}
                          documents={activeSelectedProfile ? getDocumentsForProfile(activeSelectedProfile.id) : []}
                          summary={activeSelectedProfile ? getSummaryForProfile(activeSelectedProfile.id) : undefined}
                          summaryLoading={activeSelectedProfile ? isSummaryLoading(activeSelectedProfile.id) : false}
                          onAddDocument={() => activeSelectedProfile && void refreshDocuments(activeSelectedProfile.id)}
                          onRemoveDocument={async (docId) => {
                            if (activeSelectedProfile) await removeDocument(activeSelectedProfile.id, docId);
                          }}
                          canManageDocuments={canManageDocuments}
                          canDeleteCrew={canManageDocuments && user?.id !== activeSelectedProfile?.id}
                          onDeleteCrew={handleDeleteCrewMember}
                          isFocusMode={true}
                          onToggleFocusMode={() => setIsFocusMode(false)}
                          onPrevProfile={handlePrevProfile}
                          onNextProfile={handleNextProfile}
                          profileIndex={currentSelectedIdx >= 0 ? currentSelectedIdx : 0}
                          totalProfiles={results.length}
                        />
                        </Suspense>
                      </motion.div>
                    </AnimatePresence>
                  </div>
                ) : (
                  /* Standard Split-Pane Operations Command */
                  <div className="scan-workspace grid grid-cols-1 md:grid-cols-12 gap-5 items-stretch min-h-0 md:min-h-[520px] py-2 sm:py-3">
                    {/* Left Column: Animated List */}
                    <section aria-label="Specialist search results" className="md:col-span-5 min-h-0 h-full overflow-y-auto pr-1 scan-scroll-panel space-y-2">
                      <div className="sticky top-0 z-10 flex items-center justify-between gap-3 bg-zinc-950/95 px-1 pb-2 pt-1 backdrop-blur-sm">
                        <span className="text-[11px] font-semibold uppercase tracking-wider text-zinc-400">Results</span>
                        <span className="font-mono text-xs text-zinc-500">Select to view dossier</span>
                      </div>
                      <AnimatePresence mode="popLayout">
                        {results.map((profile, index) => {
                          const isSelected = selectedProfileId === profile.id;
                          const isProfileBookmarked = isBookmarked(profile.id);
                          const isCompared = compareIds.includes(profile.id);
                          const isAvailableNow = profile.availability?.toLowerCase().includes('immediately');
                          const matchedResult = aiQueryData?.results.find((result) => result.id === profile.id);

                          return (
                            <motion.div
                              layout
                              initial={{ opacity: 0, y: 14, scale: 0.98 }}
                              animate={{ opacity: 1, y: 0, scale: 1 }}
                              exit={{ opacity: 0, y: -10, scale: 0.96 }}
                              transition={{
                                duration: 0.22,
                                delay: Math.min(index * 0.02, 0.18),
                                ease: [0.16, 1, 0.3, 1],
                              }}
                              key={profile.id}
                              className={`group relative p-3.5 rounded-2xl border transition-all duration-150 cursor-pointer flex items-center justify-between gap-3 ${
                                isSelected
                                  ? 'bg-zinc-900 border-zinc-700 shadow-lg shadow-black/10'
                                  : 'bg-transparent hover:bg-zinc-900/60 border-transparent hover:border-zinc-800'
                              }`}
                            >
                              <button
                                type="button"
                                id={`specialist-result-${profile.id}`}
                                onClick={() => {
                                  setSelectedProfileId(profile.id);
                                  if (window.matchMedia('(max-width: 767px)').matches) setModalProfile(profile);
                                }}
                                className="flex items-center gap-3 min-w-0 flex-1 text-left cursor-pointer"
                                aria-label={`View ${profile.name} dossier, ${profile.title}`}
                                aria-current={isSelected ? 'true' : undefined}
                              >
                              <div className="flex items-center gap-3 min-w-0 flex-1">
                                <div className="relative shrink-0">
                                  <img
                                    src={profile.avatar}
                                    alt={profile.name}
                                    referrerPolicy="no-referrer"
                                    className="w-11 h-11 rounded-lg object-cover border border-zinc-800/90 group-hover:border-zinc-700 transition-colors"
                                  />
                                  {isAvailableNow && (
                                    <span
                                      className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-emerald-400 border-2 border-zinc-950"
                                      title="Available immediately"
                                    />
                                  )}
                                </div>

                                <div className="min-w-0 space-y-1 flex-1">
                                  <div className="flex items-center justify-between gap-2">
                                    <div className="flex items-center gap-1.5 min-w-0">
                                    <h3 className={`font-semibold text-sm tracking-tight truncate ${isSelected ? 'text-blue-300' : 'text-zinc-100 group-hover:text-zinc-50'}`}>
                                        <HighlightText text={profile.name} query={committedQuery} />
                                      </h3>
                                      {profile.isHighlyRecommended && (
                                        <BadgeCheck className="w-3.5 h-3.5 text-blue-400 shrink-0" title="Verified Specialist" />
                                      )}
                                    </div>

                                    <span className="text-xs font-mono font-semibold text-zinc-200 shrink-0">
                                      {profile.dayRate ? `£${profile.dayRate}/d` : 'Rate n/a'}
                                    </span>
                                  </div>

                                  <p className="text-xs text-zinc-400 truncate font-normal">
                                    <HighlightText text={profile.title} query={committedQuery} />
                                  </p>

                                  <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-zinc-400 pt-1">
                                    <span className="badge-accent px-1.5 py-0.5 rounded font-medium">
                                      {profile.department}
                                    </span>
                                    <span className={`px-1.5 py-0.5 rounded font-medium ${isAvailableNow ? 'badge-positive' : 'badge-neutral'}`}>
                                      {profile.availability.replace('Available ', '')}
                                    </span>
                                    <span className="truncate text-zinc-400">{profile.location.split(',')[0]}</span>
                                    <span className="font-mono text-zinc-300">{profile.yearsOfExperience}y</span>
                                    {profile.rating && <span className="font-mono text-amber-300">★ {profile.rating.toFixed(1)}</span>}
                                  </div>
                                  <div className="flex items-center gap-1.5 pt-1 text-[11px] text-zinc-500">
                                    {profile.skills.slice(0, 2).map((skill) => (
                                      <span key={skill} className="truncate rounded-md border border-zinc-800 bg-zinc-950/60 px-1.5 py-0.5 text-zinc-400">
                                        <HighlightText text={skill} query={committedQuery} />
                                      </span>
                                    ))}
                                    {profile.skills.length > 2 && <span className="shrink-0 font-mono">+{profile.skills.length - 2}</span>}
                                  </div>
                                  {aiQueryActive && (
                                    <MatchEvidence
                                      profile={profile}
                                      criteria={aiQueryData?.criteria}
                                      resultCertifications={matchedResult?.certifications}
                                      compact
                                    />
                                  )}
                                </div>
                              </div>
                              </button>

                              {/* Secondary actions stay available without competing with dossier selection. */}
                              <div className="shrink-0" onClick={(event) => event.stopPropagation()}>
                                <SpecialistActionsMenu
                                  profile={profile}
                                  isBookmarked={isProfileBookmarked}
                                  isCompared={isCompared}
                                  onToggleBookmark={() => toggleBookmark(profile.id)}
                                  onToggleCompare={() => handleToggleCompare(profile)}
                                  onRequestMobilization={() => handleRequestMobilization(profile)}
                                />
                              </div>
                            </motion.div>
                          );
                        })}
                      </AnimatePresence>
                    </section>

                    {/* Right Column: Live Specialist Dossier */}
                    <div className="hidden md:col-span-7 md:block min-h-0 h-full overflow-hidden md:sticky md:top-20">
                      <div className="mb-2 flex items-center justify-between px-1 md:hidden">
                        <span className="text-[11px] font-semibold uppercase tracking-wider text-zinc-400">Selected dossier</span>
                        <span className="text-[11px] text-zinc-500">Scroll for details</span>
                      </div>
                      <AnimatePresence mode="wait">
                        <motion.div
                          key={activeSelectedProfile ? activeSelectedProfile.id : 'empty'}
                          initial={{ opacity: 0, y: 8 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0, y: -8 }}
                          transition={{ duration: 0.2, ease: 'easeOut' }}
                          className="h-full min-h-0"
                        >
                          <Suspense fallback={<DossierFallback />}>
                          <SpecialistDossierPane
                            profile={activeSelectedProfile}
                            searchQuery={committedQuery}
                            isBookmarked={activeSelectedProfile ? isBookmarked(activeSelectedProfile.id) : false}
                            onToggleBookmark={toggleBookmark}
                            onShowToast={showToast}
                            isCompared={activeSelectedProfile ? compareIds.includes(activeSelectedProfile.id) : false}
                            onToggleCompare={handleToggleCompare}
                            onRequestMobilization={handleRequestMobilization}
                            onPrintDossier={handlePrintDossier}
                            documents={activeSelectedProfile ? getDocumentsForProfile(activeSelectedProfile.id) : []}
                            summary={activeSelectedProfile ? getSummaryForProfile(activeSelectedProfile.id) : undefined}
                            summaryLoading={activeSelectedProfile ? isSummaryLoading(activeSelectedProfile.id) : false}
                            onAddDocument={() => activeSelectedProfile && void refreshDocuments(activeSelectedProfile.id)}
                            onRemoveDocument={async (docId) => {
                              if (activeSelectedProfile) {
                                try {
                                  await removeDocument(activeSelectedProfile.id, docId);
                                } catch {
                                  showToast('Failed to remove document');
                                }
                              }
                            }}
                            canManageDocuments={canManageDocuments}
                            canDeleteCrew={canManageDocuments && user?.id !== activeSelectedProfile?.id}
                            onDeleteCrew={handleDeleteCrewMember}
                            isFocusMode={false}
                            onToggleFocusMode={() => setIsFocusMode(true)}
                            onPrevProfile={handlePrevProfile}
                            onNextProfile={handleNextProfile}
                            profileIndex={currentSelectedIdx >= 0 ? currentSelectedIdx : 0}
                            totalProfiles={results.length}
                          />
                          </Suspense>
                        </motion.div>
                      </AnimatePresence>
                    </div>
                  </div>
                )
              ) : viewMode === 'table' ? (
                /* High-Density Spreadsheet Matrix */
                <Suspense fallback={<SkeletonResults viewMode="list" />}>
                <SpecialistTableView
                  profiles={results}
                  searchQuery={committedQuery}
                  selectedId={selectedProfileId}
                  onSelectProfile={(p) => {
                    setSelectedProfileId(p.id);
                    setModalProfile(p);
                  }}
                  isBookmarked={isBookmarked}
                  onToggleBookmark={toggleBookmark}
                  onShowToast={showToast}
                  compareIds={compareIds}
                  onToggleCompare={handleToggleCompare}
                  onRequestMobilization={handleRequestMobilization}
                />
                </Suspense>
              ) : (
                /* Visual Grid Cards View with Motion */
                <motion.div layout className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
                  <AnimatePresence mode="popLayout">
                    {results.map((profile, index) => {
                      const isProfileBookmarked = isBookmarked(profile.id);
                      const isCompared = compareIds.includes(profile.id);
                      const isAvailableNow = profile.availability?.toLowerCase().includes('immediately');
                      const matchedResult = aiQueryData?.results.find((result) => result.id === profile.id);

                      return (
                        <motion.div
                          layout
                          initial={{ opacity: 0, y: 18, scale: 0.96 }}
                          animate={{ opacity: 1, y: 0, scale: 1 }}
                          exit={{ opacity: 0, y: -12, scale: 0.94 }}
                          transition={{
                            duration: 0.26,
                            delay: Math.min(index * 0.03, 0.2),
                            ease: [0.16, 1, 0.3, 1],
                          }}
                          key={profile.id}
                          className="group bg-zinc-900/35 hover:bg-zinc-900/70 border border-transparent hover:border-zinc-800 rounded-2xl p-5 transition-[background-color,border-color,box-shadow] duration-200 flex flex-col justify-between space-y-4 hover:shadow-xl hover:shadow-black/10"
                        >
                          {/* Header Row */}
                          <div className="flex items-start justify-between gap-3">
                            <div className="flex items-center gap-3 min-w-0">
                              <div className="relative shrink-0">
                                <img
                                  src={profile.avatar}
                                  alt={profile.name}
                                  referrerPolicy="no-referrer"
                                  className="w-11 h-11 rounded-xl object-cover border border-zinc-800"
                                />
                                {isAvailableNow && (
                                  <span
                                    className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-emerald-400 border border-zinc-950"
                                    title="Available immediately"
                                  />
                                )}
                              </div>

                              <div className="min-w-0">
                                <div className="flex items-center gap-1.5">
                                  <h3 className="font-medium text-sm text-zinc-100 group-hover:text-blue-400 transition-colors truncate">
                                    <HighlightText text={profile.name} query={committedQuery} />
                                  </h3>
                                  {profile.isHighlyRecommended && (
                                    <BadgeCheck className="w-3.5 h-3.5 text-blue-400 shrink-0" title="Verified Specialist" />
                                  )}
                                </div>
                                <p className="text-xs text-zinc-400 truncate font-light">
                                  <HighlightText text={profile.title} query={committedQuery} />
                                </p>
                                {profile.isHighlyRecommended && (
                                  <span className="mt-1 inline-flex items-center gap-1 text-[10px] font-medium text-blue-300">
                                    <span className="h-1.5 w-1.5 rounded-full bg-blue-400" />
                                    Strong match
                                  </span>
                                )}
                              </div>
                            </div>

                            <div className="shrink-0" onClick={(event) => event.stopPropagation()}>
                              <SpecialistActionsMenu
                                profile={profile}
                                isBookmarked={isProfileBookmarked}
                                isCompared={isCompared}
                                copied={copiedId === profile.id}
                                onToggleBookmark={() => toggleBookmark(profile.id)}
                                onToggleCompare={() => handleToggleCompare(profile)}
                                onCopyEmail={() => handleCopyEmail(profile)}
                                onRequestMobilization={() => handleRequestMobilization(profile)}
                              />
                            </div>
                          </div>

                          {/* Compact Specs Line */}
                          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-zinc-400 border-t border-b border-zinc-800/50 py-1.5">
                            <span className="flex items-center gap-1 truncate">
                              <MapPin className="w-3 h-3 text-zinc-500 shrink-0" />
                              <HighlightText text={profile.location.split(',')[0]} query={committedQuery} />
                            </span>
                            <span>•</span>
                            <span>{profile.yearsOfExperience} yrs exp</span>
                            {profile.dayRate && (
                              <>
                                <span>•</span>
                                <span className="text-emerald-400 font-medium">£{profile.dayRate}/day</span>
                              </>
                            )}
                            <span className={isAvailableNow ? 'text-emerald-300 font-medium' : 'text-zinc-400'}>
                              {profile.availability.replace('Available ', '')}
                            </span>
                            {profile.rating && <span className="font-mono text-amber-300">★ {profile.rating.toFixed(1)}</span>}
                          </div>

                          {/* Certifications with Tooltips */}
                          {profile.certifications && profile.certifications.length > 0 && (
                            <div className="flex flex-wrap gap-1" onClick={(e) => e.stopPropagation()}>
                              {profile.certifications.slice(0, 3).map((cert) => (
                                <CertificationBadge key={cert} certification={cert} size="sm" />
                              ))}
                            </div>
                          )}

                          {aiQueryActive && (
                            <MatchEvidence
                              profile={profile}
                              criteria={aiQueryData?.criteria}
                              resultCertifications={matchedResult?.certifications}
                            />
                          )}

                          {/* Bio snippet */}
                          <p className="text-xs text-zinc-400 line-clamp-2 leading-relaxed font-light">
                            <HighlightText text={profile.bio} query={committedQuery} />
                          </p>

                          {/* Footer / Skills */}
                          <div className="flex items-center justify-between gap-2 pt-1 border-t border-zinc-850">
                            <div className="flex items-center gap-1.5 flex-wrap">
                              {profile.skills.slice(0, 3).map((skill) => (
                                <span
                                  key={skill}
                                  className="px-2 py-0.5 rounded-md bg-zinc-800/80 text-zinc-400 text-[11px]"
                                >
                                  <HighlightText text={skill} query={committedQuery} />
                                </span>
                              ))}
                              {profile.skills.length > 3 && (
                                <span className="text-[11px] text-zinc-500 font-mono">
                                  +{profile.skills.length - 3}
                                </span>
                              )}
                            </div>

                            <div className="flex items-center gap-2">
                              <button
                                type="button"
                                onClick={() => setModalProfile(profile)}
                                aria-label={`Open ${profile.name} dossier`}
                                className="inline-flex min-h-11 items-center gap-1 rounded-lg border border-blue-800/60 bg-blue-950/40 px-2.5 py-1.5 text-xs font-semibold text-blue-300 transition-colors hover:border-blue-600/70 hover:bg-blue-900/50 hover:text-blue-100 shrink-0"
                              >
                                Open dossier <ArrowUpRight className="w-3 h-3 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
                              </button>
                            </div>
                          </div>
                        </motion.div>
                      );
                    })}
                  </AnimatePresence>
                </motion.div>
              )
            ) : (
              /* Clean Animated Empty State */
              <motion.div
                initial={{ opacity: 0, scale: 0.97, y: 10 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.97, y: -10 }}
                transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
                className="text-center py-14 px-4 border border-zinc-800/60 rounded-2xl bg-zinc-900/20 space-y-3"
              >
                <div className="w-12 h-12 rounded-2xl bg-zinc-900 border border-zinc-800 flex items-center justify-center text-zinc-500 mx-auto">
                  <Compass className="w-6 h-6 text-zinc-500" />
                </div>
                <div className="space-y-1">
                  <h3 className="text-sm font-semibold text-zinc-200">No close matches found</h3>
                  <p className="text-xs text-zinc-500 max-w-sm mx-auto">
                    {committedQuery.trim()
                      ? <>Nothing in the network matches <span className="text-zinc-300">“{committedQuery.trim()}”</span> yet. Try a broader role, skill, or region.</>
                      : 'No active specialists match the selected filters. Try widening your search.'}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={handleResetAll}
                  className="min-h-11 px-3.5 py-1.5 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-xs text-zinc-200 transition-colors cursor-pointer font-medium"
                >
                  Reset all filters
                </button>
              </motion.div>
            )}
          </div>
        )}
      </main>

      {/* Floating Comparison Action Bar */}
      <ComparisonBar
        compareProfiles={compareProfiles}
        onOpenCompareModal={() => setIsCompareModalOpen(true)}
        onClearCompare={handleClearCompare}
        onRemoveProfile={handleRemoveCompare}
      />

      {/* Candidate Comparison Modal */}
      <Suspense fallback={null}>
      <CandidateCompareModal
        isOpen={isCompareModalOpen}
        onClose={() => setIsCompareModalOpen(false)}
        compareProfiles={compareProfiles}
        allProfiles={allProfiles}
        onRemoveProfile={handleRemoveCompare}
        onAddProfile={(p) => handleToggleCompare(p)}
        onRequestMobilization={(p) => {
          setIsCompareModalOpen(false);
          handleRequestMobilization(p);
        }}
        onSelectProfileDetail={(p) => {
          setIsCompareModalOpen(false);
          setModalProfile(p);
        }}
      />

      {/* Mobilization Inquiry Modal */}
      <MobilizationInquiryModal
        isOpen={isInquiryModalOpen}
        onClose={() => setIsInquiryModalOpen(false)}
        profile={inquiryProfile}
        onShowToast={showToast}
      />

      {/* Dossier Print Preview Modal */}
      {printProfile && (
        <DossierPrintView
          profile={printProfile}
          onClose={() => setPrintProfile(null)}
        />
      )}

      {/* Standalone Detail Modal */}
      {modalProfile && (
        <ProfileDetailModal
          profile={modalProfile}
          onClose={() => setModalProfile(null)}
          isBookmarked={isBookmarked(modalProfile.id)}
          onToggleBookmark={(id) => toggleBookmark(id)}
          onShowToast={showToast}
          isCompared={compareIds.includes(modalProfile.id)}
          onToggleCompare={handleToggleCompare}
          onRequestMobilization={handleRequestMobilization}
          onPrintDossier={handlePrintDossier}
          documents={getDocumentsForProfile(modalProfile.id)}
          onAddDocument={() => void refreshDocuments(modalProfile.id)}
          onRemoveDocument={async (docId) => {
            try {
              await removeDocument(modalProfile.id, docId);
            } catch {
              showToast('Failed to remove document');
            }
          }}
          canManageDocuments={canManageDocuments}
          canDeleteCrew={canManageDocuments && user?.id !== modalProfile.id}
          onDeleteCrew={handleDeleteCrewMember}
        />
      )}

      {/* Shortcuts Guide Modal */}
      <ShortcutsModal
        isOpen={isShortcutsOpen}
        onClose={() => setIsShortcutsOpen(false)}
      />

      {/* Shortlist Exporter & Manager Modal */}
      <ExportShortlistModal
        isOpen={isExportShortlistOpen}
        onClose={() => setIsExportShortlistOpen(false)}
        shortlistedProfiles={shortlistedProfiles}
        onClear={() => {
          clearShortlist();
          showToast('Cleared shortlist');
        }}
        onRemoveProfile={(id) => {
          toggleBookmark(id);
        }}
        onSelectProfile={(p) => {
          setSelectedProfileId(p.id);
          setModalProfile(p);
        }}
      />

      {/* Add Specialist Modal */}
      <AddCrewMemberModal
        isOpen={isAddCrewMemberOpen}
        onClose={() => setIsAddCrewMemberOpen(false)}
        onSuccess={() => {
          showToast('Specialist added successfully');
          refetchProfiles();
        }}
      />
      <FilterModal
        isOpen={isFilterOpen}
        onClose={() => setIsFilterOpen(false)}
        filters={filters}
        onUpdateFilters={setFilters}
        onResetFilters={resetFilters}
        onApplyPreset={(preset) => handleSelectPreset(preset.id)}
        totalFilteredCount={isSearchActive ? results.length : allProfiles.length}
        totalCount={allProfiles.length}
      />
      </Suspense>

      {/* Toast Feedback */}
      <Toast message={toastMessage} />

      {isLoginOpen && (
        <Suspense fallback={<LazySurfaceFallback />}>
        <LoginPage
          isModal
          onCancel={() => setIsLoginOpen(false)}
          onSuccess={() => {
            setAuthSessionKey((k) => k + 1);
            setIsLoginOpen(false);
            void refreshSession();
          }}
        />
        </Suspense>
      )}
    </div>
  );
}
