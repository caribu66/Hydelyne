import { useCallback } from 'react'

/**
 * Returns a `guardAuth()` function that returns `true` when the user is
 * authenticated, or calls `requestLogin` and returns `false` otherwise.
 * Use at the top of any action handler that requires authentication:
 *
 *   const guardAuth = useRequireAuth(isAuthenticated, requestLogin);
 *   const handleAction = useCallback(() => {
 *     if (!guardAuth()) return;
 *     // …action…
 *   }, [guardAuth, …]);
 */
export function useRequireAuth(
  isAuthenticated: boolean,
  requestLogin: () => void,
) {
  return useCallback(() => {
    if (!isAuthenticated) {
      requestLogin()
      return false
    }
    return true
  }, [isAuthenticated, requestLogin])
}
