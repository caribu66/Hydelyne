import { describe, expect, it } from 'vitest';
import { escapeRegExp, getSearchTerms } from './searchTerms';

describe('getSearchTerms', () => {
  it('drops stop words and short tokens', () => {
    expect(getSearchTerms('who has experience with survey')).toEqual(['survey']);
  });

  it('sorts by descending length, then alphabetically', () => {
    expect(getSearchTerms('mmo pam bosiet')).toEqual(['bosiet', 'mmo', 'pam']);
  });

  it('deduplicates repeated terms', () => {
    expect(getSearchTerms('survey survey diver')).toEqual(['survey', 'diver']);
  });

  it('splits on commas as well as whitespace', () => {
    expect(getSearchTerms('mmo,pam, bosiet')).toEqual(['bosiet', 'mmo', 'pam']);
  });

  it('returns an empty list for an all-stop-word query', () => {
    expect(getSearchTerms('who has the experience')).toEqual([]);
  });

  it('returns an empty list for an empty query', () => {
    expect(getSearchTerms('   ')).toEqual([]);
  });
});

describe('escapeRegExp', () => {
  it('escapes regex metacharacters', () => {
    expect(escapeRegExp('C++ (advanced)')).toBe('C\\+\\+ \\(advanced\\)');
  });

  it('leaves plain text untouched', () => {
    expect(escapeRegExp('survey diver')).toBe('survey diver');
  });

  it('produces a pattern that matches the literal source string', () => {
    const raw = 'JNCC MMO (Certified)';
    const regex = new RegExp(escapeRegExp(raw));
    expect(regex.test(`Holds ${raw} accreditation`)).toBe(true);
  });
});
