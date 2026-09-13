import { describe, expect, it } from 'vitest';
import {
  isCrewQueryResultCurrent,
  isNaturalLanguage,
  parseCrewResults,
  shouldShowSummary,
} from '../hooks/useCrewQuery';

describe('isCrewQueryResultCurrent', () => {
  it('rejects a result retained from another account or logged-out scope', () => {
    expect(isCrewQueryResultCurrent(true, true, 'account-a:staff', 'account-b:staff', 'find b', 'find b')).toBe(false);
    expect(isCrewQueryResultCurrent(true, true, 'account-a:staff', null, 'find b', 'find b')).toBe(false);
    expect(isCrewQueryResultCurrent(false, true, 'account-a:staff', 'account-a:staff', 'find b', 'find b')).toBe(false);
    expect(isCrewQueryResultCurrent(true, true, 'account-a:staff', 'account-a:staff', 'find a', 'find b')).toBe(false);
  });

  it('accepts only a completed result for the active session', () => {
    expect(isCrewQueryResultCurrent(true, true, 'account-a:staff', 'account-a:staff', 'find b', ' Find B ')).toBe(true);
    expect(isCrewQueryResultCurrent(true, false, 'account-a:staff', 'account-a:staff', 'find b', 'find b')).toBe(false);
  });

  it('rejects an old payload retained while a new query is loading', () => {
    expect(
      isCrewQueryResultCurrent(
        true,
        true,
        'account-a:staff',
        'account-a:staff',
        'find b',
        'find b',
        'find a',
      ),
    ).toBe(false);
  });

  it('rejects retained data when the current query has an Apollo error', () => {
    expect(
      isCrewQueryResultCurrent(
        true,
        true,
        'account-a:staff',
        'account-a:staff',
        'find b',
        'find b',
        'find b',
        true,
      ),
    ).toBe(false);
  });
});

describe('parseCrewResults', () => {
  it('drops malformed optional fields before results reach the UI', () => {
    expect(parseCrewResults(JSON.stringify([
      {
        id: 'crew-1',
        name: 'Safe Result',
        email: { leaked: true },
        availability: ['available'],
        certifications: ['BOSIET', 42, null],
        experience_months: Number.POSITIVE_INFINITY,
      },
      {
        id: 'crew-1b',
        name: 'Backend Result',
        experience_years: 12.5,
      },
      { id: 42, name: 'Invalid ID' },
      { id: 'crew-2', name: 'Second Result', certifications: ['HSE'] },
    ]))).toEqual([
      {
        id: 'crew-1',
        name: 'Safe Result',
        certifications: ['BOSIET'],
      },
      {
        id: 'crew-1b',
        name: 'Backend Result',
        experience_years: 12.5,
      },
      {
        id: 'crew-2',
        name: 'Second Result',
        certifications: ['HSE'],
      },
    ]);
  });

  it('preserves authoritative profile fields returned by natural search', () => {
    expect(parseCrewResults(JSON.stringify([{
      id: 'crew-3',
      name: 'Profile Result',
      country_of_residence: 'Norway',
      nationality: 'Norwegian',
      education: 'MSc Oceanography',
      professional_summary: 'Verified survey specialist',
      languages: ['English', 4],
      tags: ['Hydrography'],
      systems_experience: ['QINSy'],
    }]))).toEqual([{
      id: 'crew-3',
      name: 'Profile Result',
      country_of_residence: 'Norway',
      nationality: 'Norwegian',
      education: 'MSc Oceanography',
      professional_summary: 'Verified survey specialist',
      languages: ['English'],
      tags: ['Hydrography'],
      systems_experience: ['QINSy'],
    }]);
  });
});

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
