import { describe, expect, it } from 'vitest';
import { ALL_LOCATIONS, ALL_SKILLS } from '../data/mockProfiles';
import { UserProfile } from '../types';
import {
  filterProfiles,
  generateAIOverview,
  getActiveFilterCount,
  INITIAL_FILTER_STATE,
  parseNaturalLanguageQuery,
  sortProfiles,
} from './filterUtils';

function makeProfile(overrides: Partial<UserProfile> = {}): UserProfile {
  return {
    id: 'p1',
    name: 'Alex Rivera',
    title: 'Marine Mammal Observer',
    avatar: '',
    company: 'Hydenlyne Consultancy Network',
    department: 'Environmental',
    location: 'Aberdeen, Scotland',
    remoteType: 'On-site',
    yearsOfExperience: 5,
    skills: ['JNCC MMO', 'PAMGUARD'],
    bio: 'Experienced offshore MMO/PAM specialist.',
    availability: 'Available immediately',
    education: 'BSc Marine Biology',
    email: 'alex@example.com',
    rating: 4.5,
    ...overrides,
  };
}

describe('parseNaturalLanguageQuery', () => {
  it('returns an empty object for a blank query', () => {
    expect(parseNaturalLanguageQuery('   ')).toEqual({});
  });

  it('detects a known skill by word boundary', () => {
    const result = parseNaturalLanguageQuery('Looking for a JNCC MMO specialist');
    expect(result.selectedSkills).toContain('JNCC MMO');
  });

  it('does not match a skill as a substring of another word', () => {
    // "PAM" should not match inside an unrelated word like "campaign".
    const result = parseNaturalLanguageQuery('planning the campaign logistics');
    expect(result.selectedSkills).not.toContain('PAMGUARD');
  });

  it('detects remote mode keywords', () => {
    expect(parseNaturalLanguageQuery('remote PyTorch engineers').remoteTypes).toEqual(['Remote']);
    expect(parseNaturalLanguageQuery('hybrid role').remoteTypes).toEqual(['Hybrid']);
    expect(parseNaturalLanguageQuery('on-site only').remoteTypes).toEqual(['On-site']);
  });

  it('detects a known location by city name', () => {
    const target = ALL_LOCATIONS[0] ?? '';
    const city = target.split(',')[0] ?? '';
    const result = parseNaturalLanguageQuery(`specialists based in ${city}`);
    expect(result.locations).toContain(target);
  });

  it('maps seniority language to a minimum experience', () => {
    expect(parseNaturalLanguageQuery('senior surveyor').minExperience).toBe(5);
    expect(parseNaturalLanguageQuery('principal geophysicist').minExperience).toBe(8);
  });

  it('maps junior language to a bounded experience range', () => {
    const result = parseNaturalLanguageQuery('junior analyst');
    expect(result.minExperience).toBe(0);
    expect(result.maxExperience).toBe(3);
  });

  it('parses an explicit "X-Y years" range', () => {
    const result = parseNaturalLanguageQuery('3-6 years experience');
    expect(result.minExperience).toBe(3);
    expect(result.maxExperience).toBe(6);
  });

  it('parses "X+ years" as a minimum only', () => {
    const result = parseNaturalLanguageQuery('5+ years experience');
    expect(result.minExperience).toBe(5);
    expect(result.maxExperience).toBeUndefined();
  });

  it('detects availability phrasing', () => {
    expect(parseNaturalLanguageQuery('available immediately').availability).toContain(
      'Available immediately'
    );
    expect(parseNaturalLanguageQuery('open to offers').availability).toContain('Open to offers');
    expect(parseNaturalLanguageQuery('freelance contractor').availability).toContain(
      'Contract / Freelance'
    );
  });

  it('detects every known skill without throwing', () => {
    // Guards against a future skill name breaking the word-boundary regex
    // (e.g. one containing unescaped regex metacharacters).
    for (const skill of ALL_SKILLS) {
      expect(() => parseNaturalLanguageQuery(`Need someone with ${skill}`)).not.toThrow();
    }
  });
});

describe('filterProfiles', () => {
  it('returns all profiles when no filters are active', () => {
    const profiles = [makeProfile(), makeProfile({ id: 'p2' })];
    expect(filterProfiles(profiles, INITIAL_FILTER_STATE)).toHaveLength(2);
  });

  it('matches a keyword against name, title, bio, and skills', () => {
    const profiles = [makeProfile()];
    expect(
      filterProfiles(profiles, { ...INITIAL_FILTER_STATE, keyword: 'Rivera' })
    ).toHaveLength(1);
    expect(
      filterProfiles(profiles, { ...INITIAL_FILTER_STATE, keyword: 'PAMGUARD' })
    ).toHaveLength(1);
    expect(
      filterProfiles(profiles, { ...INITIAL_FILTER_STATE, keyword: 'nonexistent-term' })
    ).toHaveLength(0);
  });

  it('matches when at least 66% of a 3+ word keyword query hits', () => {
    const profile = makeProfile({ bio: 'Experienced offshore MMO specialist based in Aberdeen.' });
    // "offshore mmo specialist team" — 3 of 4 words match (75%) once stop
    // words ("specialist") are filtered by getSearchTerms.
    const result = filterProfiles(
      [profile],
      { ...INITIAL_FILTER_STATE, keyword: 'offshore mmo aberdeen missing-word' }
    );
    expect(result).toHaveLength(1);
  });

  it('excludes a profile below the fuzzy keyword match threshold', () => {
    const profile = makeProfile({ bio: 'Nothing relevant here.' });
    const result = filterProfiles(
      [profile],
      { ...INITIAL_FILTER_STATE, keyword: 'totally unrelated missing words here' }
    );
    expect(result).toHaveLength(0);
  });

  it('filters by location using the city name prefix', () => {
    const profiles = [
      makeProfile({ location: 'Aberdeen, Scotland' }),
      makeProfile({ id: 'p2', location: 'Houston, TX' }),
    ];
    const result = filterProfiles(profiles, {
      ...INITIAL_FILTER_STATE,
      locations: ['Aberdeen, Scotland'],
    });
    expect(result.map((p) => p.id)).toEqual(['p1']);
  });

  it('filters by remote type', () => {
    const profiles = [
      makeProfile({ remoteType: 'Remote' }),
      makeProfile({ id: 'p2', remoteType: 'On-site' }),
    ];
    const result = filterProfiles(profiles, { ...INITIAL_FILTER_STATE, remoteTypes: ['Remote'] });
    expect(result.map((p) => p.id)).toEqual(['p1']);
  });

  it('requires only one match in ANY skill mode', () => {
    const profile = makeProfile({ skills: ['JNCC MMO'] });
    const result = filterProfiles([profile], {
      ...INITIAL_FILTER_STATE,
      selectedSkills: ['JNCC MMO', 'PAMGUARD'],
      skillMatchMode: 'ANY',
    });
    expect(result).toHaveLength(1);
  });

  it('requires every skill in ALL skill mode', () => {
    const profile = makeProfile({ skills: ['JNCC MMO'] });
    const result = filterProfiles([profile], {
      ...INITIAL_FILTER_STATE,
      selectedSkills: ['JNCC MMO', 'PAMGUARD'],
      skillMatchMode: 'ALL',
    });
    expect(result).toHaveLength(0);
  });

  it('treats certifications as matchable skills', () => {
    const profile = makeProfile({ skills: [], certifications: ['BOSIET'] });
    const result = filterProfiles([profile], {
      ...INITIAL_FILTER_STATE,
      selectedSkills: ['BOSIET'],
      skillMatchMode: 'ANY',
    });
    expect(result).toHaveLength(1);
  });

  it('filters by an experience range', () => {
    const profiles = [
      makeProfile({ id: 'junior', yearsOfExperience: 1 }),
      makeProfile({ id: 'mid', yearsOfExperience: 5 }),
      makeProfile({ id: 'senior', yearsOfExperience: 12 }),
    ];
    const result = filterProfiles(profiles, {
      ...INITIAL_FILTER_STATE,
      minExperience: 3,
      maxExperience: 10,
    });
    expect(result.map((p) => p.id)).toEqual(['mid']);
  });

  it('treats the default max experience (20) as unbounded', () => {
    const profile = makeProfile({ yearsOfExperience: 30 });
    const result = filterProfiles([profile], { ...INITIAL_FILTER_STATE, minExperience: 0 });
    expect(result).toHaveLength(1);
  });

  it('matches a company against current or past employer', () => {
    const profile = makeProfile({ company: 'Current Co', pastCompanies: ['Past Co'] });
    expect(
      filterProfiles([profile], { ...INITIAL_FILTER_STATE, companies: ['Past Co'] })
    ).toHaveLength(1);
    expect(
      filterProfiles([profile], { ...INITIAL_FILTER_STATE, companies: ['Unrelated Co'] })
    ).toHaveLength(0);
  });

  it('filters by availability and department', () => {
    const profile = makeProfile({ availability: 'Open to offers', department: 'Geotechnical' });
    expect(
      filterProfiles([profile], { ...INITIAL_FILTER_STATE, availability: ['Open to offers'] })
    ).toHaveLength(1);
    expect(
      filterProfiles([profile], { ...INITIAL_FILTER_STATE, departments: ['Environmental'] })
    ).toHaveLength(0);
  });

  it('combines multiple active filters with AND semantics', () => {
    const profile = makeProfile({
      location: 'Aberdeen, Scotland',
      skills: ['JNCC MMO'],
      yearsOfExperience: 6,
    });
    const result = filterProfiles([profile], {
      ...INITIAL_FILTER_STATE,
      locations: ['Aberdeen, Scotland'],
      selectedSkills: ['JNCC MMO'],
      minExperience: 5,
    });
    expect(result).toHaveLength(1);

    const failing = filterProfiles([profile], {
      ...INITIAL_FILTER_STATE,
      locations: ['Aberdeen, Scotland'],
      selectedSkills: ['PAMGUARD'], // not held by this profile
    });
    expect(failing).toHaveLength(0);
  });
});

describe('sortProfiles', () => {
  const profiles = [
    makeProfile({ id: 'a', name: 'Charlie', yearsOfExperience: 3, rating: 4.9 }),
    makeProfile({ id: 'b', name: 'Alice', yearsOfExperience: 9, rating: 4.2 }),
    makeProfile({ id: 'c', name: 'Bob', yearsOfExperience: 6, rating: 4.6 }),
  ];

  it('sorts by experience descending / ascending', () => {
    expect(sortProfiles(profiles, 'experience-desc', '').map((p) => p.id)).toEqual([
      'b',
      'c',
      'a',
    ]);
    expect(sortProfiles(profiles, 'experience-asc', '').map((p) => p.id)).toEqual(['a', 'c', 'b']);
  });

  it('sorts by name ascending / descending', () => {
    expect(sortProfiles(profiles, 'name-asc', '').map((p) => p.id)).toEqual(['b', 'c', 'a']);
    expect(sortProfiles(profiles, 'name-desc', '').map((p) => p.id)).toEqual(['a', 'c', 'b']);
  });

  it('falls back to rating when relevance has no keyword or AI ranking', () => {
    expect(sortProfiles(profiles, 'relevance', '').map((p) => p.id)).toEqual(['a', 'c', 'b']);
  });

  it('preserves backend AI ranking order over incidental keyword scoring', () => {
    // "b" would score lower than "a" or "c" on name/bio relevance alone, but
    // the backend has already ranked structured matches — that order wins.
    const result = sortProfiles(profiles, 'relevance', 'charlie', ['b', 'c', 'a']);
    expect(result.map((p) => p.id)).toEqual(['b', 'c', 'a']);
  });

  it('does not mutate the input array', () => {
    const original = [...profiles];
    sortProfiles(profiles, 'experience-desc', '');
    expect(profiles).toEqual(original);
  });
});

describe('getActiveFilterCount', () => {
  it('is zero for the initial filter state', () => {
    expect(getActiveFilterCount(INITIAL_FILTER_STATE)).toBe(0);
  });

  it('counts a keyword as a single active filter', () => {
    expect(getActiveFilterCount({ ...INITIAL_FILTER_STATE, keyword: 'survey' })).toBe(1);
  });

  it('counts each selected value in multi-select filters', () => {
    expect(
      getActiveFilterCount({
        ...INITIAL_FILTER_STATE,
        locations: ['Aberdeen, Scotland', 'Houston, TX'],
      })
    ).toBe(2);
  });

  it('counts a narrowed experience range as a single active filter', () => {
    expect(
      getActiveFilterCount({ ...INITIAL_FILTER_STATE, minExperience: 5, maxExperience: 10 })
    ).toBe(1);
  });

  it('sums multiple simultaneously active filters', () => {
    const count = getActiveFilterCount({
      ...INITIAL_FILTER_STATE,
      keyword: 'survey',
      selectedSkills: ['JNCC MMO', 'PAMGUARD'],
      availability: ['Available immediately'],
    });
    expect(count).toBe(1 + 2 + 1);
  });
});

describe('generateAIOverview', () => {
  it('returns null for an empty result set', () => {
    expect(generateAIOverview('mmo', [], INITIAL_FILTER_STATE)).toBeNull();
  });

  it('summarizes averages and top skills across the matched cohort', () => {
    const profiles = [
      makeProfile({ id: 'a', yearsOfExperience: 4, skills: ['JNCC MMO'] }),
      makeProfile({ id: 'b', yearsOfExperience: 8, skills: ['JNCC MMO', 'PAMGUARD'] }),
    ];
    const overview = generateAIOverview('mmo specialists', profiles, INITIAL_FILTER_STATE);
    expect(overview).not.toBeNull();
    expect(overview?.avgExperience).toBe(6);
    expect(overview?.topSkillsFound).toContain('JNCC MMO');
    expect(overview?.highlightProfileId).toBe('a');
  });
});
