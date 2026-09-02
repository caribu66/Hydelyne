const meta = import.meta as unknown as {
  env?: Record<string, string | undefined>
  DEV?: boolean
}

const env: Record<string, string | undefined> = meta.env ?? {}

export const GRAPHQL_URL: string =
  env.VITE_GRAPHQL_URL || env.VITE_API_URL || 'http://localhost:8000/graphql'

/**
 * Demo mode controls the mock-profile fallback.
 * - In dev builds (import.meta.env.DEV) it's ON by default so the UI never looks empty.
 * - In production builds it's OFF unless explicitly enabled (VITE_ENABLE_DEMO_MODE=true),
 *   so fabricated consultants are never shown against live infrastructure.
 */
export const DEMO_MODE_ENABLED: boolean =
  env.VITE_ENABLE_DEMO_MODE === 'true' ||
  (env.VITE_ENABLE_DEMO_MODE !== 'false' && meta.DEV === true)