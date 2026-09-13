import { describe, expect, it } from 'vitest'
import { apolloResultHasErrors, isSessionDataReady, isSessionRequestCurrent } from './sessionScope'

describe('apolloResultHasErrors', () => {
  it('detects an Apollo error returned alongside partial data', () => {
    expect(apolloResultHasErrors({ error: new Error('forbidden') })).toBe(true)
    expect(apolloResultHasErrors({ errors: [{ message: 'forbidden' }] })).toBe(true)
  })

  it('accepts a result without errors', () => {
    expect(apolloResultHasErrors({})).toBe(false)
  })
})

describe('isSessionDataReady', () => {
  it('rejects retained data when the current request has errored', () => {
    expect(isSessionDataReady(true, 'session-1', 'session-1', false, new Error('forbidden'))).toBe(false)
  })

  it('accepts only the loaded, settled session scope', () => {
    expect(isSessionDataReady(true, 'session-1', 'session-1', false, undefined)).toBe(true)
    expect(isSessionDataReady(true, 'session-1', 'session-1', true, undefined)).toBe(false)
    expect(isSessionDataReady(true, 'session-1', 'session-2', false, undefined)).toBe(false)
  })
})

describe('isSessionRequestCurrent', () => {
  it('rejects a late response from an earlier request or session', () => {
    expect(isSessionRequestCurrent(1, 2, 'session-2', 'session-1')).toBe(false)
    expect(isSessionRequestCurrent(2, 2, 'session-2', 'session-1')).toBe(false)
  })

  it('accepts the current request for the current session', () => {
    expect(isSessionRequestCurrent(2, 2, 'session-2', 'session-2')).toBe(true)
  })
})
