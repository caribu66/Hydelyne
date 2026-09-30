import { describe, expect, it } from 'vitest';
import { latestWorkHistoryEntry, visibleDossierItems } from './dossierUtils';

describe('visibleDossierItems', () => {
  it('keeps dense lists scannable until the agent expands them', () => {
    expect(visibleDossierItems(['one', 'two', 'three', 'four'], false, 2)).toEqual(['one', 'two']);
  });

  it('returns every record after expansion and does not hide small lists', () => {
    expect(visibleDossierItems(['one', 'two', 'three'], true, 2)).toEqual(['one', 'two', 'three']);
    expect(visibleDossierItems(['one', 'two'], false, 2)).toEqual(['one', 'two']);
  });
});

describe('latestWorkHistoryEntry', () => {
  it('picks the latest entry by parsed date, not string order', () => {
    const entries = [
      { clientName: 'Old Client', startDate: '2024-01-15' },
      { clientName: 'New Client', startDate: '2025-06-01' },
    ];

    expect(latestWorkHistoryEntry(entries)?.clientName).toBe('New Client');
  });

  it('lets malformed or missing dates lose to a real date', () => {
    const entries = [
      { clientName: 'Malformed Quarter', startDate: 'Q3 2024' },
      { clientName: 'Real Date', startDate: '2024-01-15' },
      { clientName: 'Missing Date', startDate: null },
    ];

    // Lexicographic comparison would rank "Q3 2024" above "2024-01-15".
    expect(latestWorkHistoryEntry(entries)?.clientName).toBe('Real Date');
  });

  it('returns undefined when no entry has a parseable date', () => {
    expect(latestWorkHistoryEntry([{ startDate: null }, {}])).toBeUndefined();
    expect(latestWorkHistoryEntry([])).toBeUndefined();
  });
});
