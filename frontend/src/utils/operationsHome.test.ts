import { describe, expect, it } from 'vitest'
import {
  deriveCrewReadinessMetrics,
  formatExpiringCertSearchQuery,
  formatProjectSearchQuery,
  getFirstName,
  getGreeting,
  getGreetingForUser,
  isStaffOrAdmin,
} from './operationsHome'
import { UserProfile } from '../types'

function makeProfile(overrides: Partial<UserProfile> = {}): UserProfile {
  return {
    id: 'p1',
    name: 'Alex Rivera',
    title: 'Marine Mammal Observer',
    avatar: '',
    company: 'Hydenlyne',
    department: 'Environmental',
    location: 'Aberdeen, Scotland',
    remoteType: 'On-site',
    yearsOfExperience: 5,
    skills: [],
    bio: '',
    availability: 'Available immediately',
    education: '',
    email: 'alex@example.com',
    ...overrides,
  }
}

describe('getFirstName', () => {
  it('extracts the first token from a full name', () => {
    expect(getFirstName('Test Recruiter')).toBe('Test')
    expect(getFirstName('Alex')).toBe('Alex')
    expect(getFirstName('  Morgan Reed  ')).toBe('Morgan')
  })

  it('returns empty for blank or missing names', () => {
    expect(getFirstName('')).toBe('')
    expect(getFirstName('   ')).toBe('')
    expect(getFirstName(null)).toBe('')
    expect(getFirstName(undefined)).toBe('')
  })
})

describe('isStaffOrAdmin', () => {
  it('allows staff and admin, denies others', () => {
    expect(isStaffOrAdmin('staff')).toBe(true)
    expect(isStaffOrAdmin('admin')).toBe(true)
    expect(isStaffOrAdmin('user')).toBe(false)
    expect(isStaffOrAdmin(null)).toBe(false)
    expect(isStaffOrAdmin(undefined)).toBe(false)
    expect(isStaffOrAdmin('')).toBe(false)
  })
})

describe('getGreeting', () => {
  it('returns time-aware greeting with first name', () => {
    expect(getGreeting(8, 'Alex')).toBe('Good morning, Alex')
    expect(getGreeting(13, 'Alex')).toBe('Good afternoon, Alex')
    expect(getGreeting(19, 'Alex')).toBe('Good evening, Alex')
  })

  it('omits the name when not provided', () => {
    expect(getGreeting(9, '')).toBe('Good morning')
    expect(getGreeting(14, '   ')).toBe('Good afternoon')
  })
})

describe('getGreetingForUser', () => {
  it('derives greeting from fullName and current hour', () => {
    expect(getGreetingForUser('Test Recruiter', new Date('2026-09-06T08:00:00'))).toBe(
      'Good morning, Test'
    )
    expect(getGreetingForUser('Jamie Cole', new Date('2026-09-06T15:00:00'))).toBe(
      'Good afternoon, Jamie'
    )
  })
})

describe('deriveCrewReadinessMetrics', () => {
  it('counts by availability status', () => {
    const profiles = [
      makeProfile({ availability: 'Available immediately' }),
      makeProfile({ id: 'p2', availability: 'Available immediately' }),
      makeProfile({ id: 'p3', availability: 'Employed (Not looking)' }),
      makeProfile({ id: 'p4', availability: 'Unavailable' }),
      makeProfile({ id: 'p5', availability: 'Unavailable' }),
      makeProfile({ id: 'p6', availability: 'Unavailable' }),
    ]
    expect(deriveCrewReadinessMetrics(profiles)).toEqual({
      available: 2,
      onAssignment: 1,
      unavailable: 3,
      total: 6,
    })
  })

  it('returns zeros for an empty roster', () => {
    expect(deriveCrewReadinessMetrics([])).toEqual({
      available: 0,
      onAssignment: 0,
      unavailable: 0,
      total: 0,
    })
  })

  it('ignores unexpected availability values but still counts total', () => {
    const profiles = [
      makeProfile({ availability: 'Available immediately' }),
      makeProfile({ id: 'p2', availability: 'Contract / Freelance' as unknown as UserProfile['availability'] }),
    ]
    // Contract / Freelance is a valid variant but is deliberately not counted as a readiness bucket here;
    // it still contributes to total.
    const result = deriveCrewReadinessMetrics(profiles)
    expect(result.total).toBe(2)
    // Only the explicit metric buckets are counted — freelance is not in available/onAssignment/unavailable.
    expect(result.available).toBe(1)
  })
})

describe('formatProjectSearchQuery', () => {
  it('joins project type and location', () => {
    expect(formatProjectSearchQuery({ projectType: 'marine_seismic', location: 'North Sea' })).toBe(
      'marine seismic North Sea'
    )
  })

  it('falls back to country when location missing', () => {
    expect(formatProjectSearchQuery({ projectType: 'offshore_wind', country: 'Norway' })).toBe(
      'offshore wind Norway'
    )
  })

  it('handles missing fields', () => {
    expect(formatProjectSearchQuery({})).toBe('')
    expect(formatProjectSearchQuery({ location: 'Aberdeen' })).toBe('Aberdeen')
  })
})

describe('formatExpiringCertSearchQuery', () => {
  it('builds a query for a specific cert type', () => {
    expect(formatExpiringCertSearchQuery('BOSIET')).toBe('Who has BOSIET expiring soon?')
  })

  it('builds a generic query when no type given', () => {
    expect(formatExpiringCertSearchQuery()).toBe('Who has certifications expiring soon?')
    expect(formatExpiringCertSearchQuery('   ')).toBe('Who has certifications expiring soon?')
  })
})
