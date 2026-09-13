import { describe, expect, it } from 'vitest'
import { isAddCrewOperationCurrent, isCvProcessingFailure } from './addCrewMemberUtils'

describe('isCvProcessingFailure', () => {
  it('treats failed extraction as a retryable submission error', () => {
    expect(isCvProcessingFailure('failed')).toBe(true)
  })

  it('treats rejected extraction as a submission error', () => {
    expect(isCvProcessingFailure('rejected')).toBe(true)
  })

  it('does not reject a CV that is awaiting review', () => {
    expect(isCvProcessingFailure('awaiting_review')).toBe(false)
  })

  it('does not treat an in-progress status as a completed submission', () => {
    expect(isCvProcessingFailure('processing')).toBe(false)
  })
})

describe('isAddCrewOperationCurrent', () => {
  it('rejects a failure from a prior modal operation', () => {
    expect(isAddCrewOperationCurrent(1, 2, true, true, 'session-1', 'session-1')).toBe(false)
    expect(isAddCrewOperationCurrent(2, 2, true, true, 'session-1', 'session-1')).toBe(true)
  })

  it('rejects updates after the modal closes or the session changes', () => {
    expect(isAddCrewOperationCurrent(2, 2, false, false, 'session-1', 'session-1')).toBe(false)
    expect(isAddCrewOperationCurrent(2, 2, true, true, 'session-2', 'session-1')).toBe(false)
  })
})
