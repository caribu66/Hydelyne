/**
 * Terms that add grammatical context to a natural-language query but should
 * neither decide a keyword match nor be presented as a result match.
 */
const SEARCH_STOP_WORDS = new Set([
  'in', 'at', 'with', 'for', 'and', 'the', 'of', 'to', 'who', 'is', 'a', 'an',
  // Conversational wording should not be required to occur in a profile.
  'has', 'have', 'having', 'experience', 'experienced', 'crew', 'member',
  'members', 'people', 'person', 'specialist', 'specialists', 'candidate',
  'candidates', 'find', 'show', 'list', 'me',
]);

/**
 * Produces the meaningful, distinct terms used by keyword search and result
 * highlighting. Longest-first ordering prevents a short term from consuming
 * the start of a longer overlapping term (for example, "survey" / "surveyor").
 */
export function getSearchTerms(query: string): string[] {
  const uniqueTerms = new Set(
    query
      .trim()
      .toLowerCase()
      .split(/[\s,]+/)
      .map((term) => term.trim())
      .filter((term) => term.length > 1 && !SEARCH_STOP_WORDS.has(term))
  );

  return [...uniqueTerms].sort((a, b) => b.length - a.length || a.localeCompare(b));
}

export function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}
