export function isVesselSearchSessionReady(
  loadedSessionKey: string | null,
  sessionKey: string | null | undefined,
  loading: boolean,
  error: Error | undefined,
): boolean {
  return loadedSessionKey === sessionKey && Boolean(sessionKey) && !loading && !error
}
