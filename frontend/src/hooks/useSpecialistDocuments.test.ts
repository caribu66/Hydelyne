import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  backendCategoryToFrontend,
  getDocumentComplianceStatus,
  refreshAfterDocumentMutation,
} from './useSpecialistDocuments'

describe('getDocumentComplianceStatus', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('treats a date-only expiry occurring today as expiring, not expired', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-09-12T15:00:00'))

    const result = getDocumentComplianceStatus({
      id: 'doc-1',
      title: 'Medical',
      category: 'medical',
      fileName: 'medical.pdf',
      expiryDate: '2026-09-12',
      uploadedAt: '2026-01-01T00:00:00Z',
    })

    expect(result.status).toBe('expiring_soon')
    expect(result.daysLeft).toBe(0)
  })

  it('does not imply approval for an unverified permanent document', () => {
    const result = getDocumentComplianceStatus({
      id: 'doc-2',
      title: 'Seamans book',
      category: 'seamans_book',
      fileName: 'seamans-book.pdf',
      uploadedAt: '2026-01-01T00:00:00Z',
      isVerified: false,
    })

    expect(result.status).toBe('no_expiry')
    expect(result.label).toBe('No expiry recorded')
  })

  it('does not infer permanence from approval when no expiry is recorded', () => {
    const result = getDocumentComplianceStatus({
      id: 'doc-verified-no-expiry',
      title: 'Seamans book',
      category: 'seamans_book',
      fileName: 'seamans-book.pdf',
      uploadedAt: '2026-01-01T00:00:00Z',
      isVerified: true,
    })

    expect(result.status).toBe('no_expiry')
    expect(result.label).toBe('No expiry recorded')
  })

  it('does not present an invalid expiry date as valid', () => {
    const result = getDocumentComplianceStatus({
      id: 'doc-3',
      title: 'Certificate',
      category: 'certificate',
      fileName: 'certificate.pdf',
      expiryDate: 'not-a-date',
      uploadedAt: '2026-01-01T00:00:00Z',
    })

    expect(result.status).toBe('invalid')
    expect(result.label).toBe('Invalid expiry date')
  })

  it('rejects date-only values with impossible calendar days', () => {
    const result = getDocumentComplianceStatus({
      id: 'doc-invalid-calendar-date',
      title: 'Certificate',
      category: 'certificate',
      fileName: 'certificate.pdf',
      expiryDate: '2026-02-31',
      uploadedAt: '2026-01-01T00:00:00Z',
    })

    expect(result.status).toBe('invalid')
    expect(result.label).toBe('Invalid expiry date')
  })

  it('does not imply review approval for an unverified future expiry', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-09-12T15:00:00'))

    const result = getDocumentComplianceStatus({
      id: 'doc-unverified-future-expiry',
      title: 'Certificate',
      category: 'certificate',
      fileName: 'certificate.pdf',
      expiryDate: '2027-09-12',
      uploadedAt: '2026-01-01T00:00:00Z',
      isVerified: false,
    })

    expect(result.status).toBe('valid')
    expect(result.label).toBe('Expiry recorded (12 mo remaining)')
  })

  it('does not present a rejected document as date-valid', () => {
    const result = getDocumentComplianceStatus({
      id: 'doc-rejected',
      title: 'Rejected certificate',
      category: 'certificate',
      fileName: 'certificate.pdf',
      expiryDate: '2027-09-12',
      extractionStatus: 'rejected',
      uploadedAt: '2026-01-01T00:00:00Z',
    })

    expect(result.status).toBe('invalid')
    expect(result.label).toBe('Rejected document')
  })
})

describe('backendCategoryToFrontend', () => {
  it('recognizes the backend canonical certificate classification', () => {
    expect(backendCategoryToFrontend('certificate')).toBe('certificate')
    expect(backendCategoryToFrontend('cert')).toBe('certificate')
  })
})

describe('document mutation refresh handling', () => {
  it('reports a refresh failure separately from a completed mutation', async () => {
    const result = await refreshAfterDocumentMutation(async () => {
      throw new Error('refresh unavailable')
    })

    expect(result).toEqual({ refreshFailed: true })
  })

  it('reports a successful refresh', async () => {
    const result = await refreshAfterDocumentMutation(async () => undefined)

    expect(result).toEqual({ refreshFailed: false })
  })
})
