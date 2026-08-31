import { useState, useEffect, useCallback } from 'react';
import { UserProfile } from '../types';

const STORAGE_KEY = 'hydenlyne_bookmarked_ids';

export function useShortlist(allProfiles: UserProfile[]) {
  const [bookmarkedIds, setBookmarkedIds] = useState<string[]>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(bookmarkedIds));
    } catch {
      // Ignore storage write errors (e.g. incognito restrictions)
    }
  }, [bookmarkedIds]);

  const toggleBookmark = useCallback((profileId: string) => {
    setBookmarkedIds((prev) =>
      prev.includes(profileId) ? prev.filter((id) => id !== profileId) : [...prev, profileId]
    );
  }, []);

  const isBookmarked = useCallback(
    (profileId: string) => bookmarkedIds.includes(profileId),
    [bookmarkedIds]
  );

  const clearShortlist = useCallback(() => {
    setBookmarkedIds([]);
  }, []);

  const shortlistedProfiles = allProfiles.filter((p) => bookmarkedIds.includes(p.id));

  const exportAsCSV = useCallback(() => {
    if (shortlistedProfiles.length === 0) return '';
    const headers = ['Name', 'Title', 'Discipline', 'Location', 'Availability', 'Day Rate (GBP)', 'Experience (Yrs)', 'Email'];
    const rows = shortlistedProfiles.map((p) => [
      `"${p.name.replace(/"/g, '""')}"`,
      `"${p.title.replace(/"/g, '""')}"`,
      `"${p.department.replace(/"/g, '""')}"`,
      `"${p.location.replace(/"/g, '""')}"`,
      `"${(p.availability || 'Available').replace(/"/g, '""')}"`,
      p.dayRate ? `${p.dayRate}` : 'N/A',
      `${p.yearsOfExperience}`,
      `"${p.email.replace(/"/g, '""')}"`,
    ]);

    return [headers.join(','), ...rows.map((r) => r.join(','))].join('\n');
  }, [shortlistedProfiles]);

  const copyShortlistSummary = useCallback(async () => {
    if (shortlistedProfiles.length === 0) return false;
    const text = shortlistedProfiles
      .map(
        (p, idx) =>
          `${idx + 1}. ${p.name} - ${p.title} (${p.department})\n   Location: ${p.location} | Avail: ${p.availability || 'Available'} | Rate: £${p.dayRate || 'Req'}/day\n   Contact: ${p.email}`
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
    bookmarkedIds,
    shortlistedProfiles,
    toggleBookmark,
    isBookmarked,
    clearShortlist,
    exportAsCSV,
    copyShortlistSummary,
    shortlistCount: bookmarkedIds.length,
  };
}
