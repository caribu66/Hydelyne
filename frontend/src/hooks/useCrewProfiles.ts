import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useApolloClient, useQuery } from '@apollo/client'
import { CREW_MEMBERS_QUERY } from '../lib/queries'
import { backendCrewListToProfiles, BackendCrew } from '../lib/mappers'
import { MOCK_PROFILES } from '../data/mockProfiles'
import { DEMO_MODE_ENABLED } from '../config'
import { UserProfile } from '../types'
import { apolloResultHasErrors } from '../utils/sessionScope'

const PAGE_SIZE = 50
// Bound auto-pagination: first page + up to 4 more (250 records). Beyond
// that the caller pages on demand via loadMore/hasMore.
const MAX_AUTO_PAGES = 4

export function resolveCrewProfileState(
  raw: BackendCrew[] | undefined,
  loading: boolean,
  demoModeEnabled: boolean,
  hasError = false,
): { profiles: UserProfile[]; isLive: boolean; demoActive: boolean } {
  if (hasError) {
    // Retained Apollo data is not authoritative when the current request
    // failed. Keep the roster empty rather than showing a stale account scope.
    return { profiles: [], isLive: false, demoActive: false }
  }
  if (raw !== undefined) {
    if (raw.length === 0) {
      // An empty successful response is authoritative. Never replace it with
      // demo contractors, even when demo mode is enabled.
      return { profiles: [], isLive: true, demoActive: false }
    }
    try {
      return { profiles: backendCrewListToProfiles(raw), isLive: true, demoActive: false }
    } catch {
      // A live payload must never be replaced with unrelated demo records
      // after a mapper failure.
      return { profiles: [], isLive: false, demoActive: false }
    }
  }
  if (loading) {
    return { profiles: [], isLive: false, demoActive: false }
  }
  if (demoModeEnabled) {
    return { profiles: MOCK_PROFILES, isLive: false, demoActive: true }
  }
  return { profiles: [], isLive: false, demoActive: false }
}

export function useCrewProfiles(options?: {
  skip?: boolean
  sessionKey?: string | null
}): {
  profiles: UserProfile[]
  loading: boolean
  error: string | null
  isLive: boolean
  demoActive: boolean
  refetch: () => Promise<void>
  loadMore: () => void
  hasMore: boolean
} {
  const client = useApolloClient()
  const skip = options?.skip ?? false
  const sessionKey = options?.sessionKey ?? null
  const { data, loading, error, refetch } = useQuery(CREW_MEMBERS_QUERY, {
    variables: { limit: PAGE_SIZE, offset: 0 },
    // The roster is account-scoped: a cache-first leg can briefly render the
    // previous account's draft rows before the current session is verified.
    fetchPolicy: 'network-only',
    skip,
  })

  const firstPage = data?.crewMembers as BackendCrew[] | undefined
  const [allPages, setAllPages] = useState<BackendCrew[]>([])
  const [hasMore, setHasMore] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const loadingMoreEpochRef = useRef<number | null>(null)
  const fetchedForRef = useRef<BackendCrew[] | undefined>(undefined)
  const nextOffsetRef = useRef(PAGE_SIZE)
  const sessionEpochRef = useRef(0)
  const initialSessionRef = useRef(true)
  const sessionRefetchInFlightRef = useRef(false)
  const sessionRefetchFailedRef = useRef(false)
  const [sessionReady, setSessionReady] = useState(false)
  const [readySessionKey, setReadySessionKey] = useState<string | null>(null)

  useEffect(() => {
    sessionEpochRef.current += 1
    fetchedForRef.current = undefined
    nextOffsetRef.current = PAGE_SIZE
    setAllPages([])
    setHasMore(false)
    setLoadingMore(false)
    loadingMoreEpochRef.current = null
    setSessionReady(false)
    setReadySessionKey(null)
    sessionRefetchFailedRef.current = false

    if (!skip && !initialSessionRef.current) {
      const requestEpoch = sessionEpochRef.current
      sessionRefetchInFlightRef.current = true
      void refetch()
        .then((result) => {
          if (apolloResultHasErrors(result)) throw new Error('Roster refresh failed')
          if (requestEpoch === sessionEpochRef.current) {
            setSessionReady(true)
            setReadySessionKey(sessionKey)
          }
        })
        .catch(() => {
          // Keep the roster empty when the current account cannot be
          // verified; Apollo may retain the previous account's data after a
          // failed refetch, and that must never become a fallback.
          if (requestEpoch === sessionEpochRef.current) {
            sessionRefetchFailedRef.current = true
          }
        })
        .finally(() => {
          if (requestEpoch === sessionEpochRef.current) {
            sessionRefetchInFlightRef.current = false
          }
        })
    }
    initialSessionRef.current = false
  }, [refetch, sessionKey, skip])

  useEffect(() => {
    if (
      !skip
      && !loading
      && !sessionRefetchInFlightRef.current
      && !sessionRefetchFailedRef.current
    ) {
      setSessionReady(true)
      setReadySessionKey(sessionKey)
    }
  }, [firstPage, loading, sessionKey, skip])

  useEffect(() => {
    if (skip || !sessionReady || readySessionKey !== sessionKey) return
    if (!firstPage || firstPage.length < PAGE_SIZE) {
      fetchedForRef.current = firstPage
      setAllPages(firstPage ?? [])
      setHasMore(false)
      nextOffsetRef.current = PAGE_SIZE
      return
    }
    if (fetchedForRef.current === firstPage) return

    const requestEpoch = sessionEpochRef.current
    let cancelled = false
    void (async () => {
      const accumulated: BackendCrew[] = []
      let offset = PAGE_SIZE
      let pagesFetched = 0
      let moreAvailable = false
      try {
        while (pagesFetched < MAX_AUTO_PAGES) {
          const pageResult = await client.query({
            query: CREW_MEMBERS_QUERY,
            variables: { limit: PAGE_SIZE, offset },
            fetchPolicy: 'network-only',
          })
          if (apolloResultHasErrors(pageResult)) throw new Error('Roster page refresh failed')
          const pageData = pageResult.data
          const page = (pageData?.crewMembers as BackendCrew[] | undefined) ?? []
          accumulated.push(...page)
          offset += PAGE_SIZE
          pagesFetched += 1
          if (page.length < PAGE_SIZE) break
          if (pagesFetched >= MAX_AUTO_PAGES) moreAvailable = true
        }
      } catch {
        // Page fetch failed: keep what we have (at least the first page)
        // instead of leaving the UI stuck.
        moreAvailable = true
      }
      if (!cancelled && requestEpoch === sessionEpochRef.current) {
        fetchedForRef.current = firstPage
        setAllPages([...firstPage, ...accumulated])
        setHasMore(moreAvailable)
        nextOffsetRef.current = offset
      }
    })()

    return () => {
      cancelled = true
    }
  }, [firstPage, client, readySessionKey, sessionKey, sessionReady, skip])

  const loadMore = useCallback(async () => {
    if (
      skip
      || !sessionReady
      || readySessionKey !== sessionKey
      || loadingMore
      || loadingMoreEpochRef.current !== null
    ) return
    const requestEpoch = sessionEpochRef.current
    loadingMoreEpochRef.current = requestEpoch
    setLoadingMore(true)
    try {
      const pageResult = await client.query({
        query: CREW_MEMBERS_QUERY,
        variables: { limit: PAGE_SIZE, offset: nextOffsetRef.current },
        fetchPolicy: 'network-only',
      })
      if (apolloResultHasErrors(pageResult)) throw new Error('Roster page refresh failed')
      const pageData = pageResult.data
      const page = (pageData?.crewMembers as BackendCrew[] | undefined) ?? []
      if (requestEpoch !== sessionEpochRef.current) return
      nextOffsetRef.current += PAGE_SIZE
      if (page.length > 0) setAllPages((prev) => [...prev, ...page])
      setHasMore(page.length >= PAGE_SIZE)
    } catch {
      // Keep existing pages; caller can retry via loadMore.
      if (requestEpoch === sessionEpochRef.current) setHasMore(true)
    } finally {
      if (loadingMoreEpochRef.current === requestEpoch) {
        loadingMoreEpochRef.current = null
        if (requestEpoch === sessionEpochRef.current) setLoadingMore(false)
      }
    }
  }, [client, loadingMore, readySessionKey, sessionKey, sessionReady, skip])

  const { profiles, isLive, demoActive } = useMemo(() => {
    if (skip || !sessionReady || readySessionKey !== sessionKey) {
      return { profiles: [], isLive: false, demoActive: false }
    }
    const raw = allPages.length > 0 ? allPages : firstPage
    return resolveCrewProfileState(raw, loading, DEMO_MODE_ENABLED, Boolean(error))
  }, [allPages, error, firstPage, loading, readySessionKey, sessionKey, sessionReady, skip])

  return {
    profiles,
    loading,
    error: error ? error.message : null,
    isLive,
    demoActive,
    refetch: async () => {
      const result = await refetch()
      if (apolloResultHasErrors(result)) throw new Error('Roster refresh failed')
    },
    loadMore,
    hasMore,
  }
}
