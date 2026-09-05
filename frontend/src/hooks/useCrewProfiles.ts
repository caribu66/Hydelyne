import { useEffect, useMemo, useRef, useState } from 'react'
import { useApolloClient, useQuery } from '@apollo/client'
import { CREW_MEMBERS_QUERY } from '../lib/queries'
import { backendCrewListToProfiles, BackendCrew } from '../lib/mappers'
import { MOCK_PROFILES } from '../data/mockProfiles'
import { DEMO_MODE_ENABLED } from '../config'
import { UserProfile } from '../types'

// The backend caps a single page at 100 records ("Enforce pagination limits
// to avoid abuse" - backend/app/graphql/schema.py's crew_members resolver
// clamps limit to <= 100 regardless of what's requested), so raising this
// constant alone would not fix anything past the first page. The crew
// network already exceeds 100 (109 real records at last count), so a
// one-shot fetch silently truncated the list used for browsing, filtering,
// and intersecting AI search matches - up to 9 real specialists were
// invisible everywhere in the app with no error or indication.
const PAGE_SIZE = 100

export function useCrewProfiles(options?: {
  skip?: boolean
}): {
  profiles: UserProfile[]
  loading: boolean
  error: string | null
  isLive: boolean
  demoActive: boolean
  refetch: () => void
} {
  const client = useApolloClient()
  const { data, loading, error, refetch } = useQuery(CREW_MEMBERS_QUERY, {
    variables: { limit: PAGE_SIZE, offset: 0 },
    fetchPolicy: 'cache-and-network',
    // Don't fire the query until the user has signed in (avoids a 401 storm on the login screen).
    skip: options?.skip,
  })

  const firstPage = data?.crewMembers as BackendCrew[] | undefined

  // A full first page (exactly PAGE_SIZE records) means there may be more -
  // page through the rest. Tracked by reference to the page-1 array so this
  // re-runs after a real refetch (a new array from the network) but not on
  // every unrelated re-render.
  const [remainingPages, setRemainingPages] = useState<BackendCrew[]>([])
  const fetchedForRef = useRef<BackendCrew[] | undefined>(undefined)

  useEffect(() => {
    if (!firstPage || firstPage.length < PAGE_SIZE) {
      fetchedForRef.current = firstPage
      setRemainingPages([])
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
        setRemainingPages(accumulated)
      }
    })()

    return () => {
      cancelled = true
    }
  }, [firstPage, client])

  const { profiles, isLive, demoActive } = useMemo(() => {
    const raw = firstPage ? [...firstPage, ...remainingPages] : undefined
    if (raw && raw.length > 0) {
      try {
        return { profiles: backendCrewListToProfiles(raw), isLive: true, demoActive: false }
      } catch {
        // fall through to demo/empty handling on mapper error
      }
    }
    // No live data (empty, error, or still loading).
    if (loading && !raw) {
      return { profiles: [], isLive: false, demoActive: false }
    }
    // Demo mode: fabricate mock profiles so the UI stays usable in dev/showcase.
    if (DEMO_MODE_ENABLED) {
      return { profiles: MOCK_PROFILES, isLive: false, demoActive: true }
    }
    // Production: never show fabricated data. Empty list -> UI declares live data required.
    return { profiles: [], isLive: false, demoActive: false }
  }, [firstPage, remainingPages, loading])

  return {
    profiles,
    loading,
    error: error ? error.message : null,
    isLive,
    demoActive,
    refetch: () => {
      void refetch()
    },
  }
}
