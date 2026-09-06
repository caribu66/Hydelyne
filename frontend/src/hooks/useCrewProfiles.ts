import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useApolloClient, useQuery } from '@apollo/client'
import { CREW_MEMBERS_QUERY } from '../lib/queries'
import { backendCrewListToProfiles, BackendCrew } from '../lib/mappers'
import { MOCK_PROFILES } from '../data/mockProfiles'
import { DEMO_MODE_ENABLED } from '../config'
import { UserProfile } from '../types'

const PAGE_SIZE = 50

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
  const fetchedForRef = useRef<BackendCrew[] | undefined>(undefined)

  useEffect(() => {
    if (!firstPage || firstPage.length < PAGE_SIZE) {
      fetchedForRef.current = firstPage
      setAllPages(firstPage ?? [])
      setHasMore(false)
      return
    }
    if (fetchedForRef.current === firstPage) return

    let cancelled = false
    void (async () => {
      const accumulated: BackendCrew[] = []
      let offset = PAGE_SIZE
      for (;;) {
        const { data: pageData } = await client.query({
          query: CREW_MEMBERS_QUERY,
          variables: { limit: PAGE_SIZE, offset },
          fetchPolicy: 'network-only',
        })
        const page = (pageData?.crewMembers as BackendCrew[] | undefined) ?? []
        accumulated.push(...page)
        if (page.length < PAGE_SIZE) break
        offset += PAGE_SIZE
      }
      if (!cancelled) {
        fetchedForRef.current = firstPage
        setAllPages([...firstPage, ...accumulated])
        setHasMore(false)
      }
    })()

    return () => {
      cancelled = true
    }
  }, [firstPage, client])

  const loadMore = useCallback(() => {
    // Future: trigger next-page fetch on demand when dataset grows past
    // the auto-paginated threshold. Currently auto-pagination loads all
    // records, so this is a no-op until the auto-pagination limit is reached.
  }, [])

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
