import { describe, expect, it } from 'vitest'
import {
  calculateCampaignWindow,
  formatAssignmentStatus,
  buildMobilizationReference,
  getRoleKeyword,
  validateAssignmentInput,
  evaluateCandidatePreflightCompliance,
} from './assignmentUtils'

describe('getRoleKeyword', () => {
  it('maps Marine Mammal Observer to MMO', () => {
    expect(getRoleKeyword('Marine Mammal Observer (MMO)')).toBe('MMO')
  })

  it('maps PAM Operator to PAM', () => {
    expect(getRoleKeyword('PAM Operator')).toBe('PAM')
  })

  it('maps Senior Hydrographer to Hydrograph', () => {
    expect(getRoleKeyword('Senior Hydrographer')).toBe('Hydrograph')
  })

  it('maps Lead Seismic QC to Seismic', () => {
    expect(getRoleKeyword('Lead Seismic QC')).toBe('Seismic')
  })

  it('maps OBN Acquisition QC to OBN', () => {
    expect(getRoleKeyword('OBN Acquisition QC')).toBe('OBN')
  })

  it('maps Geotechnical CPT Specialist to Geotech', () => {
    expect(getRoleKeyword('Geotechnical CPT Specialist')).toBe('Geotech')
  })

  it('maps Offshore HSE Advisor to HSE', () => {
    expect(getRoleKeyword('Offshore HSE Advisor')).toBe('HSE')
  })

  it('maps Fisheries Liaison Officer to Fisheries', () => {
    expect(getRoleKeyword('Fisheries Liaison Officer (FLO)')).toBe('Fisheries')
  })

  it('maps Client Representative to Client Rep', () => {
    expect(getRoleKeyword('Client Representative')).toBe('Client Rep')
  })

  it('handles empty and custom roles cleanly', () => {
    expect(getRoleKeyword('')).toBe('')
    expect(getRoleKeyword('Custom ROV Pilot')).toBe('Custom ROV Pilot')
  })
})

describe('calculateCampaignWindow', () => {
  it('correctly calculates start and end date for given duration', () => {
    const window = calculateCampaignWindow('2026-06-01', 21)
    expect(window.startDate).toBe('2026-06-01')
    expect(window.endDate).toBe('2026-06-22')
  })

  it('handles single day deployment', () => {
    const window = calculateCampaignWindow('2026-07-10', 1)
    expect(window.startDate).toBe('2026-07-10')
    expect(window.endDate).toBe('2026-07-11')
  })

  it('throws for invalid start date', () => {
    expect(() => calculateCampaignWindow('invalid-date', 14)).toThrow('Invalid start date')
  })

  it('throws for non-positive duration', () => {
    expect(() => calculateCampaignWindow('2026-06-01', 0)).toThrow('Duration days must be at least 1')
  })
})

describe('formatAssignmentStatus', () => {
  it('maps on_board to positive badge', () => {
    const res = formatAssignmentStatus('on_board')
    expect(res.label).toBe('On Board')
    expect(res.badgeClass).toBe('badge-positive')
  })

  it('maps confirmed to accent badge', () => {
    const res = formatAssignmentStatus('confirmed')
    expect(res.label).toBe('Confirmed')
    expect(res.badgeClass).toBe('badge-accent')
  })

  it('maps proposed to neutral badge', () => {
    const res = formatAssignmentStatus('proposed')
    expect(res.label).toBe('Proposed')
    expect(res.badgeClass).toBe('badge-neutral')
  })

  it('maps completed and cancelled gracefully', () => {
    expect(formatAssignmentStatus('completed').label).toBe('Completed')
    expect(formatAssignmentStatus('cancelled').label).toBe('Cancelled')
  })
})

describe('buildMobilizationReference', () => {
  it('formats clean alphanumeric reference from uuid', () => {
    const ref = buildMobilizationReference('123e4567-e89b-12d3-a456-426614174000')
    expect(ref).toBe('HYD-MOB-123E4567')
  })

  it('returns fallback reference for empty id', () => {
    const ref = buildMobilizationReference('')
    expect(ref).toMatch(/^HYD-MOB-2026-\d{4}$/)
  })
})

describe('validateAssignmentInput', () => {
  it('validates correct inputs', () => {
    const res = validateAssignmentInput({
      roleOnBoard: 'Chief QC',
      startDate: '2026-09-01',
      durationDays: 14,
    })
    expect(res.valid).toBe(true)
    expect(res.error).toBeUndefined()
  })

  it('rejects empty role on board', () => {
    const res = validateAssignmentInput({
      roleOnBoard: '',
      startDate: '2026-09-01',
      durationDays: 14,
    })
    expect(res.valid).toBe(false)
    expect(res.error).toContain('Role on board')
  })

  it('rejects invalid date', () => {
    const res = validateAssignmentInput({
      roleOnBoard: 'Client Rep',
      startDate: 'not-a-date',
      durationDays: 14,
    })
    expect(res.valid).toBe(false)
    expect(res.error).toContain('valid start date')
  })

  it('rejects invalid duration', () => {
    const res = validateAssignmentInput({
      roleOnBoard: 'Client Rep',
      startDate: '2026-09-01',
      durationDays: 0,
    })
    expect(res.valid).toBe(false)
    expect(res.error).toContain('Duration must be at least 1 day')
  })
})

describe('evaluateCandidatePreflightCompliance', () => {
  it('returns compliant when medical and BOSIET are valid throughout campaign', () => {
    const report = evaluateCandidatePreflightCompliance({
      availabilityStatus: 'Available immediately',
      medicalExpiry: '2027-01-01',
      campaignStartDate: '2026-10-01',
      campaignEndDate: '2026-10-28',
      certifications: [
        {
          name: 'OPITO BOSIET with CA-EBS',
          expiryDate: '2027-05-15',
        },
      ],
    })

    expect(report.status).toBe('compliant')
    expect(report.badgeLabel).toBe('Compliant')
    expect(report.badgeClass).toBe('badge-positive')
    expect(report.issues.length).toBe(0)
    expect(report.checks.every((c) => c.status === 'pass')).toBe(true)
  })

  it('flags warning when BOSIET expires during campaign', () => {
    const report = evaluateCandidatePreflightCompliance({
      availabilityStatus: 'Available immediately',
      medicalExpiry: '2027-01-01',
      campaignStartDate: '2026-10-01',
      campaignEndDate: '2026-10-28',
      certifications: [
        {
          name: 'BOSIET',
          expiryDate: '2026-10-15',
        },
      ],
    })

    expect(report.status).toBe('warning')
    expect(report.badgeLabel).toBe('Notice')
    expect(report.badgeClass).toBe('badge-warning')
    expect(report.issues.some((i) => i.includes('expires during campaign'))).toBe(true)
  })

  it('flags critical when candidate is currently on assignment', () => {
    const report = evaluateCandidatePreflightCompliance({
      availabilityStatus: 'on_assignment',
      medicalExpiry: '2027-01-01',
      campaignStartDate: '2026-10-01',
      campaignEndDate: '2026-10-28',
      certifications: [
        {
          name: 'BOSIET',
          expiryDate: '2027-10-15',
        },
      ],
    })

    expect(report.status).toBe('critical')
    expect(report.badgeLabel).toBe('Non-compliant')
    expect(report.badgeClass).toBe('badge-negative')
    expect(report.issues.some((i) => i.includes('currently marked as on assignment'))).toBe(true)
  })

  it('flags critical when medical expired prior to mobilization', () => {
    const report = evaluateCandidatePreflightCompliance({
      availabilityStatus: 'available',
      medicalExpiry: '2026-09-01',
      campaignStartDate: '2026-10-01',
      campaignEndDate: '2026-10-28',
      certifications: [
        {
          name: 'OPITO FOET',
          expiryDate: '2027-10-15',
        },
      ],
    })

    expect(report.status).toBe('critical')
    expect(report.issues.some((i) => i.toLowerCase().includes('expired on'))).toBe(true)
  })

  it('flags warning when survival certification is missing', () => {
    const report = evaluateCandidatePreflightCompliance({
      availabilityStatus: 'available',
      medicalExpiry: '2027-01-01',
      campaignStartDate: '2026-10-01',
      campaignEndDate: '2026-10-28',
      certifications: [],
    })

    expect(report.status).toBe('warning')
    expect(report.issues.some((i) => i.includes('No OPITO BOSIET'))).toBe(true)
  })

  it('recognizes OGUK Medical in certifications array when medicalExpiry is null', () => {
    const report = evaluateCandidatePreflightCompliance({
      availabilityStatus: 'Available immediately',
      medicalExpiry: null,
      campaignStartDate: '2026-10-01',
      campaignEndDate: '2026-10-28',
      certifications: [
        {
          name: 'OPITO BOSIET with CA-EBS',
          expiryDate: '2027-05-15',
        },
        {
          name: 'OGUK Medical',
          expiryDate: '2027-11-01',
        },
      ],
    })

    expect(report.status).toBe('compliant')
    expect(report.badgeLabel).toBe('Compliant')
    expect(report.badgeClass).toBe('badge-positive')
    expect(report.checks.every((c) => c.status === 'pass')).toBe(true)
  })

  it('allows candidate on assignment if current tour ends before campaign starts', () => {
    const report = evaluateCandidatePreflightCompliance({
      availabilityStatus: 'on_assignment',
      availabilityDate: '2026-09-25',
      medicalExpiry: '2027-11-01',
      campaignStartDate: '2026-10-01',
      campaignEndDate: '2026-10-28',
      certifications: [
        { name: 'OPITO BOSIET with CA-EBS', expiryDate: '2027-05-15' },
      ],
    })

    expect(report.status).toBe('compliant')
    expect(report.badgeLabel).toBe('Compliant')
    const schedCheck = report.checks.find((c) => c.item === 'Schedule Availability')
    expect(schedCheck?.status).toBe('pass')
    expect(schedCheck?.detail).toContain('ends 2026-09-25 prior to campaign')
  })

  it('rejects candidate on assignment if current tour extends into campaign window', () => {
    const report = evaluateCandidatePreflightCompliance({
      availabilityStatus: 'on_assignment',
      availabilityDate: '2026-10-15',
      medicalExpiry: '2027-11-01',
      campaignStartDate: '2026-10-01',
      campaignEndDate: '2026-10-28',
      certifications: [
        { name: 'OPITO BOSIET with CA-EBS', expiryDate: '2027-05-15' },
      ],
    })

    expect(report.status).toBe('critical')
    const schedCheck = report.checks.find((c) => c.item === 'Schedule Availability')
    expect(schedCheck?.status).toBe('fail')
  })

  it('warns when medical expires exactly on the campaign end date', () => {
    const report = evaluateCandidatePreflightCompliance({
      availabilityStatus: 'available',
      medicalExpiry: '2026-10-28',
      campaignStartDate: '2026-10-01',
      campaignEndDate: '2026-10-28',
      certifications: [
        { name: 'OPITO BOSIET', expiryDate: '2027-05-15' },
      ],
    })

    expect(report.status).toBe('warning')
    expect(report.badgeLabel).toBe('Notice')
    const medCheck = report.checks.find((c) => c.item === 'Offshore Medical')
    expect(medCheck?.status).toBe('warn')
    expect(medCheck?.detail).toContain('Expires on 2026-10-28')
  })

  it('passes when medical expires the day after campaign ends', () => {
    const report = evaluateCandidatePreflightCompliance({
      availabilityStatus: 'available',
      medicalExpiry: '2026-10-29',
      campaignStartDate: '2026-10-01',
      campaignEndDate: '2026-10-28',
      certifications: [
        { name: 'OPITO BOSIET', expiryDate: '2027-05-15' },
      ],
    })

    expect(report.status).toBe('compliant')
    const medCheck = report.checks.find((c) => c.item === 'Offshore Medical')
    expect(medCheck?.status).toBe('pass')
  })

  it('resolves the latest medical cert when profile medicalExpiry is stale or expired', () => {
    const report = evaluateCandidatePreflightCompliance({
      availabilityStatus: 'available',
      medicalExpiry: '2024-05-01', // old expired date
      campaignStartDate: '2026-10-01',
      campaignEndDate: '2026-10-28',
      certifications: [
        { name: 'OPITO BOSIET', expiryDate: '2027-05-15' },
        { name: 'OEUK Offshore Medical', expiryDate: '2027-11-30' }, // renewed cert
      ],
    })

    expect(report.status).toBe('compliant')
    const medCheck = report.checks.find((c) => c.item === 'Offshore Medical')
    expect(medCheck?.status).toBe('pass')
    expect(medCheck?.detail).toContain('valid through 2027-11-30')
  })

  it('warns when certs are on file but no expiry is recorded', () => {
    const report = evaluateCandidatePreflightCompliance({
      availabilityStatus: 'available',
      campaignStartDate: '2026-10-01',
      campaignEndDate: '2026-10-28',
      certifications: [
        { name: 'OGUK Medical' },
        { name: 'OPITO BOSIET' },
      ],
    })

    expect(report.status).toBe('warning')
    const medCheck = report.checks.find((c) => c.item === 'Offshore Medical')
    expect(medCheck?.status).toBe('warn')
    const survCheck = report.checks.find((c) => c.item === 'Survival / BOSIET')
    expect(survCheck?.status).toBe('warn')
    expect(report.issues.some((i) => i.includes('expiry not recorded'))).toBe(true)
  })

  it('resolves the valid renewed survival cert when older cert is expired', () => {
    const report = evaluateCandidatePreflightCompliance({
      availabilityStatus: 'available',
      medicalExpiry: '2027-11-01',
      campaignStartDate: '2026-10-01',
      campaignEndDate: '2026-10-28',
      certifications: [
        { name: 'OPITO BOSIET', expiryDate: '2023-01-15' }, // expired
        { name: 'OPITO FOET with CA-EBS', expiryDate: '2027-09-20' }, // valid refresher
      ],
    })

    expect(report.status).toBe('compliant')
    const survCheck = report.checks.find((c) => c.item === 'Survival / BOSIET')
    expect(survCheck?.status).toBe('pass')
    expect(survCheck?.detail).toContain('valid through 2027-09-20')
  })

  it('handles leap day transitions accurately in calculateCampaignWindow', () => {
    const leapWindow = calculateCampaignWindow('2028-02-28', 1)
    expect(leapWindow.startDate).toBe('2028-02-28')
    expect(leapWindow.endDate).toBe('2028-02-29')

    const afterLeap = calculateCampaignWindow('2028-02-28', 2)
    expect(afterLeap.endDate).toBe('2028-03-01')
  })

  it('handles year boundary crossovers in calculateCampaignWindow', () => {
    const crossover = calculateCampaignWindow('2026-12-25', 10)
    expect(crossover.startDate).toBe('2026-12-25')
    expect(crossover.endDate).toBe('2027-01-04')
  })

  it('handles empty certifications list without throwing', () => {
    const report = evaluateCandidatePreflightCompliance({
      availabilityStatus: 'available',
      medicalExpiry: null,
      campaignStartDate: '2026-10-01',
      campaignEndDate: '2026-10-28',
      certifications: [],
    })

    expect(report.status).toBe('warning')
    expect(report.badgeLabel).toBe('Notice')
    expect(report.issues.length).toBeGreaterThanOrEqual(2)
    const survCheck = report.checks.find((c) => c.item === 'Survival / BOSIET')
    expect(survCheck?.status).toBe('warn')
    const medCheck = report.checks.find((c) => c.item === 'Offshore Medical')
    expect(medCheck?.status).toBe('warn')
  })

  it('handles null and undefined candidate input safely', () => {
    const report = evaluateCandidatePreflightCompliance({
      campaignStartDate: '2026-10-01',
      campaignEndDate: '2026-10-28',
    })

    expect(report.status).toBe('warning')
    expect(report.badgeLabel).toBe('Notice')
  })

  it('evaluates single day mobilization compliance accurately', () => {
    const report = evaluateCandidatePreflightCompliance({
      availabilityStatus: 'available',
      medicalExpiry: '2026-10-01', // expires on same day
      campaignStartDate: '2026-10-01',
      campaignEndDate: '2026-10-01',
      certifications: [
        { name: 'OPITO BOSIET', expiryDate: '2027-05-15' },
      ],
    })

    // Medical expires on the campaign end date (which is also start date) -> warning notice
    expect(report.status).toBe('warning')
    expect(report.badgeLabel).toBe('Notice')
  })

  it('robustly maps roles with mixed case, extra whitespace, and combined designations', () => {
    expect(getRoleKeyword('   mArInE   mAmMaL   oBsErVeR (MMO)   ')).toBe('MMO')
    expect(getRoleKeyword('SEISMIC DATA QC / PROCESSING')).toBe('Seismic')
    expect(getRoleKeyword('Senior Offshore Hydrographer & Surveyor')).toBe('Hydrograph')
    expect(getRoleKeyword('   ')).toBe('')
  })
})


