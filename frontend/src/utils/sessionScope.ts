export function buildAuthSessionKey(
  user: { id: string; role?: string | null } | null,
): string | null {
  return user ? `${user.id}:${user.role ?? 'user'}` : null;
}

export function isSessionScopeCurrent(
  enabled: boolean,
  loadedSessionKey: string | null,
  sessionKey: string | null,
): boolean {
  return enabled && loadedSessionKey === sessionKey;
}

export function isSessionDataReady(
  enabled: boolean,
  loadedSessionKey: string | null,
  sessionKey: string | null | undefined,
  loading: boolean,
  error: unknown,
): boolean {
  return isSessionScopeCurrent(enabled, loadedSessionKey, sessionKey ?? null) && !loading && !error;
}

export function isSessionRequestCurrent(
  requestVersion: number,
  currentRequestVersion: number,
  currentSessionKey: string | null | undefined,
  expectedSessionKey: string | null,
): boolean {
  return requestVersion === currentRequestVersion && currentSessionKey === expectedSessionKey;
}

export function isSessionQueryEnabled(
  enabled: boolean,
  sessionKey: string | null | undefined,
): boolean {
  return enabled && Boolean(sessionKey);
}

export function apolloResultHasErrors(result: {
  error?: unknown
  errors?: ReadonlyArray<unknown>
}): boolean {
  return Boolean(result.error) || Boolean(result.errors?.length)
}
