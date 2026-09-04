import { useState, useEffect, useMemo, useCallback } from 'react'
import { UserProfile, SortOption, FilterState } from '../types'
import { FILTER_PRESETS } from '../data/mockProfiles'
import { filterProfiles, getActiveFilterCount, INITIAL_FILTER_STATE, sortProfiles } from '../utils/filterUtils'
import { CrewQueryResult } from './useCrewQuery'

interface UseSearchWorkspaceOptions {
  allProfiles: UserProfile[]
  isBookmarked: (id: string) => boolean
  aiQueryData: CrewQueryResult | null
  aiQueryActive: boolean
  isAuthenticated: boolean
}

export interface UseSearchWorkspaceReturn {
  query: string
  setQuery: (q: string) => void
  committedQuery: string
  setCommittedQuery: (q: string) => void
  activePresetId: string
  filters: FilterState
  setFilters: (updater: (previous: FilterState) => FilterState) => void
  resetFilters: () => void
  activeFilterCount: number
  showSavedOnly: boolean
  setShowSavedOnly: (v: boolean) => void
  viewMode: 'split' | 'grid' | 'table'
  setViewMode: (m: 'split' | 'grid' | 'table') => void
  sortBy: SortOption
  setSortBy: (s: SortOption) => void
  selectedProfileId: string | null
  setSelectedProfileId: (id: string | null) => void
  isResultsUpdating: boolean
  isSearchActive: boolean
  results: UserProfile[]
  activeSelectedProfile: UserProfile | null
  currentSelectedIdx: number
  handleSelectPreset: (presetId: string) => void
  handleResetAll: () => void
  handlePrevProfile: () => void
  handleNextProfile: () => void
}

export function useSearchWorkspace({
  allProfiles,
  isBookmarked,
  aiQueryData,
  aiQueryActive,
  isAuthenticated,
}: UseSearchWorkspaceOptions): UseSearchWorkspaceReturn {
  const [query, setQuery] = useState('')
  const [committedQuery, setCommittedQuery] = useState('')
  const [activePresetId, setActivePresetId] = useState('all')
  const [filters, setFiltersState] = useState<FilterState>(INITIAL_FILTER_STATE)
  const [selectedProfileId, setSelectedProfileId] = useState<string | null>(null)
  const [showSavedOnly, setShowSavedOnly] = useState(false)
  const [viewMode, setViewMode] = useState<'split' | 'grid' | 'table'>('split')
  const [sortBy, setSortBy] = useState<SortOption>('relevance')
  const activeFilterCount = useMemo(() => getActiveFilterCount(filters), [filters])

  // Debounce: keep the result canvas stable while the user is still typing
  useEffect(() => {
    const timer = window.setTimeout(() => {
      setCommittedQuery(query.trim())
    }, 420)
    return () => window.clearTimeout(timer)
  }, [query])

  const isResultsUpdating = query.trim() !== committedQuery.trim()
  // Gate at the single point every result-revealing block in App.tsx already
  // keys off, so no future entry point (URL param, restored state, a
  // websocket push) can render gated UI just by forgetting its own auth check.
  const isSearchActive = Boolean(
    isAuthenticated && (committedQuery.trim() || showSavedOnly || activeFilterCount > 0)
  )

  const handleSelectPreset = useCallback((presetId: string) => {
    const preset = FILTER_PRESETS.find((item) => item.id === presetId)
    setActivePresetId(presetId)
    setFiltersState({
      ...INITIAL_FILTER_STATE,
      ...(preset?.filters ?? {}),
    })
  }, [])

  const setFilters = useCallback((updater: (previous: FilterState) => FilterState) => {
    setActivePresetId('all')
    setFiltersState(updater)
  }, [])

  const resetFilters = useCallback(() => {
    setActivePresetId('all')
    setFiltersState(INITIAL_FILTER_STATE)
  }, [])

  const handleResetAll = useCallback(() => {
    setShowSavedOnly(false)
    setQuery('')
    setCommittedQuery('')
    setActivePresetId('all')
    setFiltersState(INITIAL_FILTER_STATE)
    setSortBy('relevance')
  }, [])

  // Filtered & Ranked Specialists
  const results = useMemo(() => {
    if (!isSearchActive) return []

    let list = filterProfiles(allProfiles, { ...filters, keyword: '' })

    // Search query filter
    if (committedQuery.trim()) {
      const aiMatchedIds = aiQueryData?.results?.map((result) => result.id) ?? []
      const aiMatchesCurrentQuery = aiQueryActive
        && aiQueryData?.query.trim().toLowerCase() === committedQuery.trim().toLowerCase()
      const hasVisibleAIMatches = aiMatchedIds.some((id) => list.some((profile) => profile.id === id))

      if (aiMatchesCurrentQuery && hasVisibleAIMatches) {
        list = list.filter((profile) => aiMatchedIds.includes(profile.id))
      } else {
        list = filterProfiles(list, {
          keyword: committedQuery.trim(),
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
        })
      }
    }

    if (showSavedOnly) {
      list = list.filter((p) => isBookmarked(p.id))
    }

    const aiMatchedIds = aiQueryData?.results?.map((r) => r.id) || []
    return sortProfiles(list, sortBy, committedQuery, aiMatchedIds)
  }, [isSearchActive, committedQuery, showSavedOnly, isBookmarked, sortBy, filters, allProfiles, aiQueryData, aiQueryActive])

  // Keep first result selected in split-view if current selection is invalid
  useEffect(() => {
    if (results.length > 0) {
      if (!selectedProfileId || !results.some((r) => r.id === selectedProfileId)) {
        // Non-null: guarded by `results.length > 0` above.
        setSelectedProfileId(results[0]!.id)
      }
    } else {
      setSelectedProfileId(null)
    }
  }, [results, selectedProfileId])

  const activeSelectedProfile = useMemo(() => {
    return results.find((r) => r.id === selectedProfileId) || results[0] || null
  }, [results, selectedProfileId])

  const currentSelectedIdx = results.findIndex((r) => r.id === (activeSelectedProfile?.id || selectedProfileId))

  const handlePrevProfile = useCallback(() => {
    if (results.length === 0) return
    const prevIdx = currentSelectedIdx > 0 ? currentSelectedIdx - 1 : results.length - 1
    // Non-null: prevIdx is always within [0, results.length) given the guard above.
    setSelectedProfileId(results[prevIdx]!.id)
  }, [results, currentSelectedIdx])

  const handleNextProfile = useCallback(() => {
    if (results.length === 0) return
    const nextIdx = currentSelectedIdx < results.length - 1 ? currentSelectedIdx + 1 : 0
    // Non-null: nextIdx is always within [0, results.length) given the guard above.
    setSelectedProfileId(results[nextIdx]!.id)
  }, [results, currentSelectedIdx])

  return {
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
  }
}
