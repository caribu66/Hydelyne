import { FC, useState, useEffect, useRef, FormEvent, useMemo } from 'react'
import { useMutation, useQuery } from '@apollo/client'
import { AnimatePresence, motion } from 'motion/react'
import {
  X,
  Ship,
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  Check,
  Copy,
  Loader2,
  Search,
  UserPlus,
  Calendar,
  MapPin,
  ShieldAlert,
} from 'lucide-react'
import { useAccessibleDialog } from '../../hooks/useAccessibleDialog'
import { CampaignAssignment, CampaignAssignmentStatus } from '../../types'
import { CREATE_CAMPAIGN_ASSIGNMENT, CREW_MEMBERS_QUERY, VESSEL_ROSTER_QUERY } from '../../lib/queries'
import { backendCrewListToProfiles } from '../../lib/mappers'
import {
  buildMobilizationReference,
  calculateCampaignWindow,
  evaluateCandidatePreflightCompliance,
  getRoleKeyword,
  validateAssignmentInput,
} from '../../utils/assignmentUtils'

export interface VesselForMobilization {
  imo: string
  name: string
  vesselType?: string | null
  flag?: string | null
  callsign?: string | null
}

interface VesselMobilizationModalProps {
  isOpen: boolean
  onClose: () => void
  vessel: VesselForMobilization | null
  onShowToast: (message: string) => void
  onSuccess?: (assignment: CampaignAssignment) => void
}

const COMMON_DISCIPLINES = [
  'Client Representative',
  'Lead Seismic QC',
  'OBN Acquisition QC',
  'Marine Mammal Observer (MMO)',
  'PAM Operator',
  'Senior Hydrographer',
  'Geotechnical CPT Specialist',
  'Offshore HSE Advisor',
  'Fisheries Liaison Officer (FLO)',
]

export const VesselMobilizationModal: FC<VesselMobilizationModalProps> = ({
  isOpen,
  onClose,
  vessel,
  onShowToast,
  onSuccess,
}) => {
  const dialogRef = useRef<HTMLDivElement>(null)
  useAccessibleDialog(isOpen && Boolean(vessel), dialogRef, onClose)

  const [roleOnBoard, setRoleOnBoard] = useState('Client Representative')
  const [customRole, setCustomRole] = useState('')
  const [deploymentPort, setDeploymentPort] = useState('Aberdeen, Scotland')
  const [projectName, setProjectName] = useState('Johan Sverdrup 4D OBN Survey')
  const [startDate, setStartDate] = useState(() => {
    const d = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000)
    return d.toISOString().slice(0, 10)
  })
  const [durationDays, setDurationDays] = useState(28)
  const [candidateQuery, setCandidateQuery] = useState('')
  const [filterByRole, setFilterByRole] = useState(true)
  const [selectedCrewId, setSelectedCrewId] = useState<string | null>(null)
  const [agreedDayRate, setAgreedDayRate] = useState(850)
  const [specialInstructions, setSpecialInstructions] = useState('')

  const [submittedRef, setSubmittedRef] = useState<string | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [isCopied, setIsCopied] = useState(false)

  const effectiveRole = roleOnBoard === 'Custom' ? customRole.trim() : roleOnBoard
  const roleKeyword = useMemo(() => getRoleKeyword(effectiveRole), [effectiveRole])

  const effectiveSearch = useMemo(() => {
    const custom = candidateQuery.trim()
    if (custom) return custom
    if (filterByRole && roleKeyword) return roleKeyword
    return undefined
  }, [candidateQuery, filterByRole, roleKeyword])

  // Compute rotation window safely
  const { endDate } = useMemo(() => {
    try {
      return calculateCampaignWindow(startDate, durationDays)
    } catch {
      return { startDate, endDate: startDate }
    }
  }, [startDate, durationDays])

  // Query candidates
  const { data: crewData, loading: crewLoading } = useQuery(CREW_MEMBERS_QUERY, {
    variables: {
      search: effectiveSearch,
      limit: 30,
    },
    skip: !isOpen || !vessel,
    fetchPolicy: 'cache-and-network',
  })

  const candidates = useMemo(() => {
    if (!crewData?.crewMembers) return []
    return backendCrewListToProfiles(crewData.crewMembers)
  }, [crewData])

  const selectedCandidate = useMemo(() => {
    return candidates.find((c) => c.id === selectedCrewId) || null
  }, [candidates, selectedCrewId])

  // Live pre-flight compliance for the selected candidate
  const selectedCompliance = useMemo(() => {
    if (!selectedCandidate) return null
    return evaluateCandidatePreflightCompliance({
      certifications: selectedCandidate.certificationDetails,
      medicalExpiry: selectedCandidate.medical?.expiry || null,
      campaignStartDate: startDate,
      campaignEndDate: endDate,
      availabilityStatus: selectedCandidate.availability,
      availabilityDate: selectedCandidate.availabilityDate || null,
    })
  }, [selectedCandidate, startDate, endDate])

  const [createAssignmentMutation, { loading: isSubmitting }] = useMutation<{
    createCampaignAssignment: CampaignAssignment
  }>(CREATE_CAMPAIGN_ASSIGNMENT, {
    refetchQueries: vessel?.imo ? [{ query: VESSEL_ROSTER_QUERY, variables: { imo: vessel.imo } }] : [],
  })

  useEffect(() => {
    if (isOpen) {
      setSubmittedRef(null)
      setErrorMessage(null)
      setSelectedCrewId(null)
      setCandidateQuery('')
      setFilterByRole(true)
      setSpecialInstructions('')
    }
  }, [isOpen, vessel])

  if (!isOpen || !vessel) return null

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setErrorMessage(null)

    if (!selectedCrewId || !selectedCandidate) {
      setErrorMessage('Please select a specialist consultant to mobilize')
      return
    }

    const validation = validateAssignmentInput({
      roleOnBoard: effectiveRole,
      startDate,
      durationDays,
    })
    if (!validation.valid && validation.error) {
      setErrorMessage(validation.error)
      return
    }

    const notesPayload = [
      specialInstructions ? `Instructions: ${specialInstructions}` : '',
      deploymentPort ? `Port: ${deploymentPort}` : '',
      projectName ? `Project: ${projectName}` : '',
      selectedCompliance?.status === 'warning' ? `Pre-flight notice: ${selectedCompliance.issues.join('; ')}` : '',
    ]
      .filter(Boolean)
      .join('\n')

    try {
      const res = await createAssignmentMutation({
        variables: {
          input: {
            crewMemberId: selectedCandidate.id,
            vesselImo: vessel.imo,
            vesselName: vessel.name,
            roleOnBoard: effectiveRole,
            startDate,
            endDate,
            agreedDayRate,
            notes: notesPayload,
            status: 'CONFIRMED' as CampaignAssignmentStatus,
          },
        },
      })

      const assignment = res.data?.createCampaignAssignment
      if (assignment) {
        const refCode = buildMobilizationReference(assignment.id)
        setSubmittedRef(refCode)
        onShowToast(`Mobilization ${refCode} confirmed for ${selectedCandidate.name} on ${vessel.name}`)
        onSuccess?.(assignment)
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to record campaign assignment'
      setErrorMessage(msg)
    }
  }

  const handleCopySummary = () => {
    const summary = `
[HYDENLYNE MOBILIZATION DISPATCH - ${submittedRef}]
VESSEL: ${vessel.name} (IMO: ${vessel.imo}, Flag: ${vessel.flag || 'Unspecified'})
SPECIALIST: ${selectedCandidate?.name} (${selectedCandidate?.title})
ROLE: ${effectiveRole}
PORT: ${deploymentPort}
ROTATION: ${startDate} → ${endDate} (${durationDays} days)
DAY RATE: £${agreedDayRate}/day
PRE-FLIGHT COMPLIANCE: ${selectedCompliance?.badgeLabel || 'Verified'}
PROJECT: ${projectName || 'Offshore Campaign'}
INSTRUCTIONS: ${specialInstructions || 'Standard offshore mobilization'}
STATUS: CONFIRMED
    `.trim()

    void navigator.clipboard?.writeText(summary)
    setIsCopied(true)
    onShowToast('Mobilization dispatch summary copied to clipboard')
    setTimeout(() => setIsCopied(false), 2000)
  }

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.18, ease: 'easeOut' }}
        className="fixed inset-0 z-50 flex items-center justify-center p-2 sm:p-4 bg-canvas/80 backdrop-blur-md"
      >
        <motion.div
          ref={dialogRef}
          initial={{ opacity: 0, scale: 0.96, y: 8 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.96, y: 8 }}
          transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
          className="w-full max-w-3xl bg-surface border border-border-subtle rounded-[14px] shadow-2xl overflow-hidden flex flex-col max-h-[92vh]"
          role="dialog"
          aria-modal="true"
          aria-labelledby="vessel-mobilization-modal-title"
        >
          {/* Header */}
          <div className="flex items-center justify-between px-5 py-4 border-b border-border-subtle bg-surface-raised shrink-0">
            <div className="flex items-center gap-3">
              <div className="flex items-center justify-center w-10 h-10 rounded-[10px] bg-accent-soft/60 border border-border-strong/60 text-accent">
                <Ship className="w-5 h-5" aria-hidden="true" />
              </div>
              <div>
                <h2 id="vessel-mobilization-modal-title" className="text-base font-semibold text-primary">
                  Mobilize specialist to vessel
                </h2>
                <p className="text-xs text-secondary font-mono">
                  {vessel.name} · IMO {vessel.imo} {vessel.flag ? `· Flag: ${vessel.flag}` : ''}
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="inline-flex min-h-9 min-w-9 items-center justify-center rounded-lg bg-surface border border-border-subtle text-secondary hover:text-primary hover:bg-surface-selected transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
              aria-label="Close modal"
            >
              <X className="w-4 h-4" aria-hidden="true" />
            </button>
          </div>

          {/* Body */}
          <div className="flex-1 overflow-y-auto p-5 sm:p-6 space-y-6">
            {submittedRef ? (
              <div className="py-6 text-center space-y-4">
                <div className="w-12 h-12 rounded-full bg-positive-soft/80 border border-positive-border text-positive flex items-center justify-center mx-auto">
                  <CheckCircle2 className="w-6 h-6" aria-hidden="true" />
                </div>

                <div className="space-y-1">
                  <h3 className="text-base font-bold text-primary">Mobilization confirmed</h3>
                  <p className="text-xs text-secondary max-w-md mx-auto">
                    The consultant has been assigned to <span className="font-semibold text-primary">{vessel.name}</span>. The vessel roster and specialist availability have been synchronized.
                  </p>
                </div>

                <div className="p-4 rounded-[10px] bg-canvas/80 border border-border-subtle max-w-md mx-auto text-left space-y-2 text-xs">
                  <div className="flex justify-between border-b border-border-subtle pb-2">
                    <span className="text-secondary font-mono">Dispatch reference:</span>
                    <span className="font-bold text-accent font-mono">{submittedRef}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-secondary">Specialist:</span>
                    <span className="text-primary font-medium">{selectedCandidate?.name}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-secondary">Vessel / IMO:</span>
                    <span className="text-primary font-medium">{vessel.name} ({vessel.imo})</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-secondary">Role:</span>
                    <span className="text-primary font-medium">{effectiveRole}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-secondary">Rotation Window:</span>
                    <span className="text-primary font-mono">{startDate} → {endDate} ({durationDays}d)</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-secondary">Agreed Rate:</span>
                    <span className="text-primary font-mono">£{agreedDayRate}/day</span>
                  </div>
                </div>

                <div className="flex items-center justify-center gap-3 pt-2">
                  <button
                    type="button"
                    onClick={handleCopySummary}
                    className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-border-subtle bg-surface-raised px-3 py-1.5 text-xs font-medium text-secondary hover:text-primary hover:bg-surface-selected transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                  >
                    {isCopied ? <Check className="w-3.5 h-3.5 text-positive" /> : <Copy className="w-3.5 h-3.5" />}
                    <span>{isCopied ? 'Copied' : 'Copy dispatch brief'}</span>
                  </button>
                  <button
                    type="button"
                    onClick={onClose}
                    className="inline-flex min-h-9 items-center gap-1.5 rounded-lg bg-accent text-accent-contrast px-4 py-1.5 text-xs font-semibold hover:bg-accent-hover transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                  >
                    Done
                  </button>
                </div>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-6">
                {errorMessage && (
                  <div className="p-3.5 rounded-[10px] bg-negative-soft/60 border border-negative-border text-negative text-xs flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 shrink-0" aria-hidden="true" />
                    <span>{errorMessage}</span>
                  </div>
                )}

                {/* Step 1: Campaign Rotation Slot */}
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-secondary font-mono flex items-center gap-1.5">
                      <Calendar className="w-3.5 h-3.5 text-accent" />
                      <span>1. Campaign Rotation & Role</span>
                    </h3>
                    <span className="text-xs font-mono text-muted">
                      Window: <strong className="text-primary">{startDate}</strong> → <strong className="text-primary">{endDate}</strong>
                    </span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div>
                      <label htmlFor="mob-start-date" className="block text-xs font-medium text-secondary mb-1">
                        Mobilisation date
                      </label>
                      <input
                        id="mob-start-date"
                        type="date"
                        value={startDate}
                        onChange={(e) => setStartDate(e.target.value)}
                        required
                        className="w-full min-h-9 rounded-lg border border-border-subtle bg-surface-raised px-2.5 py-1 text-xs text-primary font-mono focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
                      />
                    </div>

                    <div>
                      <label htmlFor="mob-duration" className="block text-xs font-medium text-secondary mb-1">
                        Duration (days)
                      </label>
                      <input
                        id="mob-duration"
                        type="number"
                        min="1"
                        max="180"
                        value={durationDays}
                        onChange={(e) => setDurationDays(Math.max(1, parseInt(e.target.value, 10) || 1))}
                        required
                        className="w-full min-h-9 rounded-lg border border-border-subtle bg-surface-raised px-2.5 py-1 text-xs text-primary font-mono focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
                      />
                    </div>

                    <div>
                      <label htmlFor="mob-port" className="block text-xs font-medium text-secondary mb-1">
                        Port of mobilisation
                      </label>
                      <div className="relative">
                        <MapPin className="w-3.5 h-3.5 text-muted absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                        <input
                          id="mob-port"
                          type="text"
                          value={deploymentPort}
                          onChange={(e) => setDeploymentPort(e.target.value)}
                          placeholder="e.g. Aberdeen, Bergen"
                          className="w-full min-h-9 rounded-lg border border-border-subtle bg-surface-raised pl-8 pr-2.5 py-1 text-xs text-primary focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
                        />
                      </div>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
                    <div>
                      <label htmlFor="mob-role" className="block text-xs font-medium text-secondary mb-1">
                        Role on board
                      </label>
                      <select
                        id="mob-role"
                        value={roleOnBoard}
                        onChange={(e) => {
                          setRoleOnBoard(e.target.value)
                          setFilterByRole(true)
                          setCandidateQuery('')
                          setSelectedCrewId(null)
                        }}
                        className="w-full min-h-9 rounded-lg border border-border-subtle bg-surface-raised px-2.5 py-1 text-xs text-primary focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
                      >
                        {COMMON_DISCIPLINES.map((discipline) => (
                          <option key={discipline} value={discipline}>
                            {discipline}
                          </option>
                        ))}
                        <option value="Custom">Custom Role...</option>
                      </select>
                      {roleOnBoard === 'Custom' && (
                        <input
                          type="text"
                          value={customRole}
                          onChange={(e) => {
                            setCustomRole(e.target.value)
                            setFilterByRole(true)
                          }}
                          placeholder="Enter exact operational role"
                          required
                          className="mt-2 w-full min-h-9 rounded-lg border border-border-subtle bg-surface-raised px-2.5 py-1 text-xs text-primary focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
                        />
                      )}
                    </div>

                    <div>
                      <label htmlFor="mob-project" className="block text-xs font-medium text-secondary mb-1">
                        Project / Scope name
                      </label>
                      <input
                        id="mob-project"
                        type="text"
                        value={projectName}
                        onChange={(e) => setProjectName(e.target.value)}
                        placeholder="e.g. Johan Sverdrup 4D OBN Survey"
                        className="w-full min-h-9 rounded-lg border border-border-subtle bg-surface-raised px-2.5 py-1 text-xs text-primary focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
                      />
                    </div>
                  </div>
                </div>

                {/* Step 2: Select Specialist & Pre-Flight Compliance */}
                <div className="space-y-3 pt-2 border-t border-border-subtle">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-secondary font-mono flex items-center gap-1.5">
                      <UserPlus className="w-3.5 h-3.5 text-accent" />
                      <span>2. Select Specialist & Pre-Flight Matrix</span>
                    </h3>
                    {selectedCandidate && (
                      <button
                        type="button"
                        onClick={() => setSelectedCrewId(null)}
                        className="text-xs text-accent hover:underline font-medium cursor-pointer"
                      >
                        Change specialist
                      </button>
                    )}
                  </div>

                  {selectedCandidate ? (
                    <div className="p-4 rounded-[12px] bg-canvas border border-border-subtle space-y-3">
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex items-center gap-3">
                          <img
                            src={selectedCandidate.avatar}
                            alt={selectedCandidate.name}
                            className="w-11 h-11 rounded-[10px] object-cover border border-border-strong shrink-0"
                          />
                          <div>
                            <div className="flex items-center gap-2">
                              <h4 className="font-semibold text-sm text-primary">{selectedCandidate.name}</h4>
                              <span className="badge-neutral rounded px-1.5 py-0.5 text-xs font-mono">
                                {selectedCandidate.availability}
                              </span>
                            </div>
                            <p className="text-xs text-secondary">{selectedCandidate.title} · {selectedCandidate.location}</p>
                          </div>
                        </div>

                        {selectedCompliance && (
                          <span className={`rounded-md px-2 py-0.5 text-xs font-mono font-semibold uppercase ${selectedCompliance.badgeClass}`}>
                            {selectedCompliance.badgeLabel}
                          </span>
                        )}
                      </div>

                      {/* Compliance Checklist Breakdown */}
                      {selectedCompliance && (
                        <div className="rounded-lg border border-border-subtle bg-surface-raised/60 p-3 space-y-2">
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-medium text-secondary">
                              Pre-flight compliance report for {startDate} → {endDate}
                            </span>
                            {selectedCompliance.status === 'compliant' ? (
                              <span className="text-xs font-medium text-positive flex items-center gap-1">
                                <CheckCircle2 className="w-3.5 h-3.5" /> All checks passed
                              </span>
                            ) : selectedCompliance.status === 'warning' ? (
                              <span className="text-xs font-medium text-warning flex items-center gap-1">
                                <AlertTriangle className="w-3.5 h-3.5" /> Review notice before dispatch
                              </span>
                            ) : (
                              <span className="text-xs font-medium text-negative flex items-center gap-1">
                                <ShieldAlert className="w-3.5 h-3.5" /> Critical item requires override
                              </span>
                            )}
                          </div>

                          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 pt-1 border-t border-border-subtle/50 text-xs">
                            {selectedCompliance.checks.map((check) => (
                              <div key={check.item} className="flex flex-col gap-0.5 p-2 rounded bg-surface border border-border-subtle">
                                <div className="flex items-center justify-between">
                                  <span className="font-medium text-primary">{check.item}</span>
                                  {check.status === 'pass' && <Check className="w-3.5 h-3.5 text-positive" />}
                                  {check.status === 'warn' && <AlertTriangle className="w-3.5 h-3.5 text-warning" />}
                                  {check.status === 'fail' && <X className="w-3.5 h-3.5 text-negative" />}
                                </div>
                                <span className="text-muted text-2xs truncate">{check.detail}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="space-y-2.5">
                      {/* Search Bar */}
                      <div className="relative">
                        <Search className="w-4 h-4 text-muted absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                        <input
                          type="text"
                          value={candidateQuery}
                          onChange={(e) => setCandidateQuery(e.target.value)}
                          placeholder="Search specialists by name, role, qualification (e.g. MMO, BOSIET)..."
                          className="w-full min-h-9 rounded-lg border border-border-subtle bg-surface-raised pl-9 pr-8 py-1.5 text-xs text-primary focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
                        />
                        {candidateQuery && (
                          <button
                            type="button"
                            onClick={() => setCandidateQuery('')}
                            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-secondary hover:text-primary p-0.5 rounded cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                            aria-label="Clear search"
                          >
                            <X className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>

                      {/* Filter Status & Quick Discipline Chips */}
                      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 text-2xs pt-0.5">
                        <div className="flex items-center gap-1.5 text-secondary flex-wrap">
                          {candidateQuery.trim() ? (
                            <>
                              <span>Search:</span>
                              <span className="font-semibold text-primary font-mono">"{candidateQuery.trim()}"</span>
                              <span className="text-muted">({candidates.length} found)</span>
                              <button
                                type="button"
                                onClick={() => setCandidateQuery('')}
                                className="text-accent hover:underline font-medium cursor-pointer ml-1"
                              >
                                Clear search
                              </button>
                            </>
                          ) : filterByRole && roleKeyword ? (
                            <>
                              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-accent-soft/60 border border-border-subtle text-accent font-medium font-mono">
                                Filtered by role: {roleKeyword}
                              </span>
                              <span className="text-muted">({candidates.length} matched)</span>
                              <button
                                type="button"
                                onClick={() => setFilterByRole(false)}
                                className="text-accent hover:underline font-medium cursor-pointer ml-1"
                              >
                                Show all specialists
                              </button>
                            </>
                          ) : (
                            <>
                              <span className="text-muted font-mono">Showing all specialists ({candidates.length})</span>
                              {roleKeyword && (
                                <button
                                  type="button"
                                  onClick={() => setFilterByRole(true)}
                                  className="text-accent hover:underline font-medium cursor-pointer ml-1"
                                >
                                  Filter for {effectiveRole}
                                </button>
                              )}
                            </>
                          )}
                        </div>

                        {/* Quick filter discipline chips */}
                        <div className="flex items-center gap-1 overflow-x-auto pb-0.5">
                          {[
                            {
                              label: 'Role focus',
                              action: () => {
                                setFilterByRole(true)
                                setCandidateQuery('')
                              },
                              active: filterByRole && !candidateQuery.trim(),
                            },
                            {
                              label: 'All',
                              action: () => {
                                setFilterByRole(false)
                                setCandidateQuery('')
                              },
                              active: !filterByRole && !candidateQuery.trim(),
                            },
                            {
                              label: 'MMO / PAM',
                              action: () => {
                                setFilterByRole(false)
                                setCandidateQuery('MMO')
                              },
                              active: candidateQuery.trim().toLowerCase() === 'mmo',
                            },
                            {
                              label: 'Hydrography',
                              action: () => {
                                setFilterByRole(false)
                                setCandidateQuery('Hydrograph')
                              },
                              active: candidateQuery.trim().toLowerCase() === 'hydrograph',
                            },
                            {
                              label: 'Seismic QC',
                              action: () => {
                                setFilterByRole(false)
                                setCandidateQuery('Seismic')
                              },
                              active: candidateQuery.trim().toLowerCase() === 'seismic',
                            },
                            {
                              label: 'Client Rep',
                              action: () => {
                                setFilterByRole(false)
                                setCandidateQuery('Client Rep')
                              },
                              active: candidateQuery.trim().toLowerCase() === 'client rep',
                            },
                            {
                              label: 'Geotech',
                              action: () => {
                                setFilterByRole(false)
                                setCandidateQuery('Geotech')
                              },
                              active: candidateQuery.trim().toLowerCase() === 'geotech',
                            },
                            {
                              label: 'HSE',
                              action: () => {
                                setFilterByRole(false)
                                setCandidateQuery('HSE')
                              },
                              active: candidateQuery.trim().toLowerCase() === 'hse',
                            },
                          ].map((chip) => (
                            <button
                              key={chip.label}
                              type="button"
                              onClick={chip.action}
                              className={`rounded px-2 py-0.5 text-2xs font-mono transition-colors cursor-pointer shrink-0 ${
                                chip.active
                                  ? 'bg-accent text-accent-contrast font-semibold shadow-2xs'
                                  : 'bg-surface border border-border-subtle text-secondary hover:text-primary hover:bg-surface-selected'
                              }`}
                            >
                              {chip.label}
                            </button>
                          ))}
                        </div>
                      </div>

                      {crewLoading ? (
                        <div className="flex items-center justify-center gap-2 py-6 text-muted text-xs">
                          <Loader2 className="w-4 h-4 animate-spin text-accent" />
                          <span>Searching qualified consultants…</span>
                        </div>
                      ) : candidates.length === 0 ? (
                        <div className="py-6 text-center space-y-2 rounded-lg border border-dashed border-border-subtle bg-surface-raised/40">
                          <p className="text-muted text-xs">
                            No specialists found matching {candidateQuery.trim() ? `"${candidateQuery.trim()}"` : `role "${effectiveRole}"`}.
                          </p>
                          <button
                            type="button"
                            onClick={() => {
                              setFilterByRole(false)
                              setCandidateQuery('')
                            }}
                            className="inline-flex min-h-8 items-center rounded-lg bg-surface border border-border-subtle px-2.5 py-1 text-xs font-medium text-accent hover:text-accent-hover hover:bg-surface-selected transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                          >
                            View all specialists without filter
                          </button>
                        </div>
                      ) : (
                        <div className="max-h-56 overflow-y-auto divide-y divide-border-subtle/40 rounded-lg border border-border-subtle bg-surface-raised">
                          {candidates.map((c) => {
                            const comp = evaluateCandidatePreflightCompliance({
                              certifications: c.certificationDetails,
                              medicalExpiry: c.medical?.expiry || null,
                              campaignStartDate: startDate,
                              campaignEndDate: endDate,
                              availabilityStatus: c.availability,
                              availabilityDate: c.availabilityDate || null,
                            })

                            return (
                              <div
                                key={c.id}
                                className="p-2.5 flex items-center justify-between gap-3 hover:bg-surface-selected transition-colors"
                              >
                                <div className="flex items-center gap-2.5 min-w-0">
                                  <img
                                    src={c.avatar}
                                    alt={c.name}
                                    className="w-8 h-8 rounded-full object-cover border border-border-subtle shrink-0"
                                  />
                                  <div className="min-w-0">
                                    <div className="flex items-center gap-2">
                                      <span className="font-semibold text-xs text-primary truncate">{c.name}</span>
                                      <span className="text-muted text-xs truncate">· {c.title}</span>
                                    </div>
                                    <div className="flex items-center gap-2 font-mono text-2xs text-secondary">
                                      <span>{c.location}</span>
                                      <span>·</span>
                                      <span className={c.availability === 'Available immediately' ? 'text-positive' : 'text-muted'}>
                                        {c.availability}
                                      </span>
                                    </div>
                                    {c.skills && c.skills.length > 0 && (
                                      <div className="flex items-center gap-1 mt-1 overflow-hidden">
                                        {c.skills.slice(0, 3).map((s) => (
                                          <span
                                            key={s}
                                            className="rounded bg-surface border border-border-subtle/80 px-1.5 py-0.5 font-mono text-3xs text-secondary truncate max-w-[140px]"
                                          >
                                            {s}
                                          </span>
                                        ))}
                                      </div>
                                    )}
                                  </div>
                                </div>

                                <div className="flex items-center gap-2 shrink-0">
                                  <span className={`rounded px-1.5 py-0.5 text-2xs font-mono uppercase font-semibold ${comp.badgeClass}`}>
                                    {comp.badgeLabel}
                                  </span>
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setSelectedCrewId(c.id)
                                      if (c.dayRate) setAgreedDayRate(c.dayRate)
                                    }}
                                    className="inline-flex min-h-8 items-center rounded-lg bg-surface border border-border-subtle px-2.5 py-1 text-xs font-medium text-secondary hover:text-primary hover:bg-surface-selected transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                                  >
                                    Select
                                  </button>
                                </div>
                              </div>
                            )
                          })}
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Step 3: Commercial Terms & Instructions */}
                <div className="space-y-3 pt-2 border-t border-border-subtle">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-secondary font-mono flex items-center gap-1.5">
                    <span>3. Commercial & Instructions</span>
                  </h3>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <label htmlFor="mob-day-rate" className="block text-xs font-medium text-secondary mb-1">
                        Agreed day rate (£/day)
                      </label>
                      <input
                        id="mob-day-rate"
                        type="number"
                        min="100"
                        step="25"
                        value={agreedDayRate}
                        onChange={(e) => setAgreedDayRate(parseFloat(e.target.value) || 0)}
                        required
                        className="w-full min-h-9 rounded-lg border border-border-subtle bg-surface-raised px-2.5 py-1 text-xs text-primary font-mono focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
                      />
                    </div>

                    <div>
                      <label htmlFor="mob-notes" className="block text-xs font-medium text-secondary mb-1">
                        Dispatch notes & transit instructions
                      </label>
                      <input
                        id="mob-notes"
                        type="text"
                        value={specialInstructions}
                        onChange={(e) => setSpecialInstructions(e.target.value)}
                        placeholder="e.g. Join via heliport check-in; PPE standard EN ISO 20471"
                        className="w-full min-h-9 rounded-lg border border-border-subtle bg-surface-raised px-2.5 py-1 text-xs text-primary focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
                      />
                    </div>
                  </div>
                </div>

                {/* Footer buttons */}
                <div className="flex items-center justify-end gap-3 pt-4 border-t border-border-subtle">
                  <button
                    type="button"
                    onClick={onClose}
                    className="inline-flex min-h-9 items-center justify-center rounded-lg border border-border-subtle bg-surface-raised px-4 py-1.5 text-xs font-medium text-secondary hover:text-primary hover:bg-surface-selected transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                  >
                    Cancel
                  </button>

                  <button
                    type="submit"
                    disabled={isSubmitting || !selectedCrewId}
                    className="inline-flex min-h-9 items-center justify-center gap-1.5 rounded-lg bg-accent px-4 py-1.5 text-xs font-semibold text-accent-contrast shadow-xs hover:bg-accent-hover transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                  >
                    {isSubmitting ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden="true" />
                        <span>Confirming…</span>
                      </>
                    ) : (
                      <>
                        <CheckCircle2 className="w-3.5 h-3.5" aria-hidden="true" />
                        <span>Confirm & mobilize specialist</span>
                      </>
                    )}
                  </button>
                </div>
              </form>
            )}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  )
}
