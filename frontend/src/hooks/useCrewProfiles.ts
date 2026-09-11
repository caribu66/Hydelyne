import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useApolloClient, useQuery } from '@apollo/client'
import { CREW_MEMBERS_QUERY } from '../lib/queries'
import { backendCrewListToProfiles, BackendCrew } from '../lib/mappers'
import { MOCK_PROFILES } from '../data/mockProfiles'
import { DEMO_MODE_ENABLED } from '../config'
import { UserProfile } from '../types'

const PAGE_SIZE = 50
// Bound auto-pagination: first page + up to 4 more (250 records). Beyond
// that the caller pages on demand via loadMore/hasMore.
const MAX_AUTO_PAGES = 4

export function useCrewProfiles(options?: {
  skip?: boolean
}): {
  profiles: UserProfile[]
  loading: boolean
  error: string | null
  isLive: boolean
  demoActive: boolean
  refetch: () => void
  loadMore: () => void
  hasMore: boolean
} {
  const client = useApolloClient()
  const { data, loading, error, refetch } = useQuery(CREW_MEMBERS_QUERY, {
    variables: { limit: PAGE_SIZE, offset: 0 },
    fetchPolicy: 'cache-and-network',
    skip: options?.skip,
  })

  const firstPage = data?.crewMembers as BackendCrew[] | undefined
  const [allPages, setAllPages] = useState<BackendCrew[]>([])
  const [hasMore, setHasMore] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const fetchedForRef = useRef<BackendCrew[] | undefined>(undefined)
  const nextOffsetRef = useRef(PAGE_SIZE)

  useEffect(() => {
    if (!firstPage || firstPage.length < PAGE_SIZE) {
      fetchedForRef.current = firstPage
      setAllPages(firstPage ?? [])
      setHasMore(false)
      nextOffsetRef.current = PAGE_SIZE
      return
    }
    if (fetchedForRef.current === firstPage) return

    let cancelled = false
    void (async () => {
      const accumulated: BackendCrew[] = []
      let offset = PAGE_SIZE
      let pagesFetched = 0
      let moreAvailable = false
      try {
        while (pagesFetched < MAX_AUTO_PAGES) {
          const { data: pageData } = await client.query({
            query: CREW_MEMBERS_QUERY,
            variables: { limit: PAGE_SIZE, offset },
            fetchPolicy: 'network-only',
          })
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
      if (!cancelled) {
        fetchedForRef.current = firstPage
        setAllPages([...firstPage, ...accumulated])
        setHasMore(moreAvailable)
        nextOffsetRef.current = offset
      }
    })()

    return () => {
      cancelled = true
    }
  }, [firstPage, client])

  const loadMore = useCallback(async () => {
    if (loadingMore) return
    setLoadingMore(true)
    try {
      const { data: pageData } = await client.query({
        query: CREW_MEMBERS_QUERY,
        variables: { limit: PAGE_SIZE, offset: nextOffsetRef.current },
        fetchPolicy: 'network-only',
      })
      const page = (pageData?.crewMembers as BackendCrew[] | undefined) ?? []
      nextOffsetRef.current += PAGE_SIZE
      if (page.length > 0) setAllPages((prev) => [...prev, ...page])
      setHasMore(page.length >= PAGE_SIZE)
    } catch {
      // Keep existing pages; caller can retry via loadMore.
      setHasMore(true)
    } finally {
      setLoadingMore(false)
    }
  }, [client, loadingMore])

  const { profiles, isLive, demoActive } = useMemo(() => {
    const raw = allPages.length > 0 ? allPages : firstPage
    if (raw && raw.length > 0) {
      try {
        return { profiles: backendCrewListToProfiles(raw), isLive: true, demoActive: false }
      } catch {
        // fall through to demo/empty handling on mapper error
      }
    }
    if (loading && !raw) {
      return { profiles: [], isLive: false, demoActive: false }
    }
    if (DEMO_MODE_ENABLED) {
      return { profiles: MOCK_PROFILES, isLive: false, demoActive: true }
    }
    return { profiles: [], isLive: false, demoActive: false }
  }, [firstPage, allPages, loading])

  return {
    profiles,
    loading,
    error: error ? error.message : null,
    isLive,
    demoActive,
    refetch: () => {
      void refetch()
    },
    loadMore,
    hasMore,
  }
}
