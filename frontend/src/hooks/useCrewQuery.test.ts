import { describe, expect, it } from 'vitest';
import { isNaturalLanguage, shouldShowSummary } from '../hooks/useCrewQuery';

describe('isNaturalLanguage', () => {
  it('rejects empty and whitespace-only queries', () => {
    expect(isNaturalLanguage('')).toBe(false);
    expect(isNaturalLanguage('   ')).toBe(false);
  });

  it('rejects single names', () => {
    expect(isNaturalLanguage('John Smith')).toBe(false);
    expect(isNaturalLanguage('Helena Lindqvist')).toBe(false);
  });

  it('accepts short queries that start with a question word and have 3 or fewer words', () => {
    expect(isNaturalLanguage('Find BOSIET')).toBe(false);
    expect(isNaturalLanguage('Show me MMO')).toBe(false);
    expect(isNaturalLanguage('Who has medical?')).toBe(true);
    expect(isNaturalLanguage('List unavailable')).toBe(false);
    expect(isNaturalLanguage('Get IMCA')).toBe(false);
  });

  it('rejects short queries that do not start with a question word', () => {
    expect(isNaturalLanguage('BOSIET')).toBe(false);
    expect(isNaturalLanguage('MMO Poland')).toBe(false);
    expect(isNaturalLanguage('Dutch medic')).toBe(false);
  });

  it('accepts 4+ word queries containing a question word', () => {
    expect(isNaturalLanguage('Who has BOSIET certification?')).toBe(true);
    expect(isNaturalLanguage('Find Spanish offshore medics')).toBe(true);
    expect(isNaturalLanguage('Show available surveyors next month')).toBe(true);
  });

  it('accepts queries matching question patterns', () => {
    expect(isNaturalLanguage('Looking for someone with experience')).toBe(true);
    expect(isNaturalLanguage('Need a contractor who has HUET')).toBe(true);
    expect(isNaturalLanguage('Available immediately for mobilization')).toBe(true);
    expect(isNaturalLanguage('Expired medical certification')).toBe(true);
    expect(isNaturalLanguage('5 years of offshore experience')).toBe(true);
    expect(isNaturalLanguage('Having experience in subsea inspection')).toBe(true);
  });

  it('is case-insensitive', () => {
    expect(isNaturalLanguage('WHO HAS BOSIET?')).toBe(true);
    expect(isNaturalLanguage('find dutch medic')).toBe(false);
  });
});

describe('shouldShowSummary', () => {
  it('rejects short queries', () => {
    expect(shouldShowSummary('Find BOSIET')).toBe(false);
    expect(shouldShowSummary('MMO')).toBe(false);
  });

  it('accepts queries with 4 or more words', () => {
    expect(shouldShowSummary('Who has BOSIET certification?')).toBe(true);
    expect(shouldShowSummary('Find Spanish offshore medics with experience')).toBe(true);
  });
});
