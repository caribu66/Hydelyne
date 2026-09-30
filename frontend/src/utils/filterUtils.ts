import { UserProfile, FilterState, AIOverviewData } from '../types';
import { numericExperience } from './experience';
import { ALL_SKILLS, ALL_LOCATIONS, ALL_COMPANIES } from '../data/mockProfiles';
import { escapeRegExp, getSearchTerms } from './searchTerms';

export const INITIAL_FILTER_STATE: FilterState = {
  keyword: '',
  locations: [],
  remoteTypes: [],
  selectedSkills: [],
  skillMatchMode: 'ANY',
  minExperience: 0,
  maxExperience: 20,
  companies: [],
  availability: [],
  departments: [],
  sortBy: 'relevance',
};

/**
 * Natural language parser that extracts structured intent from conversational prompts
 * e.g., "Senior remote PyTorch engineers in London with 5+ years exp"
 */
export function parseNaturalLanguageQuery(
  query: string,
  profiles: UserProfile[] = [],
): Partial<FilterState> {
  const clean = query.trim().toLowerCase();
  if (!clean) return {};

  const availableSkills = profiles.length
    ? Array.from(new Set(profiles.flatMap((profile) => profile.skills))).sort()
    : ALL_SKILLS;
  const availableLocations = profiles.length
    ? Array.from(new Set(profiles.map((profile) => profile.location))).sort()
    : ALL_LOCATIONS;
  const availableCompanies = profiles.length
    ? Array.from(new Set(profiles.map((profile) => profile.company))).sort()
    : ALL_COMPANIES;

  const detected: Partial<FilterState> = {
    selectedSkills: [],
    locations: [],
    remoteTypes: [],
    companies: [],
    availability: [],
  };

  // 1. Detect Skills
  availableSkills.forEach((skill) => {
    const sLower = skill.toLowerCase();
    const regex = new RegExp(`\\b${escapeRegExp(sLower)}\\b`, 'i');
    if (regex.test(clean)) {
      detected.selectedSkills?.push(skill);
    }
  });

  // 2. Detect Remote Mode
  if (/\b(remote|wfh|work from home|anywhere)\b/i.test(clean)) {
    detected.remoteTypes?.push('Remote');
  }
  if (/\b(hybrid)\b/i.test(clean)) {
    detected.remoteTypes?.push('Hybrid');
  }
  if (/\b(on-site|onsite|in-office|in office)\b/i.test(clean)) {
    detected.remoteTypes?.push('On-site');
  }

  // 3. Detect Locations
  availableLocations.forEach((loc) => {
    const cityName = loc.split(',')[0]?.trim().toLowerCase();
    if (cityName && (clean.includes(cityName) || clean.includes(loc.toLowerCase()))) {
      detected.locations?.push(loc);
    }
  });

  // 4. Detect Companies
  availableCompanies.forEach((comp) => {
    const regex = new RegExp(`\\b${escapeRegExp(comp.toLowerCase())}\\b`, 'i');
    if (regex.test(clean)) {
      detected.companies?.push(comp);
    }
  });

  // 5. Detect Experience Levels / Numbers
  if (/\b(staff|principal|director|lead|head of)\b/i.test(clean)) {
    detected.minExperience = 8;
  } else if (/\b(senior|sr\.?)\b/i.test(clean)) {
    detected.minExperience = 5;
  } else if (/\b(junior|entry|grad|intern)\b/i.test(clean)) {
    detected.minExperience = 0;
    detected.maxExperience = 3;
  } else if (/\b(mid-level|intermediate)\b/i.test(clean)) {
    detected.minExperience = 3;
    detected.maxExperience = 6;
  }

  // Regex for "X+ years", "X yrs", "X-Y years"
  const rangeMatch = clean.match(/(\d+)\s*[-to]+\s*(\d+)\s*(?:years|yrs)/i);
  if (rangeMatch && rangeMatch[1] && rangeMatch[2]) {
    detected.minExperience = parseInt(rangeMatch[1], 10);
    detected.maxExperience = parseInt(rangeMatch[2], 10);
  } else {
    const plusMatch = clean.match(/(\d+)\s*\+?\s*(?:years|yrs)/i);
    if (plusMatch && plusMatch[1]) {
      detected.minExperience = parseInt(plusMatch[1], 10);
    }
  }

  // 6. Detect Availability
  if (/\b(available immediately|immediate|ready to start|available now)\b/i.test(clean)) {
    detected.availability?.push('Available immediately');
  }
  if (/\b(freelance|contract|contractor|consultant)\b/i.test(clean)) {
    detected.availability?.push('Contract / Freelance');
  }
  if (/\b(open to offers|actively looking|open to work)\b/i.test(clean)) {
    detected.availability?.push('Open to offers');
  }

  return detected;
}

/**
 * Filter profiles with multi-criteria matching and natural language tolerance
 */
export function filterProfiles(profiles: UserProfile[], filters: FilterState): UserProfile[] {
  return profiles.filter((profile) => {
    // 1. Keyword search (checks name, title, bio, company, department, skills, pastCompanies, education)
    if (filters.keyword.trim()) {
      const q = filters.keyword.toLowerCase().trim();
      const searchableFields = [
        profile.name,
        profile.title,
        profile.company,
        profile.department,
        profile.bio,
        profile.location,
        profile.education,
        ...(profile.skills || []),
        ...(profile.pastCompanies || []),
        ...(profile.featuredProjects || []),
      ].join(' ').toLowerCase();

      // Check if all words in keyword query match or if any significant phrase matches
      const queryWords = getSearchTerms(q);

      if (queryWords.length > 0) {
        // Must match either the exact phrase or all significant tokens
        const hasAllWords = queryWords.every((word) => searchableFields.includes(word));
        const hasSubstring = searchableFields.includes(q);
        if (!hasAllWords && !hasSubstring) {
          // If query has 3+ words, allow matching 75% of words
          if (queryWords.length >= 3) {
            const matchedCount = queryWords.filter((word) => searchableFields.includes(word)).length;
            if (matchedCount / queryWords.length < 0.66) {
              return false;
            }
          } else {
            return false;
          }
        }
      }
    }

    // 2. Locations filter
    if (filters.locations.length > 0) {
      const matchesLocation = filters.locations.some((loc) => {
        const city = loc.toLowerCase().split(',')[0]?.trim();
        return city ? profile.location.toLowerCase().includes(city) : false;
      });
      if (!matchesLocation) return false;
    }

    // 3. Remote Types filter (Remote, Hybrid, On-site)
    if (filters.remoteTypes.length > 0) {
      if (!filters.remoteTypes.includes(profile.remoteType)) {
        return false;
      }
    }

    // 4. Skills filter (with ANY / ALL modes)
    if (filters.selectedSkills.length > 0) {
      const profileSkillsLower = [...profile.skills, ...(profile.certifications ?? [])].map((s) => s.toLowerCase());
      if (filters.skillMatchMode === 'ALL') {
        const matchesAll = filters.selectedSkills.every((skill) =>
          profileSkillsLower.includes(skill.toLowerCase())
        );
        if (!matchesAll) return false;
      } else {
        // ANY mode
        const matchesAny = filters.selectedSkills.some((skill) =>
          profileSkillsLower.includes(skill.toLowerCase())
        );
        if (!matchesAny) return false;
      }
    }

    // 5. Years of Experience range
    const experience = numericExperience(profile.yearsOfExperience);
    if (experience < filters.minExperience) {
      return false;
    }
    if (filters.maxExperience < 20 && experience > filters.maxExperience) {
      return false;
    }

    // 6. Companies filter
    if (filters.companies.length > 0) {
      const matchesCompany = filters.companies.some(
        (comp) =>
          profile.company.toLowerCase() === comp.toLowerCase() ||
          (profile.pastCompanies &&
            profile.pastCompanies.some((pc) => pc.toLowerCase() === comp.toLowerCase()))
      );
      if (!matchesCompany) return false;
    }

    // 7. Availability filter
    if (filters.availability.length > 0) {
      if (!filters.availability.includes(profile.availability)) {
        return false;
      }
    }

    // 8. Departments filter
    if (filters.departments.length > 0) {
      if (!filters.departments.includes(profile.department)) {
        return false;
      }
    }

    return true;
  });
}

/**
 * Intelligent sorting with relevance scoring
 */
export function sortProfiles(
  profiles: UserProfile[],
  sortBy: FilterState['sortBy'],
  keyword: string,
  aiMatchedIds?: string[]
): UserProfile[] {
  const list = [...profiles];
  const aiIdSet = aiMatchedIds ? new Set(aiMatchedIds) : null;
  const aiRank = new Map(aiMatchedIds?.map((id, index) => [id, index]) || []);

  const aiBoost = (profile: UserProfile): number => {
    return aiIdSet?.has(profile.id) ? 25 : 0;
  };

  switch (sortBy) {
    case 'experience-desc':
      return list.sort((a, b) => numericExperience(b.yearsOfExperience) - numericExperience(a.yearsOfExperience));
    case 'experience-asc':
      // Unknown experience sorts last, not as zero years: same nulls-last
      // convention as the rate-asc branch below.
      return list.sort((a, b) => (a.yearsOfExperience ?? Number.MAX_SAFE_INTEGER) - (b.yearsOfExperience ?? Number.MAX_SAFE_INTEGER));
    case 'recent': {
      return list.sort((a, b) => {
        const timeA = validTimestamp(a.dateAdded);
        const timeB = validTimestamp(b.dateAdded);
        return timeB - timeA;
      });
    }
    case 'name-asc':
      return list.sort((a, b) => a.name.localeCompare(b.name));
    case 'name-desc':
      return list.sort((a, b) => b.name.localeCompare(a.name));
    case 'rate-desc':
      return list.sort((a, b) => (b.dayRate ?? 0) - (a.dayRate ?? 0));
    case 'rate-asc':
      return list.sort((a, b) => (a.dayRate ?? Number.MAX_SAFE_INTEGER) - (b.dayRate ?? Number.MAX_SAFE_INTEGER));
    case 'rating-desc':
      return list.sort((a, b) => (b.rating ?? 0) - (a.rating ?? 0));
    case 'relevance':
    default: {
      // The backend has already ranked structured AI matches by hard
      // requirements, availability, and audited experience. Preserve that
      // order rather than letting incidental words in the original sentence
      // reshuffle the shortlist.
      if (aiRank.size > 0) {
        return list.sort((a, b) => (aiRank.get(a.id) ?? Number.MAX_SAFE_INTEGER) - (aiRank.get(b.id) ?? Number.MAX_SAFE_INTEGER));
      }
      if (!keyword.trim()) {
        return list.sort((a, b) => (b.rating ?? 0) - (a.rating ?? 0));
      }
      // Calculate relevance score
      const q = keyword.toLowerCase().trim();
      const tokens = q.split(/\s+/).filter(Boolean);

      return list.sort((a, b) => {
        const scoreA = calculateRelevanceScore(a, q, tokens) + aiBoost(a);
        const scoreB = calculateRelevanceScore(b, q, tokens) + aiBoost(b);
        return scoreB - scoreA;
      });
    }
  }
}

function validTimestamp(value?: string): number {
  if (!value) return 0;
  const timestamp = Date.parse(value);
  return Number.isFinite(timestamp) ? timestamp : 0;
}

function calculateRelevanceScore(profile: UserProfile, query: string, tokens: string[]): number {
  let score = (profile.rating ?? 0) * 2;
  const nameL = profile.name.toLowerCase();
  const titleL = profile.title.toLowerCase();
  const bioL = profile.bio.toLowerCase();
  const compL = profile.company.toLowerCase();
  const skillsL = profile.skills.map((s) => s.toLowerCase());

  if (nameL.includes(query)) score += 50;
  if (titleL.includes(query)) score += 35;
  if (compL.includes(query)) score += 20;

  tokens.forEach((token) => {
    if (nameL.includes(token)) score += 15;
    if (titleL.includes(token)) score += 12;
    if (skillsL.some((s) => s.includes(token))) score += 10;
    if (compL.includes(token)) score += 8;
    if (bioL.includes(token)) score += 4;
  });

  if (profile.availability === 'Available immediately') score += 5;
  return score;
}

/**
 * Generate Google Gemini-style AI Overview summary
 */
export function generateAIOverview(
  query: string,
  profiles: UserProfile[],
  filters: FilterState
): AIOverviewData | null {
  if (profiles.length === 0) return null;

  const total = profiles.length;
  const recordedExperience = profiles
    .map((profile) => profile.yearsOfExperience)
    .filter((years): years is number => years != null);
  const avgExp = recordedExperience.length > 0
    ? Math.round(recordedExperience.reduce((acc, years) => acc + years, 0) / recordedExperience.length)
    : null;
  const availableCount = profiles.filter(
    (p) => p.availability === 'Available immediately' || p.availability === 'Open to offers'
  ).length;
  const availablePercentage = Math.round((availableCount / total) * 100);

  // Collect most common skills in the matched cohort
  const skillCountMap = new Map<string, number>();
  profiles.forEach((p) => {
    p.skills.forEach((s) => {
      skillCountMap.set(s, (skillCountMap.get(s) || 0) + 1);
    });
  });

  const sortedSkills = Array.from(skillCountMap.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map((e) => e[0]);

  const topCompanies = Array.from(
    new Set(profiles.map((p) => p.company).filter((company) => company !== 'Company not recorded')),
  ).slice(0, 3);
  const remotePercentage = Math.round(
    (profiles.filter((p) => p.remoteType === 'Remote').length / total) * 100
  );

  let summary = '';
  if (query.trim()) {
    summary = `Identified ${total} ${
      total === 1 ? 'contractor' : 'contractors'
    } matching "${query}". ${avgExp == null ? 'Audited experience was not recorded for this cohort.' : `The cohort averages ${avgExp} years of offshore & survey tenure.`} Deep domain expertise includes ${sortedSkills.slice(0, 3).join(', ')}.`;
  } else if (filters.selectedSkills.length > 0) {
    const companySummary = topCompanies.length > 0
      ? `Recorded company history includes ${topCompanies.join(', ')}.`
      : 'Company history was not recorded for this cohort.';
    summary = `Found ${total} offshore contractors matching ${filters.selectedSkills.join(', ')}. ${companySummary}`;
  } else {
    summary = `Indexed ${total} contractors across marine geophysics, environmental MMO/PAM, geotechnical, and client-representation work. ${availablePercentage}% are available immediately or open for mobilization.`;
  }

  const keyInsights: string[] = [
    `${availablePercentage}% of matched contractors are available for immediate mobilization or offshore rotation.`,
    `${remotePercentage}% support hybrid onshore processing & remote QC reporting.`,
  ];

  const rates = profiles.flatMap((profile) => (
    profile.dayRate != null && Number.isFinite(profile.dayRate) ? [profile.dayRate] : []
  ));
  if (rates.length > 0) {
    const minRate = Math.min(...rates);
    const maxRate = Math.max(...rates);
    keyInsights.push(`Recorded day rates across this cohort range between £${minRate} - £${maxRate} / day.`);
  }

  return {
    summary,
    keyInsights,
    topSkillsFound: sortedSkills,
    avgExperience: avgExp,
    availablePercentage,
    highlightProfileId: profiles[0]?.id,
  };
}

export function getActiveFilterCount(filters: FilterState): number {
  let count = 0;
  if (filters.keyword.trim()) count++;
  if (filters.locations.length > 0) count += filters.locations.length;
  if (filters.remoteTypes.length > 0) count += filters.remoteTypes.length;
  if (filters.selectedSkills.length > 0) count += filters.selectedSkills.length;
  if (filters.minExperience > 0 || filters.maxExperience < 20) count++;
  if (filters.companies.length > 0) count += filters.companies.length;
  if (filters.availability.length > 0) count += filters.availability.length;
  if (filters.departments.length > 0) count += filters.departments.length;
  return count;
}
