import { describe, expect, it } from 'vitest'
import { UserProfile } from '../types'
import { selectAIResultProfiles } from './useSearchWorkspace'

function makeProfile(id: string): UserProfile {
  return {
    id,
    name: `Specialist ${id}`,
    title: 'Surveyor',
    avatar: '',
    company: '',
    department: '',
    location: '',
    remoteType: 'On-site',
    yearsOfExperience: 5,
    skills: [],
    bio: '',
    availability: 'Available immediately',
    education: '',
    email: `${id}@example.com`,
  }
}

describe('selectAIResultProfiles', () => {
  it('preserves an authoritative empty AI result set', () => {
    expect(selectAIResultProfiles([makeProfile('local-1')], [])).toEqual([])
  })

  it('keeps backend result order and resolves local profiles', () => {
    const local = makeProfile('local-1')
    const result = selectAIResultProfiles([local], [
      { id: 'remote-1', name: 'Remote Specialist', availability: 'available' },
      { id: 'local-1', name: local.name },
    ])

    expect(result.map((profile) => profile.id)).toEqual(['remote-1', 'local-1'])
    expect(result[0]?.availability).toBe('Available immediately')
    expect(result[1]).toBe(local)
  })

  it('uses the backend years field for results outside the loaded roster', () => {
    const [profile] = selectAIResultProfiles([], [
      { id: 'remote-1', name: 'Remote Specialist', experience_years: 12.5 },
    ])

    expect(profile?.yearsOfExperience).toBe(12.5)
  })

  it('synthesizes a usable avatar and department for results outside the roster', () => {
    const [profile] = selectAIResultProfiles([], [
      { id: 'remote-1', name: 'Remote Specialist', tags: ['PAM', 'Offshore'] },
    ])

    // An empty avatar breaks <img> in shortlist and detail views; reuse the
    // local mapper's initials avatar instead.
    expect(profile?.avatar).toMatch(/^data:image\/svg\+xml,/)
    expect(profile?.avatar).toContain('RS')
    // Same department derivation as the local roster mapper, not an empty badge.
    expect(profile?.department).toBe('Marine Environmental')
  })

  it('falls back to the generic department when AI tags carry no discipline', () => {
    const [profile] = selectAIResultProfiles([], [{ id: 'remote-1', name: 'Remote Specialist' }])

    expect(profile?.department).toBe('Survey, HSE & Client Rep')
  })
})
