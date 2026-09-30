export function visibleDossierItems<T>(items: readonly T[], isExpanded: boolean, initialItems: number): readonly T[] {
  return isExpanded || items.length <= initialItems ? items : items.slice(0, initialItems);
}

interface DatedWorkHistoryEntry {
  startDate?: string | null;
}

/** Latest work-history entry by parsed start date. String comparison would
 * let a malformed value (e.g. "Q3 2024") outrank a real ISO date, so
 * unparseable or missing dates sort last instead of first. */
export function latestWorkHistoryEntry<T extends DatedWorkHistoryEntry>(
  entries: readonly T[],
): T | undefined {
  let latest: T | undefined;
  let latestTime = Number.NEGATIVE_INFINITY;
  for (const entry of entries) {
    if (!entry.startDate) continue;
    const timestamp = Date.parse(entry.startDate);
    if (!Number.isFinite(timestamp) || timestamp <= latestTime) continue;
    latestTime = timestamp;
    latest = entry;
  }
  return latest;
}
