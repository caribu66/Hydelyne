import { describe, expect, it } from 'vitest'
import { resolveCrewProfileState } from './useCrewProfiles'

describe('resolveCrewProfileState', () => {
  it('keeps an authoritative empty roster empty when demo mode is enabled', () => {
    expect(resolveCrewProfileState([], false, true)).toEqual({
      profiles: [],
      isLive: true,
      demoActive: false,
    })
  })

  it('uses demo profiles only when no live response exists', () => {
    const result = resolveCrewProfileState(undefined, false, true)

    expect(result.demoActive).toBe(true)
    expect(result.isLive).toBe(false)
    expect(result.profiles.length).toBeGreaterThan(0)
  })

  it('does not show demo profiles after a live roster error', () => {
    expect(resolveCrewProfileState(undefined, false, true, true)).toEqual({
      profiles: [],
      isLive: false,
      demoActive: false,
    })
  })

  it('does not show retained live profiles after a roster error', () => {
    expect(resolveCrewProfileState([{ id: 'stale-1', fullName: 'Stale profile' }], false, true, true)).toEqual({
      profiles: [],
      isLive: false,
      demoActive: false,
    })
  })
})
