import { UserProfile } from '../types'

export function getFirstName(fullName: string | null | undefined): string {
  if (!fullName) return ''
  const trimmed = fullName.trim()
  if (!trimmed) return ''
  const first = trimmed.split(/\s+/)[0]
  return first ?? ''
}

export function isStaffOrAdmin(role: string | null | undefined): boolean {
  return role === 'staff' || role === 'admin'
}

export function getGreeting(hour: number, firstName: string): string {
  const name = firstName.trim()
  const prefix =
    hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening'
  return name ? `${prefix}, ${name}` : prefix
}

export function getGreetingForUser(
  fullName: string | null | undefined,
  now: Date = new Date()
): string {
  const firstName = getFirstName(fullName)
  return getGreeting(now.getHours(), firstName)
}

export interface CrewReadinessMetrics {
  available: number
  onAssignment: number
  unavailable: number
  total: number
}

export function deriveCrewReadinessMetrics(profiles: UserProfile[]): CrewReadinessMetrics {
  let available = 0
  let onAssignment = 0
  let unavailable = 0
  for (const profile of profiles) {
    const availability = profile.availability
    if (availability === 'Available immediately') available += 1
    else if (availability === 'Employed (Not looking)') onAssignment += 1
    else if (availability === 'Unavailable') unavailable += 1
  }
  return {
    available,
    onAssignment,
    unavailable,
    total: profiles.length,
  }
}

export function formatProjectSearchQuery(project: {
  projectType?: string | null
  location?: string | null
  country?: string | null
}): string {
  const parts: string[] = []
  if (project.projectType) {
    // Convert enum like marine_seismic -> "marine seismic"
    parts.push(project.projectType.replaceAll('_', ' '))
  }
  const loc = project.location || project.country
  if (loc) parts.push(loc)
  return parts.join(' ').trim()
}

export function formatCalendarDate(value: string | null | undefined): string {
  if (!value) return '—'

  const dateOnly = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  if (dateOnly) {
    const [, yearText, monthText, dayText] = dateOnly
    const year = Number(yearText)
    const month = Number(monthText)
    const day = Number(dayText)
    const localDate = new Date(year, month - 1, day)
    if (
      localDate.getFullYear() === year
      && localDate.getMonth() === month - 1
      && localDate.getDate() === day
    ) {
      return localDate.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
    }
    return value
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}

export function isoDateAfterDays(days: number, now: Date = new Date()): string {
  if (!Number.isInteger(days)) throw new Error('days must be an integer')
  const date = new Date(now.getFullYear(), now.getMonth(), now.getDate() + days)
  const year = date.getFullYear().toString().padStart(4, '0')
  const month = (date.getMonth() + 1).toString().padStart(2, '0')
  const day = date.getDate().toString().padStart(2, '0')
  return `${year}-${month}-${day}`
}

export function formatExpiringCertSearchQuery(certType?: string): string {
  if (certType && certType.trim()) return `Who has ${certType.trim()} expiring soon?`
  return 'Who has certifications expiring soon?'
}
