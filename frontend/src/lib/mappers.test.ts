import { describe, expect, it } from 'vitest'
import { backendCrewToProfile } from './mappers'

describe('backendCrewToProfile', () => {
  it('uses a neutral initials avatar instead of a stock person for live records', () => {
    const profile = backendCrewToProfile({
      id: 'crew-avatar',
      fullName: 'Ada Lovelace',
    })

    expect(profile.avatar.startsWith('data:image/svg+xml,')).toBe(true)
    expect(decodeURIComponent(profile.avatar)).toContain('>AL</text>')
    expect(decodeURIComponent(profile.avatar)).toContain('fill="Canvas"')
    expect(decodeURIComponent(profile.avatar)).toContain('fill="CanvasText"')
    expect(profile.avatar).not.toContain('unsplash')
  })

  it('ignores malformed tag values without dropping the roster record', () => {
    const profile = backendCrewToProfile({
      id: 'crew-1',
      fullName: 'Test Contractor',
      tags: JSON.stringify(['MMO', { unexpected: true }, 42, null]),
    })

    expect(profile.id).toBe('crew-1')
    expect(profile.expertise).toContain('MMO')
    expect(profile.skills).not.toContain('[object Object]')
  })

  it('maps location from residence rather than nationality', () => {
    const profile = backendCrewToProfile({
      id: 'crew-2',
      fullName: 'Dutch Contractor',
      nationality: 'Dutch',
      countryOfResidence: 'United Kingdom',
    })

    expect(profile.location).toBe('United Kingdom')
    expect(profile.nationality).toBe('Dutch')
  })

  it('keeps languages when the API supplies a string representation', () => {
    const profile = backendCrewToProfile({
      id: 'crew-3',
      fullName: 'Language Contract Test',
      languages: 'English',
    })

    expect(profile.languages).toEqual(['English'])
  })

  it('parses a JSON scalar language without retaining quote characters', () => {
    const profile = backendCrewToProfile({
      id: 'crew-4',
      fullName: 'JSON Language Contract Test',
      languages: JSON.stringify('English'),
    })

    expect(profile.languages).toEqual(['English'])
  })
})
