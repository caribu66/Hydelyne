import { useState, useCallback, useEffect } from 'react'
import { useMutation, useQuery } from '@apollo/client'
import { LOGIN_MUTATION, LOGOUT_MUTATION, ME_QUERY } from '../lib/queries'

export interface AuthUser {
  id: string
  fullName: string
  email: string
  role?: string
}

export function useAuth() {
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
    async (email: string, password: string, remember = true): Promise<{ ok: boolean; message?: string }> => {
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
    try {
      await logoutMutation()
    } catch {
      // Logout is best-effort; clear local state regardless of server response
    }
    setUser(null)
  }, [logoutMutation])

  const isAuthenticated = Boolean(user)

  const refreshSession = useCallback(async () => {
    await refetch()
  }, [refetch])

  return { user, initialized, isAuthenticated, login, logout, refreshSession, loggingIn, error }
}
