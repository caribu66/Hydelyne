import { CampaignAssignmentStatus } from '../types'

function parseIsoCalendarDate(value: string, field: string): Date {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  const yearText = match?.[1]
  const monthText = match?.[2]
  const dayText = match?.[3]
  if (!yearText || !monthText || !dayText) {
    throw new Error(`Invalid ${field}: ${value}`)
  }

  const year = Number(yearText)
  const month = Number(monthText)
  const day = Number(dayText)
  const parsed = new Date(Date.UTC(year, month - 1, day))
  if (
    parsed.getUTCFullYear() !== year ||
    parsed.getUTCMonth() !== month - 1 ||
    parsed.getUTCDate() !== day
  ) {
    throw new Error(`Invalid ${field}: ${value}`)
  }
  return parsed
}

function normalizeOptionalCalendarDate(value: string | null | undefined): string | null {
  if (!value) return null
  const datePart = value.slice(0, 10)
  try {
    return parseIsoCalendarDate(datePart, 'date').toISOString().slice(0, 10)
  } catch {
    return null
  }
}

/**
 * Computes ISO date window given a start date and duration in days.
 */
export function calculateCampaignWindow(
  startDate: string,
  durationDays: number,
): { startDate: string; endDate: string } {
  const start = parseIsoCalendarDate(startDate, 'start date')
  if (!Number.isFinite(durationDays) || !Number.isInteger(durationDays) || durationDays < 1) {
    throw new Error('Duration days must be at least 1')
  }

  const end = new Date(start.getTime() + durationDays * 24 * 60 * 60 * 1000)
  return {
    startDate: start.toISOString().slice(0, 10),
    endDate: end.toISOString().slice(0, 10),
  }
}

/**
 * Returns user-facing label and semantic CSS badge class for campaign assignment status.
 */
export function formatAssignmentStatus(status: CampaignAssignmentStatus): {
  label: string
  badgeClass: string
} {
  switch (status) {
    case 'on_board':
      return { label: 'On Board', badgeClass: 'badge-positive' }
    case 'confirmed':
      return { label: 'Confirmed', badgeClass: 'badge-accent' }
    case 'proposed':
      return { label: 'Proposed', badgeClass: 'badge-neutral' }
    case 'completed':
      return { label: 'Completed', badgeClass: 'badge-neutral' }
    case 'cancelled':
      return { label: 'Cancelled', badgeClass: 'badge-neutral opacity-60' }
    default:
      return { label: status, badgeClass: 'badge-neutral' }
  }
}

/**
 * Formats standard Hydenlyne campaign mobilization reference.
 */
export function buildMobilizationReference(assignmentId: string): string {
  if (!assignmentId || !assignmentId.trim()) {
    return `HYD-MOB-2026-${Math.floor(1000 + Math.random() * 9000)}`
  }
  const clean = assignmentId.replace(/[^a-zA-Z0-9]/g, '').toUpperCase()
  return `HYD-MOB-${clean.slice(0, 8)}`
}

/**
 * Maps a vessel role on board to a targeted search keyword for specialist discovery.
 */
export function getRoleKeyword(role: string): string {
  if (!role) return ''
  const normalized = role.toLowerCase().trim()
  if (normalized.includes('mmo') || normalized.includes('mammal')) return 'MMO'
  if (normalized.includes('pam')) return 'PAM'
  if (normalized.includes('hydrograph') || normalized.includes('bathymetry')) return 'Hydrograph'
  if (normalized.includes('obn')) return 'OBN'
  if (normalized.includes('seismic')) return 'Seismic'
  if (normalized.includes('geotech') || normalized.includes('cpt') || normalized.includes('vibrocor')) return 'Geotech'
  if (normalized.includes('hse') || normalized.includes('safety') || normalized.includes('case')) return 'HSE'
  if (normalized.includes('fisher') || normalized.includes('flo')) return 'Fisheries'
  if (normalized.includes('rep') || normalized.includes('client')) return 'Client Rep'
  if (normalized.includes('survey') || normalized.includes('qc')) return 'Survey QC'
  return role.trim()
}

/**
 * Validates basic client-side inputs for campaign mobilization assignment.
 */
export function validateAssignmentInput(params: {
  roleOnBoard: string
  startDate: string
  durationDays: number
}): { valid: boolean; error?: string } {
  if (!params.roleOnBoard || !params.roleOnBoard.trim()) {
    return { valid: false, error: 'Role on board is required' }
  }
  try {
    parseIsoCalendarDate(params.startDate, 'start date')
  } catch {
    return { valid: false, error: 'A valid start date is required' }
  }
  if (
    !Number.isFinite(params.durationDays) ||
    !Number.isInteger(params.durationDays) ||
    params.durationDays < 1
  ) {
    return { valid: false, error: 'Duration must be at least 1 day' }
  }
  return { valid: true }
}

/**
 * Validates the administrator-supplied commercial rate before assignment.
 * A missing rate must remain missing rather than becoming an invented default.
 */
export function validateAgreedDayRate(
  value: number | null | undefined,
): { valid: boolean; error?: string } {
  if (value == null || !Number.isFinite(value) || value < 100) {
    return { valid: false, error: 'Enter an agreed day rate of at least £100' }
  }
  return { valid: true }
}

export interface PreflightComplianceCheck {
  item: string
  status: 'pass' | 'warn' | 'fail'
  detail: string
}

export interface PreflightComplianceReport {
  status: 'compliant' | 'warning' | 'critical'
  badgeClass: string
  badgeLabel: string
  issues: string[]
  checks: PreflightComplianceCheck[]
}

export interface CandidatePreflightInput {
  certifications?: Array<{
    certType?: string
    name?: string
    expiryDate?: string | null
    status?: string | null
    verificationStatus?: string | null
  }>
  medicalExpiry?: string | null
  campaignStartDate: string
  campaignEndDate: string
  availabilityStatus?: string
  availabilityDate?: string | null
}

/**
 * Evaluates candidate qualifications, offshore survival certs, medical, and availability
 * against a specific vessel campaign window.
 */
export function evaluateCandidatePreflightCompliance(
  input: CandidatePreflightInput
): PreflightComplianceReport {
  const issues: string[] = []
  const checks: PreflightComplianceCheck[] = []

  // 1. Availability / Schedule
  const isUnavailable =
    input.availabilityStatus === 'unavailable' ||
    input.availabilityStatus === 'Unavailable'

  const isOnAssignment =
    input.availabilityStatus === 'on_assignment' ||
    input.availabilityStatus === 'Employed (Not looking)'

  if (isUnavailable) {
    issues.push('Specialist is currently marked as unavailable in roster')
    checks.push({
      item: 'Schedule Availability',
      status: 'fail',
      detail: 'Specialist is marked unavailable',
    })
  } else if (isOnAssignment) {
    const availabilityDate = normalizeOptionalCalendarDate(input.availabilityDate)
    if (availabilityDate && availabilityDate < input.campaignStartDate) {
      checks.push({
        item: 'Schedule Availability',
        status: 'pass',
        detail: `Current assignment ends ${availabilityDate} prior to campaign`,
      })
    } else if (availabilityDate) {
      issues.push(`Specialist is on assignment through ${availabilityDate}`)
      checks.push({
        item: 'Schedule Availability',
        status: 'fail',
        detail: `Active tour ends ${availabilityDate} during or after campaign start`,
      })
    } else {
      issues.push('Candidate is currently marked as on assignment or unavailable')
      checks.push({
        item: 'Schedule Availability',
        status: 'fail',
        detail: 'Specialist has active assignment or is marked unavailable',
      })
    }
  } else {
    checks.push({
      item: 'Schedule Availability',
      status: 'pass',
      detail: 'Available for mobilization window',
    })
  }

  // 2. Offshore Medical
  const certs = input.certifications || []
  let effectiveMedExp = normalizeOptionalCalendarDate(input.medicalExpiry)
  let medCertName = 'Offshore Medical'

  const isRejected = (cert: (typeof certs)[number]) =>
    cert.status?.toLowerCase() === 'rejected' || cert.verificationStatus?.toLowerCase() === 'rejected'
  const isUsable = (cert: (typeof certs)[number]) => {
    const status = cert.status?.toLowerCase()
    const verificationStatus = cert.verificationStatus?.toLowerCase()
    return (
      !isRejected(cert) &&
      (!status || ['valid', 'expiring_soon', 'expired'].includes(status)) &&
      verificationStatus === 'verified'
    )
  }

  const medCerts = certs.filter((c) => {
    const title = (c.certType || c.name || '').toLowerCase()
    return /medical|oguk|oeuk|eng1/.test(title) && !isRejected(c)
  })

  if (medCerts.length > 0) {
    const withExpiry = medCerts.filter((c) => normalizeOptionalCalendarDate(c.expiryDate) && isUsable(c))
    const verifiedMedical = medCerts.find(
      (cert) => cert.verificationStatus?.toLowerCase() === 'verified',
    )
    if (withExpiry.length > 0) {
      withExpiry.sort(
        (a, b) =>
          (normalizeOptionalCalendarDate(b.expiryDate) || '').localeCompare(
            normalizeOptionalCalendarDate(a.expiryDate) || '',
          ),
      )
      const latestMed = withExpiry[0]
      const certExp = normalizeOptionalCalendarDate(latestMed?.expiryDate)
      if (latestMed && certExp) {
        // Verified certificate evidence is authoritative. A stale root
        // medicalExpiry must not extend a mobilization beyond the certificate.
        effectiveMedExp = certExp
        medCertName = latestMed.certType || latestMed.name || 'OGUK Medical'
      }
    } else if (verifiedMedical) {
      // Verified certificate evidence is authoritative, including when its
      // expiry is missing; do not fall back to stale profile medicalExpiry.
      effectiveMedExp = null
      medCertName = verifiedMedical.certType || verifiedMedical.name || 'OGUK Medical'
    } else if (!effectiveMedExp) {
      const firstMed = medCerts[0]
      medCertName = firstMed?.certType || firstMed?.name || 'OGUK Medical'
    }
  }

  if (!effectiveMedExp) {
    if (medCerts.length > 0) {
      // A certificate on file without any expiry date cannot prove validity
      // through the campaign window — warn, don't pass.
      issues.push(`${medCertName} on file but expiry not recorded — validity unverified`)
      checks.push({
        item: 'Offshore Medical',
        status: 'warn',
        detail: `${medCertName} on file, expiry not recorded`,
      })
    } else {
      issues.push('Offshore medical certificate date not recorded or unverified')
      checks.push({
        item: 'Offshore Medical',
        status: 'warn',
        detail: 'Medical record missing or pending verification',
      })
    }
  } else if (effectiveMedExp < input.campaignStartDate) {
    issues.push(`${medCertName} expired on ${effectiveMedExp} prior to mobilization`)
    checks.push({
      item: 'Offshore Medical',
      status: 'fail',
      detail: `Expired on ${effectiveMedExp}`,
    })
  } else if (effectiveMedExp <= input.campaignEndDate) {
    issues.push(`${medCertName} expires during campaign window on ${effectiveMedExp}`)
    checks.push({
      item: 'Offshore Medical',
      status: 'warn',
      detail: `Expires on ${effectiveMedExp} during tour`,
    })
  } else {
    checks.push({
      item: 'Offshore Medical',
      status: 'pass',
      detail: `${medCertName} valid through ${effectiveMedExp}`,
    })
  }

  // 3. Survival / BOSIET / FOET
  const survivalCerts = certs.filter((c) => {
    const title = (c.certType || c.name || '').toLowerCase()
    return /bosiet|foet|survival|opito|ca-ebs/.test(title) && !isRejected(c)
  })

  if (survivalCerts.length === 0) {
    issues.push('No OPITO BOSIET or FOET offshore survival certificate found on profile')
    checks.push({
      item: 'Survival / BOSIET',
      status: 'warn',
      detail: 'No offshore survival certificate recorded',
    })
  } else {
    const validSurvivals = survivalCerts.filter((c) => {
      const expiry = normalizeOptionalCalendarDate(c.expiryDate)
      return Boolean(expiry && isUsable(c) && expiry >= input.campaignEndDate)
    })
    validSurvivals.sort(
      (a, b) =>
        (normalizeOptionalCalendarDate(b.expiryDate) || '').localeCompare(
          normalizeOptionalCalendarDate(a.expiryDate) || '',
        ),
    )

    const expiringSurvivals = survivalCerts.filter((c) => {
      const expiry = normalizeOptionalCalendarDate(c.expiryDate)
      return Boolean(
        expiry && isUsable(c) && expiry >= input.campaignStartDate && expiry < input.campaignEndDate,
      )
    })
    expiringSurvivals.sort(
      (a, b) =>
        (normalizeOptionalCalendarDate(a.expiryDate) || '').localeCompare(
          normalizeOptionalCalendarDate(b.expiryDate) || '',
        ),
    )

    const expiredSurvivals = survivalCerts.filter(
      (c) => {
        const expiry = normalizeOptionalCalendarDate(c.expiryDate)
        return Boolean(expiry && isUsable(c) && expiry < input.campaignStartDate)
      },
    )
    expiredSurvivals.sort(
      (a, b) =>
        (normalizeOptionalCalendarDate(b.expiryDate) || '').localeCompare(
          normalizeOptionalCalendarDate(a.expiryDate) || '',
        ),
    )

    const [best] = validSurvivals
    const [expiring] = expiringSurvivals
    const [expired] = expiredSurvivals

    if (best) {
      const name = best.certType || best.name || 'BOSIET'
      checks.push({
        item: 'Survival / BOSIET',
        status: 'pass',
        detail: `${name} valid through ${best.expiryDate?.slice(0, 10)}`,
      })
    } else if (expiring) {
      const name = expiring.certType || expiring.name || 'BOSIET'
      const expStr = normalizeOptionalCalendarDate(expiring.expiryDate)
      issues.push(`${name} expires during campaign on ${expStr}`)
      checks.push({
        item: 'Survival / BOSIET',
        status: 'warn',
        detail: `Expires during tour on ${expStr}`,
      })
    } else if (expired) {
      const name = expired.certType || expired.name || 'BOSIET'
      const expStr = normalizeOptionalCalendarDate(expired.expiryDate)
      issues.push(`${name} expired on ${expStr}`)
      checks.push({
        item: 'Survival / BOSIET',
        status: 'fail',
        detail: `Expired on ${expStr}`,
      })
    } else {
      // Certificates on file but none carry an expiry date — validity
      // through the campaign cannot be established.
      const [firstSurv] = survivalCerts
      const name = firstSurv?.certType || firstSurv?.name || 'BOSIET'
      issues.push(`${name} on file but expiry not recorded — validity unverified`)
      checks.push({
        item: 'Survival / BOSIET',
        status: 'warn',
        detail: `${name} on file, expiry not recorded`,
      })
    }
  }

  // Verdict calculation
  const hasFail = checks.some((c) => c.status === 'fail')
  const hasWarn = checks.some((c) => c.status === 'warn')

  if (hasFail) {
    return {
      status: 'critical',
      badgeClass: 'badge-negative',
      badgeLabel: 'Non-compliant',
      issues,
      checks,
    }
  }

  if (hasWarn) {
    return {
      status: 'warning',
      badgeClass: 'badge-warning',
      badgeLabel: 'Notice',
      issues,
      checks,
    }
  }

  return {
    status: 'compliant',
    badgeClass: 'badge-positive',
    badgeLabel: 'Compliant',
    issues,
    checks,
  }
}
