import { FC, useCallback, useEffect, useState, useRef, ChangeEvent, FormEvent } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { X, UserPlus, Loader2, Upload, FileText, CheckCircle } from 'lucide-react';
import { ApolloError, useMutation } from '@apollo/client';
import { CREATE_CREW_MEMBER } from '../lib/queries';
import { getDocumentStatus, previewCv, uploadDocument } from '../lib/documentsApi';
import { useAccessibleDialog } from '../hooks/useAccessibleDialog';
import { apolloResultHasErrors } from '../utils/sessionScope';
import { isAddCrewOperationCurrent, isCvProcessingFailure } from './addCrewMemberUtils';

interface AddCrewMemberModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
  isAdmin: boolean;
  sessionKey?: string | null;
}

interface UploadedCv {
  documentId: string;
  status: string;
}

export const AddCrewMemberModal: FC<AddCrewMemberModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
  isAdmin,
  sessionKey = null,
}) => {
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [nationality, setNationality] = useState('');
  const [cvFile, setCvFile] = useState<File | null>(null);
  const [uploadedCv, setUploadedCv] = useState<UploadedCv | null>(null);
  const [createdCrewId, setCreatedCrewId] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [confirmDistinct, setConfirmDistinct] = useState(false);
  const [duplicateCandidateId, setDuplicateCandidateId] = useState<string | null>(null);
  const [step, setStep] = useState<'form' | 'creating' | 'extracting' | 'done'>('form');
  const uploadKeyRef = useRef<string | null>(null);
  const currentSessionKeyRef = useRef(sessionKey);
  const previousSessionKeyRef = useRef(sessionKey);
  const currentIsOpenRef = useRef(isOpen);
  const operationVersionRef = useRef(0);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  currentIsOpenRef.current = isOpen;

  const resetForm = useCallback(() => {
    operationVersionRef.current += 1;
    setFullName('');
    setEmail('');
    setPhone('');
    setNationality('');
    setCvFile(null);
    setUploadedCv(null);
    setCreatedCrewId(null);
    setUploadError(null);
    setIsPreviewing(false);
    setConfirmDistinct(false);
    setDuplicateCandidateId(null);
    setStep('form');
    uploadKeyRef.current = null;
  }, []);

  const handleClose = useCallback(() => {
    resetForm();
    onClose();
  }, [onClose, resetForm]);

  currentSessionKeyRef.current = sessionKey;

  useEffect(() => {
    operationVersionRef.current += 1;
    if (previousSessionKeyRef.current !== null && previousSessionKeyRef.current !== sessionKey) {
      resetForm();
      onClose();
    }
    previousSessionKeyRef.current = sessionKey;
  }, [onClose, resetForm, sessionKey]);

  useAccessibleDialog(isOpen, dialogRef, handleClose);

  const [createCrewMember] = useMutation(CREATE_CREW_MEMBER);

  const handleFileChange = async (e: ChangeEvent<HTMLInputElement>) => {
    operationVersionRef.current += 1;
    const file = e.target.files?.[0];
    if (file && sessionKey && currentSessionKeyRef.current === sessionKey) {
      if (file.type === 'application/pdf' || file.name.endsWith('.pdf')) {
        setCvFile(file);
        uploadKeyRef.current = null;
        setUploadError(null);
        setIsPreviewing(true);
        const operationVersion = ++operationVersionRef.current;
        try {
          const preview = await previewCv(file);
          if (
            operationVersion !== operationVersionRef.current
            || !currentIsOpenRef.current
            || currentSessionKeyRef.current !== sessionKey
          ) return;
          if (preview.full_name && !fullName.trim()) setFullName(preview.full_name);
          if (preview.email && !email.trim()) setEmail(preview.email);
          if (preview.phone && !phone.trim()) setPhone(preview.phone);
          if (preview.nationality && !nationality.trim()) setNationality(preview.nationality);
        } catch (error) {
          if (
            operationVersion !== operationVersionRef.current
            || !currentIsOpenRef.current
            || currentSessionKeyRef.current !== sessionKey
          ) return;
          setUploadError(error instanceof Error ? error.message : 'Could not read CV details');
        } finally {
          if (
            operationVersion === operationVersionRef.current
            && currentIsOpenRef.current
            && currentSessionKeyRef.current === sessionKey
          ) setIsPreviewing(false);
        }
      } else {
        setCvFile(null);
        setUploadedCv(null);
        setIsPreviewing(false);
        setUploadError(null);
        alert('Please upload a PDF file');
        e.target.value = '';
      }
    } else if (file) {
      setCvFile(null);
      setUploadedCv(null);
      setIsPreviewing(false);
    }
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!cvFile || !sessionKey || currentSessionKeyRef.current !== sessionKey) return;

    setStep('creating');
    setUploadError(null);
    const operationVersion = ++operationVersionRef.current;

    const operationIsCurrent = () => isAddCrewOperationCurrent(
      operationVersion,
      operationVersionRef.current,
      true,
      currentIsOpenRef.current,
      currentSessionKeyRef.current,
      sessionKey,
    );

    try {
      let crewId = createdCrewId;
      if (!crewId) {
        const result = await createCrewMember({
          variables: {
            fullName: fullName.trim() || 'Pending CV import',
            email: email.trim() || undefined,
            phone: phone.trim() || undefined,
            nationality: nationality.trim() || undefined,
            cvSubmission: true,
            confirmDistinct,
          },
        });
        if (apolloResultHasErrors(result)) throw new Error('Contractor creation returned errors');
        if (!operationIsCurrent()) return;
        crewId = result.data?.createCrewMember?.id ?? null;
        setCreatedCrewId(crewId);
        setDuplicateCandidateId(null);
      }

      if (cvFile && crewId) {
        setStep('extracting');
        let result: Awaited<ReturnType<typeof uploadDocument>>;
        try {
          // Multipart upload transfers the selected CV bytes; the legacy
          // GraphQL mutation sent metadata only and could never extract it.
          uploadKeyRef.current ??= crypto.randomUUID();
          result = await uploadDocument(crewId, cvFile, 'cv', uploadKeyRef.current);
          if (!operationIsCurrent()) return;
          setUploadedCv({ documentId: result.id, status: result.status });
        } catch (extractError) {
          if (!operationIsCurrent()) return;
          // Preserve the draft ID so retrying uploads to the same contractor
          // instead of creating an accidental duplicate.
          setUploadError(extractError instanceof Error ? extractError.message : 'CV upload failed');
          setStep('form');
          return;
        }

        try {
          // Polling is separate from upload: a temporary status-read failure
          // must never cause the CV bytes to be uploaded a second time.
          let status = result.status;
          for (let attempt = 0; attempt < 30 && ['pending', 'processing'].includes(status); attempt += 1) {
            await new Promise((resolve) => window.setTimeout(resolve, 2_000));
            const latest = await getDocumentStatus(result.id);
            if (!operationIsCurrent()) return;
            status = latest.extraction_status;
            setUploadedCv({ documentId: result.id, status });
          }
          if (isCvProcessingFailure(status)) {
            setUploadError('CV processing failed. Please try again.');
            setStep('form');
            return;
          }
          if (['pending', 'processing'].includes(status)) {
            setUploadError('CV processing is taking longer than expected. Please try again.');
            setStep('form');
            return;
          }
        } catch (statusError) {
          if (!operationIsCurrent()) return;
          setUploadError(statusError instanceof Error ? statusError.message : 'Could not refresh CV status');
          setStep('form');
          return;
        }
      }

      if (!operationIsCurrent()) return;
      setStep('done');
      onSuccess?.();
    } catch (error) {
      if (!operationIsCurrent()) return;
      const message = error instanceof Error ? error.message : 'Could not create contractor';
      if (error instanceof ApolloError) {
        const candidateId = error.graphQLErrors
          .map((graphQLError) => graphQLError.extensions?.candidateId)
          .find((value): value is string => typeof value === 'string');
        setDuplicateCandidateId(candidateId ?? null);
      }
      setUploadError(message.includes('possible duplicate')
        ? `${message}. An administrator must check the existing profile before this can continue.`
        : message);
      setStep('form');
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="fixed inset-0 bg-canvas/80 backdrop-blur-sm"
            onClick={handleClose}
          />
          <motion.div
            ref={dialogRef}
            initial={{ opacity: 0, scale: 0.96, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 8 }}
            transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
            className="max-h-[calc(100dvh-1.5rem)] w-full max-w-md overflow-y-auto rounded-[14px] border border-border-subtle bg-surface p-4 shadow-2xl sm:max-h-[92vh] sm:p-6 z-10"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-labelledby="add-specialist-title"
          >
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-[10px] bg-surface-raised border border-border-strong">
                  <UserPlus className="h-5 w-5 text-secondary" />
                </div>
                <h2 id="add-specialist-title" className="text-lg font-semibold text-primary">Add contractor</h2>
              </div>
              <button
                type="button"
                onClick={handleClose}
                className="inline-flex min-h-9 min-w-9 items-center justify-center rounded-lg text-secondary hover:text-primary hover:bg-surface-raised transition-colors cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                aria-label="Close"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

        {step === 'done' ? (
          <div className="space-y-4">
            <div className="flex items-center gap-3 p-4 rounded-[10px] bg-positive-soft/30 border border-positive-border/60">
              <CheckCircle className="w-6 h-6 text-positive shrink-0" />
              <div>
                <p className="font-medium text-positive">CV submitted for review</p>
                <p className="text-sm text-positive/80">
                  An administrator must approve the CV information before this contractor appears in search.
                </p>
              </div>
            </div>

            {uploadedCv && (
              <div className="space-y-1 p-4 rounded-[10px] bg-surface-raised/50 border border-border-strong">
                <h3 className="text-sm font-medium text-primary">CV processing</h3>
                <p className="text-sm text-secondary">Status: {uploadedCv.status}.</p>
                <p className="text-xs text-muted">Document ID: {uploadedCv.documentId}</p>
              </div>
            )}

            {uploadError && (
              <p className="rounded-[10px] border border-warning-border/60 bg-warning-soft/30 p-3 text-sm text-warning">
                The CV needs attention: {uploadError}
              </p>
            )}

            <button
              type="button"
              onClick={handleClose}
              className="w-full px-4 py-2.5 rounded-[10px] bg-action hover:bg-action-hover text-on-action transition-colors cursor-pointer font-medium"
            >
              Done
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            {createdCrewId && <p className="rounded-lg border border-warning-border bg-warning-soft/30 p-3 text-sm text-warning">The draft is saved. Retry the CV upload below; a second contractor will not be created.</p>}
            <div>
              <label htmlFor="fullName" className="block text-sm font-medium text-secondary mb-1.5">
                Full name {!cvFile && <span className="text-danger">*</span>}
              </label>
              <input
                id="fullName"
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder={cvFile ? 'Optional — extracted from CV if left blank' : 'e.g. John Smith'}
                required={!cvFile}
                disabled={step !== 'form' || Boolean(createdCrewId)}
                className="w-full px-3 py-2.5 rounded-[10px] bg-surface-raised border border-border-strong text-primary placeholder:text-muted focus:outline-none focus:border-border-strong focus:ring-1 focus:ring-focus/20 disabled:opacity-50"
              />
            </div>

            {isAdmin && duplicateCandidateId && (
              <label className="flex items-start gap-3 rounded-[10px] border border-border-subtle bg-surface-raised/40 p-3 text-sm text-secondary">
                <input type="checkbox" checked={confirmDistinct} onChange={(event) => setConfirmDistinct(event.target.checked)} className="mt-0.5 h-4 w-4 accent-current" />
                <span><strong className="block font-semibold text-primary">This is a different specialist</strong> Use only after checking a possible duplicate result.</span>
              </label>
            )}

            <div>
              <label htmlFor="email" className="block text-sm font-medium text-secondary mb-1.5">
                Email
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="e.g. john@example.com"
                disabled={step !== 'form' || Boolean(createdCrewId)}
                className="w-full px-3 py-2.5 rounded-[10px] bg-surface-raised border border-border-strong text-primary placeholder:text-muted focus:outline-none focus:border-border-strong focus:ring-1 focus:ring-focus/20 disabled:opacity-50"
              />
            </div>

            <div>
              <label htmlFor="phone" className="block text-sm font-medium text-secondary mb-1.5">
                Phone
              </label>
              <input
                id="phone"
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="e.g. +44 123 456789"
                disabled={step !== 'form' || Boolean(createdCrewId)}
                className="w-full px-3 py-2.5 rounded-[10px] bg-surface-raised border border-border-strong text-primary placeholder:text-muted focus:outline-none focus:border-border-strong focus:ring-1 focus:ring-focus/20 disabled:opacity-50"
              />
            </div>

            <div>
              <label htmlFor="nationality" className="block text-sm font-medium text-secondary mb-1.5">
                Nationality
              </label>
              <input
                id="nationality"
                type="text"
                value={nationality}
                onChange={(e) => setNationality(e.target.value)}
                placeholder="e.g. British"
                disabled={step !== 'form' || Boolean(createdCrewId)}
                className="w-full px-3 py-2.5 rounded-[10px] bg-surface-raised border border-border-strong text-primary placeholder:text-muted focus:outline-none focus:border-border-strong focus:ring-1 focus:ring-focus/20 disabled:opacity-50"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-secondary mb-1.5">
                CV (PDF) <span className="text-danger">*</span>
              </label>
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,application/pdf"
                onChange={handleFileChange}
                className="hidden"
                disabled={step !== 'form'}
              />
              {cvFile ? (
                <div className="flex items-center gap-3 p-3 rounded-[10px] bg-surface-raised border border-border-strong">
                  <FileText className="w-5 h-5 text-secondary shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-primary truncate">{cvFile.name}</p>
                    <p className="text-xs text-muted">{(cvFile.size / 1024).toFixed(0)} KB</p>
                  </div>
                  {step === 'form' && (
                    <button
                      type="button"
                      onClick={() => {
                        setCvFile(null);
                        uploadKeyRef.current = null;
                        if (fileInputRef.current) fileInputRef.current.value = '';
                      }}
                      className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-lg text-secondary hover:bg-surface-selected hover:text-primary cursor-pointer"
                      aria-label="Remove selected CV"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  )}
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={step !== 'form'}
                  className="w-full p-4 rounded-[10px] border-2 border-dashed border-border-strong hover:border-border-strong text-secondary hover:text-secondary transition-colors cursor-pointer disabled:opacity-50 flex flex-col items-center gap-2"
                >
                  <Upload className="w-5 h-5" />
                  <span className="text-sm">Click to upload CV (PDF)</span>
                  <span className="text-xs text-secondary">We'll read the name and nationality from the CV to pre-fill this form</span>
                </button>
              )}
              {isPreviewing && (
                <div className="mt-2 flex items-center gap-2 text-sm text-secondary">
                  <Loader2 className="h-4 w-4 animate-spin" /> Reading CV and filling the form…
                </div>
              )}
              {uploadError && step === 'form' && (
                <div className="mt-2 space-y-2 rounded-lg border border-warning-border bg-warning-soft/30 p-3 text-sm text-warning">
                  <p>{uploadError}</p>
                  {isAdmin && duplicateCandidateId && (
                    <button type="button" onClick={() => { setCreatedCrewId(duplicateCandidateId); setDuplicateCandidateId(null); setUploadError(null); }} className="min-h-11 rounded-lg border border-warning-border bg-surface px-3 font-semibold text-primary hover:bg-surface-raised focus-visible:ring-2 focus-visible:ring-focus">Use the existing contractor</button>
                  )}
                </div>
              )}
            </div>

            {step === 'creating' && (
              <div className="flex items-center gap-2 p-3 rounded-[10px] bg-surface-raised/70 border border-border-strong text-secondary">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span className="text-sm">Creating contractor…</span>
              </div>
            )}

            {step === 'extracting' && (
              <div className="flex items-center gap-2 p-3 rounded-[10px] bg-surface-raised/70 border border-border-strong text-secondary">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span className="text-sm">Uploading CV and queuing extraction...</span>
              </div>
            )}

            <div className="flex gap-3 pt-2">
              <button
                type="button"
                onClick={handleClose}
                disabled={step !== 'form'}
                className="min-h-11 flex-1 px-4 py-2.5 rounded-[10px] border border-border-strong text-secondary hover:bg-surface-raised transition-colors cursor-pointer font-medium disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={step !== 'form' || isPreviewing || !cvFile}
                className="min-h-11 flex-1 px-4 py-2.5 rounded-[10px] bg-action hover:bg-action-hover disabled:bg-surface-selected disabled:text-muted text-on-action transition-colors cursor-pointer font-medium flex items-center justify-center gap-2"
              >
                {step === 'form'
                  ? createdCrewId ? 'Retry CV upload' : 'Add contractor'
                  : <Loader2 className="w-4 h-4 animate-spin" />}
              </button>
            </div>
          </form>
        )}
        </motion.div>
      </div>
    )}
  </AnimatePresence>
  );
};
