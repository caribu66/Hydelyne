import { createContext, useCallback, useContext, useEffect, useState, ReactNode } from 'react'
import { useApolloClient, useMutation, useQuery } from '@apollo/client'
import { LOGIN_MUTATION, LOGOUT_MUTATION, ME_QUERY } from '../lib/queries'
import { setAuthToken } from '../lib/apollo'

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

function useAuthState(): AuthContextValue {
  const apolloClient = useApolloClient()
  const [user, setUser] = useState<AuthUser | null>(null)
  const [initialized, setInitialized] = useState(false)

  const [loginMutation, { loading: loggingIn, error }] = useMutation(LOGIN_MUTATION)
  const [logoutMutation] = useMutation(LOGOUT_MUTATION)
  const { data: sessionData, loading: sessionLoading, refetch } = useQuery(ME_QUERY, {
    fetchPolicy: 'network-only',
    errorPolicy: 'ignore',
  })

  useEffect(() => {
    if (!sessionLoading) {
      const remote = sessionData?.me
      setUser(remote ? { id: remote.id, fullName: remote.fullName, email: remote.email, role: remote.role } : null)
      setInitialized(true)
    }
  }, [sessionData, sessionLoading])

  useEffect(() => {
    const handleSessionExpired = () => setUser(null)
    window.addEventListener('hydenlyne:session-expired', handleSessionExpired)
    return () => window.removeEventListener('hydenlyne:session-expired', handleSessionExpired)
  }, [])

  const login = useCallback(
    async (email: string, password: string, _remember = true): Promise<{ ok: boolean; message?: string }> => {
      try {
        const { data } = await loginMutation({ variables: { email, password } })
        const result = data?.login
        if (result?.success && result.token) {
          const u: AuthUser = {
            id: result.user?.id ?? '',
            fullName: result.user?.fullName ?? '',
            email: result.user?.email ?? email,
            role: result.user?.role ?? 'user',
          }
          setAuthToken(result.token, _remember)
          setUser(u)
          return { ok: true }
        }
        return { ok: false, message: result?.message ?? 'Login failed' }
      } catch (e) {
        return { ok: false, message: e instanceof Error ? e.message : 'Login failed' }
      }
    },
    [loginMutation]
  )

  const logout = useCallback(async () => {
    setUser(null)
    try {
      await logoutMutation()
    } catch {
      // best-effort
    }
    setAuthToken(null)
    await apolloClient.clearStore()
  }, [apolloClient, logoutMutation])

  const isAuthenticated = Boolean(user)

  const refreshSession = useCallback(async () => {
    await refetch()
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
