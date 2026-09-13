export function documentTimestamp(value?: string): number | null {
  if (!value) return null
  const timestamp = Date.parse(value)
  return Number.isFinite(timestamp) ? timestamp : null
}

export function formatDocumentDate(value?: string): string {
  const calendarMatch = value?.match(/^(\d{4})-(\d{2})-(\d{2})$/)
  if (calendarMatch) {
    const year = Number(calendarMatch[1])
    const month = Number(calendarMatch[2])
    const day = Number(calendarMatch[3])
    const calendarDate = new Date(Date.UTC(year, month - 1, day))
    if (
      calendarDate.getUTCFullYear() !== year
      || calendarDate.getUTCMonth() !== month - 1
      || calendarDate.getUTCDate() !== day
    ) return 'Archived'
    return calendarDate.toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
      timeZone: 'UTC',
    })
  }
  const timestamp = documentTimestamp(value)
  if (timestamp === null) return 'Archived'
  return new Date(timestamp).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

export function formatDocumentDateTime(value?: string): string {
  const timestamp = documentTimestamp(value)
  return timestamp === null ? 'Date unavailable' : new Date(timestamp).toLocaleString()
}

export function isDocumentAuditCleared(
  documents: ReadonlyArray<{ isVerified?: boolean; complianceStatus: string }>,
): boolean {
  return documents.length > 0 && documents.every(
    (document) => document.isVerified === true
      && (document.complianceStatus === 'valid' || document.complianceStatus === 'no_expiry'),
  )
}

export function resolveSelectedDocument(
  selected: SpecialistDocument | null,
  documents: ReadonlyArray<SpecialistDocument>,
): SpecialistDocument | null {
  if (!selected) return null
  return documents.find((document) => document.id === selected.id) ?? null
}
import { SpecialistDocument } from '../types'
