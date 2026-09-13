import { describe, expect, it } from 'vitest'
import { formatExpiryTime } from './contractorDocumentUtils'

describe('formatExpiryTime', () => {
  it('does not render malformed token expiry as valid NaN days', () => {
    expect(formatExpiryTime('not-a-date')).toEqual({
      relative: 'Expiry unavailable',
      full: 'Expiry date could not be read',
    })
  })
})
