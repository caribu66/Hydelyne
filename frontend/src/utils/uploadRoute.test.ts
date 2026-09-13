import { describe, expect, it } from 'vitest'
import { decodeUploadTokenSegment } from './uploadRoute'

describe('decodeUploadTokenSegment', () => {
  it('decodes a valid token segment', () => {
    expect(decodeUploadTokenSegment('token%2Dvalue')).toBe('token-value')
  })

  it('preserves malformed encoding for safe API rejection', () => {
    expect(decodeUploadTokenSegment('token%ZZ')).toBe('token%ZZ')
  })
})
