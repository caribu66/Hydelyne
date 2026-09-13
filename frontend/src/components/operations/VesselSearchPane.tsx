import { FC, FormEvent, useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@apollo/client'
import { ChevronDown, ChevronUp, Filter, Loader2, Search, Ship, UserPlus, Users, X } from 'lucide-react'
import { SEARCH_VESSELS_QUERY, VESSEL_ROSTER_QUERY } from '../../lib/queries'
import { CampaignAssignment } from '../../types'
import { formatAssignmentStatus } from '../../utils/assignmentUtils'
import { apolloResultHasErrors, isSessionDataReady, isSessionQueryEnabled } from '../../utils/sessionScope'
import { VesselForMobilization, VesselMobilizationModal } from './VesselMobilizationModal'
import { isVesselSearchSessionReady } from './vesselSearchUtils'

export type VesselIdType = 'imo' | 'mmsi' | 'eni'

export interface VesselSummary {
  id: string
  name: string | null
  imo: string | null
  mmsi: string | null
  callsign: string | null
  vesselType: string | null
  flag: string | null
  length: number | null
  width: number | null
  yearBuilt: number | null
}

export interface VesselSearchResponse {
  vessels: VesselSummary[]
  cached: boolean
  provider: string
  upstreamCount: number | null
  configured: boolean
}

interface VesselRosterSectionProps {
  imo: string
  id: string
  isAdmin: boolean
  sessionKey: string | null | undefined
  onMobilize?: () => void
}

export const VesselRosterSection: FC<VesselRosterSectionProps> = ({
  imo,
  id,
  isAdmin,
  sessionKey,
  onMobilize,
}) => {
  const { data, loading, error, refetch } = useQuery<{ vesselRoster: CampaignAssignment[] }>(
    VESSEL_ROSTER_QUERY,
    {
      variables: { imo },
      fetchPolicy: 'network-only',
      skip: !sessionKey,
    }
  )

  const [loadedSessionKey, setLoadedSessionKey] = useState<string | null>(null)
  const scopeKey = sessionKey ? `${sessionKey}:${imo}` : null
  const previousScopeKeyRef = useRef<string | null>(null)
  const refreshPendingScopeKeyRef = useRef<string | null>(null)
  const hasCommittedRosterRef = useRef(false)
  const [visibleRoster, setVisibleRoster] = useState<CampaignAssignment[] | undefined>(undefined)

  useEffect(() => {
    const previousScopeKey = previousScopeKeyRef.current
    previousScopeKeyRef.current = scopeKey
    hasCommittedRosterRef.current = false
    setVisibleRoster(undefined)
    setLoadedSessionKey(null)
    refreshPendingScopeKeyRef.current = null
    if (!scopeKey || previousScopeKey === null) return

    refreshPendingScopeKeyRef.current = scopeKey
    let active = true
    void refetch({ imo })
      .then((result) => {
        if (apolloResultHasErrors(result)) throw new Error('Vessel roster refresh failed')
        if (active && refreshPendingScopeKeyRef.current === scopeKey) {
          hasCommittedRosterRef.current = true
          setVisibleRoster(result.data?.vesselRoster ?? [])
          setLoadedSessionKey(scopeKey)
        }
      })
      .catch(() => {})
      .finally(() => {
        if (refreshPendingScopeKeyRef.current === scopeKey) {
          refreshPendingScopeKeyRef.current = null
        }
      })
    return () => {
      active = false
    }
  }, [imo, refetch, scopeKey])

  useEffect(() => {
    if (
      scopeKey
      && loadedSessionKey === scopeKey
      && !hasCommittedRosterRef.current
    ) {
      hasCommittedRosterRef.current = true
      setVisibleRoster(data?.vesselRoster ?? [])
    }
  }, [data, loadedSessionKey, scopeKey])

  useEffect(() => {
    if (
      scopeKey
      && !loading
      && !error
      && refreshPendingScopeKeyRef.current !== scopeKey
    ) setLoadedSessionKey(scopeKey)
  }, [error, loading, scopeKey])

  const rosterReady = isSessionDataReady(Boolean(scopeKey), loadedSessionKey, scopeKey, loading, error)
  const roster = rosterReady ? visibleRoster ?? [] : []

  return (
    <div
      id={id}
      className="mt-2.5 rounded-lg border border-border-subtle bg-canvas/60 p-3 text-xs"
      role="region"
      aria-label={`Crew roster for IMO ${imo}`}
    >
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-primary">Assigned specialists</span>
          <span className="font-mono text-muted">
            {loading ? 'Checking roster…' : `(${roster.length})`}
          </span>
        </div>
        {onMobilize && (
          <button
            type="button"
            onClick={onMobilize}
            className="inline-flex items-center gap-1 text-xs font-semibold text-accent hover:underline cursor-pointer"
          >
            <UserPlus className="h-3.5 w-3.5" aria-hidden="true" />
            <span>+ Mobilize</span>
          </button>
        )}
      </div>

      {loading ? (
        <div className="flex items-center gap-2 py-2 text-muted">
          <Loader2 className="h-3.5 w-3.5 animate-spin text-muted" aria-hidden="true" />
          <span>Loading vessel roster…</span>
        </div>
      ) : error ? (
        <p className="text-muted py-1">Unable to load crew roster for this vessel.</p>
      ) : roster.length === 0 ? (
        <div className="flex flex-wrap items-center justify-between gap-2 py-1">
          <p className="text-muted">No specialists currently assigned to this vessel.</p>
          {onMobilize && (
            <button
              type="button"
              onClick={onMobilize}
              className="inline-flex items-center gap-1 text-xs font-semibold text-accent hover:underline cursor-pointer"
            >
              <UserPlus className="h-3.5 w-3.5" aria-hidden="true" />
              <span>Mobilize specialist</span>
            </button>
          )}
        </div>
      ) : (
        <div className="divide-y divide-border-subtle/50">
          {roster.map((assignment) => {
            const { label, badgeClass } = formatAssignmentStatus(assignment.status)

            return (
              <div key={assignment.id} className="flex flex-col gap-1 py-2 first:pt-0 last:pb-0">
                <div className="flex flex-wrap items-center justify-between gap-1.5">
                  <div className="flex items-center gap-1.5">
                    <span className="font-semibold text-primary">
                      {assignment.crewName || 'Specialist'}
                    </span>
                    <span className="text-muted">·</span>
                    <span className="text-secondary">{assignment.roleOnBoard}</span>
                  </div>
                  <span className={`rounded px-1.5 py-0.5 text-xs font-mono uppercase ${badgeClass}`}>
                    {label}
                  </span>
                </div>
                <div className="flex flex-wrap items-center gap-x-3 text-secondary font-mono text-xs">
                  <span>
                    Rotation: {assignment.startDate} → {assignment.endDate}
                  </span>
                  {assignment.projectName && (
                    <span>Project: {assignment.projectName}</span>
                  )}
                  {isAdmin && assignment.agreedDayRate != null && (
                    <span>£{assignment.agreedDayRate}/d</span>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

export interface VesselSearchPaneProps {
  onShowToast?: (message: string) => void
  isAdmin: boolean
  sessionKey?: string | null
}

export const VesselSearchPane: FC<VesselSearchPaneProps> = ({
  onShowToast,
  isAdmin,
  sessionKey = null,
}) => {
  const [query, setQuery] = useState('')
  const [searchedQuery, setSearchedQuery] = useState('')
  const [expandedImo, setExpandedImo] = useState<string | null>(null)
  const [mobilizingVessel, setMobilizingVessel] = useState<VesselForMobilization | null>(null)
  const previousSessionKeyRef = useRef<string | null>(null)
  const currentSessionKeyRef = useRef(sessionKey)
  const requestVersionRef = useRef(0)
  const refreshPendingSessionKeyRef = useRef<string | null>(null)
  const hasIssuedSearchRef = useRef(false)
  const [loadedSessionKey, setLoadedSessionKey] = useState<string | null>(null)
  const [visibleSearchResult, setVisibleSearchResult] = useState<VesselSearchResponse | undefined>(undefined)
  currentSessionKeyRef.current = sessionKey

  const handleOpenMobilization = (v: VesselSummary) => {
    if (!v.imo) return
    setMobilizingVessel({
      imo: v.imo,
      name: v.name || `Vessel ${v.imo}`,
      vesselType: v.vesselType,
      flag: v.flag,
      callsign: v.callsign,
    })
  }


  const { data, loading, error, refetch } = useQuery<{ vesselSearch: VesselSearchResponse }>(
    SEARCH_VESSELS_QUERY,
    {
      variables: { name: '', limit: 20 },
      fetchPolicy: 'network-only',
      skip: !isSessionQueryEnabled(true, sessionKey),
    }
  )

  useEffect(() => {
    requestVersionRef.current += 1
    hasIssuedSearchRef.current = false
    setVisibleSearchResult(undefined)
    setLoadedSessionKey(null)
    setSearchedQuery('')
    setExpandedImo(null)
    setMobilizingVessel(null)
    refreshPendingSessionKeyRef.current = null
    if (!sessionKey) {
      previousSessionKeyRef.current = null
      return
    }
    const sessionChanged =
      previousSessionKeyRef.current !== null && previousSessionKeyRef.current !== sessionKey
    previousSessionKeyRef.current = sessionKey
    if (sessionChanged) {
      refreshPendingSessionKeyRef.current = sessionKey
      void refetch({ name: '', limit: 20 })
        .then((result) => {
          if (apolloResultHasErrors(result)) throw new Error('Vessel search refresh failed')
        })
        .catch(() => {})
        .finally(() => {
          if (refreshPendingSessionKeyRef.current === sessionKey) {
            refreshPendingSessionKeyRef.current = null
          }
        })
    }
  }, [refetch, sessionKey])

  useEffect(() => {
    if (sessionKey && loadedSessionKey === sessionKey && !hasIssuedSearchRef.current) {
      setVisibleSearchResult(data?.vesselSearch)
    }
  }, [data, loadedSessionKey, sessionKey])

  useEffect(() => {
    if (
      sessionKey
      && !loading
      && !error
      && refreshPendingSessionKeyRef.current !== sessionKey
    ) setLoadedSessionKey(sessionKey)
  }, [error, loading, sessionKey])

  // Apollo can retain the previous successful result after a later search
  // fails. Do not expose that result while the current request is errored.
  const sessionReady = isVesselSearchSessionReady(loadedSessionKey, sessionKey, loading, error)
  const searchResult = sessionReady ? visibleSearchResult : undefined
  const isConfigured = searchResult?.configured !== false
  const vessels = useMemo(() => searchResult?.vessels ?? [], [searchResult?.vessels])
  const isCached = searchResult?.cached ?? false

  const [typeFilter, setTypeFilter] = useState<'all' | 'survey' | 'offshore' | 'support'>('all')

  const displayedVessels = useMemo(() => {
    if (typeFilter === 'all') return vessels
    return vessels.filter((v) => {
      const t = (v.vesselType || '').toLowerCase()
      if (typeFilter === 'survey') return t.includes('survey') || t.includes('research') || t.includes('seismic')
      if (typeFilter === 'offshore') return t.includes('offshore') || t.includes('supply') || t.includes('platform')
      if (typeFilter === 'support') return t.includes('tug') || t.includes('support') || t.includes('utility')
      return true
    })
  }, [vessels, typeFilter])

  const handleSearch = async (term: string) => {
    const trimmed = term.trim()
    if (!trimmed || !sessionKey || currentSessionKeyRef.current !== sessionKey) return
    const requestVersion = ++requestVersionRef.current
    hasIssuedSearchRef.current = true
    try {
      const result = await refetch({ name: trimmed, limit: 20 })
      if (requestVersion !== requestVersionRef.current || currentSessionKeyRef.current !== sessionKey) return
      if (apolloResultHasErrors(result)) throw new Error('Vessel search failed')
      setVisibleSearchResult(result.data?.vesselSearch)
      setSearchedQuery(trimmed)
    } catch {
      // Handled via Apollo error state
    }
  }

  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    void handleSearch(query)
  }

  return (
    <div className="mt-3 flex flex-col gap-3">
      {/* Quick filter chips */}
      <div className="flex flex-wrap items-center gap-1.5 pb-0.5">
        <span className="text-xs text-muted flex items-center gap-1 mr-1">
          <Filter className="h-3 w-3" aria-hidden="true" />
          Filter:
        </span>
        {[
          { id: 'all', label: 'All vessels' },
          { id: 'survey', label: 'Survey & Research' },
          { id: 'offshore', label: 'Offshore & Supply' },
          { id: 'support', label: 'Support & Tug' },
        ].map((chip) => {
          const isActive = typeFilter === chip.id
          return (
            <button
              key={chip.id}
              type="button"
              onClick={() => setTypeFilter(chip.id as typeof typeFilter)}
              className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus ${
                isActive
                  ? 'bg-accent-soft border border-border-strong text-accent font-semibold shadow-xs'
                  : 'bg-surface-raised border border-border-subtle text-secondary hover:text-primary hover:bg-surface-selected'
              }`}
            >
              {chip.label}
            </button>
          )
        })}
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-2 sm:flex-row">
        <div className="relative flex-1">
          <label htmlFor="vessel-search-input" className="sr-only">
            Search vessels
          </label>
          <input
            id="vessel-search-input"
            type="search"
            placeholder="Search vessel name, IMO, MMSI, or callsign…"
            className="w-full min-h-11 rounded-lg border border-border-subtle bg-surface px-3.5 pr-9 py-2 text-sm text-primary placeholder:text-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus transition-colors"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          {query && (
            <button
              type="button"
              onClick={() => {
                if (!sessionKey || currentSessionKeyRef.current !== sessionKey) return
                const requestVersion = ++requestVersionRef.current
                hasIssuedSearchRef.current = true
                setQuery('')
                void refetch({ name: '', limit: 20 })
                  .then((result) => {
                    if (requestVersion !== requestVersionRef.current || currentSessionKeyRef.current !== sessionKey) return
                    if (apolloResultHasErrors(result)) throw new Error('Vessel search failed')
                    setVisibleSearchResult(result.data?.vesselSearch)
                    setSearchedQuery('')
                  })
                  .catch(() => {})
              }}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 p-1 text-muted hover:text-primary transition-colors cursor-pointer rounded-full"
              aria-label="Clear vessel search"
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          )}
        </div>
        <button
          type="submit"
          disabled={loading || !query.trim()}
          className="inline-flex min-h-11 items-center justify-center gap-1.5 rounded-lg bg-action px-4 py-2 text-xs font-semibold text-on-action transition-colors hover:bg-action-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus disabled:opacity-50 cursor-pointer shrink-0"
          aria-label="Submit vessel search"
        >
          {loading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin text-on-action" aria-hidden="true" />
              <span>Searching…</span>
            </>
          ) : (
            <>
              <Search className="h-4 w-4 text-on-action" aria-hidden="true" />
              <span>Search vessels</span>
            </>
          )}
        </button>
      </form>

      {!isConfigured && (
        <div
          role="status"
          className="rounded-[10px] border border-border-subtle bg-surface-raised/40 p-3.5 text-xs text-secondary flex items-start gap-2.5"
        >
          <Ship className="h-4 w-4 text-muted shrink-0 mt-0.5" aria-hidden="true" />
          <div>
            <p className="font-semibold text-primary">Live AIS vessel tracking unconfigured</p>
            <p className="mt-0.5 text-muted">
              Live tracking requires a valid <code className="font-mono text-primary">VESSELAPI_API_KEY</code> on the backend.
            </p>
          </div>
        </div>
      )}

      {error && isConfigured && (
        <p className="rounded-[10px] border border-border-subtle bg-surface-raised/30 p-3 text-xs text-muted" role="alert">
          Unable to complete vessel lookup: {error.message}
        </p>
      )}

      {searchedQuery && !loading && isConfigured && !error && displayedVessels.length === 0 && (
        <p className="rounded-[10px] border border-border-subtle bg-surface-raised/30 p-4 text-center text-xs text-muted">
          No vessels found matching “{searchedQuery}”.
        </p>
      )}

      {displayedVessels.length > 0 && (
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between px-1 text-xs text-secondary">
            <span>
              Found <strong className="font-semibold text-primary">{displayedVessels.length}</strong> {displayedVessels.length === 1 ? 'vessel' : 'vessels'}
            </span>
            {isCached && (
              <span className="badge-neutral rounded-md px-1.5 py-0.5 font-mono text-xs">
                Cached
              </span>
            )}
          </div>

          <div
            className="divide-y divide-border-subtle/60 rounded-[10px] border border-border-subtle bg-surface-raised/20 overflow-hidden"
            role="region"
            aria-label="Vessel search results"
          >
            {displayedVessels.map((vessel) => (
              <div
                key={vessel.id || vessel.imo || vessel.mmsi || vessel.name}
                className="flex flex-col gap-1.5 p-3 hover:bg-surface-raised/40 transition-colors"
              >
                <div className="flex flex-wrap items-baseline justify-between gap-x-2 gap-y-1">
                  <span className="text-sm font-semibold text-primary">
                    {vessel.name || 'Unnamed Vessel'}
                  </span>
                  <div className="flex items-center gap-1.5">
                    {vessel.vesselType && (
                      <span className="badge-neutral rounded-md px-2 py-0.5 text-xs font-mono">
                        {vessel.vesselType}
                      </span>
                    )}
                    {vessel.flag && (
                      <span className="badge-neutral rounded-md px-2 py-0.5 text-xs font-mono">
                        {vessel.flag}
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex flex-wrap items-center justify-between gap-2 pt-1 border-t border-border-subtle/40">
                  <div className="flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-xs text-secondary">
                    {vessel.imo && (
                      <span>
                        IMO: <span className="text-primary">{vessel.imo}</span>
                      </span>
                    )}
                    {vessel.mmsi && (
                      <span>
                        MMSI: <span className="text-primary">{vessel.mmsi}</span>
                      </span>
                    )}
                    {vessel.callsign && (
                      <span>
                        Callsign: <span className="text-primary">{vessel.callsign}</span>
                      </span>
                    )}
                    {(vessel.length !== null || vessel.width !== null) && (
                      <span>
                        Dim: <span className="text-primary">{vessel.length ?? '—'}m × {vessel.width ?? '—'}m</span>
                      </span>
                    )}
                    {vessel.yearBuilt && (
                      <span>
                        Built: <span className="text-primary">{vessel.yearBuilt}</span>
                      </span>
                    )}
                  </div>

                  {vessel.imo && (
                    <div className="flex items-center gap-2 shrink-0">
                      <button
                        type="button"
                        onClick={() => handleOpenMobilization(vessel)}
                        className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-accent/40 bg-accent-soft/40 px-2.5 py-1 text-xs font-semibold text-accent hover:bg-accent-soft/80 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus cursor-pointer shrink-0"
                        aria-label={`Mobilize specialist to ${vessel.name || vessel.imo}`}
                      >
                        <UserPlus className="h-3.5 w-3.5" aria-hidden="true" />
                        <span>Mobilize</span>
                      </button>

                      <button
                        type="button"
                        onClick={() => setExpandedImo(expandedImo === vessel.imo ? null : vessel.imo)}
                        className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-border-subtle bg-surface-raised px-2.5 py-1 text-xs font-medium text-secondary hover:text-primary hover:bg-surface-selected transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus cursor-pointer shrink-0"
                        aria-expanded={expandedImo === vessel.imo}
                        aria-controls={`vessel-roster-${vessel.imo}`}
                      >
                        <Users className="h-3.5 w-3.5" aria-hidden="true" />
                        <span>{expandedImo === vessel.imo ? 'Hide roster' : 'Crew roster'}</span>
                        {expandedImo === vessel.imo ? (
                          <ChevronUp className="h-3.5 w-3.5 text-muted" aria-hidden="true" />
                        ) : (
                          <ChevronDown className="h-3.5 w-3.5 text-muted" aria-hidden="true" />
                        )}
                      </button>
                    </div>
                  )}
                </div>

                {vessel.imo && expandedImo === vessel.imo && (
                  <VesselRosterSection
                    imo={vessel.imo}
                    id={`vessel-roster-${vessel.imo}`}
                    isAdmin={isAdmin}
                    sessionKey={sessionKey}
                    onMobilize={() => handleOpenMobilization(vessel)}
                  />
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      <VesselMobilizationModal
        key={sessionKey ?? 'no-session'}
        isOpen={mobilizingVessel !== null}
        onClose={() => setMobilizingVessel(null)}
        vessel={mobilizingVessel}
        isAdmin={isAdmin}
        sessionKey={sessionKey}
        onShowToast={onShowToast || (() => {})}
      />
    </div>
  )
}
