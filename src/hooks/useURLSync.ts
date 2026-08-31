import { useEffect, useRef } from 'react';

interface URLSyncParams {
  query: string;
  viewMode: 'split' | 'cards' | 'table';
  onSyncQuery: (query: string) => void;
  onSyncViewMode: (mode: 'split' | 'cards' | 'table') => void;
}

export function useURLSync({
  query,
  viewMode,
  onSyncQuery,
  onSyncViewMode,
}: URLSyncParams) {
  const isInitialized = useRef(false);

  // Initialize from URL on initial mount
  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      const params = new URLSearchParams(window.location.search);
      const urlQuery = params.get('q');
      const urlView = params.get('view') as 'split' | 'cards' | 'table' | null;

      if (urlQuery) {
        onSyncQuery(urlQuery);
      }
      if (urlView && ['split', 'cards', 'table'].includes(urlView)) {
        onSyncViewMode(urlView);
      }
    } catch {
      // Ignore URL parsing errors in restricted environments
    } finally {
      isInitialized.current = true;
    }
  }, [onSyncQuery, onSyncViewMode]);

  // Update URL as state changes
  useEffect(() => {
    if (!isInitialized.current || typeof window === 'undefined') return;
    try {
      const params = new URLSearchParams(window.location.search);
      if (query.trim()) {
        params.set('q', query.trim());
      } else {
        params.delete('q');
      }

      if (viewMode !== 'split') {
        params.set('view', viewMode);
      } else {
        params.delete('view');
      }

      const newRelativePathQuery =
        window.location.pathname + (params.toString() ? `?${params.toString()}` : '');
      window.history.replaceState(null, '', newRelativePathQuery);
    } catch {
      // Ignore history state errors in iframe preview
    }
  }, [query, viewMode]);
}
