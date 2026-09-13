/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { lazy, Suspense, useState, useMemo, useEffect, useCallback, useRef, MouseEvent } from 'react';
import { useApolloClient, useMutation } from '@apollo/client';
import { motion, AnimatePresence } from 'motion/react';
import { UserProfile, SortOption } from './types';
import { FILTER_PRESETS } from './data/mockProfiles';
import { useShortlist } from './hooks/useShortlist';
import { useURLSync } from './hooks/useURLSync';
import { formatExperience } from './utils/experience';
import { availabilityLabel } from './utils/profileLabels';
import { useSpecialistDocuments } from './hooks/useSpecialistDocuments';
import { useCrewSummary } from './hooks/useCrewSummary';
import { useTheme } from './hooks/useTheme';
import { useCrewProfiles } from './hooks/useCrewProfiles';
import { useAuth } from './hooks/useAuth';
import { useRequireAuth } from './hooks/useRequireAuth';
import { useKeyboardNavigation } from './hooks/useKeyboardNavigation';
import { useSearchWorkspace } from './hooks/useSearchWorkspace';
import { useSplitPaneResize } from './hooks/useSplitPaneResize';
import { apolloResultHasErrors, buildAuthSessionKey } from './utils/sessionScope';
import { CREW_MEMBER_DETAIL_QUERY, DELETE_CREW_MEMBER } from './lib/queries';
import { backendCrewToProfile, BackendCrew } from './lib/mappers';
import { CrewQueryResult } from './hooks/useCrewQuery';
import { ModernHeroSearch } from './components/ModernHeroSearch';
import { CrewQuerySummary } from './components/CrewQuerySummary';
import { OperationsHome } from './components/operations/OperationsHome';
import { isStaffOrAdmin } from './utils/operationsHome';
import { copyTextToClipboard } from './utils/clipboard';
import { MatchEvidence } from './components/MatchEvidence';
import { ActiveFilterChips } from './components/ActiveFilterChips';
import { SpecialistActionsMenu } from './components/SpecialistActionsMenu';
import { ComparisonBar } from './components/ComparisonBar';
import { HighlightText } from './components/HighlightText';
import { CertificationBadge } from './components/CertificationBadge';
import { Toast } from './components/Toast';
import { IncomingDocumentAlert } from './components/IncomingDocumentAlert';
import { DocumentReviewModal } from './components/DocumentReviewModal';
import { ServiceStatus } from './components/ServiceStatus';
import { DensityIndicator } from './components/DensityIndicator';
import { SkeletonResults } from './components/SkeletonResults';
import { SegmentedControl } from './components/ui';
import {
  MapPin,
  Bookmark,
  LayoutGrid,
  Columns,
  Table,
  Compass,
  ArrowUpRight,
  BadgeCheck,
  Scale,
  AlertTriangle,
  X,
  UserPlus,
  Menu,
  GripVertical,
  Star,
  ArrowLeft,
} from 'lucide-react';
import hydenlyneLogoWhite from './assets/hydenlyne-logo-white.png';
import hydenlyneLogoColour from './assets/hydenlyne-logo-colour.png';

const LoginPage = lazy(() => import('./components/LoginPage').then((module) => ({ default: module.LoginPage })));
const AddCrewMemberModal = lazy(() => import('./components/AddCrewMemberModal').then((module) => ({ default: module.AddCrewMemberModal })));
const CvReviewModal = lazy(() => import('./components/CvReviewModal').then((module) => ({ default: module.CvReviewModal })));
const ManageStaffModal = lazy(() => import('./components/ManageStaffModal').then((module) => ({ default: module.ManageStaffModal })));
const AppMenuDrawer = lazy(() => import('./components/AppMenuDrawer').then((module) => ({ default: module.AppMenuDrawer })));
const FilterModal = lazy(() => import('./components/FilterModal').then((module) => ({ default: module.FilterModal })));
const ProfileDetailModal = lazy(() => import('./components/ProfileDetailModal').then((module) => ({ default: module.ProfileDetailModal })));
const CandidateCompareModal = lazy(() => import('./components/CandidateCompareModal').then((module) => ({ default: module.CandidateCompareModal })));
const MobilizationInquiryModal = lazy(() => import('./components/MobilizationInquiryModal').then((module) => ({ default: module.MobilizationInquiryModal })));
const DossierPrintView = lazy(() => import('./components/DossierPrintView').then((module) => ({ default: module.DossierPrintView })));
const ShortcutsModal = lazy(() => import('./components/ShortcutsModal').then((module) => ({ default: module.ShortcutsModal })));
const ExportShortlistModal = lazy(() => import('./components/ExportShortlistModal').then((module) => ({ default: module.ExportShortlistModal })));
const SpecialistDossierPane = lazy(() => import('./components/SpecialistDossierPane').then((module) => ({ default: module.SpecialistDossierPane })));
const SpecialistTableView = lazy(() => import('./components/SpecialistTableView').then((module) => ({ default: module.SpecialistTableView })));


const DossierFallback = () => (
  <div className="flex h-full min-h-80 items-center justify-center rounded-[14px] bg-surface/40" role="status" aria-live="polite">
    <span className="text-sm text-secondary">Opening dossier…</span>
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
  const { isDark, toggleTheme } = useTheme();
  const { initialized: authInitialized, isAuthenticated, user, logout } = useAuth();
  const authSessionKey = buildAuthSessionKey(user);
  const apolloClient = useApolloClient();
  const canManageDocuments = user?.role === 'admin';
  const canRequestDocuments = user?.role === 'admin' || user?.role === 'staff';
  const canSubmitCv = user?.role === 'admin' || user?.role === 'staff';
  const [deleteCrewMember] = useMutation(DELETE_CREW_MEMBER);
  const [isLoginOpen, setIsLoginOpen] = useState(false);
  const toastVersionRef = useRef(0);

  const [modalProfile, setModalProfile] = useState<UserProfile | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [isShortcutsOpen, setIsShortcutsOpen] = useState(false);
  const [isExportShortlistOpen, setIsExportShortlistOpen] = useState(false);
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isFilterOpen, setIsFilterOpen] = useState(false);
  const [isDocumentReviewOpen, setIsDocumentReviewOpen] = useState(false);
  const [documentReviewVersion, setDocumentReviewVersion] = useState(0);

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
  const [isCvReviewOpen, setIsCvReviewOpen] = useState(false);
  const [isStaffAccessOpen, setIsStaffAccessOpen] = useState(false);

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
    // setQuery/setCommittedQuery come from useSearchWorkspace() below, so
    // referencing them here (before that call) is a TDZ error, not just an
    // exhaustive-deps nit. React guarantees useState setter identity is
    // stable, so omitting them is safe.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [aiQueryData]);

  // Live backend profiles (falls back to MOCK_PROFILES only when demo mode enabled)
  const { profiles: liveProfiles, isLive, demoActive, loading: profilesLoading, error: profilesError, refetch: refetchProfiles, loadMore: loadMoreProfiles, hasMore: profilesHaveMore } = useCrewProfiles({ skip: !isAuthenticated, sessionKey: authSessionKey })
  const allProfiles = liveProfiles

  const requestLogin = useCallback(() => {
    setIsLoginOpen(true);
  }, []);

  const requireAuth = useRequireAuth(isAuthenticated, requestLogin);

  // Shortlist Hook - now works on live + mock unified list
  const {
    shortlistedProfiles,
    toggleBookmark: rawToggleBookmark,
    isBookmarked,
    clearShortlist,
    shortlistCount,
  } = useShortlist(allProfiles, user?.id ?? null)

  // Specialist Documents & Compliance Hook
  const {
    getDocumentsForProfile,
    removeDocument,
    reviewDocument,
    refreshDocuments,
  } = useSpecialistDocuments(isAuthenticated, authSessionKey);

  // AI consultant summary, shown automatically when a profile opens
  // (see backend/docs/cv-ingestion-pipeline.md).
  const {
    fetchSummary,
    getSummaryForProfile,
    isSummaryLoading,
  } = useCrewSummary(isAuthenticated, authSessionKey);

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
    openWorkspace,
    closeWorkspace,
  } = useSearchWorkspace({
    allProfiles,
    isBookmarked,
    aiQueryData,
    aiQueryActive,
    isAuthenticated,
  });

  // Logout cleanup is delayed for the exit animation. If another account
  // logs in during that window, the old cleanup must not touch the new
  // account, but shared workspace state still needs a fresh boundary.
  const lastAuthenticatedSessionKeyRef = useRef<string | null>(null);
  const loggedOutSinceLastSessionRef = useRef(false);
  useEffect(() => {
    if (!user?.id) {
      if (lastAuthenticatedSessionKeyRef.current) loggedOutSinceLastSessionRef.current = true;
      return;
    }

    const accountChanged =
      lastAuthenticatedSessionKeyRef.current !== null &&
      (lastAuthenticatedSessionKeyRef.current !== authSessionKey || loggedOutSinceLastSessionRef.current);
    if (accountChanged) {
      handleResetAll();
      setSelectedProfileId(null);
      setModalProfile(null);
      setCopiedId(null);
      setIsLoginOpen(false);
      setIsShortcutsOpen(false);
      setIsExportShortlistOpen(false);
      setIsFilterOpen(false);
      setCompareIds([]);
      setIsCompareModalOpen(false);
      setInquiryProfile(null);
      setIsInquiryModalOpen(false);
      setIsDocumentReviewOpen(false);
      setPrintProfile(null);
      setAiQueryData(null);
      setAiQueryLoading(false);
      setAiQueryActive(false);
      setShowAISummary(false);
      setIsAddCrewMemberOpen(false);
      setIsCvReviewOpen(false);
      setIsStaffAccessOpen(false);
      setIsFocusMode(false);
      window.history.replaceState(null, '', '/');
    }

    lastAuthenticatedSessionKeyRef.current = authSessionKey;
    loggedOutSinceLastSessionRef.current = false;
  }, [authSessionKey, handleResetAll, setSelectedProfileId, user?.id]);

  const currentSessionKeyRef = useRef(authSessionKey);
  currentSessionKeyRef.current = authSessionKey;
  useEffect(() => {
    currentSessionKeyRef.current = authSessionKey;
  }, [authSessionKey]);

  const handleOperationsSearch = useCallback((nextQuery: string) => {
    const trimmed = nextQuery.trim()
    openWorkspace()
    setQuery(nextQuery)
    setCommittedQuery(trimmed)
    requestAnimationFrame(() => {
      const input = document.querySelector<HTMLTextAreaElement>('textarea[aria-label="Search contractors"]')
      if (input) input.focus()
    })
  }, [openWorkspace, setCommittedQuery, setQuery])

  const handleOpenDocumentReview = useCallback(() => {
    setIsDocumentReviewOpen(true)
  }, [])

  const handleDocumentReviewResolved = useCallback(() => {
    setDocumentReviewVersion((currentVersion) => currentVersion + 1)
    if (activeSelectedProfile) {
      void refreshDocuments(activeSelectedProfile.id).catch(() => {})
    }
    if (modalProfile) {
      void refreshDocuments(modalProfile.id).catch(() => {})
    }
  }, [activeSelectedProfile, modalProfile, refreshDocuments])

  // Focused Workspace mode for working comfortably on a contractor
  const [isFocusMode, setIsFocusMode] = useState(false);

  const {
    splitRatio,
    minRatio: MIN_SPLIT_RATIO,
    maxRatio: MAX_SPLIT_RATIO,
    isDraggingSplitter,
    splitContainerRef,
    handleSplitterPointerDown,
    handleSplitterDoubleClick,
    handleSplitterKeyDown,
  } = useSplitPaneResize();

  const showToast = useCallback((msg: string) => {
    const toastVersion = ++toastVersionRef.current;
    setToastMessage(msg);
    setTimeout(() => {
      if (toastVersion === toastVersionRef.current) setToastMessage(null);
    }, 2200);
  }, []);

  const openIncomingDocumentContractor = useCallback(async (crewId: string) => {
    const requestSessionKey = authSessionKey;
    if (!requestSessionKey) return;
    try {
      const result = await apolloClient.query<{ crewMember: BackendCrew | null }>({
        query: CREW_MEMBER_DETAIL_QUERY,
        variables: { id: crewId },
        fetchPolicy: 'network-only',
      });
      if (apolloResultHasErrors(result)) throw new Error('Contractor dossier request failed');
      if (currentSessionKeyRef.current !== requestSessionKey || !result.data.crewMember) return;
      setModalProfile(backendCrewToProfile(result.data.crewMember));
      setSelectedProfileId(crewId);
      setShowSavedOnly(false);
    } catch {
      if (currentSessionKeyRef.current === requestSessionKey) {
        showToast('Could not open this contractor dossier');
      }
    }
  }, [apolloClient, authSessionKey, setSelectedProfileId, setShowSavedOnly, showToast]);

  const handleToggleTheme = useCallback(() => {
    toggleTheme();
    showToast(isDark ? 'Light theme enabled' : 'Dark theme enabled');
  }, [toggleTheme, isDark, showToast]);

  const handleDeleteCrewMember = useCallback(async (profile: UserProfile) => {
    const requestSessionKey = authSessionKey;
    if (!requestSessionKey || currentSessionKeyRef.current !== requestSessionKey) return;
    const result = await deleteCrewMember({ variables: { id: profile.id } });
    if (apolloResultHasErrors(result)) throw new Error('Contractor deletion returned errors');
    const { data } = result;
    if (currentSessionKeyRef.current !== requestSessionKey) return;
    if (!data?.deleteCrewMember) {
      throw new Error(`${profile.name} could not be deleted`);
    }
    let refreshFailed = false;
    try {
      await refetchProfiles();
    } catch {
      refreshFailed = true;
    }
    if (currentSessionKeyRef.current !== requestSessionKey) return;
    if (isBookmarked(profile.id)) rawToggleBookmark(profile.id);
    setCompareIds((ids) => ids.filter((id) => id !== profile.id));
    setSelectedProfileId((currentSelectedId) => (
      currentSelectedId === profile.id ? null : currentSelectedId
    ));
    setModalProfile((currentProfile) => (
      currentProfile?.id === profile.id ? null : currentProfile
    ));
    showToast(
      refreshFailed
        ? `${profile.name} was deleted — roster refresh unavailable`
        : `${profile.name} was deleted`,
    );
  }, [
    authSessionKey,
    deleteCrewMember,
    isBookmarked,
    rawToggleBookmark,
    refetchProfiles,
    showToast,
    setSelectedProfileId,
  ]);

  const toggleBookmark = useCallback((id: string, e?: MouseEvent) => {
    if (e) e.stopPropagation();
    if (!requireAuth()) return;
    const profile = allProfiles.find((p) => p.id === id);
    const name = profile ? profile.name.split(' ')[0] : 'Contractor';
    const currentlyBookmarked = isBookmarked(id);
    rawToggleBookmark(id);
    showToast(currentlyBookmarked ? `Removed ${name} from shortlist` : `Saved ${name} to shortlist`);
  }, [requireAuth, isBookmarked, rawToggleBookmark, showToast, allProfiles]);

  const handleCopyEmail = useCallback(async (profile: UserProfile, e?: MouseEvent) => {
    e?.stopPropagation();
    if (!requireAuth()) return;
    if (await copyTextToClipboard(profile.email)) {
      setCopiedId(profile.id);
      showToast(`Copied ${profile.email}`);
      setTimeout(() => {
        setCopiedId((currentCopiedId) => (
          currentCopiedId === profile.id ? null : currentCopiedId
        ));
      }, 1800);
    } else {
      showToast('Could not copy the email address. Please try again.');
    }
  }, [requireAuth, showToast]);

  // Comparison toggle handler
  const handleToggleCompare = useCallback((profile: UserProfile) => {
    if (!requireAuth()) return;
    setCompareIds((prev) => {
      if (prev.includes(profile.id)) {
        return prev.filter((id) => id !== profile.id);
      }
      if (prev.length >= 4) {
        showToast('You can compare up to 4 contractors at once');
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
    if (!isStaffOrAdmin(user?.role)) {
      showToast('Mobilization requests are available to operations staff.');
      return;
    }
    setInquiryProfile(profile);
    setIsInquiryModalOpen(true);
  }, [requireAuth, showToast, user?.role]);

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
      // No auth check needed here: isSearchActive (useSearchWorkspace.ts) is
      // itself authentication-gated, so committing a query while logged out
      // never renders result chrome — see docs/ARCHITECTURE.md's Security
      // boundaries. Calling requestLogin() here as well used to race the
      // async session check on mount, popping the sign-in dialog open for
      // already-authenticated deep-linked visits and leaving it stuck open.
    }, [setCommittedQuery, setQuery]),
    onSyncViewMode: useCallback((mode: 'split' | 'cards' | 'table') => {
      setViewMode(mode === 'cards' ? 'grid' : mode);
    }, [setViewMode]),
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
    viewMode,
    setViewMode,
    onToggleCompare: handleToggleCompare,
  });

  const handleLogout = useCallback(async () => {
    const exitingSessionKey = authSessionKey;
    setIsMenuOpen(false);
    // Close every authenticated overlay before authentication state changes;
    // the public shell must not retain private dossier or administration
    // surfaces during the logout transition.
    setModalProfile(null);
    setPrintProfile(null);
    setIsShortcutsOpen(false);
    setIsExportShortlistOpen(false);
    setIsFilterOpen(false);
    setIsCompareModalOpen(false);
    setInquiryProfile(null);
    setIsInquiryModalOpen(false);
    setIsDocumentReviewOpen(false);
    setIsCvReviewOpen(false);
    setIsStaffAccessOpen(false);
    setIsAddCrewMemberOpen(false);
    setIsFocusMode(false);
    let serverLogoutFailed = false;
    try {
      await logout();
    } catch {
      // Local credentials and private UI are still cleared; tell the user
      // that server-side revocation could not be confirmed.
      serverLogoutFailed = true;
    }
    // Preserve the exiting workspace snapshot for the calm exit animation
    // (header/workspace fade y -6 / 0.2) before clearing filters, selection,
    // and URL state — otherwise the exiting branch would render empty.
    window.setTimeout(() => {
      // A new login may complete during the exit animation. The old logout
      // cleanup must never clear that account's workspace or URL state.
      if (currentSessionKeyRef.current !== null && currentSessionKeyRef.current !== exitingSessionKey) return;
      handleResetAll();
      setViewMode('split');
      setSelectedProfileId(null);
      clearShortlist();
      setModalProfile(null);
      setCopiedId(null);
      setIsLoginOpen(false);
      setIsShortcutsOpen(false);
      setIsExportShortlistOpen(false);
      setIsFilterOpen(false);
      setCompareIds([]);
      setIsCompareModalOpen(false);
      setInquiryProfile(null);
      setIsInquiryModalOpen(false);
      setIsDocumentReviewOpen(false);
      setPrintProfile(null);
      setAiQueryData(null);
      setAiQueryLoading(false);
      setAiQueryActive(false);
      setShowAISummary(false);
      setIsAddCrewMemberOpen(false);
      setIsCvReviewOpen(false);
      setIsStaffAccessOpen(false);
      setIsFocusMode(false);
      window.history.replaceState(null, '', '/');
      showToast(
        serverLogoutFailed
          ? 'Signed out locally — server logout could not be confirmed'
          : 'Signed out — workspace cleared',
      );
    }, 220);
    // Setters are stable; handleResetAll/clearShortlist/showToast capture latest closures.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authSessionKey, logout, handleResetAll, clearShortlist, showToast]);

  useEffect(() => {
    const handleSessionExpired = () => {
      setIsMenuOpen(false);
      handleResetAll();
      setViewMode('split');
      setSelectedProfileId(null);
      clearShortlist();
      setModalProfile(null);
      setCopiedId(null);
      setIsLoginOpen(false);
      setIsShortcutsOpen(false);
      setIsExportShortlistOpen(false);
      setIsFilterOpen(false);
      setCompareIds([]);
      setIsCompareModalOpen(false);
      setInquiryProfile(null);
      setIsInquiryModalOpen(false);
      setIsDocumentReviewOpen(false);
      setPrintProfile(null);
      setAiQueryData(null);
      setAiQueryLoading(false);
      setAiQueryActive(false);
      setShowAISummary(false);
      setIsAddCrewMemberOpen(false);
      setIsCvReviewOpen(false);
      setIsStaffAccessOpen(false);
      setIsFocusMode(false);
      window.history.replaceState(null, '', '/');
    };
    window.addEventListener('hydenlyne:session-expired', handleSessionExpired);
    return () => window.removeEventListener('hydenlyne:session-expired', handleSessionExpired);
  }, [clearShortlist, handleResetAll, setSelectedProfileId, setViewMode]);

  const shellKey = !authInitialized ? 'gate' : !isAuthenticated ? 'public' : 'workspace';

  return (
    <div className="relative flex min-h-screen flex-col overflow-x-hidden bg-canvas font-sans text-primary antialiased selection:bg-action selection:text-on-action">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[100] focus:rounded-lg focus:bg-action focus:px-3 focus:py-2 focus:text-xs focus:font-semibold focus:text-on-action"
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
      <header className="w-full border-b border-border-subtle/60 bg-canvas/80 backdrop-blur-xl sticky top-0 z-30">
        <div className="mx-auto flex h-16 max-w-7xl min-w-0 items-center justify-between gap-5 px-4 sm:px-6">
          {/* Logo / Brand Name */}
          <button
            type="button"
            onClick={handleResetAll}
            className="flex items-center gap-2.5 cursor-pointer select-none group focus:outline-none focus-visible:ring-2 focus-visible:ring-focus rounded-lg"
            aria-label="Go to Hydenlyne home"
          >
            <img
              src={isDark ? hydenlyneLogoWhite : hydenlyneLogoColour}
              alt="Hydenlyne"
              width={104}
              height={28}
              className="w-[104px] h-auto"
            />
          </button>

          {/* Right Nav */}
          <div className="flex items-center gap-2 shrink-0">
            {!authInitialized ? (
              <div className="h-8 w-20 animate-pulse rounded-lg bg-surface-raised" aria-hidden="true" />
            ) : (
              <>
                {isAuthenticated && canSubmitCv && (
                  <span className="hidden max-w-[180px] truncate text-xs text-secondary sm:inline" title={user?.email}>
                    {user?.email}
                  </span>
                )}
                {!isAuthenticated && (
                  <button type="button" onClick={requestLogin} className="inline-flex min-h-11 items-center rounded-[10px] bg-action px-3 py-1.5 text-xs font-semibold text-on-action transition-colors hover:bg-action-hover cursor-pointer">
                    Sign in
                  </button>
                )}
              </>
            )}
            {isAuthenticated && canSubmitCv && (
              <button type="button" onClick={() => setIsAddCrewMemberOpen(true)} className="inline-flex min-h-11 items-center gap-1.5 rounded-[10px] border border-border-strong bg-surface px-3 py-1.5 text-xs font-semibold text-secondary transition-colors hover:border-border-strong hover:bg-surface-raised hover:text-primary cursor-pointer" aria-label="Add contractor" title="Add a contractor to the network">
                <UserPlus className="h-3.5 w-3.5" aria-hidden="true" />
                <span className="hidden sm:inline">Add contractor</span>
              </button>
            )}
            {isAuthenticated && canSubmitCv && (
              <IncomingDocumentAlert
                key={authSessionKey ?? 'authenticated-session'}
                sessionKey={authSessionKey}
                onOpenContractor={openIncomingDocumentContractor}
                onShowToast={showToast}
                onReviewResolved={() => {
                  handleDocumentReviewResolved()
                }}
              />
            )}
            {user?.role === 'admin' && <ServiceStatus />}
            {isAuthenticated && (
              <button type="button" onClick={() => setShowSavedOnly(!showSavedOnly)} className={`inline-flex min-h-11 items-center gap-1.5 rounded-[10px] border px-3 py-1.5 text-xs font-semibold transition-colors cursor-pointer ${showSavedOnly ? 'border-border-strong bg-action text-on-action' : 'border-border-subtle bg-surface text-secondary hover:border-border-strong hover:bg-surface-raised hover:text-primary'}`} aria-pressed={showSavedOnly} title={showSavedOnly ? 'Show all contractors' : 'View shortlist'}>
                <Bookmark className={`h-3.5 w-3.5 ${showSavedOnly ? 'fill-on-action' : ''}`} aria-hidden="true" />
                <span className="hidden sm:inline">Shortlist</span>
                <span className="font-mono text-xs">({shortlistCount})</span>
              </button>
            )}
            <button
              type="button"
              onClick={() => setIsMenuOpen(true)}
              className="inline-flex min-h-11 items-center justify-center gap-1.5 rounded-[10px] border border-border-subtle bg-surface px-2.5 text-secondary transition-colors hover:border-border-strong hover:bg-surface-raised hover:text-primary cursor-pointer focus-visible:ring-2 focus-visible:ring-focus"
              aria-label="Open workspace menu"
              aria-controls="workspace-menu"
              aria-expanded={isMenuOpen}
            >
              <Menu className="h-4 w-4" aria-hidden="true" />
              <span className="text-xs font-semibold">Menu</span>
            </button>
          </div>
        </div>
      </header>

      <Suspense fallback={null}>
      <AppMenuDrawer
        isOpen={isMenuOpen}
        onClose={() => setIsMenuOpen(false)}
        isAuthenticated={isAuthenticated}
        isDark={isDark}
        onToggleTheme={handleToggleTheme}
        onOpenShortcuts={() => setIsShortcutsOpen(true)}
        onOpenAddSpecialist={() => setIsAddCrewMemberOpen(true)}
        onOpenCvReviews={() => setIsCvReviewOpen(true)}
        canSubmitCv={canSubmitCv}
        isAdmin={user?.role === 'admin'}
        onOpenStaffAccess={() => setIsStaffAccessOpen(true)}
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
      </Suspense>

      {/* Main Container */}
      <main id="main-content" className="mx-auto flex w-full max-w-7xl flex-1 flex-col justify-start px-4 sm:px-6" aria-label="Contractor network workspace">
        {/* Live-data required banner (prod, no demo fallback) */}
        {isAuthenticated && !profilesLoading && !isLive && !demoActive && (
          <div className="mt-4 rounded-[14px] border border-danger-border/60 bg-danger-soft/30 px-4 py-3 flex items-start gap-3" role="alert">
            <AlertTriangle className="w-5 h-5 text-danger shrink-0 mt-0.5" />
            <div className="flex-1">
              <h2 className="text-sm font-semibold text-danger">Live contractor data unavailable</h2>
              <p className="text-xs text-danger/80 mt-0.5">
                The backend returned no data{profilesError ? ` (${profilesError})` : ''}. Demo profiles
                are disabled in this build — sign in and confirm the API is reachable.
              </p>
            </div>
            <button
              type="button"
              onClick={refetchProfiles}
              className="shrink-0 min-h-11 px-3 py-1.5 rounded-lg bg-danger-soft/60 border border-danger-border/60 text-danger hover:bg-danger-soft/60 text-xs font-medium transition-colors cursor-pointer"
            >
              Retry
            </button>
          </div>
        )}
        <AnimatePresence mode="wait" initial={false}>
          {shellKey === 'gate' && (
            <motion.div
              key="gate"
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
              className="flex flex-1 flex-col items-center justify-center py-12"
            >
              <h1 className="mx-auto max-w-xl text-center text-3xl sm:text-4xl lg:text-[2.65rem] lg:leading-[1.12] font-semibold tracking-[-0.03em] text-primary">
                Find the right contractor for the next campaign.
              </h1>
              <p className="mt-3 max-w-md text-center text-sm leading-relaxed text-secondary">
                Search Hydenlyne&apos;s private specialist network by discipline, certification, region, and availability.
              </p>
              <div className="mt-8 flex items-center gap-2 text-xs text-muted font-mono" role="status" aria-live="polite">
                <span className="h-2 w-2 rounded-full bg-action animate-pulse" aria-hidden="true" />
                Loading session…
              </div>
              <p className="mt-6 text-center text-xs text-muted">Private workforce network. Access is protected.</p>
            </motion.div>
          )}
          {shellKey === 'public' && (
            <motion.div
              key="public"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.20, ease: [0.22, 1, 0.36, 1] }}
              className="py-2"
            >
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
                sessionKey={authSessionKey}
                onAIResults={handleAIResults}
                onOpenFilters={() => setIsFilterOpen(true)}
              />
            </motion.div>
          )}
          {shellKey === 'workspace' && (
            <motion.div
              key="workspace"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.20, ease: [0.22, 1, 0.36, 1] }}
            >
              <OperationsHome
                key={authSessionKey ?? 'workspace-session'}
                fullName={user?.fullName}
                profiles={allProfiles}
                profilesLoading={profilesLoading}
                profilesError={profilesError}
                onSearch={handleOperationsSearch}
                onOpenDocumentReview={handleOpenDocumentReview}
                documentReviewVersion={documentReviewVersion}
                isStaff={isStaffOrAdmin(user?.role)}
                isAdmin={user?.role === 'admin'}
                sessionKey={authSessionKey}
                onShowToast={showToast}
                searchControl={
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
                    sessionKey={authSessionKey}
                    onAIResults={handleAIResults}
                    onOpenFilters={() => setIsFilterOpen(true)}
                    variant="compact"
                  />
                }
              >
                {/* Results Header */}
                <div className="ui-panel mb-3 flex flex-col gap-3 px-3 py-2.5 text-xs text-secondary sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex items-center gap-2 flex-wrap" aria-live="polite">
                    {isAuthenticated && isSearchActive && (
                      <button
                        type="button"
                        onClick={() => {
                          closeWorkspace();
                          setQuery('');
                          setCommittedQuery('');
                          resetFilters();
                        }}
                        className="badge-neutral inline-flex min-h-11 items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs hover:brightness-95 cursor-pointer font-medium"
                        aria-label="Return to operations overview"
                      >
                        <ArrowLeft className="h-3 w-3 opacity-80" aria-hidden="true" />
                        <span>Operations</span>
                      </button>
                    )}
                    <span>
                      {isSearchActive ? 'Found' : 'Showing'} <strong className="text-primary font-semibold">{results.length}</strong> {results.length === 1 ? 'contractor' : 'contractors'}
                    </span>
                    {isResultsUpdating && (
                      <span className="inline-flex items-center gap-1.5 text-muted">
                        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" aria-hidden="true" />
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

                  <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto sm:justify-end">
                    <SegmentedControl
                      label="Result view"
                      value={viewMode}
                      onChange={setViewMode}
                      className="hidden md:inline-flex"
                      options={[
                        { value: 'split', label: 'Split', icon: <Columns className="h-3.5 w-3.5" aria-hidden="true" /> },
                        { value: 'grid', label: 'Cards', icon: <LayoutGrid className="h-3.5 w-3.5" aria-hidden="true" /> },
                        { value: 'table', label: 'Matrix', icon: <Table className="h-3.5 w-3.5" aria-hidden="true" /> },
                      ]}
                    />
                    {compareIds.length > 0 && (
                      <button type="button" onClick={() => setIsCompareModalOpen(true)} className="inline-flex min-h-11 items-center gap-1.5 rounded-[10px] border border-border-strong bg-surface px-3 font-semibold text-primary transition-colors hover:bg-surface-raised">
                        <Scale className="h-3.5 w-3.5" aria-hidden="true" />
                        Compare {compareIds.length}
                      </button>
                    )}
                    {/* Sort Dropdown */}
                    <select
                      value={sortBy}
                      onChange={(e) => setSortBy(e.target.value as SortOption)}
                      aria-label="Sort contractors"
                      className="ui-control min-w-0 flex-1 px-2.5 text-xs font-medium text-secondary sm:flex-none"
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
                        className="min-h-11 shrink-0 rounded-lg px-2 text-xs font-medium text-secondary transition-colors hover:bg-surface-raised hover:text-primary"
                      >
                        Clear all
                      </button>
                    )}
                  </div>
                </div>

                {activeFilterCount > 0 && (
                  <ActiveFilterChips
                    filters={filters}
                    onUpdateFilters={setFilters}
                    onResetFilters={resetFilters}
                  />
                )}

                {/* Results Area */}
                <div className="pb-16" role="region" aria-busy={profilesLoading || aiQueryLoading} aria-label="Specialist database results">
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
              <AnimatePresence mode="wait">
                {viewMode === 'split' ? (
                  isFocusMode ? (
                    /* Focused Contractor Workspace (Enlarged & Centered for comfortable working) */
                    <motion.div
                      key="focus-workspace"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      transition={{ duration: 0.18 }}
                      className="fixed inset-0 z-40 flex flex-col overflow-hidden bg-canvas/95 px-2 py-3 sm:p-4 backdrop-blur-sm"
                    >
                      {/* Crew Selector Navigation Strip */}
                      <div className="w-full max-w-6xl mx-auto flex items-center justify-between bg-surface/90 border border-border-subtle p-2.5 sm:p-3 rounded-[14px] backdrop-blur-md shadow-xl gap-3 shrink-0">
                        <div className="flex items-center gap-2 overflow-x-auto py-1 scrollbar-none max-w-2xl">
                          {results.map((profile, idx) => {
                            const isSel = (activeSelectedProfile?.id || selectedProfileId) === profile.id;
                            return (
                              <button
                                key={profile.id}
                                id={`specialist-result-${profile.id}`}
                                type="button"
                                onClick={() => setSelectedProfileId(profile.id)}
                                className={`flex items-center gap-2.5 px-3.5 py-1.5 rounded-[10px] text-xs font-medium shrink-0 transition-all cursor-pointer ${
                                  isSel
                                    ? 'bg-surface-raised text-primary border border-border-strong shadow-md font-semibold'
                                    : 'bg-canvas/60 border border-border-subtle text-secondary hover:bg-surface-raised/80 hover:text-primary'
                                }`}
                              >
                                <img
                                  src={profile.avatar}
                                  alt={profile.name}
                                  referrerPolicy="no-referrer"
                                  className="w-5 h-5 rounded-full object-cover border border-border-strong"
                                />
                                <span className="truncate max-w-[110px]">{profile.name}</span>
                                <span className="font-mono text-xs opacity-60">#{idx + 1}</span>
                              </button>
                            );
                          })}
                        </div>

                        <div className="flex items-center gap-2 shrink-0">
                          <button
                            type="button"
                            onClick={() => setIsFocusMode(false)}
                            className="px-3.5 py-1.5 rounded-[10px] bg-surface-raised hover:bg-surface-selected border border-border-strong text-primary text-xs font-medium transition-colors cursor-pointer flex items-center gap-1.5 shadow-xs"
                            title="Exit Focus Mode (F / Esc)"
                          >
                            <span>Exit Focus</span>
                            <span className="font-mono text-xs text-secondary">Esc</span>
                          </button>
                        </div>
                      </div>

                      {/* Centered Enlarged Contractor dossier Card */}
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
                            sessionKey={authSessionKey}
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
                            onAddDocument={() => activeSelectedProfile
                              ? refreshDocuments(activeSelectedProfile.id)
                              : undefined}
                            onRemoveDocument={async (docId) => {
                              if (activeSelectedProfile) {
                                return removeDocument(activeSelectedProfile.id, docId);
                              }
                              return undefined;
                            }}
                            onReviewDocument={async (docId, action) => {
                              if (activeSelectedProfile) {
                                return reviewDocument(activeSelectedProfile.id, docId, action);
                              }
                              return undefined;
                            }}
                            canManageDocuments={canManageDocuments}
                            canRequestDocuments={canRequestDocuments}
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
                    </motion.div>
                  ) : (
                    /* Standard Split-Pane Operations Command */
                    <motion.div
                      key="split-layout"
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -6 }}
                      transition={{ duration: 0.18, ease: 'easeOut' }}
                      ref={splitContainerRef}
                      className="scan-workspace flex flex-col md:flex-row items-stretch min-h-0 md:h-[calc(100vh-145px)] md:min-h-[660px] py-2 sm:py-3"
                    >
                      {/* Left Column: Animated List */}
                      <section
                        aria-label="Contractor search results"
                        style={{ width: `${splitRatio}%` }}
                        className="w-full md:w-auto min-h-0 h-full overflow-y-auto pr-1 scan-scroll-panel space-y-2 shrink-0 max-w-full"
                      >
                        <div className="sticky top-0 z-10 flex items-center justify-between gap-3 bg-canvas/95 px-1 pb-2 pt-1 backdrop-blur-sm">
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-semibold uppercase tracking-wider text-secondary">Results</span>
                            <span className="hidden sm:inline-flex items-center gap-1 font-mono text-xs text-muted">
                              <kbd className="px-1 py-0.2 rounded bg-surface border border-border-subtle text-secondary font-mono text-xs">J</kbd>
                              <kbd className="px-1 py-0.2 rounded bg-surface border border-border-subtle text-secondary font-mono text-xs">K</kbd>
                              <span>to navigate</span>
                            </span>
                          </div>
                          <span className="font-mono text-xs text-muted">Select to view dossier</span>
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
                                initial={{ opacity: 0, y: 14 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, scale: 0.95 }}
                                transition={{
                                  duration: 0.22,
                                  delay: Math.min(index * 0.02, 0.18),
                                  ease: [0.16, 1, 0.3, 1],
                                }}
                                key={profile.id}
                                className={`group relative p-3.5 rounded-[14px] border transition-all duration-200 cursor-pointer flex items-center justify-between gap-3 ${
                                  isSelected
                                    ? 'bg-surface border-border-strong shadow-md ring-1 ring-border-strong'
                                    : 'bg-surface/30 hover:bg-surface/80 border-border-subtle/60 hover:border-border-subtle'
                                }`}
                              >
                                {/* Left active selection accent indicator bar */}
                                <div
                                  className={`absolute left-0 top-3.5 bottom-3.5 w-1 rounded-r-full transition-all duration-200 ${
                                    isSelected ? 'bg-primary opacity-100' : 'bg-transparent opacity-0'
                                  }`}
                                  aria-hidden="true"
                                />

                                <button
                                  type="button"
                                  id={`specialist-result-${profile.id}`}
                                  onClick={() => {
                                    setSelectedProfileId(profile.id);
                                    if (window.matchMedia('(max-width: 767px)').matches) setModalProfile(profile);
                                  }}
                                  className="flex items-start gap-3.5 min-w-0 flex-1 text-left cursor-pointer pl-1 focus:outline-none focus-visible:ring-2 focus-visible:ring-focus rounded-lg"
                                  aria-label={`View ${profile.name} dossier, ${profile.title}`}
                                  aria-current={isSelected ? 'true' : undefined}
                                >
                                  <div className="relative shrink-0 mt-0.5">
                                    <img
                                      src={profile.avatar}
                                      alt={profile.name}
                                      referrerPolicy="no-referrer"
                                      className="w-12 h-12 rounded-xl object-cover border border-border-subtle shadow-xs group-hover:border-border-strong transition-colors"
                                    />
                                    {isAvailableNow && (
                                      <span
                                        className="absolute -bottom-1 -right-1 w-3 h-3 rounded-full bg-positive border-2 border-surface shadow-xs"
                                        title="Available immediately"
                                      />
                                    )}
                                  </div>

                                  <div className="min-w-0 flex-1 space-y-1">
                                    {/* Row 1: Name, Badges & Rates */}
                                    <div className="flex items-baseline justify-between gap-2">
                                      <div className="flex items-center gap-1.5 min-w-0">
                                        <h3 className="font-semibold text-sm text-primary group-hover:text-primary transition-colors truncate">
                                          <HighlightText text={profile.name} query={committedQuery} />
                                        </h3>
                                        {profile.isHighlyRecommended && (
                                          <span className="badge-accent shrink-0 px-1.5 py-0.2 rounded text-xs font-semibold">
                                            Top Fit
                                          </span>
                                        )}
                                      </div>
                                      <span className="font-mono font-bold text-xs text-primary shrink-0">
                                        {profile.dayRate != null ? `£${profile.dayRate}/d` : 'Rate on req'}
                                      </span>
                                    </div>

                                    {/* Row 2: Headline Role */}
                                    <p className="text-xs text-secondary truncate font-medium">
                                      <HighlightText text={profile.title} query={committedQuery} />
                                    </p>

                                    {/* Row 3: Availability & Rating */}
                                    <div className="flex items-center gap-2 text-xs">
                                      <span className={`inline-flex items-center gap-1 font-medium ${isAvailableNow ? 'text-positive' : 'text-secondary'}`}>
                                        <span className={`w-1.5 h-1.5 rounded-full ${isAvailableNow ? 'bg-positive' : 'bg-surface-selected'}`} />
                                        <span className="truncate">{availabilityLabel(profile.availability).replace('Available ', '')}</span>
                                      </span>
                                      <span>·</span>
                                      <span className="text-secondary flex items-center gap-0.5 font-mono">
                                        <Star className="w-3 h-3 text-warning fill-warning" />
                                        <span>{profile.rating != null ? profile.rating : '—'}</span>
                                      </span>
                                      <span>·</span>
                                      <span className="text-secondary truncate">{profile.department}</span>
                                    </div>

                                    {/* Row 4: Clean Metadata Strip (Location & Experience) */}
                                    <div className="flex items-center gap-2 text-xs text-muted">
                                      <span className="truncate text-secondary">{profile.location.split(',')[0]}</span>
                                      <span>·</span>
                                      <span className="font-mono text-secondary shrink-0">{formatExperience(profile.yearsOfExperience)}{profile.yearsOfExperience == null ? '' : 'y exp'}</span>
                                      {profile.skills.length > 0 && (
                                        <>
                                          <span>·</span>
                                          <span className="truncate text-secondary">
                                            {profile.skills.slice(0, 2).join(', ')}
                                            {profile.skills.length > 2 ? ` +${profile.skills.length - 2}` : ''}
                                          </span>
                                        </>
                                      )}
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
                                </button>

                                {/* Secondary actions stay available without competing with dossier selection. */}
                                <div className="flex items-center gap-1 shrink-0 self-start mt-0.5" onClick={(event) => event.stopPropagation()}>
                                  <button
                                    type="button"
                                    onClick={() => handleToggleCompare(profile)}
                                    aria-label={isCompared ? `Remove ${profile.name} from comparison` : `Add ${profile.name} to comparison`}
                                    title={isCompared ? 'In comparison' : 'Compare'}
                                    className={`inline-flex min-h-11 min-w-11 items-center justify-center rounded-[10px] transition-colors cursor-pointer ${
                                      isCompared
                                        ? 'text-primary bg-surface-raised border border-border-strong shadow-xs ring-1 ring-border-strong/40'
                                        : 'text-muted hover:text-primary hover:bg-surface-raised/70'
                                    }`}
                                  >
                                    <Scale
                                      className={`h-4 w-4 transition-transform active:scale-90 ${
                                        isCompared ? 'stroke-[2.5]' : ''
                                      }`}
                                      aria-hidden="true"
                                    />
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => toggleBookmark(profile.id)}
                                    aria-label={isProfileBookmarked ? `Remove ${profile.name} from shortlist` : `Save ${profile.name} to shortlist`}
                                    title={isProfileBookmarked ? 'Shortlisted' : 'Save to shortlist'}
                                    className={`inline-flex min-h-11 min-w-11 items-center justify-center rounded-[10px] transition-colors cursor-pointer ${
                                      isProfileBookmarked
                                        ? 'text-action bg-surface-raised border border-border-strong/60 shadow-xs'
                                        : 'text-muted hover:text-primary hover:bg-surface-raised/70'
                                    }`}
                                  >
                                    <Bookmark
                                      className={`h-4 w-4 transition-transform active:scale-90 ${
                                        isProfileBookmarked ? 'fill-current' : ''
                                      }`}
                                      aria-hidden="true"
                                    />
                                  </button>
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

                      {/* Desktop Split-Pane Draggable Resizer Gutter */}
                      <div
                        role="separator"
                        tabIndex={0}
                        aria-orientation="vertical"
                        aria-label="Resize results and dossier panes. Use arrow keys to adjust, double click to cycle presets."
                        aria-valuenow={Math.round(splitRatio)}
                        aria-valuemin={MIN_SPLIT_RATIO}
                        aria-valuemax={MAX_SPLIT_RATIO}
                        onPointerDown={handleSplitterPointerDown}
                        onDoubleClick={handleSplitterDoubleClick}
                        onKeyDown={handleSplitterKeyDown}
                        title="Drag to resize panes · Double-click to cycle presets (35% / 50% / 28%)"
                        className={`hidden md:flex items-center justify-center relative select-none cursor-col-resize w-3.5 -mx-1 shrink-0 z-20 transition-colors group focus:outline-none focus-visible:ring-2 focus-visible:ring-focus rounded-full ${
                          isDraggingSplitter ? 'cursor-col-resize' : ''
                        }`}
                      >
                        {/* Vertical line indicator */}
                        <div
                          className={`w-0.5 h-full transition-colors duration-150 rounded-full ${
                            isDraggingSplitter
                              ? 'bg-primary'
                              : 'bg-border-subtle group-hover:bg-border-strong group-focus-visible:bg-primary'
                          }`}
                        />
                        {/* Subtle centered grip pills */}
                        <div
                          className={`absolute top-1/2 -translate-y-1/2 w-3 h-8 rounded-full border flex items-center justify-center transition-all duration-150 shadow-xs ${
                            isDraggingSplitter
                              ? 'bg-surface-raised border-border-strong text-primary scale-110'
                              : 'bg-surface border-border-subtle text-muted group-hover:border-border-strong group-hover:text-secondary'
                          }`}
                        >
                          <GripVertical className="w-2.5 h-2.5" />
                        </div>
                      </div>

                      {/* Right Column: Live Contractor dossier */}
                      <div className="hidden md:block flex-1 min-w-0 pl-1 min-h-0 h-full overflow-hidden md:sticky md:top-20">
                        <div className="mb-2 flex items-center justify-between px-1 md:hidden">
                          <span className="text-xs font-semibold uppercase tracking-wider text-secondary">Selected dossier</span>
                          <span className="text-xs text-muted">Scroll for details</span>
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
                              sessionKey={authSessionKey}
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
                              onAddDocument={() => activeSelectedProfile
                                ? refreshDocuments(activeSelectedProfile.id)
                                : undefined}
                              onRemoveDocument={async (docId) => {
                                if (activeSelectedProfile) {
                                  try {
                                    return await removeDocument(activeSelectedProfile.id, docId);
                                  } catch {
                                    showToast('Failed to remove document');
                                  }
                                }
                                return undefined;
                              }}
                              onReviewDocument={async (docId, action) => {
                                if (activeSelectedProfile) {
                                  return reviewDocument(activeSelectedProfile.id, docId, action);
                                }
                                return undefined;
                              }}
                              canManageDocuments={canManageDocuments}
                              canRequestDocuments={canRequestDocuments}
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
                    </motion.div>
                  )
                ) : viewMode === 'table' ? (
                  /* High-Density Spreadsheet Matrix */
                  <motion.div
                    key="table-layout"
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -6 }}
                    transition={{ duration: 0.18, ease: 'easeOut' }}
                  >
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
                  </motion.div>
                ) : (
                  /* Visual Grid Cards View with Motion */
                  <motion.div
                    key="grid-layout"
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -6 }}
                    transition={{ duration: 0.18, ease: 'easeOut' }}
                    layout
                    className="grid grid-cols-1 md:grid-cols-2 gap-3.5"
                  >
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
                          className={`group rounded-[14px] p-5 transition-all duration-200 flex flex-col justify-between space-y-4 ${
                            isCompared
                              ? 'bg-surface-raised/40 border-2 border-border-strong shadow-md ring-1 ring-border-strong/50'
                              : 'bg-surface hover:bg-surface-raised/40 border border-border-subtle hover:border-border-strong shadow-xs hover:shadow-md'
                          }`}
                        >
                          {/* Header Row */}
                          <div className="flex items-start justify-between gap-3">
                            <div className="flex items-center gap-3.5 min-w-0">
                              <div className="relative shrink-0">
                                <img
                                  src={profile.avatar}
                                  alt={profile.name}
                                  referrerPolicy="no-referrer"
                                  className="h-12 w-12 rounded-xl object-cover ring-1 ring-border-subtle/80 shadow-xs group-hover:ring-border-strong transition-all"
                                />
                                {isAvailableNow && (
                                  <span
                                    className="absolute -bottom-1 -right-1 h-3.5 w-3.5 rounded-full bg-positive ring-2 ring-surface shadow-xs"
                                    title="Available immediately"
                                  />
                                )}
                              </div>

                              <div className="min-w-0">
                                <div className="flex items-center gap-1.5 flex-wrap">
                                  <h3 className="font-semibold text-sm text-primary group-hover:text-primary transition-colors truncate">
                                    <HighlightText text={profile.name} query={committedQuery} />
                                  </h3>
                                  {profile.isHighlyRecommended && (
                                    <span title="Strong match"><BadgeCheck className="w-3.5 h-3.5 text-accent shrink-0" /></span>
                                  )}
                                  {isCompared && (
                                    <span className="inline-flex items-center gap-1 rounded px-1.5 py-0.2 text-xs font-semibold bg-surface-raised border border-border-strong text-primary shrink-0">
                                      <Scale className="w-3 h-3 text-secondary" /> Comparing
                                    </span>
                                  )}
                                </div>
                                <p className="text-xs text-secondary truncate font-normal">
                                  <HighlightText text={profile.title} query={committedQuery} />
                                </p>
                                {profile.isHighlyRecommended && (
                                  <span className="mt-1 inline-flex items-center gap-1 text-xs font-medium text-accent">
                                    <span className="h-1.5 w-1.5 rounded-full bg-accent" />
                                    Strong match
                                  </span>
                                )}
                              </div>
                            </div>

                            <div className="flex items-center gap-1 shrink-0" onClick={(event) => event.stopPropagation()}>
                              <button
                                type="button"
                                onClick={() => handleToggleCompare(profile)}
                                aria-label={isCompared ? `Remove ${profile.name} from comparison` : `Add ${profile.name} to comparison`}
                                title={isCompared ? 'In comparison' : 'Compare'}
                                className={`inline-flex min-h-11 min-w-11 items-center justify-center rounded-[10px] transition-colors cursor-pointer ${
                                  isCompared
                                    ? 'text-primary bg-surface-raised border border-border-strong shadow-xs ring-1 ring-border-strong/40'
                                    : 'text-muted hover:text-primary hover:bg-surface-raised/70'
                                }`}
                              >
                                <Scale
                                  className={`h-4 w-4 transition-transform active:scale-90 ${
                                    isCompared ? 'stroke-[2.5]' : ''
                                  }`}
                                  aria-hidden="true"
                                />
                              </button>
                              <button
                                type="button"
                                onClick={() => toggleBookmark(profile.id)}
                                aria-label={isProfileBookmarked ? `Remove ${profile.name} from shortlist` : `Save ${profile.name} to shortlist`}
                                title={isProfileBookmarked ? 'Shortlisted' : 'Save to shortlist'}
                                className={`inline-flex min-h-11 min-w-11 items-center justify-center rounded-[10px] transition-colors cursor-pointer ${
                                  isProfileBookmarked
                                    ? 'text-action bg-surface-raised border border-border-strong/60 shadow-xs'
                                    : 'text-muted hover:text-primary hover:bg-surface-raised/70'
                                }`}
                              >
                                <Bookmark
                                  className={`h-4 w-4 transition-transform active:scale-90 ${
                                    isProfileBookmarked ? 'fill-current' : ''
                                  }`}
                                  aria-hidden="true"
                                />
                              </button>
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
                          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-secondary border-t border-b border-border-subtle/60 py-2">
                            <span className="flex items-center gap-1.5 truncate">
                              <MapPin className="w-3.5 h-3.5 text-muted shrink-0" />
                              <HighlightText text={profile.location.split(',')[0] ?? profile.location} query={committedQuery} />
                            </span>
                            <span className="text-muted/60">•</span>
                            <span>{formatExperience(profile.yearsOfExperience)} yrs exp</span>
                            {profile.dayRate != null && (
                              <>
                                <span className="text-muted/60">•</span>
                                <span className="font-mono font-medium text-positive">£{profile.dayRate}/day</span>
                              </>
                            )}
                            <span className="text-muted/60">•</span>
                            <span className={isAvailableNow ? 'text-positive font-medium' : 'text-secondary'}>
                              {availabilityLabel(profile.availability).replace('Available ', '')}
                            </span>
                            {profile.rating != null && (
                              <>
                                <span className="text-muted/60">•</span>
                                <span className="font-mono text-warning font-medium inline-flex items-center gap-0.5">
                                  <Star className="w-3 h-3 fill-current" /> {profile.rating.toFixed(1)}
                                </span>
                              </>
                            )}
                          </div>

                          {/* Certifications with Tooltips */}
                          {profile.certifications && profile.certifications.length > 0 && (
                            <div className="flex flex-wrap gap-1.5" onClick={(e) => e.stopPropagation()}>
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
                          <p className="text-xs text-secondary line-clamp-2 leading-relaxed font-light">
                            <HighlightText text={profile.bio} query={committedQuery} />
                          </p>

                          {/* Footer / Skills */}
                          <div className="flex items-center justify-between gap-2 pt-1 border-t border-border-subtle/60">
                            <div className="flex items-center gap-1.5 flex-wrap">
                              {profile.skills.slice(0, 3).map((skill) => (
                                <span
                                  key={skill}
                                  className="px-2.5 py-1 rounded-md bg-surface-raised border border-border-subtle/70 text-secondary text-xs font-medium"
                                >
                                  <HighlightText text={skill} query={committedQuery} />
                                </span>
                              ))}
                              {profile.skills.length > 3 && (
                                <span className="text-xs text-muted font-mono font-medium">
                                  +{profile.skills.length - 3}
                                </span>
                              )}
                            </div>

                            <button
                              type="button"
                              onClick={() => setModalProfile(profile)}
                              aria-label={`Open ${profile.name} dossier`}
                              className="inline-flex min-h-11 items-center gap-1.5 rounded-lg border border-border-strong/70 bg-surface hover:bg-surface-raised px-3 py-1.5 text-xs font-semibold text-primary transition-colors shrink-0 shadow-xs cursor-pointer group/btn"
                            >
                              <span>Open dossier</span>
                              <ArrowUpRight className="w-3.5 h-3.5 text-secondary group-hover/btn:text-primary transition-transform group-hover/btn:translate-x-0.5 group-hover/btn:-translate-y-0.5" />
                            </button>
                          </div>
                        </motion.div>
                      );
                    })}
                  </AnimatePresence>
                </motion.div>
              )}
              {profilesHaveMore && !aiQueryActive && (
                <div className="mt-4 flex justify-center">
                  <button
                    type="button"
                    onClick={() => void loadMoreProfiles()}
                    className="min-h-11 rounded-lg border border-border-strong bg-surface px-4 text-xs font-semibold text-secondary transition-colors hover:bg-surface-raised hover:text-primary focus-visible:ring-2 focus-visible:ring-focus"
                  >
                    Load more contractors
                  </button>
                </div>
              )}
              </AnimatePresence>
            ) : (
              /* Clean Animated Empty State */
              <motion.div
                initial={{ opacity: 0, scale: 0.97, y: 10 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.97, y: -10 }}
                transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
                className="text-center py-14 px-4 border border-border-subtle/60 rounded-[14px] bg-surface/20 space-y-3"
              >
                <div className="w-12 h-12 rounded-[14px] bg-surface border border-border-subtle flex items-center justify-center text-muted mx-auto">
                  <Compass className="w-6 h-6 text-muted" />
                </div>
                <div className="space-y-1">
                  <h3 className="text-sm font-semibold text-primary">No close matches found</h3>
                  <p className="text-xs text-muted max-w-sm mx-auto">
                    {committedQuery.trim()
                      ? <>Nothing in the network matches <span className="text-secondary">“{committedQuery.trim()}”</span> yet. Try a broader role, skill, or region.</>
                      : 'No active contractors match the selected filters. Try widening your search.'}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={handleResetAll}
                  className="min-h-11 px-3.5 py-1.5 rounded-[10px] bg-surface-raised hover:bg-surface-selected text-xs text-primary transition-colors cursor-pointer font-medium"
                >
                  Reset all filters
                </button>
                {profilesHaveMore && !aiQueryActive && (
                  <button
                    type="button"
                    onClick={() => void loadMoreProfiles()}
                    className="min-h-11 px-3.5 py-1.5 rounded-[10px] border border-border-strong bg-surface hover:bg-surface-raised text-xs text-primary transition-colors cursor-pointer font-medium focus-visible:ring-2 focus-visible:ring-focus"
                  >
                    Load more contractors
                  </button>
                )}
              </motion.div>
            )}
          </div>
        </OperationsHome>
      </motion.div>
    )}
  </AnimatePresence>
      </main>
      <DocumentReviewModal
        isOpen={isDocumentReviewOpen}
        sessionKey={authSessionKey}
        onClose={() => setIsDocumentReviewOpen(false)}
        onOpenContractor={openIncomingDocumentContractor}
        onShowToast={showToast}
        onReviewResolved={handleDocumentReviewResolved}
      />

      {/* Floating Comparison Action Bar */}
      <ComparisonBar
        compareProfiles={compareProfiles}
        onOpenCompareModal={() => setIsCompareModalOpen(true)}
        onClearCompare={handleClearCompare}
        onRemoveProfile={handleRemoveCompare}
      />

      {/* Power-User Keyboard Command Bar Hint */}
      {isSearchActive && (
        <aside
          aria-label="Keyboard shortcuts hint"
          className="fixed bottom-3 right-4 z-30 hidden lg:flex items-center gap-2 px-3 py-1.5 rounded-full bg-surface/90 border border-border-subtle shadow-md backdrop-blur-md text-xs text-secondary select-none transition-opacity hover:opacity-100 opacity-70"
        >
          <span className="flex items-center gap-1 font-mono text-xs">
            <kbd className="px-1 py-0.2 rounded bg-surface-raised border border-border-subtle text-secondary">J</kbd>
            <kbd className="px-1 py-0.2 rounded bg-surface-raised border border-border-subtle text-secondary">K</kbd>
            <span className="text-muted ml-0.5">navigate</span>
          </span>
          <span className="text-muted">·</span>
          <span className="flex items-center gap-1 font-mono text-xs">
            <kbd className="px-1 py-0.2 rounded bg-surface-raised border border-border-subtle text-secondary">S</kbd>
            <span className="text-muted ml-0.5">shortlist</span>
          </span>
          <span className="text-muted">·</span>
          <span className="flex items-center gap-1 font-mono text-xs">
            <kbd className="px-1 py-0.2 rounded bg-surface-raised border border-border-subtle text-secondary">X</kbd>
            <span className="text-muted ml-0.5">compare</span>
          </span>
          <span className="text-muted">·</span>
          <button
            type="button"
            onClick={() => setIsShortcutsOpen(true)}
            className="flex items-center gap-1 text-primary hover:underline cursor-pointer ml-1"
          >
            <kbd className="px-1 py-0.2 rounded bg-surface-raised border border-border-strong text-primary font-bold">?</kbd>
            <span>all keys</span>
          </button>
        </aside>
      )}

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
        isAdmin={user?.role === 'admin'}
        sessionKey={authSessionKey}
      />

      {/* Dossier Print Preview Modal */}
      {printProfile && (
        <DossierPrintView
          profile={printProfile}
          onClose={() => setPrintProfile(null)}
        />
      )}

      {/* Standalone Detail Modal */}
      <AnimatePresence>
        {modalProfile && (
          <ProfileDetailModal
            profile={modalProfile}
            sessionKey={authSessionKey}
            onClose={() => setModalProfile(null)}
            isBookmarked={isBookmarked(modalProfile.id)}
            onToggleBookmark={(id) => toggleBookmark(id)}
            onShowToast={showToast}
            isCompared={compareIds.includes(modalProfile.id)}
            onToggleCompare={handleToggleCompare}
            onRequestMobilization={handleRequestMobilization}
            onPrintDossier={handlePrintDossier}
            documents={getDocumentsForProfile(modalProfile.id)}
            onAddDocument={() => refreshDocuments(modalProfile.id)}
            onRemoveDocument={async (docId) => {
              try {
                return await removeDocument(modalProfile.id, docId);
              } catch {
                showToast('Failed to remove document');
              }
              return undefined;
            }}
            onReviewDocument={async (docId, action) => {
              return reviewDocument(modalProfile.id, docId, action);
            }}
            canManageDocuments={canManageDocuments}
            canRequestDocuments={canRequestDocuments}
            canDeleteCrew={canManageDocuments && user?.id !== modalProfile.id}
            onDeleteCrew={handleDeleteCrewMember}
          />
        )}
      </AnimatePresence>

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

      {/* Add Contractor Modal */}
      <AddCrewMemberModal
        isOpen={isAddCrewMemberOpen}
        isAdmin={user?.role === 'admin'}
        sessionKey={authSessionKey}
        onClose={() => setIsAddCrewMemberOpen(false)}
        onSuccess={() => {
          showToast('Contractor added successfully');
          void refetchProfiles().catch(() => {
            showToast('Contractor added successfully — roster refresh unavailable');
          });
        }}
      />
      <Suspense fallback={null}>
        <CvReviewModal
          isOpen={isCvReviewOpen}
          isAdmin={user?.role === 'admin'}
          sessionKey={authSessionKey}
          onClose={() => setIsCvReviewOpen(false)}
          onApproved={() => {
            showToast('CV approved and contractor published');
            void refetchProfiles().catch(() => {
              showToast('CV approved — roster refresh unavailable');
            });
          }}
        />
        <ManageStaffModal
          isOpen={isStaffAccessOpen}
          sessionKey={authSessionKey}
          onClose={() => setIsStaffAccessOpen(false)}
        />
      </Suspense>
      <FilterModal
        isOpen={isFilterOpen}
        profiles={allProfiles}
        onClose={() => setIsFilterOpen(false)}
        filters={filters}
        onUpdateFilters={setFilters}
        onResetFilters={resetFilters}
        onApplyPreset={(preset) => handleSelectPreset(preset.id)}
        totalFilteredCount={isSearchActive ? results.length : allProfiles.length}
        totalCount={allProfiles.length}
      />

      {/* Sign-in Modal */}
      <LoginPage
        isOpen={isLoginOpen}
        isModal
        onCancel={() => setIsLoginOpen(false)}
        onSuccess={() => {
          setIsLoginOpen(false);
        }}
      />
      </Suspense>

      {/* Toast Feedback */}
      <Toast message={toastMessage} />
    </div>
  );
}
