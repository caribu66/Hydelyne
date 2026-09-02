import { FC, useState, useEffect, useRef, FormEvent } from 'react';
import { useAccessibleDialog } from '../hooks/useAccessibleDialog';
import { UserProfile } from '../types';
import { motion } from 'motion/react';
import {
  X,
  Send,
  Anchor,
  CheckCircle2,
  Copy,
  Check,
} from 'lucide-react';

interface MobilizationInquiryModalProps {
  isOpen: boolean;
  onClose: () => void;
  profile: UserProfile | null;
  onShowToast: (message: string) => void;
}

export const MobilizationInquiryModal: FC<MobilizationInquiryModalProps> = ({
  isOpen,
  onClose,
  profile,
  onShowToast,
}) => {
  const [projectName, setProjectName] = useState('');
  const [deploymentPort, setDeploymentPort] = useState('Aberdeen, Scotland');
  const [surveyScope, setSurveyScope] = useState('Marine Seismic QC / OBN');
  const [startDate, setStartDate] = useState(
    new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10)
  );
  const [durationDays, setDurationDays] = useState(21);
  const [clientCompany, setClientCompany] = useState('');
  const [clientName, setClientName] = useState('');
  const [clientEmail, setClientEmail] = useState('');
  const [specialInstructions, setSpecialInstructions] = useState('');

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submittedRef, setSubmittedRef] = useState<string | null>(null);
  const [isCopied, setIsCopied] = useState(false);
  const dialogRef = useRef<HTMLDivElement>(null);
  useAccessibleDialog(isOpen && Boolean(profile), dialogRef, onClose);

  useEffect(() => {
    if (isOpen) {
      setSubmittedRef(null);
      setIsSubmitting(false);
    }
  }, [isOpen, profile]);

  if (!isOpen || !profile) return null;

  const estimatedDayRate = profile.dayRate || 850;
  const estimatedTotalRate = estimatedDayRate * durationDays;

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);

    setTimeout(() => {
      const generatedRef = `HYD-MOB-2026-${Math.floor(1000 + Math.random() * 9000)}`;
      setSubmittedRef(generatedRef);
      setIsSubmitting(false);
      onShowToast(`Mobilization request ${generatedRef} dispatched to Hydenlyne operations`);
    }, 600);
  };

  const handleCopySummary = () => {
    const summary = `
[HYDENLYNE MOBILIZATION REQUEST - ${submittedRef}]
Specialist: ${profile.name} (${profile.title})
Standard Day Rate: £${estimatedDayRate}/day
Campaign: ${projectName || 'Offshore Campaign'}
Port: ${deploymentPort}
Scope: ${surveyScope}
Start Date: ${startDate} (${durationDays} Days Duration)
Estimated Base Rate: £${estimatedTotalRate.toLocaleString()}
Client: ${clientName || 'Lead Recruiter'} (${clientCompany || 'Energy Operator'}) - ${clientEmail || 'contact@client.com'}
Instructions: ${specialInstructions || 'None'}
Status: PENDING HYDENLYNE OPERATIONS CONFIRMATION
    `.trim();

    navigator.clipboard?.writeText(summary);
    setIsCopied(true);
    onShowToast('Mobilization summary copied to clipboard');
    setTimeout(() => setIsCopied(false), 2000);
  };

  return (
    <div className="ui-overlay-enter fixed inset-0 z-50 flex items-center justify-center p-2 sm:p-4 bg-canvas/80 backdrop-blur-md">
      <motion.div
        ref={dialogRef}
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
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
          {/* Specialist Snapshot Banner */}
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
                  <span className="text-positive font-medium">{profile.availability}</span>
                  <span>•</span>
                  <span>{profile.location}</span>
                </div>
              </div>
            </div>

            <div className="text-right shrink-0">
              <span className="block text-xs font-medium uppercase text-secondary font-mono">Indicative day rate</span>
              <span className="text-base font-bold text-primary font-mono">
                £{estimatedDayRate}
                <span className="text-xs text-secondary font-normal">/day</span>
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
                <h3 className="text-base font-bold text-primary">Request received</h3>
                <p className="text-xs text-secondary max-w-md mx-auto">
                  Hydenlyne operations will review the details and follow up with availability and next steps within 2 hours.
                </p>
              </div>

              <div className="p-4 rounded-[10px] bg-canvas/80 border border-border-subtle max-w-md mx-auto text-left space-y-2 text-xs">
                <div className="flex justify-between border-b border-border-subtle pb-2">
                  <span className="text-secondary font-mono">Request reference:</span>
                  <span className="font-bold text-accent font-mono">{submittedRef}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-secondary">Campaign:</span>
                  <span className="text-primary font-medium">{projectName || 'Offshore Campaign'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-secondary">Duration:</span>
                  <span className="text-primary font-medium">{durationDays} Days ({startDate})</span>
                </div>
                <div className="flex justify-between">
                      <span className="text-secondary">Estimated base rate:</span>
                  <span className="text-primary font-bold font-mono">£{estimatedTotalRate.toLocaleString()}</span>
                </div>
              </div>

              <div className="flex justify-center gap-3 pt-2">
                <button
                  type="button"
                  onClick={handleCopySummary}
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-[10px] bg-surface-raised hover:bg-surface-selected text-xs font-semibold text-primary hover:text-primary transition-colors cursor-pointer"
                >
                  {isCopied ? <Check className="w-3.5 h-3.5 text-positive" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{isCopied ? 'Copied Summary' : 'Copy Booking Brief'}</span>
                </button>
                <button
                  type="button"
                  onClick={onClose}
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-[10px] bg-action hover:bg-action-hover text-xs font-semibold text-on-action transition-colors cursor-pointer"
                >
                  <span>Done</span>
                </button>
              </div>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Campaign / Vessel Name & Deployment Hub */}
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
                    className="min-h-11 w-full px-3 py-2 rounded-[10px] bg-canvas/70 border border-border-strong text-sm text-primary placeholder-zinc-400 focus:outline-none focus:border-border-strong transition-colors"
                  />
                </div>

                <div>
                  <label htmlFor="mobilization-port" className="block text-xs font-medium text-secondary mb-1">
                    Deployment port <span className="text-accent">*</span>
                  </label>
                  <select
                    id="mobilization-port"
                    value={deploymentPort}
                    onChange={(e) => setDeploymentPort(e.target.value)}
                    className="min-h-11 w-full px-3 py-2 rounded-[10px] bg-canvas/70 border border-border-strong text-sm text-primary focus:outline-none focus:border-border-strong transition-colors"
                  >
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
              </div>

              {/* Survey Discipline Scope */}
              <div>
                <label htmlFor="mobilization-scope" className="block text-xs font-medium text-secondary mb-1">
                  Work required
                </label>
                <select
                  id="mobilization-scope"
                  value={surveyScope}
                  onChange={(e) => setSurveyScope(e.target.value)}
                  className="min-h-11 w-full px-3 py-2 rounded-[10px] bg-canvas/70 border border-border-strong text-sm text-primary focus:outline-none focus:border-border-strong transition-colors"
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
                    className="min-h-11 w-full px-3 py-2 rounded-[10px] bg-canvas/70 border border-border-strong text-sm text-primary focus:outline-none focus:border-border-strong transition-colors"
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
                    className="w-full h-1.5 bg-surface-raised rounded-lg appearance-none cursor-pointer accent-blue-500"
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
                      className="min-h-11 w-full px-3 py-1.5 rounded-lg bg-surface border border-border-strong text-sm text-primary placeholder-zinc-400 focus:outline-none focus:border-border-strong"
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
                      className="min-h-11 w-full px-3 py-1.5 rounded-lg bg-surface border border-border-strong text-sm text-primary placeholder-zinc-400 focus:outline-none focus:border-border-strong"
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
                      className="min-h-11 w-full px-3 py-1.5 rounded-lg bg-surface border border-border-strong text-sm text-primary placeholder-zinc-400 focus:outline-none focus:border-border-strong"
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
                  className="w-full px-3 py-2 rounded-[10px] bg-canvas/70 border border-border-strong text-sm text-primary placeholder-zinc-400 focus:outline-none focus:border-border-strong resize-none transition-colors"
                />
              </div>

              {/* Budget Calculation & Submit */}
              <div className="flex flex-col items-stretch gap-4 border-t border-border-subtle pt-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <span className="block text-xs font-medium uppercase text-secondary font-mono">Estimated personnel budget</span>
                  <div className="text-base font-bold text-primary font-mono">
                    £{estimatedTotalRate.toLocaleString()}{' '}
                    <span className="text-xs text-secondary font-normal">
                      ({durationDays} days @ £{estimatedDayRate}/d)
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={onClose}
                    className="min-h-11 px-3 py-2 rounded-[10px] text-secondary hover:text-primary text-xs font-medium transition-colors cursor-pointer"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isSubmitting}
                    className="inline-flex min-h-11 items-center gap-1.5 px-4 py-2 rounded-[10px] bg-action hover:bg-action-hover disabled:opacity-50 text-on-action font-semibold text-xs transition-all shadow-md shadow-black/30 cursor-pointer"
                  >
                    <Send className="w-3.5 h-3.5" />
                    <span>{isSubmitting ? 'Sending…' : 'Send request'}</span>
                  </button>
                </div>
              </div>
            </form>
          )}
        </div>
      </motion.div>
    </div>
  );
};
