import { describe, expect, it } from 'vitest'
import { availabilityLabel } from './profileLabels'

describe('availabilityLabel', () => {
  it('makes missing availability explicit', () => {
    expect(availabilityLabel(undefined)).toBe('Availability not recorded')
    expect(availabilityLabel('  ')).toBe('Availability not recorded')
  })

  it('preserves recorded availability', () => {
    expect(availabilityLabel('Available immediately')).toBe('Available immediately')
  })
})
