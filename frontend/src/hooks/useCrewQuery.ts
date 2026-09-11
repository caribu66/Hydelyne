import { useState, useEffect, useMemo, useRef } from 'react';
import { useLazyQuery } from '@apollo/client';
import { QUERY_CREW } from '../lib/queries';

export interface CrewQueryResult {
  intent: string;
  query: string;
  summary: string;
  results: Array<{
    id: string;
    name: string;
    email?: string;
    availability?: string;
    certifications?: string[];
    experience_months?: number;
  }>;
  criteria: Record<string, unknown>;
  totalIssues?: number;
  crewId?: string;
  crewName?: string;
}

interface CrewQueryGraphQLResult {
  intent: string;
  query: string;
  summary: string;
  results: string;
  criteria?: string;
  totalIssues?: number;
  crewId?: string;
  crewName?: string;
}

/** Parse backend JSON scalar fields defensively. A malformed AI payload must
 * become an empty result, not an exception during React render. */
export function parseCrewResults(value: string | null | undefined): CrewQueryResult['results'] {
  if (!value) return [];
  try {
    const parsed: unknown = JSON.parse(value);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((item): item is CrewQueryResult['results'][number] => {
      if (!item || typeof item !== 'object') return false;
      const candidate = item as Record<string, unknown>;
      return typeof candidate.id === 'string' && typeof candidate.name === 'string';
    });
  } catch {
    return [];
  }
}

export function parseCrewCriteria(value: string | null | undefined): Record<string, unknown> {
  if (!value) return {};
  try {
    const parsed: unknown = JSON.parse(value);
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
      ? parsed as Record<string, unknown>
      : {};
  } catch {
    return {};
  }
}

export interface UseCrewQueryReturn {
  data: CrewQueryResult | null;
  loading: boolean;
  error: string | null;
  isAIQuery: boolean;
  showSummary: boolean;
}

const QUESTION_WORDS = ['who', 'what', 'where', 'when', 'why', 'how', 'find', 'show', 'list', 'get', 'available', 'with', 'having'];

export function isNaturalLanguage(query: string): boolean {
  const trimmed = query.trim();
  if (!trimmed) return false;

  const words = trimmed.toLowerCase().split(/\s+/);
  const lowerTrimmed = trimmed.toLowerCase();

  if (words.length < 4) {
    const isName = /^[A-Z][a-z]+(\s[A-Z][a-z]+)?$/.test(trimmed);
    if (isName) return false;

    if (words.length <= 2) {
      const hasQuestionStart = /^(who|what|where|when|how|find|show|list|get)\b/i.test(lowerTrimmed);
      if (!hasQuestionStart) return false;
    }
  }

  if (words.length >= 4) {
    const hasQuestionWord = QUESTION_WORDS.some((qw) => words.includes(qw));
    if (hasQuestionWord) return true;
  }

  const questionPatterns = [
    /^(who|what|where|when|how)\s/i,
    /\b(find|show|list|give me|looking for|need)\b.*\b(with|who|that)\b/i,
    /\b(available|unavailable)\b.*\b(for|on|immediately)\b/i,
    /\b(expired|expiring)\b.*\b(medical|certification|certificate)\b/i,
    /\b(experience|years?)\b\s*\b(in|with|of)\b/i,
    /\b(with|having)\b.*\b(experience|years?)\b/i,
  ];
  if (questionPatterns.some((p) => p.test(lowerTrimmed))) return true;

  return false;
}

export function shouldShowSummary(query: string): boolean {
  const trimmed = query.trim();
  if (!trimmed) return false;
  const words = trimmed.toLowerCase().split(/\s+/);
  return words.length >= 4;
}

export function useCrewQuery(rawQuery: string, enabled: boolean): UseCrewQueryReturn {
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [isAIQuery, setIsAIQuery] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [executeQuery, { data, loading, error }] = useLazyQuery<{
    queryCrew: CrewQueryGraphQLResult;
  }>(QUERY_CREW, {
    fetchPolicy: 'network-only',
  });

  const shouldUseAI = enabled && debouncedQuery.trim().length >= 3 && isNaturalLanguage(debouncedQuery);
  const showSummary = shouldShowSummary(debouncedQuery) && shouldUseAI;

  useEffect(() => {
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    if (!enabled || rawQuery.trim().length < 3) {
      setDebouncedQuery('');
      setIsAIQuery(false);
      return;
    }

    debounceTimerRef.current = setTimeout(() => {
      setDebouncedQuery(rawQuery.trim());
    }, 300);

    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, [rawQuery, enabled]);

  useEffect(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }

    if (!shouldUseAI) {
      setIsAIQuery(false);
      return;
    }

    setIsAIQuery(true);
    const controller = new AbortController();
    abortControllerRef.current = controller;

    executeQuery({
      variables: { query: debouncedQuery },
      context: {
        fetchOptions: {
          signal: controller.signal,
        },
      },
    }).catch(() => {
      // Apollo error state is surfaced via the `error` return value
    });

    return () => {
      controller.abort();
    };
  }, [debouncedQuery, shouldUseAI, executeQuery]);

  // Memoized so this stays referentially stable across renders when the
  // underlying Apollo data hasn't changed. Without this, a fresh object
  // literal on every render fed an effect elsewhere (ModernHeroSearch's
  // onAIResults effect) whose dependency array never stabilized, causing
  // setState -> re-render -> new object -> effect fires -> setState,
  // forever ("Maximum update depth exceeded" in production).
  const result: CrewQueryResult | null = useMemo(
    () =>
      data?.queryCrew
        ? {
            intent: data.queryCrew.intent,
            query: data.queryCrew.query,
            summary: data.queryCrew.summary,
            results: parseCrewResults(data.queryCrew.results),
            criteria: parseCrewCriteria(data.queryCrew.criteria),
            totalIssues: data.queryCrew.totalIssues ?? undefined,
            crewId: data.queryCrew.crewId ?? undefined,
            crewName: data.queryCrew.crewName ?? undefined,
          }
        : null,
    [data],
  );

  return {
    data: result,
    loading,
    error: error ? error.message : null,
    isAIQuery: isAIQuery && (loading || result !== null),
    showSummary: showSummary && (loading || result !== null),
  };
}
