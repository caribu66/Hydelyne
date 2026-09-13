import { describe, expect, it } from 'vitest'
import {
  documentTimestamp,
  formatDocumentDate,
  formatDocumentDateTime,
  isDocumentAuditCleared,
  resolveSelectedDocument,
} from './documentVaultUtils'

describe('document vault date utilities', () => {
  it('fails closed for malformed dates', () => {
    expect(documentTimestamp('not-a-date')).toBeNull()
    expect(formatDocumentDate('not-a-date')).toBe('Archived')
    expect(formatDocumentDateTime('not-a-date')).toBe('Date unavailable')
  })

  it('formats valid dates consistently', () => {
    expect(formatDocumentDate('2026-09-13T12:00:00Z')).toMatch(/13 Sep(t)? 2026/)
    expect(formatDocumentDateTime('2026-09-13T12:00:00Z')).not.toBe('Date unavailable')
  })

  it('preserves the calendar day for date-only values', () => {
    expect(formatDocumentDate('2026-09-13')).toMatch(/13 Sep(t)? 2026/)
    expect(formatDocumentDate('2026-02-31')).toBe('Archived')
  })

  it('does not clear an audit with expiring or unverified documents', () => {
    expect(isDocumentAuditCleared([{ isVerified: true, complianceStatus: 'expiring_soon' }])).toBe(false)
    expect(isDocumentAuditCleared([{ isVerified: true, complianceStatus: 'invalid' }])).toBe(false)
    expect(isDocumentAuditCleared([{ isVerified: false, complianceStatus: 'valid' }])).toBe(false)
    expect(isDocumentAuditCleared([{ isVerified: true, complianceStatus: 'valid' }])).toBe(true)
    expect(isDocumentAuditCleared([])).toBe(false)
  })
})

describe('selected document reconciliation', () => {
  const selected = {
    id: 'doc-1',
    title: 'Old title',
    category: 'certificate' as const,
    fileName: 'certificate.pdf',
    uploadedAt: '2026-01-01T00:00:00Z',
  }

  it('closes the preview when the selected record disappears', () => {
    expect(resolveSelectedDocument(selected, [])).toBeNull()
  })

  it('uses the refreshed record with the same identity', () => {
    const refreshed = { ...selected, title: 'Updated title' }
    expect(resolveSelectedDocument(selected, [refreshed])).toBe(refreshed)
  })
})
