import { FC, useState, useEffect, useRef, FormEvent } from 'react';
import { useMutation } from '@apollo/client';
import { useAccessibleDialog } from '../hooks/useAccessibleDialog';
import { UserProfile, CampaignAssignment } from '../types';
import { AnimatePresence, motion } from 'motion/react';
import {
  X,
  Send,
  Anchor,
  CheckCircle2,
  Copy,
  Check,
  AlertCircle,
  Loader2,
} from 'lucide-react';
import { CREATE_CAMPAIGN_ASSIGNMENT } from '../lib/queries';
import {
  buildMobilizationReference,
  calculateCampaignWindow,
  validateAssignmentInput,
} from '../utils/assignmentUtils';
import { copyTextToClipboard } from '../utils/clipboard';
import { availabilityLabel } from '../utils/profileLabels';
import { isoDateAfterDays } from '../utils/operationsHome';
import { apolloResultHasErrors } from '../utils/sessionScope';

interface MobilizationInquiryModalProps {
  isOpen: boolean;
  onClose: () => void;
  profile: UserProfile | null;
  onShowToast: (message: string) => void;
  isAdmin: boolean;
  sessionKey?: string | null;
}

export const MobilizationInquiryModal: FC<MobilizationInquiryModalProps> = ({
  isOpen,
  onClose,
  profile,
  onShowToast,
  isAdmin,
  sessionKey = null,
}) => {
  const [projectName, setProjectName] = useState('');
  const [vesselImo, setVesselImo] = useState('');
  const [deploymentPort, setDeploymentPort] = useState('');
  const [surveyScope, setSurveyScope] = useState('Marine Seismic QC / OBN');
  const [startDate, setStartDate] = useState(
    isoDateAfterDays(7)
  );
  const [durationDays, setDurationDays] = useState(21);
  const [clientCompany, setClientCompany] = useState('');
  const [clientName, setClientName] = useState('');
  const [clientEmail, setClientEmail] = useState('');
  const [specialInstructions, setSpecialInstructions] = useState('');

  const [submittedRef, setSubmittedRef] = useState<string | null>(null);
  const [submittedAssignment, setSubmittedAssignment] = useState<CampaignAssignment | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isCopied, setIsCopied] = useState(false);
  const dialogRef = useRef<HTMLDivElement>(null);
  const currentSessionKeyRef = useRef(sessionKey);
  const previousSessionKeyRef = useRef(sessionKey);
  const currentProfileIdRef = useRef(profile?.id ?? null);
  const currentIsOpenRef = useRef(isOpen);
  const operationVersionRef = useRef(0);
  const copyFeedbackTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  currentSessionKeyRef.current = sessionKey;
  currentProfileIdRef.current = profile?.id ?? null;
  currentIsOpenRef.current = isOpen;
  useAccessibleDialog(isOpen && Boolean(profile), dialogRef, onClose);

  const [createAssignmentMutation, { loading: isSubmitting }] = useMutation<{
    createCampaignAssignment: CampaignAssignment;
  }>(CREATE_CAMPAIGN_ASSIGNMENT);

  useEffect(() => {
    operationVersionRef.current += 1;
    if (copyFeedbackTimerRef.current !== null) {
      clearTimeout(copyFeedbackTimerRef.current);
      copyFeedbackTimerRef.current = null;
    }
    if (isOpen) {
      const nextStartDate = isoDateAfterDays(7);
      setProjectName('');
      setVesselImo('');
      setDeploymentPort('');
      setSurveyScope('Marine Seismic QC / OBN');
      setStartDate(nextStartDate);
      setDurationDays(21);
      setClientCompany('');
      setClientName('');
      setClientEmail('');
      setSpecialInstructions('');
      setSubmittedRef(null);
      setSubmittedAssignment(null);
      setErrorMessage(null);
      setIsCopied(false);
    }
  }, [isOpen, profile?.id]);

  useEffect(() => {
    if (previousSessionKeyRef.current !== null && previousSessionKeyRef.current !== sessionKey) {
      setSubmittedRef(null);
      setSubmittedAssignment(null);
      setErrorMessage(null);
      onClose();
    }
    previousSessionKeyRef.current = sessionKey;
  }, [onClose, sessionKey]);

  if (!isOpen || !profile) return null;

  const estimatedDayRate = profile.dayRate;
  const estimatedTotalRate = estimatedDayRate != null ? estimatedDayRate * durationDays : null;

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!sessionKey || currentSessionKeyRef.current !== sessionKey) return;
    if (!profile) return;
    const operationVersion = ++operationVersionRef.current;
    const profileId = profile.id;
    const operationIsCurrent = () => (
      operationVersion === operationVersionRef.current
      && currentIsOpenRef.current
      && currentSessionKeyRef.current === sessionKey
      && currentProfileIdRef.current === profileId
    );
    setErrorMessage(null);

    const validation = validateAssignmentInput({
      roleOnBoard: surveyScope,
      startDate,
      durationDays,
    });
    if (!validation.valid && validation.error) {
      setErrorMessage(validation.error);
      return;
    }
    const cleanVesselImo = vesselImo.trim();
    if (!cleanVesselImo) {
      setErrorMessage('Vessel IMO is required to record a mobilization request');
      return;
    }
    if (!deploymentPort.trim()) {
      setErrorMessage('Deployment port is required to record a mobilization request');
      return;
    }

    const { endDate: computedEndDate } = calculateCampaignWindow(startDate, durationDays);
    const cleanProjectName = projectName.trim();

    const notesPayload = [
      specialInstructions ? `Instructions: ${specialInstructions}` : '',
      deploymentPort ? `Port: ${deploymentPort}` : '',
      clientName || clientEmail ? `Client: ${clientName || 'Not recorded'} (${clientCompany || 'Not recorded'}) <${clientEmail || 'Not provided'}>` : '',
    ].filter(Boolean).join('\n');

    try {
      const res = await createAssignmentMutation({
        variables: {
          input: {
            crewMemberId: profile.id,
            vesselImo: cleanVesselImo,
            ...(cleanProjectName ? { vesselName: cleanProjectName } : {}),
            roleOnBoard: surveyScope,
            startDate,
            endDate: computedEndDate,
            ...(isAdmin && estimatedDayRate != null ? { agreedDayRate: estimatedDayRate } : {}),
            notes: notesPayload,
            status: 'PROPOSED',
          },
        },
      });

      if (!operationIsCurrent()) return;
      if (apolloResultHasErrors(res)) {
        throw new Error('Mobilization request returned errors. Please try again.');
      }

      const assignment = res.data?.createCampaignAssignment;
      if (!assignment) throw new Error('The mobilization request was not returned. Please try again.');
      const refCode = buildMobilizationReference(assignment.id);
      setSubmittedRef(refCode);
      setSubmittedAssignment(assignment);
      onShowToast(`Mobilization request ${refCode} recorded for Hydenlyne operations confirmation`);
    } catch (err: unknown) {
      if (!operationIsCurrent()) return;
      const msg = err instanceof Error ? err.message : 'Failed to record campaign assignment';
      setErrorMessage(msg);
    }
  };


  const handleCopySummary = async () => {
    if (!sessionKey || currentSessionKeyRef.current !== sessionKey) return;
    const summary = `
[HYDENLYNE MOBILIZATION REQUEST - ${submittedRef}]
CONTRACTOR: ${profile.name} (${profile.title})
${isAdmin && estimatedDayRate != null ? `Standard Day Rate: £${estimatedDayRate}/day` : 'Day Rate: Set by administrator'}
Campaign: ${projectName || 'Not recorded'}
Port: ${deploymentPort || 'Not recorded'}
Scope: ${surveyScope}
Start Date: ${startDate} (${durationDays} Days Duration)
Estimated Base Rate: ${estimatedTotalRate != null ? `£${estimatedTotalRate.toLocaleString()}` : 'Rate on request'}
Client: ${clientName || 'Not recorded'} (${clientCompany || 'Not recorded'}) - ${clientEmail || 'Not provided'}
Instructions: ${specialInstructions || 'Not recorded'}
Status: PENDING HYDENLYNE OPERATIONS CONFIRMATION
    `.trim();

    if (await copyTextToClipboard(summary)) {
      setIsCopied(true);
      onShowToast('Mobilization summary copied to clipboard');
      if (copyFeedbackTimerRef.current !== null) clearTimeout(copyFeedbackTimerRef.current);
      copyFeedbackTimerRef.current = setTimeout(() => {
        copyFeedbackTimerRef.current = null;
        setIsCopied(false);
      }, 2000);
    } else {
      onShowToast('Could not copy the mobilization summary. Please try again.');
    }
  };

  return (
    <AnimatePresence>
      {isOpen && profile && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.18, ease: 'easeOut' }}
          className="fixed inset-0 z-50 flex items-center justify-center p-2 sm:p-4 bg-canvas/80 backdrop-blur-md"
        >
          <motion.div
            ref={dialogRef}
            initial={{ opacity: 0, scale: 0.95, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 8 }}
            transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
            className="w-full max-w-2xl bg-surface border border-border-subtle rounded-[14px] shadow-2xl overflow-hidden flex flex-col max-h-[94vh]"
            role="dialog"
            aria-modal="true"
            aria-labelledby="mobilization-modal-title"
          >
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border-subtle bg-surface/90 shrink-0">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-9 h-9 rounded-[10px] bg-accent-soft/60 border border-border-strong/60 text-accent">
              <Anchor className="w-4 h-4" />
            </div>
            <div>
              <h2 id="mobilization-modal-title" className="text-base font-semibold text-primary">
                Request mobilization
              </h2>
              <p className="text-xs text-secondary">
                Share the campaign essentials and Hydenlyne operations will take it from here.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-[10px] bg-surface-raised hover:bg-surface-selected text-secondary hover:text-primary transition-colors cursor-pointer"
            aria-label="Close modal"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-5">
          {/* Contractor Snapshot Banner */}
          <div className="p-3.5 rounded-[10px] bg-canvas/70 border border-border-subtle flex items-center justify-between gap-4">
            <div className="flex items-center gap-3 min-w-0">
              <img
                src={profile.avatar}
                alt={profile.name}
                className="w-11 h-11 rounded-[10px] object-cover border border-border-strong shrink-0"
              />
              <div className="min-w-0">
                <h3 className="font-semibold text-sm text-primary truncate">{profile.name}</h3>
                <p className="text-xs text-secondary truncate">{profile.title}</p>
                <div className="mt-0.5 flex items-center gap-2 text-xs text-secondary font-mono">
                  <span className="text-positive font-medium">{availabilityLabel(profile.availability)}</span>
                  <span>•</span>
                  <span>{profile.location}</span>
                </div>
              </div>
            </div>

            <div className="text-right shrink-0">
              <span className="block text-xs font-medium uppercase text-secondary font-mono">
                {isAdmin ? 'Indicative day rate' : 'Day rate'}
              </span>
              <span className="text-base font-bold text-primary font-mono">
                {isAdmin ? (
                  <>
                    {estimatedDayRate != null ? (
                      <>£{estimatedDayRate}<span className="text-xs text-secondary font-normal">/day</span></>
                    ) : 'Rate on request'}
                  </>
                ) : (
                  'Set by administrator'
                )}
              </span>
            </div>
          </div>

          {/* Form or Confirmation View */}
          {submittedRef ? (
            <div className="py-6 text-center space-y-4">
              <div className="w-12 h-12 rounded-full bg-positive-soft/80 border border-positive-border text-positive flex items-center justify-center mx-auto">
                <CheckCircle2 className="w-6 h-6" />
              </div>

              <div className="space-y-1">
                <h3 className="text-base font-bold text-primary">Mobilization request recorded</h3>
                <p className="text-xs text-secondary max-w-md mx-auto">
                  The proposed assignment has been sent to Hydenlyne operations and remains pending confirmation.
                </p>
              </div>

              <div className="p-4 rounded-[10px] bg-canvas/80 border border-border-subtle max-w-md mx-auto text-left space-y-2 text-xs">
                <div className="flex justify-between border-b border-border-subtle pb-2">
                  <span className="text-secondary font-mono">Assignment reference:</span>
                  <span className="font-bold text-accent font-mono">{submittedRef}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-secondary">Specialist:</span>
                  <span className="text-primary font-medium">{profile.name}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-secondary">Campaign / Vessel:</span>
                  <span className="text-primary font-medium">{submittedAssignment?.vesselName || projectName || 'Not recorded'}</span>
                </div>
                {submittedAssignment?.vesselImo && (
                  <div className="flex justify-between">
                    <span className="text-secondary font-mono">Vessel IMO:</span>
                    <span className="text-primary font-mono">{submittedAssignment.vesselImo}</span>
                  </div>
                )}
                <div className="flex justify-between">
                  <span className="text-secondary">Role on board:</span>
                  <span className="text-primary font-medium">{submittedAssignment?.roleOnBoard || surveyScope}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-secondary">Window:</span>
                  <span className="text-primary font-medium">
                    {startDate} → {submittedAssignment?.endDate || `${durationDays} Days`}
                  </span>
                </div>
                <div className="flex justify-between border-t border-border-subtle pt-2">
                  <span className="text-secondary">Personnel day rate:</span>
                  <span className="text-primary font-bold font-mono">
                    {isAdmin && estimatedDayRate != null ? `£${estimatedDayRate}/day` : 'Set by administrator'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-secondary">Estimated base rate:</span>
                  <span className="text-primary font-bold font-mono">
                    {isAdmin && estimatedTotalRate != null ? `£${estimatedTotalRate.toLocaleString()}` : 'Confirmed by administrator'}
                  </span>
                </div>
              </div>

              <div className="flex justify-center gap-3 pt-2">
                <button
                  type="button"
                  onClick={handleCopySummary}
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-[10px] bg-surface-raised hover:bg-surface-selected text-xs font-semibold text-primary hover:text-primary transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus cursor-pointer"
                >
                  {isCopied ? <Check className="w-3.5 h-3.5 text-positive" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{isCopied ? 'Copied Summary' : 'Copy Booking Brief'}</span>
                </button>
                <button
                  type="button"
                  onClick={onClose}
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-[10px] bg-action hover:bg-action-hover text-xs font-semibold text-on-action transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus cursor-pointer"
                >
                  <span>Done</span>
                </button>
              </div>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              {errorMessage && (
                <div
                  role="alert"
                  className="flex items-start gap-2.5 rounded-[10px] border border-negative-border bg-negative-soft p-3 text-xs text-negative"
                >
                  <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                  <div>
                    <p className="font-semibold">Unable to record assignment</p>
                    <p className="mt-0.5">{errorMessage}</p>
                  </div>
                </div>
              )}

              {/* Campaign / Vessel Name & IMO */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                <div>
                  <label htmlFor="mobilization-campaign" className="block text-xs font-medium text-secondary mb-1">
                    Campaign or vessel <span className="text-accent">*</span>
                  </label>
                  <input
                    id="mobilization-campaign"
                    type="text"
                    required
                    value={projectName}
                    onChange={(e) => setProjectName(e.target.value)}
                    placeholder="e.g. Dogger Bank C / MV Deep Arctic"
                    className="min-h-11 w-full px-3 py-2 rounded-[10px] bg-canvas/70 border border-border-strong text-sm text-primary placeholder:text-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus transition-colors"
                  />
                </div>

                <div>
                  <label htmlFor="mobilization-imo" className="block text-xs font-medium text-secondary mb-1">
                    Vessel IMO <span className="text-muted text-xs font-normal">(Required)</span>
                  </label>
                  <input
                    id="mobilization-imo"
                    type="text"
                    value={vesselImo}
                    onChange={(e) => setVesselImo(e.target.value)}
                    placeholder="e.g. 9683934"
                    maxLength={20}
                    required
                    className="min-h-11 w-full px-3 py-2 rounded-[10px] bg-canvas/70 border border-border-strong text-sm text-primary placeholder:text-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus transition-colors font-mono"
                  />
                </div>
              </div>

              {/* Deployment Port & Survey Scope */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                <div>
                  <label htmlFor="mobilization-port" className="block text-xs font-medium text-secondary mb-1">
                    Deployment port <span className="text-accent">*</span>
                  </label>
                  <select
                    id="mobilization-port"
                    value={deploymentPort}
                    onChange={(e) => setDeploymentPort(e.target.value)}
                    required
                    className="min-h-11 w-full px-3 py-2 rounded-[10px] bg-canvas/70 border border-border-strong text-sm text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus transition-colors"
                  >
                    <option value="" disabled>Select deployment port</option>
                    <option value="Aberdeen, Scotland">Aberdeen, Scotland (UK)</option>
                    <option value="Bergen / Stavanger, Norway">Bergen / Stavanger, Norway</option>
                    <option value="Great Yarmouth, UK">Great Yarmouth, UK</option>
                    <option value="Esbjerg, Denmark">Esbjerg, Denmark</option>
                    <option value="Houston, Texas (USA)">Houston, Texas (USA)</option>
                    <option value="Singapore (APAC)">Singapore (APAC)</option>
                    <option value="Rio de Janeiro, Brazil">Rio de Janeiro, Brazil</option>
                    <option value="Perth, Australia">Perth, Australia</option>
                    <option value="Other Offshore Location">Other Offshore Location</option>
                  </select>
                </div>

                <div>
                  <label htmlFor="mobilization-scope" className="block text-xs font-medium text-secondary mb-1">
                    Work required <span className="text-accent">*</span>
                  </label>
                  <select
                    id="mobilization-scope"
                    value={surveyScope}
                    onChange={(e) => setSurveyScope(e.target.value)}
                    className="min-h-11 w-full px-3 py-2 rounded-[10px] bg-canvas/70 border border-border-strong text-sm text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus transition-colors"
                  >
                    <option value="Marine Seismic QC / OBN">2D/3D/4D Marine Seismic & OBN QC</option>
                    <option value="PAM & MMO Environmental Mitigation">PAM & MMO Passive Acoustic Monitoring</option>
                    <option value="Geotechnical CPT & Coring">Geotechnical CPT Testing & Seabed Coring</option>
                    <option value="Offshore Wind Array Cable Route">Offshore Wind Array & Inter-Array Cable Route</option>
                    <option value="UXO Clearance & Identification">Subsea UXO Survey & Target Clearance</option>
                    <option value="Client Offshore Representative">Client Offshore Representative (IOGP / IMCA)</option>
                    <option value="Offshore HSE & FLO Advisory">Offshore HSE & Fisheries Liaison (FLO)</option>
                  </select>
                </div>
              </div>

              {/* Start Date & Duration */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                <div>
                  <label htmlFor="mobilization-date" className="block text-xs font-medium text-secondary mb-1">
                    Preferred start date
                  </label>
                  <input
                    id="mobilization-date"
                    type="date"
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                    className="min-h-11 w-full px-3 py-2 rounded-[10px] bg-canvas/70 border border-border-strong text-sm text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus transition-colors"
                  />
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label htmlFor="mobilization-duration" className="text-xs font-medium text-secondary">
                      Expected duration
                    </label>
                    <span className="text-xs font-bold text-accent font-mono">
                      {durationDays} Days (~{Math.round(durationDays / 7)} wks)
                    </span>
                  </div>
                  <input
                    id="mobilization-duration"
                    type="range"
                    min={3}
                    max={60}
                    step={1}
                    value={durationDays}
                    onChange={(e) => setDurationDays(parseInt(e.target.value, 10))}
                    aria-valuetext={`${durationDays} days`}
                    className="w-full h-1.5 bg-surface-raised rounded-lg appearance-none cursor-pointer accent-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                  />
                </div>
              </div>

              {/* Client Contact Info */}
              <div className="p-3.5 rounded-[10px] bg-canvas/50 border border-border-subtle space-y-3">
                <span className="text-xs font-mono text-secondary font-medium uppercase tracking-wider block">
                  Your contact details
                </span>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div>
                    <label htmlFor="mobilization-contact-name" className="sr-only">Your full name</label>
                    <input
                      id="mobilization-contact-name"
                      type="text"
                      required
                      value={clientName}
                      onChange={(e) => setClientName(e.target.value)}
                      placeholder="Your full name"
                      autoComplete="name"
                      className="min-h-11 w-full px-3 py-1.5 rounded-lg bg-surface border border-border-strong text-sm text-primary placeholder:text-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                    />
                  </div>
                  <div>
                    <label htmlFor="mobilization-contact-email" className="sr-only">Work email</label>
                    <input
                      id="mobilization-contact-email"
                      type="email"
                      required
                      value={clientEmail}
                      onChange={(e) => setClientEmail(e.target.value)}
                      placeholder="work@operator.com"
                      autoComplete="email"
                      className="min-h-11 w-full px-3 py-1.5 rounded-lg bg-surface border border-border-strong text-sm text-primary placeholder:text-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                    />
                  </div>
                  <div>
                    <label htmlFor="mobilization-contact-company" className="sr-only">Operator or company</label>
                    <input
                      id="mobilization-contact-company"
                      type="text"
                      required
                      value={clientCompany}
                      onChange={(e) => setClientCompany(e.target.value)}
                      placeholder="Operator / Company"
                      autoComplete="organization"
                      className="min-h-11 w-full px-3 py-1.5 rounded-lg bg-surface border border-border-strong text-sm text-primary placeholder:text-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                    />
                  </div>
                </div>
              </div>

              {/* Special Instructions */}
              <div>
                <label htmlFor="mobilization-notes" className="block text-xs font-medium text-secondary mb-1">
                  Special Project Requirements / Offshore Rotation Notes
                </label>
                <textarea
                  id="mobilization-notes"
                  rows={2}
                  value={specialInstructions}
                  onChange={(e) => setSpecialInstructions(e.target.value)}
                  placeholder="e.g. 12-hour night shifts, 4-week back-to-back rotation, high-pressure airgun array experience required..."
                  className="w-full px-3 py-2 rounded-[10px] bg-canvas/70 border border-border-strong text-sm text-primary placeholder:text-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus resize-none transition-colors"
                />
              </div>

              {/* Budget Calculation & Submit */}
              <div className="flex flex-col items-stretch gap-4 border-t border-border-subtle pt-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <span className="block text-xs font-medium uppercase text-secondary font-mono">Estimated personnel budget</span>
                  <div className="text-base font-bold text-primary font-mono">
                    {isAdmin && estimatedTotalRate != null ? (
                      <>
                        £{estimatedTotalRate.toLocaleString()}{' '}
                        <span className="text-xs text-secondary font-normal">
                          ({durationDays} days @ £{estimatedDayRate}/d)
                        </span>
                      </>
                    ) : 'Rate on request'}
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={onClose}
                    className="min-h-11 px-3 py-2 rounded-[10px] text-secondary hover:text-primary text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus cursor-pointer"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isSubmitting}
                    className="inline-flex min-h-11 items-center gap-1.5 px-4 py-2 rounded-[10px] bg-action hover:bg-action-hover disabled:opacity-50 text-on-action font-semibold text-xs transition-all shadow-md shadow-black/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus cursor-pointer"
                  >
                    {isSubmitting ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin text-on-action" />
                        <span>Recording…</span>
                      </>
                    ) : (
                      <>
                        <Send className="w-3.5 h-3.5" />
                        <span>Send request</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            </form>
          )}
        </div>
      </motion.div>
    </motion.div>
    )}
  </AnimatePresence>
  );
};
