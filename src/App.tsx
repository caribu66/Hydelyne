/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useMemo, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { UserProfile, SortOption } from './types';
import { MOCK_PROFILES, FILTER_PRESETS } from './data/mockProfiles';
import { filterProfiles, sortProfiles } from './utils/filterUtils';
import { useShortlist } from './hooks/useShortlist';
import { useURLSync } from './hooks/useURLSync';
import { useSpecialistDocuments } from './hooks/useSpecialistDocuments';
import { useTheme } from './hooks/useTheme';
import { ModernHeroSearch } from './components/ModernHeroSearch';
import { SpecialistDossierPane } from './components/SpecialistDossierPane';
import { SpecialistTableView } from './components/SpecialistTableView';
import { ProfileDetailModal } from './components/ProfileDetailModal';
import { CandidateCompareModal } from './components/CandidateCompareModal';
import { ComparisonBar } from './components/ComparisonBar';
import { MobilizationInquiryModal } from './components/MobilizationInquiryModal';
import { DossierPrintView } from './components/DossierPrintView';
import { ShortcutsModal } from './components/ShortcutsModal';
import { ExportShortlistModal } from './components/ExportShortlistModal';
import { HighlightText } from './components/HighlightText';
import { CertificationBadge } from './components/CertificationBadge';
import { Toast } from './components/Toast';
import {
  MapPin,
  Bookmark,
  BookmarkCheck,
  Copy,
  Check,
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
  Send,
  Printer,
  Sun,
  Moon,
} from 'lucide-react';

export default function App() {
  const { theme, isDark, toggleTheme } = useTheme();
  const [query, setQuery] = useState('');
  const [activePresetId, setActivePresetId] = useState('all');
  const [selectedProfileId, setSelectedProfileId] = useState<string | null>(null);
  const [modalProfile, setModalProfile] = useState<UserProfile | null>(null);
  const [showSavedOnly, setShowSavedOnly] = useState(false);
  const [viewMode, setViewMode] = useState<'split' | 'grid' | 'table'>('split');
  const [sortBy, setSortBy] = useState<SortOption>('relevance');
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [isShortcutsOpen, setIsShortcutsOpen] = useState(false);
  const [isExportShortlistOpen, setIsExportShortlistOpen] = useState(false);

  // Candidate Comparison state
  const [compareIds, setCompareIds] = useState<string[]>([]);
  const [isCompareModalOpen, setIsCompareModalOpen] = useState(false);

  // Mobilization Inquiry state
  const [inquiryProfile, setInquiryProfile] = useState<UserProfile | null>(null);
  const [isInquiryModalOpen, setIsInquiryModalOpen] = useState(false);

  // Printable Dossier state
  const [printProfile, setPrintProfile] = useState<UserProfile | null>(null);

  // Shortlist Hook
  const {
    bookmarkedIds,
    shortlistedProfiles,
    toggleBookmark: rawToggleBookmark,
    isBookmarked,
    clearShortlist,
    shortlistCount,
  } = useShortlist(MOCK_PROFILES);

  // Specialist Documents & Compliance Hook
  const {
    getDocumentsForProfile,
    addDocument,
    removeDocument,
  } = useSpecialistDocuments();

  // Focused Workspace mode for working comfortably on a crew member
  const [isFocusMode, setIsFocusMode] = useState(false);

  const showToast = useCallback((msg: string) => {
    setToastMessage(msg);
    setTimeout(() => {
      setToastMessage((curr) => (curr === msg ? null : curr));
    }, 2200);
  }, []);

  const toggleBookmark = useCallback((id: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    const profile = MOCK_PROFILES.find((p) => p.id === id);
    const name = profile ? profile.name.split(' ')[0] : 'Specialist';
    const currentlyBookmarked = isBookmarked(id);
    rawToggleBookmark(id);
    showToast(currentlyBookmarked ? `Removed ${name} from shortlist` : `Saved ${name} to shortlist`);
  }, [isBookmarked, rawToggleBookmark, showToast]);

  const handleCopyEmail = useCallback((profile: UserProfile, e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard?.writeText(profile.email);
    setCopiedId(profile.id);
    showToast(`Copied ${profile.email}`);
    setTimeout(() => setCopiedId(null), 1800);
  }, [showToast]);

  // Comparison toggle handler
  const handleToggleCompare = useCallback((profile: UserProfile) => {
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
  }, [showToast]);

  const handleRemoveCompare = useCallback((id: string) => {
    setCompareIds((prev) => prev.filter((i) => i !== id));
  }, []);

  const handleClearCompare = useCallback(() => {
    setCompareIds([]);
    showToast('Comparison cleared');
  }, [showToast]);

  const compareProfiles = useMemo(() => {
    return MOCK_PROFILES.filter((p) => compareIds.includes(p.id));
  }, [compareIds]);

  // Mobilization Trigger
  const handleRequestMobilization = useCallback((profile: UserProfile) => {
    setInquiryProfile(profile);
    setIsInquiryModalOpen(true);
  }, []);

  // Print Trigger
  const handlePrintDossier = useCallback((profile: UserProfile) => {
    setPrintProfile(profile);
  }, []);

  // URL Synchronization
  useURLSync({
    query,
    viewMode: viewMode === 'grid' ? 'cards' : viewMode,
    onSyncQuery: useCallback((q: string) => setQuery(q), []),
    onSyncViewMode: useCallback((mode: 'split' | 'cards' | 'table') => {
      setViewMode(mode === 'cards' ? 'grid' : mode);
    }, []),
  });

  const isSearchActive = Boolean(query.trim() || showSavedOnly || activePresetId !== 'all');

  // Apply quick preset filter logic
  const handleSelectPreset = useCallback((presetId: string) => {
    setActivePresetId(presetId);
    const preset = FILTER_PRESETS.find((p) => p.id === presetId);
    if (!preset || presetId === 'all') {
      return;
    }
  }, []);

  // Filtered & Ranked Specialists
  const results = useMemo(() => {
    if (!isSearchActive) {
      return [];
    }

    let list = MOCK_PROFILES;

    // Apply quick preset filter if active
    if (activePresetId !== 'all') {
      const preset = FILTER_PRESETS.find((p) => p.id === activePresetId);
      if (preset) {
        const filters = preset.filters;
        if (filters.availability && filters.availability.length > 0) {
          list = list.filter((p) =>
            filters.availability!.some((a) => p.availability.toLowerCase().includes(a.toLowerCase()))
          );
        }
        if (filters.departments && filters.departments.length > 0) {
          list = list.filter((p) =>
            filters.departments!.some((d) => p.department.toLowerCase().includes(d.toLowerCase()))
          );
        }
        if (filters.selectedSkills && filters.selectedSkills.length > 0) {
          list = list.filter((p) =>
            filters.selectedSkills!.some((skill) =>
              p.skills.some((ps) => ps.toLowerCase().includes(skill.toLowerCase())) ||
              p.certifications?.some((c) => c.toLowerCase().includes(skill.toLowerCase()))
            )
          );
        }
        if (filters.minExperience && filters.minExperience > 0) {
          list = list.filter((p) => p.yearsOfExperience >= filters.minExperience!);
        }
      }
    }

    // Search query filter
    if (query.trim()) {
      list = filterProfiles(list, {
        keyword: query.trim(),
        locations: [],
        remoteTypes: [],
        selectedSkills: [],
        skillMatchMode: 'ANY',
        minExperience: 0,
        maxExperience: 30,
        companies: [],
        availability: [],
        departments: [],
        sortBy: 'relevance',
      });
    }

    if (showSavedOnly) {
      list = list.filter((p) => isBookmarked(p.id));
    }

    return sortProfiles(list, sortBy, query);
  }, [isSearchActive, query, showSavedOnly, isBookmarked, sortBy, activePresetId]);

  // Keep first result selected in split-view if current selection is invalid
  useEffect(() => {
    if (results.length > 0) {
      if (!selectedProfileId || !results.some((r) => r.id === selectedProfileId)) {
        setSelectedProfileId(results[0].id);
      }
    } else {
      setSelectedProfileId(null);
    }
  }, [results, selectedProfileId]);

  const activeSelectedProfile = useMemo(() => {
    return results.find((r) => r.id === selectedProfileId) || results[0] || null;
  }, [results, selectedProfileId]);

  const currentSelectedIdx = results.findIndex((r) => r.id === (activeSelectedProfile?.id || selectedProfileId));

  const handlePrevProfile = useCallback(() => {
    if (results.length === 0) return;
    const prevIdx = currentSelectedIdx > 0 ? currentSelectedIdx - 1 : results.length - 1;
    setSelectedProfileId(results[prevIdx].id);
  }, [results, currentSelectedIdx]);

  const handleNextProfile = useCallback(() => {
    if (results.length === 0) return;
    const nextIdx = currentSelectedIdx < results.length - 1 ? currentSelectedIdx + 1 : 0;
    setSelectedProfileId(results[nextIdx].id);
  }, [results, currentSelectedIdx]);

  // Global & Split View Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes((document.activeElement?.tagName || ''))) {
        return;
      }

      if (e.key === '?') {
        e.preventDefault();
        setIsShortcutsOpen((prev) => !prev);
        return;
      }

      if (e.key.toLowerCase() === 't') {
        e.preventDefault();
        toggleTheme();
        showToast(isDark ? 'Switched to High-Contrast Light Theme' : 'Switched to Deep Zinc Dark Theme');
        return;
      }

      if (e.key.toLowerCase() === 'f' && activeSelectedProfile) {
        e.preventDefault();
        setIsFocusMode((prev) => !prev);
        return;
      }

      if (e.key === 'Escape' && isFocusMode) {
        e.preventDefault();
        setIsFocusMode(false);
        return;
      }

      if (results.length === 0) return;

      const currentIndex = results.findIndex((r) => r.id === selectedProfileId);

      if (e.key === 'ArrowDown' || e.key.toLowerCase() === 'j') {
        e.preventDefault();
        const nextIndex = currentIndex < results.length - 1 ? currentIndex + 1 : 0;
        setSelectedProfileId(results[nextIndex].id);
      } else if (e.key === 'ArrowUp' || e.key.toLowerCase() === 'k') {
        e.preventDefault();
        const prevIndex = currentIndex > 0 ? currentIndex - 1 : results.length - 1;
        setSelectedProfileId(results[prevIndex].id);
      } else if (e.key === 'ArrowLeft' && isFocusMode) {
        e.preventDefault();
        handlePrevProfile();
      } else if (e.key === 'ArrowRight' && isFocusMode) {
        e.preventDefault();
        handleNextProfile();
      } else if (e.key.toLowerCase() === 's' && activeSelectedProfile) {
        e.preventDefault();
        toggleBookmark(activeSelectedProfile.id);
      } else if (e.key.toLowerCase() === 'c' && activeSelectedProfile) {
        e.preventDefault();
        navigator.clipboard?.writeText(activeSelectedProfile.email);
        showToast(`Copied ${activeSelectedProfile.email}`);
      } else if (e.key.toLowerCase() === 'm' && activeSelectedProfile) {
        e.preventDefault();
        handleRequestMobilization(activeSelectedProfile);
      } else if (e.key === 'Enter' && activeSelectedProfile && !isFocusMode) {
        setModalProfile(activeSelectedProfile);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [results, selectedProfileId, activeSelectedProfile, toggleBookmark, showToast, handleRequestMobilization, isFocusMode, handlePrevProfile, handleNextProfile]);

  const handleResetAll = () => {
    setShowSavedOnly(false);
    setQuery('');
    setActivePresetId('all');
    setSortBy('relevance');
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col font-sans antialiased selection:bg-blue-600/30 selection:text-blue-100 relative overflow-x-hidden">
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
        <div className="max-w-6xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between gap-4">
          {/* Logo / Brand Name */}
          <div
            onClick={handleResetAll}
            className="flex items-center gap-2.5 cursor-pointer select-none group"
          >
            <div className="w-7 h-7 rounded-xl bg-zinc-900 border border-zinc-700/80 flex items-center justify-center text-zinc-100 group-hover:border-zinc-500 transition-colors shadow-xs">
              <span className="font-serif text-sm font-bold tracking-tighter">H</span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="font-medium text-sm tracking-tight text-zinc-100 group-hover:text-white transition-colors">
                HYDENLYNE
              </span>
              <span className="text-[11px] text-zinc-500 font-mono hidden sm:inline">
                / talent
              </span>
            </div>
          </div>

          {/* Right Nav */}
          <div className="flex items-center gap-2.5">
            {/* Compare Matrix Trigger Button */}
            {compareIds.length > 0 && (
              <button
                type="button"
                onClick={() => setIsCompareModalOpen(true)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-blue-950/80 border border-blue-800 text-blue-300 hover:text-white text-xs font-semibold transition-colors cursor-pointer"
                title="Compare candidates side-by-side"
              >
                <Scale className="w-3.5 h-3.5" />
                <span>Compare ({compareIds.length})</span>
              </button>
            )}

            {isSearchActive && (
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
              className="p-2 rounded-xl bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-zinc-200 transition-colors cursor-pointer"
              title="Keyboard shortcuts (?)"
              aria-label="Open keyboard shortcuts"
            >
              <Command className="w-3.5 h-3.5" />
            </button>

            {/* Theme Toggle Button */}
            <button
              type="button"
              id="app-theme-toggle-btn"
              onClick={() => {
                toggleTheme();
                showToast(isDark ? 'Switched to High-Contrast Light Theme' : 'Switched to Deep Zinc Dark Theme');
              }}
              className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-zinc-200 transition-colors cursor-pointer text-xs font-medium"
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
            <div className="flex items-center gap-1 bg-zinc-900 border border-zinc-800 p-0.5 rounded-xl">
              <button
                type="button"
                onClick={() => setShowSavedOnly(!showSavedOnly)}
                className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium transition-colors cursor-pointer ${
                  showSavedOnly
                    ? 'bg-zinc-100 text-zinc-950 font-semibold'
                    : 'text-zinc-400 hover:text-zinc-200'
                }`}
                title={showSavedOnly ? 'Show all results' : 'Filter by shortlist'}
              >
                <Bookmark className={`w-3.5 h-3.5 ${showSavedOnly ? 'fill-zinc-950' : ''}`} />
                <span className="hidden xs:inline">Shortlist</span>
                <span className="text-[11px] opacity-75 font-mono">({shortlistCount})</span>
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
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-6xl mx-auto w-full px-4 sm:px-6 flex flex-col justify-start">
        {/* Modern Search Bar */}
        <ModernHeroSearch
          query={query}
          onChange={(val) => setQuery(val)}
          onSearch={(val) => setQuery(val)}
          onClear={() => setQuery('')}
          isCalmState={!isSearchActive}
          totalSpecialists={MOCK_PROFILES.length}
        />

        {/* Results Header (Active Search Only) */}
        {isSearchActive && (
          <div className="flex items-center justify-between text-xs text-zinc-400 py-2 border-b border-zinc-800/60 mb-4">
            <div className="flex items-center gap-2 flex-wrap">
              <span>
                Found <strong className="text-zinc-100 font-semibold">{results.length}</strong> {results.length === 1 ? 'specialist' : 'specialists'}
              </span>
              {query && (
                <span>
                  matching <span className="text-blue-400 font-medium">"{query}"</span>
                </span>
              )}
              {activePresetId !== 'all' && (
                <span className="text-blue-400 font-medium">
                  • Preset: {FILTER_PRESETS.find((p) => p.id === activePresetId)?.name}
                </span>
              )}
              {showSavedOnly && <span>• Shortlist only</span>}
            </div>

            <div className="flex items-center gap-3">
              {/* Sort Dropdown */}
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as SortOption)}
                aria-label="Sort specialists"
                className="bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-zinc-200 text-xs rounded-lg px-2.5 py-1 focus:outline-none focus:border-zinc-700 cursor-pointer font-medium"
              >
                <option value="relevance">Sort: Relevance & Match</option>
                <option value="experience-desc">Sort: Experience (High to Low)</option>
                <option value="rate-desc">Sort: Day Rate (High to Low)</option>
                <option value="rate-asc">Sort: Day Rate (Low to High)</option>
                <option value="rating-desc">Sort: Rating (★ Highest)</option>
              </select>

              {(query || showSavedOnly || activePresetId !== 'all' || sortBy !== 'relevance') && (
                <button
                  type="button"
                  onClick={handleResetAll}
                  className="text-zinc-400 hover:text-zinc-200 transition-colors cursor-pointer text-xs underline"
                >
                  Clear all
                </button>
              )}
            </div>
          </div>
        )}

        {/* Results Area */}
        {isSearchActive && (
          <div className="pb-16">
            {results.length > 0 ? (
              viewMode === 'split' ? (
                isFocusMode ? (
                  /* Focused Specialist Workspace (Enlarged & Centered for comfortable working) */
                  <div className="max-w-5xl mx-auto w-full space-y-4 px-2 sm:px-4">
                    {/* Crew Selector Navigation Strip */}
                    <div className="flex items-center justify-between bg-zinc-900/90 border border-zinc-800 p-3 rounded-2xl backdrop-blur-md shadow-xl gap-3">
                      <div className="flex items-center gap-2 overflow-x-auto py-1 scrollbar-none max-w-2xl">
                        {results.map((profile, idx) => {
                          const isSel = (activeSelectedProfile?.id || selectedProfileId) === profile.id;
                          return (
                            <button
                              key={profile.id}
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
                        className="w-full flex justify-center"
                      >
                        <SpecialistDossierPane
                          profile={activeSelectedProfile}
                          searchQuery={query}
                          isBookmarked={activeSelectedProfile ? isBookmarked(activeSelectedProfile.id) : false}
                          onToggleBookmark={toggleBookmark}
                          onShowToast={showToast}
                          isCompared={activeSelectedProfile ? compareIds.includes(activeSelectedProfile.id) : false}
                          onToggleCompare={handleToggleCompare}
                          onRequestMobilization={handleRequestMobilization}
                          onPrintDossier={handlePrintDossier}
                          documents={activeSelectedProfile ? getDocumentsForProfile(activeSelectedProfile.id) : []}
                          onAddDocument={(doc) => activeSelectedProfile && addDocument(activeSelectedProfile.id, doc)}
                          onRemoveDocument={(docId) => activeSelectedProfile && removeDocument(activeSelectedProfile.id, docId)}
                          isFocusMode={true}
                          onToggleFocusMode={() => setIsFocusMode(false)}
                          onPrevProfile={handlePrevProfile}
                          onNextProfile={handleNextProfile}
                          profileIndex={currentSelectedIdx >= 0 ? currentSelectedIdx : 0}
                          totalProfiles={results.length}
                        />
                      </motion.div>
                    </AnimatePresence>
                  </div>
                ) : (
                  /* Standard Split-Pane Operations Command */
                  <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-start min-h-[580px]">
                    {/* Left Column: Animated List */}
                    <div className="lg:col-span-5 space-y-2 max-h-[720px] overflow-y-auto pr-1">
                      <AnimatePresence mode="popLayout">
                        {results.map((profile, index) => {
                          const isSelected = selectedProfileId === profile.id;
                          const isProfileBookmarked = isBookmarked(profile.id);
                          const isCompared = compareIds.includes(profile.id);
                          const isAvailableNow = profile.availability?.toLowerCase().includes('immediately');

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
                              onClick={() => setSelectedProfileId(profile.id)}
                              className={`group relative p-3.5 rounded-xl border transition-all duration-150 cursor-pointer flex items-center justify-between gap-3 ${
                                isSelected
                                  ? 'bg-zinc-900/90 border-zinc-500 shadow-md ring-1 ring-zinc-500/30'
                                  : 'bg-zinc-900/40 hover:bg-zinc-900/80 border-zinc-800/80 hover:border-zinc-700'
                              }`}
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
                                      <h3 className={`font-semibold text-xs tracking-tight truncate ${isSelected ? 'text-blue-400' : 'text-zinc-100 group-hover:text-zinc-50'}`}>
                                        <HighlightText text={profile.name} query={query} />
                                      </h3>
                                      {profile.isHighlyRecommended && (
                                        <BadgeCheck className="w-3.5 h-3.5 text-blue-400 shrink-0" title="Verified Specialist" />
                                      )}
                                    </div>

                                    <span className={`text-[10px] font-mono shrink-0 ${isAvailableNow ? 'text-emerald-400 font-medium' : 'text-zinc-400'}`}>
                                      {profile.dayRate ? `£${profile.dayRate}/d` : profile.availability.split(' ')[0]}
                                    </span>
                                  </div>

                                  <p className="text-[11px] text-zinc-400 truncate font-normal">
                                    <HighlightText text={profile.title} query={query} />
                                  </p>

                                  <div className="flex items-center gap-2 text-[10px] text-zinc-500 pt-0.5">
                                    <span className="px-1.5 py-0.5 rounded bg-zinc-800/80 border border-zinc-700/50 text-zinc-300 font-medium text-[10px]">
                                      {profile.department}
                                    </span>
                                    <span className="truncate">{profile.location.split(',')[0]}</span>
                                    <span>•</span>
                                    <span>{profile.yearsOfExperience}y exp</span>
                                  </div>
                                </div>
                              </div>

                              {/* Quick Actions */}
                              <div className="flex items-center gap-1 shrink-0" onClick={(e) => e.stopPropagation()}>
                                <button
                                  type="button"
                                  onClick={() => handleToggleCompare(profile)}
                                  className={`p-1.5 rounded-lg transition-colors cursor-pointer ${
                                    isCompared
                                      ? 'text-blue-400 bg-blue-950/60 border border-blue-700'
                                      : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/50'
                                  }`}
                                  title={isCompared ? 'In comparison' : 'Add to compare'}
                                >
                                  <Scale className="w-3.5 h-3.5" />
                                </button>

                                <button
                                  type="button"
                                  onClick={(e) => toggleBookmark(profile.id, e)}
                                  className={`p-1.5 rounded-lg transition-colors cursor-pointer ${
                                    isProfileBookmarked
                                      ? 'text-blue-400 bg-blue-950/40 border border-blue-800/40'
                                      : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/50'
                                  }`}
                                  title={isProfileBookmarked ? 'Saved in shortlist' : 'Save specialist'}
                                >
                                  {isProfileBookmarked ? (
                                    <BookmarkCheck className="w-3.5 h-3.5 fill-blue-400" />
                                  ) : (
                                    <Bookmark className="w-3.5 h-3.5" />
                                  )}
                                </button>
                              </div>
                            </motion.div>
                          );
                        })}
                      </AnimatePresence>
                    </div>

                    {/* Right Column: Live Specialist Dossier */}
                    <div className="lg:col-span-7 sticky top-20">
                      <AnimatePresence mode="wait">
                        <motion.div
                          key={activeSelectedProfile ? activeSelectedProfile.id : 'empty'}
                          initial={{ opacity: 0, y: 8 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0, y: -8 }}
                          transition={{ duration: 0.2, ease: 'easeOut' }}
                        >
                          <SpecialistDossierPane
                            profile={activeSelectedProfile}
                            searchQuery={query}
                            isBookmarked={activeSelectedProfile ? isBookmarked(activeSelectedProfile.id) : false}
                            onToggleBookmark={toggleBookmark}
                            onShowToast={showToast}
                            isCompared={activeSelectedProfile ? compareIds.includes(activeSelectedProfile.id) : false}
                            onToggleCompare={handleToggleCompare}
                            onRequestMobilization={handleRequestMobilization}
                            onPrintDossier={handlePrintDossier}
                            documents={activeSelectedProfile ? getDocumentsForProfile(activeSelectedProfile.id) : []}
                            onAddDocument={(doc) => activeSelectedProfile && addDocument(activeSelectedProfile.id, doc)}
                            onRemoveDocument={(docId) => activeSelectedProfile && removeDocument(activeSelectedProfile.id, docId)}
                            isFocusMode={false}
                            onToggleFocusMode={() => setIsFocusMode(true)}
                            onPrevProfile={handlePrevProfile}
                            onNextProfile={handleNextProfile}
                            profileIndex={currentSelectedIdx >= 0 ? currentSelectedIdx : 0}
                            totalProfiles={results.length}
                          />
                        </motion.div>
                      </AnimatePresence>
                    </div>
                  </div>
                )
              ) : viewMode === 'table' ? (
                /* High-Density Spreadsheet Matrix */
                <SpecialistTableView
                  profiles={results}
                  searchQuery={query}
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
              ) : (
                /* Visual Grid Cards View with Motion */
                <motion.div layout className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
                  <AnimatePresence mode="popLayout">
                    {results.map((profile, index) => {
                      const isProfileBookmarked = isBookmarked(profile.id);
                      const isCompared = compareIds.includes(profile.id);
                      const isAvailableNow = profile.availability?.toLowerCase().includes('immediately');

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
                          onClick={() => setModalProfile(profile)}
                          className="group bg-zinc-900/40 hover:bg-zinc-900/90 border border-zinc-800/80 hover:border-zinc-700 rounded-2xl p-4 transition-colors cursor-pointer flex flex-col justify-between space-y-3 shadow-xs"
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
                                    <HighlightText text={profile.name} query={query} />
                                  </h3>
                                  {profile.isHighlyRecommended && (
                                    <BadgeCheck className="w-3.5 h-3.5 text-blue-400 shrink-0" title="Verified Specialist" />
                                  )}
                                </div>
                                <p className="text-xs text-zinc-400 truncate font-light">
                                  <HighlightText text={profile.title} query={query} />
                                </p>
                              </div>
                            </div>

                            {/* Quick Action Icons */}
                            <div className="flex items-center gap-1 shrink-0" onClick={(e) => e.stopPropagation()}>
                              <button
                                type="button"
                                onClick={() => handleToggleCompare(profile)}
                                className={`p-1 rounded transition-colors ${
                                  isCompared ? 'text-blue-400' : 'text-zinc-500 hover:text-zinc-300'
                                }`}
                                title={isCompared ? 'In comparison' : 'Add to compare'}
                              >
                                <Scale className="w-3.5 h-3.5" />
                              </button>

                              <button
                                type="button"
                                onClick={(e) => handleCopyEmail(profile, e)}
                                className="p-1 rounded text-zinc-500 hover:text-zinc-300 transition-colors"
                                title="Copy Email"
                              >
                                {copiedId === profile.id ? (
                                  <Check className="w-3.5 h-3.5 text-emerald-400" />
                                ) : (
                                  <Copy className="w-3.5 h-3.5" />
                                )}
                              </button>

                              <button
                                type="button"
                                onClick={(e) => toggleBookmark(profile.id, e)}
                                className={`p-1 rounded transition-colors ${
                                  isProfileBookmarked ? 'text-blue-400' : 'text-zinc-500 hover:text-zinc-300'
                                }`}
                                title={isProfileBookmarked ? 'Saved' : 'Save'}
                              >
                                {isProfileBookmarked ? (
                                  <BookmarkCheck className="w-3.5 h-3.5 fill-blue-400" />
                                ) : (
                                  <Bookmark className="w-3.5 h-3.5" />
                                )}
                              </button>
                            </div>
                          </div>

                          {/* Compact Specs Line */}
                          <div className="flex items-center gap-3 text-xs text-zinc-400 border-t border-b border-zinc-800/50 py-1.5">
                            <span className="flex items-center gap-1 truncate">
                              <MapPin className="w-3 h-3 text-zinc-500 shrink-0" />
                              <HighlightText text={profile.location.split(',')[0]} query={query} />
                            </span>
                            <span>•</span>
                            <span>{profile.yearsOfExperience} yrs exp</span>
                            {profile.dayRate && (
                              <>
                                <span>•</span>
                                <span className="text-emerald-400 font-medium">£{profile.dayRate}/day</span>
                              </>
                            )}
                          </div>

                          {/* Certifications with Tooltips */}
                          {profile.certifications && profile.certifications.length > 0 && (
                            <div className="flex flex-wrap gap-1" onClick={(e) => e.stopPropagation()}>
                              {profile.certifications.slice(0, 3).map((cert) => (
                                <CertificationBadge key={cert} certification={cert} size="sm" />
                              ))}
                            </div>
                          )}

                          {/* Bio snippet */}
                          <p className="text-xs text-zinc-400 line-clamp-2 leading-relaxed font-light">
                            <HighlightText text={profile.bio} query={query} />
                          </p>

                          {/* Footer / Skills */}
                          <div className="flex items-center justify-between gap-2 pt-1 border-t border-zinc-850">
                            <div className="flex items-center gap-1.5 flex-wrap">
                              {profile.skills.slice(0, 3).map((skill) => (
                                <span
                                  key={skill}
                                  className="px-2 py-0.5 rounded-md bg-zinc-800/80 text-zinc-400 text-[11px]"
                                >
                                  <HighlightText text={skill} query={query} />
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
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleRequestMobilization(profile);
                                }}
                                className="text-xs text-zinc-300 hover:text-blue-400 font-medium flex items-center gap-1"
                              >
                                <Send className="w-3 h-3" />
                                <span>Inquire</span>
                              </button>
                              <span className="text-blue-400 text-xs font-medium flex items-center gap-0.5 group-hover:translate-x-0.5 transition-transform shrink-0">
                                View <ArrowUpRight className="w-3 h-3" />
                              </span>
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
                  <h3 className="text-sm font-semibold text-zinc-200">No Specialists Found</h3>
                  <p className="text-xs text-zinc-500 max-w-sm mx-auto">
                    No active consultants matched your query or selected filter preset.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={handleResetAll}
                  className="px-3.5 py-1.5 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-xs text-zinc-200 transition-colors cursor-pointer font-medium"
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
      <CandidateCompareModal
        isOpen={isCompareModalOpen}
        onClose={() => setIsCompareModalOpen(false)}
        compareProfiles={compareProfiles}
        allProfiles={MOCK_PROFILES}
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
          onAddDocument={(doc) => addDocument(modalProfile.id, doc)}
          onRemoveDocument={(docId) => removeDocument(modalProfile.id, docId)}
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

      {/* Toast Feedback */}
      <Toast message={toastMessage} />
    </div>
  );
}
