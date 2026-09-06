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

export function formatExpiringCertSearchQuery(certType?: string): string {
  if (certType && certType.trim()) return `Who has ${certType.trim()} expiring soon?`
  return 'Who has certifications expiring soon?'
}
