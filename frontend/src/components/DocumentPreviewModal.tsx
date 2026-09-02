import { FC, useState, useRef } from 'react';
import { createPortal } from 'react-dom';
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
} from 'lucide-react';

interface DocumentPreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  document: SpecialistDocument | null;
  profile: UserProfile;
  onDelete?: (docId: string) => void | Promise<void>;
  onShowToast?: (msg: string) => void;
}

export const DocumentPreviewModal: FC<DocumentPreviewModalProps> = ({
  isOpen,
  onClose,
  document: doc,
  profile,
  onDelete,
  onShowToast,
}) => {
  const [isDeleteConfirmationOpen, setIsDeleteConfirmationOpen] = useState(false);
  const [showRawText, setShowRawText] = useState(false);
  const dialogRef = useRef<HTMLDivElement>(null);
  useAccessibleDialog(isOpen && Boolean(doc), dialogRef, onClose);

  if (!isOpen || !doc) return null;

  const compliance = getDocumentComplianceStatus(doc);
  const originalFileAvailable = hasOriginalDocumentFile(doc);

  const extractedData = doc.extractedData;
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
    (
    <>
    <div
      className="ui-overlay-enter fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/80 backdrop-blur-md"
      onClick={onClose}
    >
      <div
        ref={dialogRef}
        className="ui-surface-enter bg-zinc-900 border border-zinc-700/80 rounded-2xl w-full max-w-3xl overflow-hidden shadow-2xl flex flex-col max-h-[90vh]"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="document-preview-title"
        aria-describedby="document-preview-description"
      >
        {/* Header */}
        <div className="sticky top-0 z-10 flex items-center justify-between px-5 py-4 border-b border-zinc-800 bg-zinc-950/95 backdrop-blur-sm">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-10 h-10 rounded-xl bg-blue-950/80 border border-blue-800/80 flex items-center justify-center text-blue-400 shrink-0">
              <FileCheck className="w-5 h-5 text-blue-400" />
            </div>
            <div className="min-w-0">
              <h2 id="document-preview-title" className="text-base font-bold text-zinc-100 truncate">{doc.title}</h2>
              <p id="document-preview-description" className="text-xs text-zinc-400 truncate">
                {profile.name} • {profile.department}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleDownload}
              disabled={!originalFileAvailable}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold transition-colors cursor-pointer disabled:cursor-not-allowed disabled:bg-zinc-800 disabled:text-zinc-500"
              title={originalFileAvailable ? 'Download original file' : 'Original file unavailable'}
            >
              <Download className="w-3.5 h-3.5" />
              <span>{originalFileAvailable ? 'Download Original' : 'Original Unavailable'}</span>
            </button>

            <button
              type="button"
              onClick={handlePrint}
              className="p-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-300 transition-colors cursor-pointer hidden sm:inline-flex"
              title="Print Document Record"
            >
              <Printer className="w-4 h-4" />
            </button>

            {onDelete && (
              <button
                type="button"
                onClick={handleDelete}
                className="p-2 rounded-xl bg-zinc-800 hover:bg-rose-900/50 hover:text-rose-400 text-zinc-400 transition-colors cursor-pointer"
                title="Delete Document"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            )}

            <button
              type="button"
              onClick={onClose}
              className="p-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200 transition-colors cursor-pointer"
              title="Close modal"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Compliance Status Ribbon */}
        <div className="px-5 py-2.5 bg-zinc-950/40 border-b border-zinc-800 flex flex-wrap items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-2">
            <span className="text-zinc-400 font-mono">Status:</span>
            <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border ${compliance.badgeClass}`}>
              {compliance.label}
            </span>
          </div>

          <div className="flex items-center gap-4 text-zinc-400 text-[11px] font-mono">
            {doc.issueDate && (
              <span className="flex items-center gap-1">
                <Calendar className="w-3.5 h-3.5 text-zinc-400" />
                Issued: {doc.issueDate}
              </span>
            )}
            {doc.expiryDate && (
              <span className="flex items-center gap-1">
                <Clock className="w-3.5 h-3.5 text-zinc-400" />
                Expires: {doc.expiryDate}
              </span>
            )}
            {doc.fileSize && <span>Size: {doc.fileSize}</span>}
          </div>
        </div>

        {/* Body / Document Preview Surface */}
        <div className="p-6 overflow-y-auto flex-1 space-y-5 bg-zinc-950/90">
          {/* Note or reference box */}
          {doc.notes && (
            <div className="p-3 rounded-xl bg-zinc-900 border border-zinc-800 text-xs text-zinc-300 flex items-start gap-2.5">
              <ShieldCheck className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold text-zinc-200 block">Verification Note:</span>
                <p className="text-zinc-400 leading-relaxed mt-0.5">{doc.notes}</p>
              </div>
            </div>
          )}

          {/* Visual Certificate / Document Sheet */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 sm:p-8 space-y-6 shadow-inner relative overflow-hidden">
            {/* Watermark */}
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-[90px] font-black text-zinc-800/20 pointer-events-none select-none tracking-widest font-mono rotate-[-20deg]">
              HYDENLYNE
            </div>

            {/* Document Header */}
            <div className="flex items-start justify-between border-b border-zinc-800 pb-4 relative z-10">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-mono uppercase px-2 py-0.5 bg-blue-950 text-blue-300 border border-blue-800 rounded-md font-bold">
                    {originalFileAvailable ? 'Original Specialist Document' : 'Compliance Record — No Original File'}
                  </span>
                  <span className="text-[10px] font-mono text-zinc-400">REF: {doc.id}</span>
                </div>
                <h3 className="text-lg font-bold text-zinc-100 mt-2">{doc.title}</h3>
                <p className="text-xs text-zinc-400 font-mono mt-0.5">File: {doc.fileName}</p>
              </div>

              <div className="text-right">
                <div className="w-12 h-12 rounded-xl bg-zinc-800 border border-zinc-700 flex items-center justify-center text-blue-400 font-serif font-bold text-xl mx-auto mb-1">
                  H
                </div>
                <span className="text-[10px] font-mono text-zinc-400">Hydenlyne QA</span>
              </div>
            </div>

            {/* Document Details Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 relative z-10 text-xs">
              <div className="p-3 bg-zinc-950/60 rounded-xl border border-zinc-800/80 space-y-1">
                <span className="text-zinc-400 font-mono text-[10px] block uppercase">Specialist / Holder</span>
                <span className="text-zinc-100 font-semibold text-sm block">{profile.name}</span>
                <span className="text-zinc-400 text-xs block">{profile.title}</span>
              </div>

              <div className="p-3 bg-zinc-950/60 rounded-xl border border-zinc-800/80 space-y-1">
                <span className="text-zinc-400 font-mono text-[10px] block uppercase">Accreditation Category</span>
                <span className="text-blue-400 font-semibold text-sm block uppercase tracking-wide">
                  {doc.category.replace('_', ' ')}
                </span>
                <span className="text-zinc-400 text-xs block">
                  {originalFileAvailable ? 'Original file available for review' : 'Metadata recorded; original file unavailable'}
                </span>
              </div>

              <div className="p-3 bg-zinc-950/60 rounded-xl border border-zinc-800/80 space-y-1">
                <span className="text-zinc-400 font-mono text-[10px] block uppercase">Validity Timeline</span>
                <div className="flex items-center gap-2">
                  <span className="text-zinc-200 font-medium">Issued: {doc.issueDate || 'Current'}</span>
                  <span>→</span>
                  <span className="text-zinc-200 font-medium">Expiry: {doc.expiryDate || 'Permanent'}</span>
                </div>
              </div>

              <div className="p-3 bg-zinc-950/60 rounded-xl border border-zinc-800/80 space-y-1">
                <span className="text-zinc-400 font-mono text-[10px] block uppercase">Audit Check</span>
                <div className={`flex items-center gap-1.5 font-semibold ${doc.isVerified ? 'text-emerald-400' : 'text-amber-400'}`}>
                  {doc.isVerified ? <CheckCircle2 className="w-4 h-4 text-emerald-400" /> : <AlertTriangle className="w-4 h-4 text-amber-400" />}
                  <span>{doc.isVerified ? 'Verified by Hydenlyne Compliance' : 'Pending Hydenlyne Compliance Review'}</span>
                </div>
              </div>
            </div>

            {/* Document Content Abstract / Preview */}
            <div className="p-4 bg-zinc-950/40 rounded-xl border border-zinc-800/60 text-xs text-zinc-300 space-y-2 relative z-10 leading-relaxed font-light">
              <p>
                {originalFileAvailable
                  ? 'The original file is available for review. This record contains the associated registration and compliance metadata.'
                  : 'This compliance record contains registration metadata only. The original document file is not available in this workspace.'}
              </p>
              <p className="text-zinc-400 text-[11px]">
                Uploaded on: {new Date(doc.uploadedAt).toLocaleDateString()}
                {originalFileAvailable ? ' • Original file attached to this record.' : ' • No original file attached.'}
              </p>
            </div>
          </div>

          {/* Extracted Content — what the pipeline actually recovered from
              this document, not just its metadata. */}
          {hasExtractedContent && (
            <div className="p-4 bg-zinc-950/40 rounded-xl border border-zinc-800/60 text-xs text-zinc-300 space-y-3 relative z-10">
              <h4 className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider font-mono flex items-center gap-1.5">
                <FileText className="w-3.5 h-3.5 text-zinc-400" />
                Extracted Content
              </h4>
              {extractedFullName && (
                <div>
                  <span className="text-zinc-500 text-[10px] uppercase block">Name on file</span>
                  <span className="text-zinc-200 font-medium">{extractedFullName}</span>
                </div>
              )}
              {extractedSummary && (
                <div>
                  <span className="text-zinc-500 text-[10px] uppercase block mb-1">Professional Summary</span>
                  <p className="text-zinc-300 leading-relaxed whitespace-pre-line">{extractedSummary}</p>
                </div>
              )}
              {extractedPersonalInfo && Object.keys(extractedPersonalInfo).length > 0 && (
                <div>
                  <span className="text-zinc-500 text-[10px] uppercase block mb-1">Personal Information</span>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1">
                    {Object.entries(extractedPersonalInfo).map(([label, value]) => (
                      <div key={label} className="flex justify-between gap-2">
                        <span className="text-zinc-500">{label.replace(/_/g, ' ')}</span>
                        <span className="text-zinc-200 text-right">{value}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {extractedCertifications.length > 0 && (
                <div>
                  <span className="text-zinc-500 text-[10px] uppercase block mb-1">Certifications Found</span>
                  <div className="flex flex-wrap gap-1.5">
                    {extractedCertifications.map((cert) => (
                      <span key={cert} className="px-2 py-0.5 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-300">
                        {cert}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {extractedSkills.length > 0 && (
                <div>
                  <span className="text-zinc-500 text-[10px] uppercase block mb-1">Skills</span>
                  <div className="flex flex-wrap gap-1.5">
                    {extractedSkills.map((skill) => (
                      <span key={skill} className="px-2 py-0.5 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-300">
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
            <div className="p-4 bg-zinc-950/40 rounded-xl border border-zinc-800/60 text-xs relative z-10">
              <button
                type="button"
                onClick={() => setShowRawText((v) => !v)}
                className="w-full flex items-center justify-between text-[11px] font-semibold text-zinc-400 uppercase tracking-wider font-mono cursor-pointer"
              >
                <span className="flex items-center gap-1.5">
                  <FileText className="w-3.5 h-3.5 text-zinc-400" />
                  Raw Extracted Text
                </span>
                <span className="text-zinc-500 normal-case font-sans">{showRawText ? 'Hide' : 'Show'}</span>
              </button>
              {showRawText && (
                <pre className="mt-3 max-h-64 overflow-y-auto whitespace-pre-wrap text-zinc-300 text-[11px] leading-relaxed font-mono bg-zinc-950/60 rounded-lg p-3 border border-zinc-800/60">
                  {doc.extractedText}
                </pre>
              )}
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="px-5 py-3.5 bg-zinc-950 border-t border-zinc-800 flex items-center justify-between text-xs">
          <span className="text-zinc-400 font-mono">Doc ID: {doc.id}</span>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-200 font-medium transition-colors cursor-pointer"
          >
            Close Preview
          </button>
        </div>
      </div>
    </div>
    <ConfirmDialog
      open={isDeleteConfirmationOpen}
      title="Remove compliance record?"
      description={`This will remove “${doc.title}” from this specialist’s vault. The action cannot be undone from this screen.`}
      confirmLabel="Remove record"
      onConfirm={confirmDelete}
      onCancel={() => setIsDeleteConfirmationOpen(false)}
    />
    </>
    ),
    document.body
  );
};
