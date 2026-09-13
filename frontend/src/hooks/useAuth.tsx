import { createContext, useCallback, useContext, useEffect, useRef, useState, ReactNode } from 'react'
import { useApolloClient, useMutation, useQuery } from '@apollo/client'
import { LOGIN_MUTATION, LOGOUT_MUTATION, ME_QUERY } from '../lib/queries'
import { clearLegacyAuthToken } from '../lib/apollo'

export interface AuthUser {
  id: string
  fullName: string
  email: string
  role?: string
}

interface AuthContextValue {
  user: AuthUser | null
  initialized: boolean
  isAuthenticated: boolean
  login: (email: string, password: string, _remember?: boolean) => Promise<{ ok: boolean; message?: string }>
  logout: () => Promise<void>
  refreshSession: () => Promise<void>
  loggingIn: boolean
  error: unknown
}

const AuthContext = createContext<AuthContextValue | null>(null)

interface SessionProfile {
  id: string
  fullName: string
  email: string
  role?: string | null
}

type SessionTransition = 'login' | 'logout' | 'refresh' | 'expired' | null

function mapSessionProfile(remote: SessionProfile | null | undefined): AuthUser | null {
  return remote
    ? { id: remote.id, fullName: remote.fullName, email: remote.email, role: remote.role ?? undefined }
    : null
}

function useAuthState(): AuthContextValue {
  const apolloClient = useApolloClient()
  const [user, setUser] = useState<AuthUser | null>(null)
  const [initialized, setInitialized] = useState(false)
  const sessionTransitionRef = useRef<SessionTransition>(null)
  const sessionGenerationRef = useRef(0)

  const [loginMutation, { loading: loggingIn, error }] = useMutation(LOGIN_MUTATION)
  const [logoutMutation] = useMutation(LOGOUT_MUTATION)
  const {
    data: sessionData,
    loading: sessionLoading,
    error: sessionError,
    refetch,
  } = useQuery(ME_QUERY, {
    fetchPolicy: 'network-only',
    errorPolicy: 'ignore',
  })

  useEffect(() => {
    clearLegacyAuthToken()
  }, [])

  useEffect(() => {
    if (!sessionLoading) {
      const remote = mapSessionProfile(sessionData?.me)
      if (sessionTransitionRef.current === null) {
        // A failed identity check must never preserve a previous account from
        // Apollo data. The session cookie is authoritative; without a
        // successful verification the public shell is the safe state.
        setUser(sessionError ? null : remote)
      }
      setInitialized(true)
    }
  }, [sessionData, sessionError, sessionLoading])

  useEffect(() => {
    const handleSessionExpired = () => {
      sessionGenerationRef.current += 1
      sessionTransitionRef.current = 'expired'
      setUser(null)
      clearLegacyAuthToken()
      void apolloClient.clearStore().catch(() => {
        // The public shell is still safe because auth state and the token are cleared.
      })
    }
    window.addEventListener('hydenlyne:session-expired', handleSessionExpired)
    return () => window.removeEventListener('hydenlyne:session-expired', handleSessionExpired)
  }, [apolloClient])

  const login = useCallback(
    async (email: string, password: string, _remember = true): Promise<{ ok: boolean; message?: string }> => {
      try {
        const { data } = await loginMutation({ variables: { email, password } })
        const result = data?.login
        if (result?.success) {
          // A login can replace an existing session without a preceding
          // logout (for example after a session expires or when switching
          // accounts). Clear account-scoped Apollo data before the new user
          // becomes visible so a cache-and-network observer cannot render the
          // previous account's records during the transition.
          try {
            await apolloClient.clearStore()
          } catch {
            // The new session's network-only queries and session gates remain
            // the source of truth if a cache observer cannot be cleared.
          }
          const u: AuthUser = {
            id: result.user?.id ?? '',
            fullName: result.user?.fullName ?? '',
            email: result.user?.email ?? email,
            role: result.user?.role ?? 'user',
          }
          // Browser sessions use the HttpOnly cookie set by the backend. Clear
          // any legacy bearer token instead of exposing a new one to storage.
          clearLegacyAuthToken()
          setUser(u)
          const generation = sessionGenerationRef.current + 1
          sessionGenerationRef.current = generation
          sessionTransitionRef.current = 'login'
          try {
            const refreshed = await refetch()
            if (sessionGenerationRef.current === generation) {
              const remote = mapSessionProfile(refreshed.data?.me)
              if (remote && remote.id === u.id) setUser(remote)
            }
          } catch {
            // The login mutation is authoritative if the follow-up session
            // check fails transiently.
          } finally {
            if (sessionGenerationRef.current === generation) {
              sessionTransitionRef.current = null
            }
          }
          return { ok: true }
        }
        return { ok: false, message: result?.message ?? 'Login failed' }
      } catch (e) {
        return { ok: false, message: e instanceof Error ? e.message : 'Login failed' }
      }
    },
    [apolloClient, loginMutation, refetch]
  )

  const logout = useCallback(async () => {
    const logoutGeneration = sessionGenerationRef.current + 1
    sessionGenerationRef.current = logoutGeneration
    sessionTransitionRef.current = 'logout'
    setUser(null)
    let logoutFailure: unknown = null
    try {
      await logoutMutation()
    } catch (error) {
      logoutFailure = error
    }
    // A new login may complete while the server-side logout is in flight.
    // Never clear that newer account's token or Apollo cache.
    if (sessionGenerationRef.current !== logoutGeneration) return
    clearLegacyAuthToken()
    try {
      await apolloClient.clearStore()
    } catch {
      // Logout must still complete locally if a cache observer fails.
    }
    if (logoutFailure) {
      throw logoutFailure instanceof Error
        ? logoutFailure
        : new Error('Could not confirm server-side logout')
    }
  }, [apolloClient, logoutMutation])

  const isAuthenticated = Boolean(user)

  const refreshSession = useCallback(async () => {
    const generation = sessionGenerationRef.current + 1
    sessionGenerationRef.current = generation
    sessionTransitionRef.current = 'refresh'
    try {
      const refreshed = await refetch()
      if (sessionGenerationRef.current === generation) {
        setUser(mapSessionProfile(refreshed.data?.me))
      }
    } catch (error) {
      if (sessionGenerationRef.current === generation) setUser(null)
      throw error
    } finally {
      if (sessionGenerationRef.current === generation) {
        sessionTransitionRef.current = null
      }
    }
  }, [refetch])

  return { user, initialized, isAuthenticated, login, logout, refreshSession, loggingIn, error }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const value = useAuthState()
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (ctx) return ctx
  throw new Error('useAuth must be used within AuthProvider — wrap your tree with <AuthProvider> in main.tsx')
}
