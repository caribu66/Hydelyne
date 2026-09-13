import { describe, expect, it } from 'vitest'
import { isVesselSearchSessionReady } from './vesselSearchUtils'

describe('vessel search result visibility', () => {
  it('does not keep prior results visible after the current request errors', () => {
    const loadedSessionKey = 'session-1'
    const sessionKey = 'session-1'
    const loading = false
    const error = new Error('lookup failed')

    expect(isVesselSearchSessionReady(loadedSessionKey, sessionKey, loading, error)).toBe(false)
  })
})
