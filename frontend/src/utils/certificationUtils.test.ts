import { describe, expect, it, vi } from 'vitest'
import { certificationExpiryStatus } from './certificationUtils'

describe('certificationExpiryStatus', () => {
  it('overrides stale status data when the expiry date is past', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-09-13T12:00:00Z'))
    expect(certificationExpiryStatus('2026-09-12')).toBe('expired')
    vi.useRealTimers()
  })

  it('treats malformed and missing dates as unknown', () => {
    expect(certificationExpiryStatus('not-a-date')).toBe('invalid')
    expect(certificationExpiryStatus(null)).toBeNull()
  })

  it('rejects impossible calendar dates', () => {
    expect(certificationExpiryStatus('2026-02-31')).toBe('invalid')
  })
})
