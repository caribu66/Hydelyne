import { FC, useState, useRef, FormEvent, DragEvent } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'motion/react';
import { UserProfile, DocumentCategory } from '../types';
import {
  X,
  UploadCloud,
  CheckCircle2,
  AlertCircle,
  File,
} from 'lucide-react';
import { uploadDocument, getDocumentStatus, feCategoryToBE } from '../lib/documentsApi';
import { useAccessibleDialog } from '../hooks/useAccessibleDialog';

interface DocumentUploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  profile: UserProfile;
  onAddDocument: () => void;
  onShowToast: (msg: string) => void;
}

export const DocumentUploadModal: FC<DocumentUploadModalProps> = ({
  isOpen,
  onClose,
  profile,
  onAddDocument,
  onShowToast,
}) => {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState('');
  const [category, setCategory] = useState<DocumentCategory>('certificate');
  const [issueDate, setIssueDate] = useState(new Date().toISOString().split('T')[0]);
  const [hasExpiry, setHasExpiry] = useState(true);
  const [expiryDate, setExpiryDate] = useState(
    new Date(Date.now() + 1000 * 60 * 60 * 24 * 365 * 2).toISOString().split('T')[0]
  );
  const [notes, setNotes] = useState('');
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  useAccessibleDialog(isOpen, dialogRef, onClose);

  if (!isOpen) return null;

  const handleFileSelection = (selectedFile: File) => {
    setFile(selectedFile);
    if (!title) {
      const cleanName = selectedFile.name.replace(/\.[^/.]+$/, '').replace(/[-_]/g, ' ');
      setTitle(cleanName.charAt(0).toUpperCase() + cleanName.slice(1));
    }

    // Auto guess category based on name
    const lowerName = selectedFile.name.toLowerCase();
    if (lowerName.includes('cv') || lowerName.includes('resume')) {
      setCategory('cv');
      setHasExpiry(false);
    } else if (lowerName.includes('med') || lowerName.includes('oeuk') || lowerName.includes('oguk') || lowerName.includes('eng1')) {
      setCategory('medical');
      setHasExpiry(true);
    } else if (lowerName.includes('seaman') || lowerName.includes('discharge') || lowerName.includes('stcw')) {
      setCategory('seamans_book');
      setHasExpiry(true);
    } else if (lowerName.includes('report') || lowerName.includes('survey') || lowerName.includes('qc')) {
      setCategory('survey_report');
      setHasExpiry(false);
    } else {
      setCategory('certificate');
      setHasExpiry(true);
    }

  };

  const handleDragOver = (e: DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelection(e.dataTransfer.files[0]);
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      setUploadError('Enter a document title before saving.');
      return;
    }

    // Documents are server-owned. A metadata-only local document would be
    // invisible to other users and must not be created.
    if (!file) {
      setUploadError('Choose a file to upload.');
      return;
    }

    {
      setIsUploading(true);
      setUploadError(null);
      try {
        const beClassification = feCategoryToBE(category);
        const res = await uploadDocument(profile.id, file, beClassification);
        onAddDocument();
        onShowToast(`Uploaded to server (ID ${res.id.slice(0, 8)}…) — processing ${res.status}`);
        // Refresh status after a short delay to reflect extraction result
        setTimeout(async () => {
          try {
            const status = await getDocumentStatus(res.id);
            if (status.extraction_status === 'failed') {
              onShowToast('Server extraction failed — review required');
            } else if (status.extraction_status === 'needs_review') {
              onShowToast('Server extraction completed — needs review');
            }
          } catch {
            /* ignore status polling errors */
          }
        }, 4000);
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Upload to server failed';
        setUploadError(msg);
        onShowToast(msg);
        return;
      } finally {
        setIsUploading(false);
      }
    }

    onClose();
  };

  return createPortal(
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 overflow-y-auto">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 bg-canvas/80 backdrop-blur-xs"
            onClick={onClose}
          />
          <motion.div
            ref={dialogRef}
            initial={{ opacity: 0, scale: 0.96, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 8 }}
            transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
            className="relative z-10 bg-surface border border-border-strong/80 rounded-[14px] w-full max-w-xl overflow-hidden shadow-2xl flex flex-col max-h-[90vh] my-auto"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-labelledby="document-upload-title"
            aria-describedby="document-upload-description"
          >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border-subtle bg-canvas/60">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-[10px] bg-accent-soft/80 border border-border-strong flex items-center justify-center text-accent">
              <UploadCloud className="w-5 h-5" />
            </div>
            <div>
            <h2 id="document-upload-title" className="text-base font-bold text-primary">Upload Contractor Document</h2>
              <p id="document-upload-description" className="text-xs text-secondary">
                Adding compliance credential to <strong className="text-primary">{profile.name}</strong>
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close document upload"
            className="p-2 rounded-[10px] bg-surface-raised hover:bg-surface-selected text-secondary hover:text-primary transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-5 overflow-y-auto space-y-4 flex-1">
          {/* Drag & Drop Box */}
          <label
            htmlFor="document-file-input"
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            className={`border-2 border-dashed rounded-[10px] p-5 text-center cursor-pointer transition-all ${
              isDragging
                ? 'border-border-strong bg-accent-soft/30'
                : file
                ? 'border-positive-border/80 bg-positive-soft/20'
                : 'border-border-strong hover:border-border-strong bg-canvas/40'
            }`}
          >
            <input
              ref={fileInputRef}
              id="document-file-input"
              type="file"
              accept=".pdf,.doc,.docx,.png,.jpg,.jpeg,.zip"
              className="hidden"
              onChange={(e) => {
                if (e.target.files && e.target.files[0]) {
                  handleFileSelection(e.target.files[0]);
                }
              }}
            />

            {file ? (
              <div className="flex items-center justify-center gap-3">
                <File className="w-8 h-8 text-positive shrink-0" />
                <div className="text-left">
                  <p className="text-sm font-semibold text-positive truncate max-w-xs">{file.name}</p>
                  <p className="text-xs text-secondary font-mono">{formatFileSize(file.size)} • Click to replace</p>
                </div>
              </div>
            ) : (
              <div className="space-y-1.5">
                <UploadCloud className="w-7 h-7 text-secondary mx-auto" />
                <p className="text-xs font-semibold text-primary">
                  Drag and drop certificate / CV file here, or <span className="text-accent underline">browse</span>
                </p>
                <p className="text-xs text-secondary">Supports PDF, Word (.docx), Scanned Certificates, PNG, JPEG</p>
              </div>
            )}
          </label>

          {/* Document Title */}
          <div>
            <label className="block text-xs font-semibold text-secondary mb-1">
              Document Title <span className="text-danger">*</span>
            </label>
            <input
              type="text"
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. OPITO BOSIET with CA-EBS (Aberdeen)"
              className="w-full bg-canvas border border-border-subtle rounded-[10px] px-3.5 py-2 text-xs text-primary placeholder:text-muted focus:outline-none focus:border-border-strong"
            />
          </div>

          {/* Category Selection */}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {[
              { value: 'certificate', label: 'Safety / Cert' },
              { value: 'medical', label: 'Medical (OEUK/ENG1)' },
              { value: 'cv', label: 'CV & Track Record' },
              { value: 'seamans_book', label: "Seaman's Book" },
              { value: 'survey_report', label: 'Survey / QC Report' },
              { value: 'other', label: 'Other Document' },
            ].map((cat) => (
              <button
                type="button"
                key={cat.value}
                onClick={() => setCategory(cat.value as DocumentCategory)}
                className={`px-3 py-2 rounded-[10px] text-xs font-medium border text-left transition-colors cursor-pointer ${
                  category === cat.value
                    ? 'bg-accent-soft/90 border-border-strong text-accent font-semibold shadow-xs'
                    : 'bg-canvas/60 border-border-subtle text-secondary hover:text-primary'
                }`}
              >
                {cat.label}
              </button>
            ))}
          </div>

          {/* Issue Date & Expiry Date */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
            <div>
              <label className="block text-xs font-semibold text-secondary mb-1">Issue Date</label>
              <input
                type="date"
                value={issueDate}
                onChange={(e) => setIssueDate(e.target.value)}
                className="w-full bg-canvas border border-border-subtle rounded-[10px] px-3 py-2 text-xs text-primary focus:outline-none focus:border-border-strong"
              />
            </div>

            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="text-xs font-semibold text-secondary">Expiry Date</label>
                <button
                  type="button"
                  onClick={() => setHasExpiry(!hasExpiry)}
                  className="text-xs text-accent hover:underline"
                >
                  {hasExpiry ? 'Set as Permanent' : 'Has Expiry Date'}
                </button>
              </div>

              {hasExpiry ? (
                <input
                  type="date"
                  value={expiryDate}
                  onChange={(e) => setExpiryDate(e.target.value)}
                  className="w-full bg-canvas border border-border-subtle rounded-[10px] px-3 py-2 text-xs text-primary focus:outline-none focus:border-border-strong"
                />
              ) : (
                <div className="px-3 py-2 rounded-[10px] bg-canvas border border-border-subtle text-xs text-secondary font-mono">
                  Permanent / No Expiration
                </div>
              )}
            </div>
          </div>

          {/* Notes / Reference Number */}
          <div>
            <label className="block text-xs font-semibold text-secondary mb-1">
              Certificate Ref # or Verification Notes
            </label>
            <textarea
              rows={2}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="e.g. OPITO Ref: #92841, OEUK Doctor Ref: Dr. Henderson Aberdeen Clinic"
              className="w-full bg-canvas border border-border-subtle rounded-[10px] px-3.5 py-2 text-xs text-primary placeholder:text-muted focus:outline-none focus:border-border-strong"
            />
          </div>

          {/* Footer Submit */}
          <div className="pt-2 flex items-center justify-end gap-2.5">
            {uploadError && (
              <span className="text-xs text-danger font-medium mr-auto flex items-center gap-1">
                <AlertCircle className="w-3.5 h-3.5" />
                {uploadError}
              </span>
            )}
            <button
              type="button"
              onClick={onClose}
              disabled={isUploading}
              className="px-4 py-2 rounded-[10px] bg-surface-raised hover:bg-surface-selected text-secondary text-xs font-medium transition-colors cursor-pointer disabled:opacity-50"
            >
              Cancel
            </button>

            <button
              type="submit"
              disabled={isUploading}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-[10px] bg-action hover:bg-action-hover disabled:opacity-60 text-on-action text-xs font-semibold transition-colors cursor-pointer shadow-md"
            >
              <CheckCircle2 className={`w-3.5 h-3.5 ${isUploading ? 'animate-pulse' : ''}`} />
              <span>{isUploading ? 'Uploading…' : 'Save to Compliance Vault'}</span>
            </button>
          </div>
        </form>
          </motion.div>
        </div>
      )}
    </AnimatePresence>,
    document.body
  );
};
