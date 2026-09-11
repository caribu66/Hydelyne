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
  openWorkspace: () => void
  closeWorkspace: () => void
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
  const [isWorkspaceOpen, setIsWorkspaceOpen] = useState(false)
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
    isAuthenticated && (isWorkspaceOpen || committedQuery.trim() || showSavedOnly || activeFilterCount > 0)
  )

  const openWorkspace = useCallback(() => {
    setIsWorkspaceOpen(true)
  }, [])

  const closeWorkspace = useCallback(() => {
    setIsWorkspaceOpen(false)
  }, [])

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
    setIsWorkspaceOpen(false)
    setShowSavedOnly(false)
    setQuery('')
    setCommittedQuery('')
    setActivePresetId('all')
    setFiltersState(INITIAL_FILTER_STATE)
    setSortBy('relevance')
  }, [])

  // Filtered & Ranked Specialists
  const results = useMemo(() => {
    let list = filterProfiles(allProfiles, { ...filters, keyword: '' })

    // Search query filter
    if (committedQuery.trim()) {
      const aiMatchedIds = aiQueryData?.results?.map((result) => result.id) ?? []
      const aiMatchesCurrentQuery = aiQueryActive
        && aiQueryData?.query.trim().toLowerCase() === committedQuery.trim().toLowerCase()

        if (aiMatchesCurrentQuery && aiMatchedIds.length > 0) {
          // Trust the backend AI result set as the source of truth. If a
          // matched specialist is not in the currently loaded local roster,
          // synthesize a minimal profile from the AI payload so the result is
          // not silently dropped.
          const localMap = new Map(allProfiles.map((p) => [p.id, p]))
          list = aiMatchedIds
            .map((id) => localMap.get(id))
            .filter((profile): profile is UserProfile => profile !== undefined)
          const missingIds = aiMatchedIds.filter((id) => !localMap.has(id))
          if (missingIds.length > 0) {
            const aiResultMap = new Map(aiQueryData.results.map((r) => [r.id, r]))
            const synthesized: UserProfile[] = []
            for (const id of missingIds) {
              const ai = aiResultMap.get(id)
              if (!ai) continue
              const availability = (ai.availability ?? 'Unavailable') as UserProfile['availability']
              synthesized.push({
                id: ai.id,
                name: ai.name,
                // The AI payload carries no title/company/location evidence —
                // never fabricate them from the name or availability string.
                title: 'Contractor',
                avatar: '',
                company: '',
                department: '',
                location: '',
                remoteType: 'On-site',
                yearsOfExperience: Math.round((ai.experience_months ?? 0) / 12),
                skills: ai.certifications ?? [],
                bio: '',
                availability,
                education: '',
                nationality: undefined,
                countryOfResidence: undefined,
                email: ai.email ?? '',
                certifications: ai.certifications ?? [],
                workHistory: [],
              })
            }
            list = [...list, ...synthesized]
            // The AI id-set replaces the keyword match, not the user's
            // facet filters — re-apply them so chips stay truthful.
            list = filterProfiles(list, { ...filters, keyword: '' })
          }
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

    // Only let AI rank order results while it matches the current query;
    // otherwise a stale payload reshuffles plain keyword searches.
    const aiMatchesSort = aiQueryActive
      && aiQueryData?.query.trim().toLowerCase() === committedQuery.trim().toLowerCase()
    const aiMatchedIds = aiMatchesSort ? aiQueryData?.results?.map((r) => r.id) || [] : []
    return sortProfiles(list, sortBy, committedQuery, aiMatchedIds)
  }, [committedQuery, showSavedOnly, isBookmarked, sortBy, filters, allProfiles, aiQueryData, aiQueryActive])

  // Keep first result selected in split-view if current selection is invalid
  useEffect(() => {
    if (results.length > 0) {
      if (!selectedProfileId || !results.some((r) => r.id === selectedProfileId)) {
        const firstProfile = results[0];
        if (firstProfile) setSelectedProfileId(firstProfile.id);
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
    const prevProfile = results[prevIdx];
    if (prevProfile) setSelectedProfileId(prevProfile.id);
  }, [results, currentSelectedIdx])

  const handleNextProfile = useCallback(() => {
    if (results.length === 0) return
    const nextIdx = currentSelectedIdx < results.length - 1 ? currentSelectedIdx + 1 : 0
    const nextProfile = results[nextIdx];
    if (nextProfile) setSelectedProfileId(nextProfile.id);
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
    openWorkspace,
    closeWorkspace,
  }
}
