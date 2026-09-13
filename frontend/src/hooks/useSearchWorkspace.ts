import { useState, useEffect, useMemo, useCallback, type Dispatch, type SetStateAction } from 'react'
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

function mapAIAvailability(value?: string): UserProfile['availability'] {
  switch (value?.toLowerCase()) {
    case 'available':
      return 'Available immediately'
    case 'on_assignment':
      return 'Employed (Not looking)'
    case 'unavailable':
      return 'Unavailable'
    default:
      return 'Unavailable'
  }
}

/** Resolve the backend's authoritative AI result set against the loaded roster. */
export function selectAIResultProfiles(
  allProfiles: UserProfile[],
  aiResults: CrewQueryResult['results'],
): UserProfile[] {
  const localMap = new Map(allProfiles.map((profile) => [profile.id, profile]))
  return aiResults.map((ai) => {
    const local = localMap.get(ai.id)
    if (local) return local

    return {
      id: ai.id,
      name: ai.name,
      title: ai.tags?.[0] ? `${ai.tags[0]} Contractor` : 'Contractor',
      avatar: '',
      company: 'Company not recorded',
      department: '',
      location: ai.country_of_residence ?? 'Location not recorded',
      remoteType: 'On-site',
      yearsOfExperience: ai.experience_years
        ?? (ai.experience_months != null ? Math.round(ai.experience_months / 12) : null),
      skills: ai.tags ?? [],
      bio: ai.professional_summary ?? 'Professional summary not recorded.',
      availability: mapAIAvailability(ai.availability),
      education: ai.education ?? 'Education not recorded',
      nationality: ai.nationality,
      countryOfResidence: ai.country_of_residence,
      languages: ai.languages,
      flyingPoint: ai.flying_point,
      geographicalExperience: ai.geographical_experience,
      systemsExperience: ai.systems_experience,
      trainingQualifications: ai.training_qualifications,
      email: ai.email ?? '',
      certifications: ai.certifications ?? [],
      workHistory: [],
    }
  })
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
  setSelectedProfileId: Dispatch<SetStateAction<string | null>>
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
      const aiMatchesCurrentQuery = aiQueryActive
        && aiQueryData?.query.trim().toLowerCase() === committedQuery.trim().toLowerCase()

        if (aiMatchesCurrentQuery) {
          // Trust the backend AI result set as the source of truth, including
          // an intentional empty result set. Otherwise a no-match response
          // falls through to local keyword matching and shows unrelated rows.
          list = selectAIResultProfiles(allProfiles, aiQueryData.results)
          list = filterProfiles(list, { ...filters, keyword: '' })
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
