import { useMemo } from 'react'
import { useQuery } from '@apollo/client'
import { CREW_MEMBERS_QUERY } from '../lib/queries'
import { backendCrewListToProfiles, BackendCrew } from '../lib/mappers'
import { MOCK_PROFILES } from '../data/mockProfiles'
import { DEMO_MODE_ENABLED } from '../config'
import { UserProfile } from '../types'

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
  const { data, loading, error, refetch } = useQuery(CREW_MEMBERS_QUERY, {
    variables: { limit: 100, offset: 0 },
    fetchPolicy: 'cache-and-network',
    // Don't fire the query until the user has signed in (avoids a 401 storm on the login screen).
    skip: options?.skip,
  })

  const { profiles, isLive, demoActive } = useMemo(() => {
    const raw = data?.crewMembers as BackendCrew[] | undefined
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
  }, [data, loading])

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