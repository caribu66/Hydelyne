import { useState, useCallback, useEffect, useRef } from 'react';
import { useLazyQuery } from '@apollo/client';
import { CREW_SUMMARY_QUERY } from '../lib/queries';
import { apolloResultHasErrors, isSessionScopeCurrent } from '../utils/sessionScope';

// Shown automatically when a profile opens (see backend/docs/cv-ingestion-pipeline.md
// and consultant-knowledge-core.md). The backend caches the generated text per
// crew member, so only the first open per consultant pays for the Ollama call.
export function useCrewSummary(enabled = true, sessionKey: string | null = null) {
  const [summariesByProfile, setSummariesByProfile] = useState<Record<string, string>>({});
  const [loadingProfileIds, setLoadingProfileIds] = useState<Record<string, boolean>>({});
  const [fetchCrewSummary] = useLazyQuery(CREW_SUMMARY_QUERY, { fetchPolicy: 'network-only' });
  const sessionEpochRef = useRef(0);
  const requestVersionByProfileRef = useRef<Record<string, number>>({});
  const [loadedSessionKey, setLoadedSessionKey] = useState<string | null>(null);
  const currentSessionKeyRef = useRef(sessionKey);
  const currentEnabledRef = useRef(enabled);
  currentSessionKeyRef.current = sessionKey;
  currentEnabledRef.current = enabled;

  useEffect(() => {
    sessionEpochRef.current += 1;
    setSummariesByProfile({});
    setLoadingProfileIds({});
    setLoadedSessionKey(sessionKey);
  }, [enabled, sessionKey]);

  const fetchSummary = useCallback(async (profileId: string) => {
    if (!isSessionScopeCurrent(enabled, loadedSessionKey, sessionKey)) return;
    const requestEpoch = sessionEpochRef.current;
    const requestVersion = (requestVersionByProfileRef.current[profileId] ?? 0) + 1;
    requestVersionByProfileRef.current[profileId] = requestVersion;
    setSummariesByProfile((current) => {
      if (!(profileId in current)) return current;
      const next = { ...current };
      delete next[profileId];
      return next;
    });
    setLoadingProfileIds((current) => ({ ...current, [profileId]: true }));
    try {
      const result = await fetchCrewSummary({ variables: { crewId: profileId } });
      if (apolloResultHasErrors(result)) throw new Error('Summary request failed');
      const { data } = result;
      const isCurrentRequest =
        enabled &&
        currentEnabledRef.current &&
        currentSessionKeyRef.current === sessionKey &&
        requestEpoch === sessionEpochRef.current &&
        requestVersion === requestVersionByProfileRef.current[profileId];
      if (isCurrentRequest && data?.crewSummary) {
        setSummariesByProfile((current) => ({ ...current, [profileId]: data.crewSummary }));
      }
    } catch {
      // Fail quietly: a missing AI summary shouldn't block viewing the rest
      // of a real profile. The card simply doesn't render (see
      // SpecialistDossierPane's isSummaryLoading/getSummaryForProfile usage).
    } finally {
      if (
        enabled &&
        currentEnabledRef.current &&
        currentSessionKeyRef.current === sessionKey &&
        requestEpoch === sessionEpochRef.current &&
        requestVersion === requestVersionByProfileRef.current[profileId]
      ) {
        setLoadingProfileIds((current) => ({ ...current, [profileId]: false }));
      }
    }
  }, [enabled, fetchCrewSummary, loadedSessionKey, sessionKey]);

  const getSummaryForProfile = useCallback((profileId: string): string | undefined => {
    if (!isSessionScopeCurrent(enabled, loadedSessionKey, sessionKey)) return undefined;
    return summariesByProfile[profileId];
  }, [enabled, loadedSessionKey, sessionKey, summariesByProfile]);

  const isSummaryLoading = useCallback((profileId: string): boolean => {
    if (!isSessionScopeCurrent(enabled, loadedSessionKey, sessionKey)) return false;
    return Boolean(loadingProfileIds[profileId]);
  }, [enabled, loadedSessionKey, loadingProfileIds, sessionKey]);

  return {
    fetchSummary,
    getSummaryForProfile,
    isSummaryLoading,
  };
}
