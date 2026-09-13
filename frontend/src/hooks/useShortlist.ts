import { useState, useEffect, useCallback } from 'react';
import { UserProfile } from '../types';
import { csvDocument } from '../utils/csv';
import { formatExperience } from '../utils/experience';
import { availabilityLabel } from '../utils/profileLabels';

const STORAGE_KEY = 'hydenlyne_bookmarked_ids';

export function useShortlist(allProfiles: UserProfile[], userId: string | null) {
  const storageKey = userId ? `${STORAGE_KEY}:${userId}` : null;
  const [bookmarkedIds, setBookmarkedIds] = useState<string[]>(() => {
    if (!storageKey) return [];
    try {
      const saved = localStorage.getItem(storageKey);
      const parsed: unknown = saved ? JSON.parse(saved) : [];
      return Array.isArray(parsed) && parsed.every((id): id is string => typeof id === 'string') ? parsed : [];
    } catch {
      return [];
    }
  });
  const [loadedStorageKey, setLoadedStorageKey] = useState(storageKey);

  useEffect(() => {
    setLoadedStorageKey(storageKey);
    if (!storageKey) {
      setBookmarkedIds([]);
      try {
        localStorage.setItem(STORAGE_KEY, '[]');
      } catch {
        // Ignore storage write errors (e.g. incognito restrictions)
      }
      return;
    }
    try {
      const saved = localStorage.getItem(storageKey);
      const parsed: unknown = saved ? JSON.parse(saved) : [];
      setBookmarkedIds(Array.isArray(parsed) && parsed.every((id): id is string => typeof id === 'string') ? parsed : []);
    } catch {
      setBookmarkedIds([]);
    }
  }, [storageKey]);

  useEffect(() => {
    if (loadedStorageKey !== storageKey || !storageKey) return;
    try {
      localStorage.setItem(storageKey, JSON.stringify(bookmarkedIds));
    } catch {
      // Ignore storage write errors (e.g. incognito restrictions)
    }
  }, [bookmarkedIds, loadedStorageKey, storageKey]);

  const toggleBookmark = useCallback((profileId: string) => {
    setBookmarkedIds((prev) =>
      prev.includes(profileId) ? prev.filter((id) => id !== profileId) : [...prev, profileId]
    );
  }, []);

  const isBookmarked = useCallback(
    (profileId: string) => loadedStorageKey === storageKey && bookmarkedIds.includes(profileId),
    [bookmarkedIds, loadedStorageKey, storageKey]
  );

  const clearShortlist = useCallback(() => {
    setBookmarkedIds([]);
    try {
      if (storageKey) localStorage.removeItem(storageKey);
      localStorage.setItem(STORAGE_KEY, '[]');
    } catch {
      // Ignore storage write errors (e.g. incognito restrictions)
    }
  }, [storageKey]);

  const visibleBookmarkedIds = loadedStorageKey === storageKey ? bookmarkedIds : [];
  const shortlistedProfiles = allProfiles.filter((p) => visibleBookmarkedIds.includes(p.id));

  const exportAsCSV = useCallback(() => {
    if (shortlistedProfiles.length === 0) return '';
    const headers = ['Name', 'Title', 'Discipline', 'Location', 'Availability', 'Day Rate (GBP)', 'Experience (Yrs)', 'Email'];
    const rows = shortlistedProfiles.map((p) => [
      p.name,
      p.title,
      p.department,
      p.location,
      availabilityLabel(p.availability),
      p.dayRate != null ? p.dayRate : 'N/A',
      formatExperience(p.yearsOfExperience),
      p.email,
    ]);

    return csvDocument([headers, ...rows]);
  }, [shortlistedProfiles]);

  const copyShortlistSummary = useCallback(async () => {
    if (shortlistedProfiles.length === 0) return false;
    const text = shortlistedProfiles
      .map(
        (p, idx) =>
          `${idx + 1}. ${p.name} - ${p.title} (${p.department})\n   Location: ${p.location} | Avail: ${availabilityLabel(p.availability)} | Rate: ${p.dayRate != null ? `£${p.dayRate}/day` : 'Rate on request'}\n   Contact: ${p.email}`
      )
      .join('\n\n');

    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      return false;
    }
  }, [shortlistedProfiles]);

  return {
    bookmarkedIds: visibleBookmarkedIds,
    shortlistedProfiles,
    toggleBookmark,
    isBookmarked,
    clearShortlist,
    exportAsCSV,
    copyShortlistSummary,
    shortlistCount: visibleBookmarkedIds.length,
  };
}
