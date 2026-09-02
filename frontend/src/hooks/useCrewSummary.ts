import { useState, useCallback } from 'react';
import { useLazyQuery } from '@apollo/client';
import { CREW_SUMMARY_QUERY } from '../lib/queries';

// Shown automatically when a profile opens (see backend/docs/cv-ingestion-pipeline.md
// and consultant-knowledge-core.md). The backend caches the generated text per
// crew member, so only the first open per consultant pays for the Ollama call.
export function useCrewSummary() {
  const [summariesByProfile, setSummariesByProfile] = useState<Record<string, string>>({});
  const [loadingProfileIds, setLoadingProfileIds] = useState<Record<string, boolean>>({});
  const [fetchCrewSummary] = useLazyQuery(CREW_SUMMARY_QUERY, { fetchPolicy: 'network-only' });

  const fetchSummary = useCallback(async (profileId: string) => {
    setLoadingProfileIds((current) => ({ ...current, [profileId]: true }));
    try {
      const { data } = await fetchCrewSummary({ variables: { crewId: profileId } });
      if (data?.crewSummary) {
        setSummariesByProfile((current) => ({ ...current, [profileId]: data.crewSummary }));
      }
    } catch {
      // Fail quietly: a missing AI summary shouldn't block viewing the rest
      // of a real profile. The card simply doesn't render (see
      // SpecialistDossierPane's isSummaryLoading/getSummaryForProfile usage).
    } finally {
      setLoadingProfileIds((current) => ({ ...current, [profileId]: false }));
    }
  }, [fetchCrewSummary]);

  const getSummaryForProfile = useCallback((profileId: string): string | undefined => {
    return summariesByProfile[profileId];
  }, [summariesByProfile]);

  const isSummaryLoading = useCallback((profileId: string): boolean => {
    return Boolean(loadingProfileIds[profileId]);
  }, [loadingProfileIds]);

  return {
    fetchSummary,
    getSummaryForProfile,
    isSummaryLoading,
  };
}
