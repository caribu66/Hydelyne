import { CampaignAssignmentStatus } from '../types'

/**
 * Computes ISO date window given a start date and duration in days.
 */
export function calculateCampaignWindow(
  startDate: string,
  durationDays: number,
): { startDate: string; endDate: string } {
  const start = new Date(startDate)
  if (Number.isNaN(start.getTime())) {
    throw new Error(`Invalid start date: ${startDate}`)
  }
  if (durationDays < 1) {
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
  const start = new Date(params.startDate)
  if (Number.isNaN(start.getTime())) {
    return { valid: false, error: 'A valid start date is required' }
  }
  if (!params.durationDays || params.durationDays < 1) {
    return { valid: false, error: 'Duration must be at least 1 day' }
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
  certifications?: Array<{ certType?: string; name?: string; expiryDate?: string | null }>
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
    if (input.availabilityDate && input.availabilityDate < input.campaignStartDate) {
      checks.push({
        item: 'Schedule Availability',
        status: 'pass',
        detail: `Current assignment ends ${input.availabilityDate.slice(0, 10)} prior to campaign`,
      })
    } else if (input.availabilityDate) {
      issues.push(`Specialist is on assignment through ${input.availabilityDate.slice(0, 10)}`)
      checks.push({
        item: 'Schedule Availability',
        status: 'fail',
        detail: `Active tour ends ${input.availabilityDate.slice(0, 10)} during or after campaign start`,
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
  let effectiveMedExp = input.medicalExpiry ? input.medicalExpiry.slice(0, 10) : null
  let medCertName = 'Offshore Medical'

  const medCerts = certs.filter((c) => {
    const title = (c.certType || c.name || '').toLowerCase()
    return /medical|oguk|oeuk|eng1/.test(title)
  })

  if (medCerts.length > 0) {
    const withExpiry = medCerts.filter((c) => c.expiryDate)
    if (withExpiry.length > 0) {
      withExpiry.sort((a, b) => (b.expiryDate || '').localeCompare(a.expiryDate || ''))
      const latestMed = withExpiry[0]
      if (latestMed?.expiryDate) {
        const certExp = latestMed.expiryDate.slice(0, 10)
        if (!effectiveMedExp || certExp > effectiveMedExp) {
          effectiveMedExp = certExp
          medCertName = latestMed.certType || latestMed.name || 'OGUK Medical'
        }
      }
    } else if (!effectiveMedExp) {
      const firstMed = medCerts[0]
      medCertName = firstMed?.certType || firstMed?.name || 'OGUK Medical'
    }
  }

  if (!effectiveMedExp) {
    if (medCerts.length > 0) {
      checks.push({
        item: 'Offshore Medical',
        status: 'pass',
        detail: `${medCertName} verified on file`,
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
    return /bosiet|foet|survival|opito|ca-ebs/.test(title)
  })

  if (survivalCerts.length === 0) {
    issues.push('No OPITO BOSIET or FOET offshore survival certificate found on profile')
    checks.push({
      item: 'Survival / BOSIET',
      status: 'warn',
      detail: 'No offshore survival certificate recorded',
    })
  } else {
    const validSurvivals = survivalCerts.filter(
      (c) => c.expiryDate && c.expiryDate.slice(0, 10) >= input.campaignEndDate
    )
    validSurvivals.sort((a, b) => (b.expiryDate || '').localeCompare(a.expiryDate || ''))

    const expiringSurvivals = survivalCerts.filter(
      (c) =>
        c.expiryDate &&
        c.expiryDate.slice(0, 10) >= input.campaignStartDate &&
        c.expiryDate.slice(0, 10) < input.campaignEndDate
    )
    expiringSurvivals.sort((a, b) => (a.expiryDate || '').localeCompare(b.expiryDate || ''))

    const expiredSurvivals = survivalCerts.filter(
      (c) => c.expiryDate && c.expiryDate.slice(0, 10) < input.campaignStartDate
    )
    expiredSurvivals.sort((a, b) => (b.expiryDate || '').localeCompare(a.expiryDate || ''))

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
      const expStr = expiring.expiryDate?.slice(0, 10)
      issues.push(`${name} expires during campaign on ${expStr}`)
      checks.push({
        item: 'Survival / BOSIET',
        status: 'warn',
        detail: `Expires during tour on ${expStr}`,
      })
    } else if (expired) {
      const name = expired.certType || expired.name || 'BOSIET'
      const expStr = expired.expiryDate?.slice(0, 10)
      issues.push(`${name} expired on ${expStr}`)
      checks.push({
        item: 'Survival / BOSIET',
        status: 'fail',
        detail: `Expired on ${expStr}`,
      })
    } else {
      const [firstSurv] = survivalCerts
      const name = firstSurv?.certType || firstSurv?.name || 'BOSIET'
      checks.push({
        item: 'Survival / BOSIET',
        status: 'pass',
        detail: `${name} verified on file`,
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

