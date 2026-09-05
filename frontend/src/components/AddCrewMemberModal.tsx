import { FC, useState, useRef, ChangeEvent, FormEvent } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { X, UserPlus, Loader2, Upload, FileText, CheckCircle } from 'lucide-react';
import { useMutation } from '@apollo/client';
import { CREATE_CREW_MEMBER } from '../lib/queries';
import { getDocumentStatus, previewCv, uploadDocument } from '../lib/documentsApi';
import { useAccessibleDialog } from '../hooks/useAccessibleDialog';

interface AddCrewMemberModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

interface UploadedCv {
  documentId: string;
  status: string;
}

export const AddCrewMemberModal: FC<AddCrewMemberModalProps> = ({ isOpen, onClose, onSuccess }) => {
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [nationality, setNationality] = useState('');
  const [cvFile, setCvFile] = useState<File | null>(null);
  const [uploadedCv, setUploadedCv] = useState<UploadedCv | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [step, setStep] = useState<'form' | 'creating' | 'extracting' | 'done'>('form');
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);

  const resetForm = () => {
    setFullName('');
    setEmail('');
    setPhone('');
    setNationality('');
    setCvFile(null);
    setUploadedCv(null);
    setUploadError(null);
    setIsPreviewing(false);
    setStep('form');
  };

  const handleClose = () => {
    resetForm();
    onClose();
  };

  useAccessibleDialog(isOpen, dialogRef, handleClose);

  const [createCrewMember] = useMutation(CREATE_CREW_MEMBER);

  const handleFileChange = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      if (file.type === 'application/pdf' || file.name.endsWith('.pdf')) {
        setCvFile(file);
        setUploadError(null);
        setIsPreviewing(true);
        try {
          const preview = await previewCv(file);
          if (preview.full_name && !fullName.trim()) setFullName(preview.full_name);
          if (preview.email && !email.trim()) setEmail(preview.email);
          if (preview.phone && !phone.trim()) setPhone(preview.phone);
          if (preview.nationality && !nationality.trim()) setNationality(preview.nationality);
        } catch (error) {
          setUploadError(error instanceof Error ? error.message : 'Could not read CV details');
        } finally {
          setIsPreviewing(false);
        }
      } else {
        alert('Please upload a PDF file');
        e.target.value = '';
      }
    }
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!fullName.trim() && !cvFile) return;

    setStep('creating');

    try {
      const { data } = await createCrewMember({
        variables: {
          // A CV-only import is completed by the background extractor.  The
          // backend replaces this marker with the extracted name, but never
          // overwrites a name typed by the operator.
          fullName: fullName.trim() || 'Pending CV import',
          email: email.trim() || undefined,
          phone: phone.trim() || undefined,
          nationality: nationality.trim() || undefined,
        },
      });

      const crewId = data?.createCrewMember?.id;

      if (cvFile && crewId) {
        setStep('extracting');
        try {
          // Multipart upload transfers the selected CV bytes; the legacy
          // GraphQL mutation sent metadata only and could never extract it.
          const result = await uploadDocument(crewId, cvFile, 'cv');
          setUploadedCv({ documentId: result.id, status: result.status });

          // The upload endpoint deliberately returns immediately, while the
          // worker extracts CV data. Wait for its terminal state so the next
          // view reflects the populated profile rather than just "queued".
          let status = result.status;
          for (let attempt = 0; attempt < 30 && ['pending', 'processing'].includes(status); attempt += 1) {
            await new Promise((resolve) => window.setTimeout(resolve, 2_000));
            const latest = await getDocumentStatus(result.id);
            status = latest.extraction_status;
            setUploadedCv({ documentId: result.id, status });
          }
        } catch (extractError) {
          // The crew record exists even if its optional CV upload fails.
          // Do not claim that extraction completed.
          setUploadError(extractError instanceof Error ? extractError.message : 'CV upload failed');
        }
      }

      setStep('done');
      onSuccess?.();
    } catch (error) {
      console.error('Failed to create contractor:', error);
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
                <p className="font-medium text-positive">Contractor added successfully!</p>
                <p className="text-sm text-positive/80">
                  {uploadedCv ? 'CV uploaded and profile extraction finished.' : 'No CV was uploaded.'}
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
                The contractor was created, but the CV was not uploaded: {uploadError}
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
                disabled={step !== 'form'}
                className="w-full px-3 py-2.5 rounded-[10px] bg-surface-raised border border-border-strong text-primary placeholder:text-muted focus:outline-none focus:border-border-strong focus:ring-1 focus:ring-focus/20 disabled:opacity-50"
              />
            </div>

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
                disabled={step !== 'form'}
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
                disabled={step !== 'form'}
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
                disabled={step !== 'form'}
                className="w-full px-3 py-2.5 rounded-[10px] bg-surface-raised border border-border-strong text-primary placeholder:text-muted focus:outline-none focus:border-border-strong focus:ring-1 focus:ring-focus/20 disabled:opacity-50"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-secondary mb-1.5">
                CV (PDF) - Optional
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
                <p className="mt-2 text-sm text-warning">{uploadError}</p>
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
                disabled={step !== 'form' || isPreviewing || (!fullName.trim() && !cvFile)}
                className="min-h-11 flex-1 px-4 py-2.5 rounded-[10px] bg-action hover:bg-action-hover disabled:bg-surface-selected disabled:text-muted text-on-action transition-colors cursor-pointer font-medium flex items-center justify-center gap-2"
              >
                {step === 'form' ? 'Add contractor' : <Loader2 className="w-4 h-4 animate-spin" />}
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
