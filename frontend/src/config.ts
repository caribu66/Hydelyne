const meta = import.meta as unknown as {
  env?: Record<string, string | undefined>
  DEV?: boolean
}

const env: Record<string, string | undefined> = meta.env ?? {}

export const GRAPHQL_URL: string =
  env.VITE_GRAPHQL_URL || env.VITE_API_URL || 'http://localhost:8000/graphql'

/**
 * Demo mode controls the mock-profile fallback. It is opt-in in every build so
 * an authenticated account with an empty or unavailable roster cannot be
 * mistaken for a populated live account.
 */
export const DEMO_MODE_ENABLED: boolean =
  env.VITE_ENABLE_DEMO_MODE === 'true'
