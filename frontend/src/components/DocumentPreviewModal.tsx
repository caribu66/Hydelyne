import { FC, useState, useRef } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'motion/react';
import { useAccessibleDialog } from '../hooks/useAccessibleDialog';
import { SpecialistDocument, UserProfile } from '../types';
import { getDocumentComplianceStatus } from '../hooks/useSpecialistDocuments';
import { hasOriginalDocumentFile } from '../utils/documentUtils';
import { ConfirmDialog } from './ConfirmDialog';
import {
  X,
  FileText,
  Download,
  Printer,
  ShieldCheck,
  Calendar,
  Clock,
  Trash2,
  CheckCircle2,
  AlertTriangle,
  FileCheck,
  Check,
  ShieldAlert,
} from 'lucide-react';

interface DocumentPreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  document: SpecialistDocument | null;
  profile: UserProfile;
  onDelete?: (docId: string) => void | Promise<void>;
  onShowToast?: (msg: string) => void;
  onReviewAction?: (docId: string, action: 'approve' | 'reject') => void | Promise<void>;
  canReview?: boolean;
}

export const DocumentPreviewModal: FC<DocumentPreviewModalProps> = ({
  isOpen,
  onClose,
  document: doc,
  profile,
  onDelete,
  onShowToast,
  onReviewAction,
  canReview = false,
}) => {
  const [isDeleteConfirmationOpen, setIsDeleteConfirmationOpen] = useState(false);
  const [isReviewing, setIsReviewing] = useState(false);
  const [showRawText, setShowRawText] = useState(false);
  const dialogRef = useRef<HTMLDivElement>(null);
  useAccessibleDialog(isOpen && Boolean(doc), dialogRef, onClose);

  const handleReview = async (action: 'approve' | 'reject') => {
    if (!doc || !onReviewAction) return;
    setIsReviewing(true);
    try {
      await onReviewAction(doc.id, action);
      onShowToast?.(
        action === 'approve'
          ? `Approved “${doc.title}” for compliance`
          : `Rejected “${doc.title}”`,
      );
      onClose();
    } catch (err) {
      onShowToast?.(err instanceof Error ? err.message : `Failed to ${action} document`);
    } finally {
      setIsReviewing(false);
    }
  };

  const compliance = doc ? getDocumentComplianceStatus(doc) : null;
  const originalFileAvailable = doc ? hasOriginalDocumentFile(doc) : false;

  const extractedData = doc?.extractedData;
  const asStringArray = (value: unknown): string[] =>
    Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : [];
  const extractedFullName = typeof extractedData?.full_name === 'string' ? extractedData.full_name : undefined;
  const extractedSummary = typeof extractedData?.professional_summary === 'string' ? extractedData.professional_summary : undefined;
  const extractedSkills = asStringArray(extractedData?.skills);
  const extractedCertifications = asStringArray(extractedData?.certifications);
  const extractedPersonalInfo =
    extractedData?.personal_information && typeof extractedData.personal_information === 'object'
      ? (extractedData.personal_information as Record<string, string>)
      : undefined;
  const hasExtractedContent = Boolean(
    extractedFullName || extractedSummary || extractedSkills.length || extractedCertifications.length || extractedPersonalInfo
  );

  const handleDownload = () => {
    if (!doc) return;
    if (!originalFileAvailable) {
      onShowToast?.(`Original file unavailable for “${doc.title}”. This is a compliance record only.`);
      return;
    }

    if (doc.fileUrl) {
      const a = window.document.createElement('a');
      a.href = doc.fileUrl;
      a.download = doc.fileName || `${doc.title}.pdf`;
      window.document.body.appendChild(a);
      a.click();
      window.document.body.removeChild(a);
      onShowToast?.(`Downloaded ${doc.fileName}`);
      return;
    }

  };

  const handlePrint = () => {
    window.print();
  };

  const handleDelete = () => {
    setIsDeleteConfirmationOpen(true);
  };

  const confirmDelete = async () => {
    if (!doc) return;
    try {
      await onDelete?.(doc.id);
      onShowToast?.(`Removed ${doc.title}`);
      setIsDeleteConfirmationOpen(false);
      onClose();
    } catch (error) {
      onShowToast?.(error instanceof Error ? error.message : `Could not remove ${doc.title}`);
    }
  };

  return createPortal(
    <>
      <AnimatePresence>
        {isOpen && doc && (
          <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.18 }}
              className="fixed inset-0 bg-canvas/80 backdrop-blur-xs"
              onClick={onClose}
            />
            <motion.div
              ref={dialogRef}
              initial={{ opacity: 0, scale: 0.96, y: 8 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.96, y: 8 }}
              transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
              className="relative z-10 bg-surface border border-border-strong/80 rounded-[14px] w-full max-w-3xl overflow-hidden shadow-2xl flex flex-col max-h-[90vh]"
              onClick={(e) => e.stopPropagation()}
              role="dialog"
              aria-modal="true"
              aria-labelledby="document-preview-title"
              aria-describedby="document-preview-description"
            >
        {/* Header */}
        <div className="sticky top-0 z-10 flex items-center justify-between px-5 py-4 border-b border-border-subtle bg-canvas/95 backdrop-blur-sm">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-10 h-10 rounded-[10px] bg-accent-soft/80 border border-border-strong/80 flex items-center justify-center text-accent shrink-0">
              <FileCheck className="w-5 h-5 text-accent" />
            </div>
            <div className="min-w-0">
              <h2 id="document-preview-title" className="text-base font-bold text-primary truncate">{doc.title}</h2>
              <p id="document-preview-description" className="text-xs text-secondary truncate">
                {profile.name} • {profile.department}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleDownload}
              disabled={!originalFileAvailable}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[10px] bg-action hover:bg-action-hover text-on-action text-xs font-semibold transition-colors cursor-pointer disabled:cursor-not-allowed disabled:bg-surface-raised disabled:text-muted"
              title={originalFileAvailable ? 'Download original file' : 'Original file unavailable'}
            >
              <Download className="w-3.5 h-3.5" />
              <span>{originalFileAvailable ? 'Download Original' : 'Original Unavailable'}</span>
            </button>

            <button
              type="button"
              onClick={handlePrint}
              className="p-2 rounded-[10px] bg-surface-raised hover:bg-surface-selected text-secondary transition-colors cursor-pointer hidden sm:inline-flex"
              title="Print Document Record"
            >
              <Printer className="w-4 h-4" />
            </button>

            {onDelete && (
              <button
                type="button"
                onClick={handleDelete}
                className="p-2 rounded-[10px] bg-surface-raised hover:bg-danger-soft/50 hover:text-danger text-secondary transition-colors cursor-pointer"
                title="Delete Document"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            )}

            <button
              type="button"
              onClick={onClose}
              className="p-2 rounded-[10px] bg-surface-raised hover:bg-surface-selected text-secondary hover:text-primary transition-colors cursor-pointer"
              title="Close modal"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Compliance Status Ribbon */}
        <div className="px-5 py-2.5 bg-canvas/40 border-b border-border-subtle flex flex-wrap items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-2">
            <span className="text-secondary font-mono">Status:</span>
            {compliance && (
              <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border ${compliance.badgeClass}`}>
                {compliance.label}
              </span>
            )}
          </div>

          <div className="flex items-center gap-4 text-secondary text-xs font-mono">
            {doc.issueDate && (
              <span className="flex items-center gap-1">
                <Calendar className="w-3.5 h-3.5 text-secondary" />
                Issued: {doc.issueDate}
              </span>
            )}
            {doc.expiryDate && (
              <span className="flex items-center gap-1">
                <Clock className="w-3.5 h-3.5 text-secondary" />
                Expires: {doc.expiryDate}
              </span>
            )}
            {doc.fileSize && <span>Size: {doc.fileSize}</span>}
          </div>
        </div>

        {/* Review Action Banner */}
        {doc.extractionStatus === 'rejected' && (
          <div className="px-5 py-2.5 bg-danger/10 border-b border-danger/20 flex items-center justify-between gap-3 text-xs text-danger">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span className="font-semibold">Document Rejected</span>
              <span className="text-secondary">— This document was rejected during review and is not relied upon for compliance.</span>
            </div>
            {canReview && onReviewAction && (
              <button
                type="button"
                disabled={isReviewing}
                onClick={() => void handleReview('approve')}
                className="inline-flex min-h-8 items-center gap-1.5 px-3 py-1 rounded-[8px] bg-action hover:bg-action-hover text-on-action font-semibold transition-colors cursor-pointer disabled:opacity-50"
              >
                <Check className="w-3.5 h-3.5" />
                <span>Re-approve</span>
              </button>
            )}
          </div>
        )}

        {doc.extractionStatus === 'approved' && (
          <div className="px-5 py-2 bg-positive/10 border-b border-positive/20 flex items-center justify-between gap-3 text-xs text-positive">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 shrink-0" />
              <span className="font-semibold">Review Approved</span>
              <span className="text-secondary">— Verified and approved for contractor compliance records.</span>
            </div>
            {canReview && onReviewAction && (
              <button
                type="button"
                disabled={isReviewing}
                onClick={() => void handleReview('reject')}
                className="inline-flex min-h-8 items-center gap-1.5 px-2.5 py-0.5 rounded-[8px] border border-border-strong bg-surface hover:bg-danger-soft/50 text-danger text-xs font-semibold transition-colors cursor-pointer disabled:opacity-50"
              >
                <X className="w-3 h-3" />
                <span>Revoke Approval</span>
              </button>
            )}
          </div>
        )}

        {canReview && onReviewAction && doc.extractionStatus !== 'approved' && doc.extractionStatus !== 'rejected' && (
          <div className="px-5 py-2.5 bg-warning/10 border-b border-warning/20 flex flex-wrap items-center justify-between gap-3 text-xs">
            <div className="flex items-center gap-2 text-warning">
              <ShieldAlert className="w-4 h-4 shrink-0" />
              <span className="font-semibold text-primary">Pending Review</span>
              <span className="text-secondary">— Contractor upload requires review before relying on it for compliance.</span>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                disabled={isReviewing}
                onClick={() => void handleReview('approve')}
                className="inline-flex min-h-8 items-center gap-1.5 px-3 py-1 rounded-[8px] bg-action hover:bg-action-hover text-on-action font-semibold transition-colors cursor-pointer disabled:opacity-50"
              >
                <Check className="w-3.5 h-3.5" />
                <span>Approve Document</span>
              </button>
              <button
                type="button"
                disabled={isReviewing}
                onClick={() => void handleReview('reject')}
                className="inline-flex min-h-8 items-center gap-1.5 px-3 py-1 rounded-[8px] border border-border-strong bg-surface hover:bg-danger-soft/60 hover:text-danger text-secondary font-semibold transition-colors cursor-pointer disabled:opacity-50"
              >
                <X className="w-3.5 h-3.5" />
                <span>Reject</span>
              </button>
            </div>
          </div>
        )}

        {/* Body / Document Preview Surface */}
        <div className="p-6 overflow-y-auto flex-1 space-y-5 bg-canvas/90">
          {/* Note or reference box */}
          {doc.notes && (
            <div className="p-3 rounded-[10px] bg-surface border border-border-subtle text-xs text-secondary flex items-start gap-2.5">
              <ShieldCheck className="w-4 h-4 text-accent shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold text-primary block">Verification Note:</span>
                <p className="text-secondary leading-relaxed mt-0.5">{doc.notes}</p>
              </div>
            </div>
          )}

          {/* Visual Certificate / Document Sheet */}
          <div className="bg-surface border border-border-subtle rounded-[14px] p-6 sm:p-8 space-y-6 shadow-inner relative overflow-hidden">
            {/* Watermark */}
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-[90px] font-black text-muted/20 pointer-events-none select-none tracking-widest font-mono rotate-[-20deg]">
              HYDENLYNE
            </div>

            {/* Document Header */}
            <div className="flex items-start justify-between border-b border-border-subtle pb-4 relative z-10">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono uppercase px-2 py-0.5 bg-accent-soft text-accent border border-border-strong rounded-md font-bold">
                    {originalFileAvailable ? 'Original Contractor Document' : 'Compliance Record — No Original File'}
                  </span>
                  <span className="text-xs font-mono text-secondary">REF: {doc.id}</span>
                </div>
                <h3 className="text-lg font-bold text-primary mt-2">{doc.title}</h3>
                <p className="text-xs text-secondary font-mono mt-0.5">File: {doc.fileName}</p>
              </div>

              <div className="text-right">
                <div className="w-12 h-12 rounded-[10px] bg-surface-raised border border-border-strong flex items-center justify-center text-accent font-serif font-bold text-xl mx-auto mb-1">
                  H
                </div>
                <span className="text-xs font-mono text-secondary">Hydenlyne QA</span>
              </div>
            </div>

            {/* Document Details Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 relative z-10 text-xs">
              <div className="p-3 bg-canvas/60 rounded-[10px] border border-border-subtle/80 space-y-1">
                <span className="text-secondary font-mono text-xs block uppercase">Contractor / Holder</span>
                <span className="text-primary font-semibold text-sm block">{profile.name}</span>
                <span className="text-secondary text-xs block">{profile.title}</span>
              </div>

              <div className="p-3 bg-canvas/60 rounded-[10px] border border-border-subtle/80 space-y-1">
                <span className="text-secondary font-mono text-xs block uppercase">Accreditation Category</span>
                <span className="text-accent font-semibold text-sm block uppercase tracking-wide">
                  {doc.category.replace('_', ' ')}
                </span>
                <span className="text-secondary text-xs block">
                  {originalFileAvailable ? 'Original file available for review' : 'Metadata recorded; original file unavailable'}
                </span>
              </div>

              <div className="p-3 bg-canvas/60 rounded-[10px] border border-border-subtle/80 space-y-1">
                <span className="text-secondary font-mono text-xs block uppercase">Validity Timeline</span>
                <div className="flex items-center gap-2">
                  <span className="text-primary font-medium">Issued: {doc.issueDate || 'Current'}</span>
                  <span>→</span>
                  <span className="text-primary font-medium">Expiry: {doc.expiryDate || 'Permanent'}</span>
                </div>
              </div>

              <div className="p-3 bg-canvas/60 rounded-[10px] border border-border-subtle/80 space-y-1">
                <span className="text-secondary font-mono text-xs block uppercase">Audit Check</span>
                <div className={`flex items-center gap-1.5 font-semibold ${doc.isVerified ? 'text-positive' : 'text-warning'}`}>
                  {doc.isVerified ? <CheckCircle2 className="w-4 h-4 text-positive" /> : <AlertTriangle className="w-4 h-4 text-warning" />}
                  <span>{doc.isVerified ? 'Verified by Hydenlyne Compliance' : 'Pending Hydenlyne Compliance Review'}</span>
                </div>
              </div>
            </div>

            {/* Document Content Abstract / Preview */}
            <div className="p-4 bg-canvas/40 rounded-[10px] border border-border-subtle/60 text-xs text-secondary space-y-2 relative z-10 leading-relaxed font-light">
              <p>
                {originalFileAvailable
                  ? 'The original file is available for review. This record contains the associated registration and compliance metadata.'
                  : 'This compliance record contains registration metadata only. The original document file is not available in this workspace.'}
              </p>
              <p className="text-secondary text-xs">
                Uploaded on: {new Date(doc.uploadedAt).toLocaleDateString()}
                {originalFileAvailable ? ' • Original file attached to this record.' : ' • No original file attached.'}
              </p>
            </div>
          </div>

          {/* Extracted Content — what the pipeline actually recovered from
              this document, not just its metadata. */}
          {hasExtractedContent && (
            <div className="p-4 bg-canvas/40 rounded-[10px] border border-border-subtle/60 text-xs text-secondary space-y-3 relative z-10">
              <h4 className="text-xs font-semibold text-secondary uppercase tracking-wider font-mono flex items-center gap-1.5">
                <FileText className="w-3.5 h-3.5 text-secondary" />
                Extracted Content
              </h4>
              {extractedFullName && (
                <div>
                  <span className="text-muted text-xs uppercase block">Name on file</span>
                  <span className="text-primary font-medium">{extractedFullName}</span>
                </div>
              )}
              {extractedSummary && (
                <div>
                  <span className="text-muted text-xs uppercase block mb-1">Professional Summary</span>
                  <p className="text-secondary leading-relaxed whitespace-pre-line">{extractedSummary}</p>
                </div>
              )}
              {extractedPersonalInfo && Object.keys(extractedPersonalInfo).length > 0 && (
                <div>
                  <span className="text-muted text-xs uppercase block mb-1">Personal Information</span>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1">
                    {Object.entries(extractedPersonalInfo).map(([label, value]) => (
                      <div key={label} className="flex justify-between gap-2">
                        <span className="text-muted">{label.replace(/_/g, ' ')}</span>
                        <span className="text-primary text-right">{value}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {extractedCertifications.length > 0 && (
                <div>
                  <span className="text-muted text-xs uppercase block mb-1">Certifications Found</span>
                  <div className="flex flex-wrap gap-1.5">
                    {extractedCertifications.map((cert) => (
                      <span key={cert} className="px-2 py-0.5 rounded-lg bg-surface border border-border-subtle text-secondary">
                        {cert}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {extractedSkills.length > 0 && (
                <div>
                  <span className="text-muted text-xs uppercase block mb-1">Skills</span>
                  <div className="flex flex-wrap gap-1.5">
                    {extractedSkills.map((skill) => (
                      <span key={skill} className="px-2 py-0.5 rounded-lg bg-surface border border-border-subtle text-secondary">
                        {skill}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Raw extracted text — always available as a fallback/reference,
              regardless of whether structured fields were recovered. */}
          {doc.extractedText && (
            <div className="p-4 bg-canvas/40 rounded-[10px] border border-border-subtle/60 text-xs relative z-10">
              <button
                type="button"
                onClick={() => setShowRawText((v) => !v)}
                className="w-full flex items-center justify-between text-xs font-semibold text-secondary uppercase tracking-wider font-mono cursor-pointer"
              >
                <span className="flex items-center gap-1.5">
                  <FileText className="w-3.5 h-3.5 text-secondary" />
                  Raw Extracted Text
                </span>
                <span className="text-muted normal-case font-sans">{showRawText ? 'Hide' : 'Show'}</span>
              </button>
              {showRawText && (
                <pre className="mt-3 max-h-64 overflow-y-auto whitespace-pre-wrap text-secondary text-xs leading-relaxed font-mono bg-canvas/60 rounded-lg p-3 border border-border-subtle/60">
                  {doc.extractedText}
                </pre>
              )}
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="px-5 py-3.5 bg-canvas border-t border-border-subtle flex items-center justify-between text-xs">
          <span className="text-secondary font-mono">Doc ID: {doc.id}</span>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-[10px] bg-surface-raised hover:bg-surface-selected text-primary font-medium transition-colors cursor-pointer"
          >
            Close Preview
          </button>
        </div>
      </motion.div>
    </div>
  )}
</AnimatePresence>
{doc && (
  <ConfirmDialog
    open={isDeleteConfirmationOpen}
    title="Remove compliance record?"
    description={`This will remove “${doc.title}” from this contractor’s vault. The action cannot be undone from this screen.`}
    confirmLabel="Remove record"
    onConfirm={confirmDelete}
    onCancel={() => setIsDeleteConfirmationOpen(false)}
  />
)}
</>,
document.body
  );
};
