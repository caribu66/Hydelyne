import { FC, useState, useRef, FormEvent, DragEvent } from 'react';
import { createPortal } from 'react-dom';
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
    (
    <div
      className="ui-overlay-enter fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/80 backdrop-blur-md"
      onClick={onClose}
    >
      <div
        ref={dialogRef}
        className="ui-surface-enter bg-zinc-900 border border-zinc-700/80 rounded-2xl w-full max-w-xl overflow-hidden shadow-2xl flex flex-col max-h-[90vh]"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="document-upload-title"
        aria-describedby="document-upload-description"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-zinc-800 bg-zinc-950/60">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-blue-950/80 border border-blue-800 flex items-center justify-center text-blue-400">
              <UploadCloud className="w-5 h-5" />
            </div>
            <div>
            <h2 id="document-upload-title" className="text-base font-bold text-zinc-100">Upload Specialist Document</h2>
              <p id="document-upload-description" className="text-xs text-zinc-400">
                Adding compliance credential to <strong className="text-zinc-200">{profile.name}</strong>
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close document upload"
            className="p-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200 transition-colors cursor-pointer"
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
            className={`border-2 border-dashed rounded-xl p-5 text-center cursor-pointer transition-all ${
              isDragging
                ? 'border-blue-500 bg-blue-950/30'
                : file
                ? 'border-emerald-700/80 bg-emerald-950/20'
                : 'border-zinc-700 hover:border-zinc-500 bg-zinc-950/40'
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
                <File className="w-8 h-8 text-emerald-400 shrink-0" />
                <div className="text-left">
                  <p className="text-sm font-semibold text-emerald-300 truncate max-w-xs">{file.name}</p>
                  <p className="text-xs text-zinc-400 font-mono">{formatFileSize(file.size)} • Click to replace</p>
                </div>
              </div>
            ) : (
              <div className="space-y-1.5">
                <UploadCloud className="w-7 h-7 text-zinc-400 mx-auto" />
                <p className="text-xs font-semibold text-zinc-200">
                  Drag and drop certificate / CV file here, or <span className="text-blue-400 underline">browse</span>
                </p>
                <p className="text-[11px] text-zinc-400">Supports PDF, Word (.docx), Scanned Certificates, PNG, JPEG</p>
              </div>
            )}
          </label>

          {/* Document Title */}
          <div>
            <label className="block text-xs font-semibold text-zinc-300 mb-1">
              Document Title <span className="text-rose-400">*</span>
            </label>
            <input
              type="text"
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. OPITO BOSIET with CA-EBS (Aberdeen)"
              className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3.5 py-2 text-xs text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:border-blue-500"
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
                className={`px-3 py-2 rounded-xl text-xs font-medium border text-left transition-colors cursor-pointer ${
                  category === cat.value
                    ? 'bg-blue-950/90 border-blue-600 text-blue-200 font-semibold shadow-xs'
                    : 'bg-zinc-950/60 border-zinc-800 text-zinc-400 hover:text-zinc-200'
                }`}
              >
                {cat.label}
              </button>
            ))}
          </div>

          {/* Issue Date & Expiry Date */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
            <div>
              <label className="block text-xs font-semibold text-zinc-300 mb-1">Issue Date</label>
              <input
                type="date"
                value={issueDate}
                onChange={(e) => setIssueDate(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:border-blue-500"
              />
            </div>

            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="text-xs font-semibold text-zinc-300">Expiry Date</label>
                <button
                  type="button"
                  onClick={() => setHasExpiry(!hasExpiry)}
                  className="text-[11px] text-blue-400 hover:underline"
                >
                  {hasExpiry ? 'Set as Permanent' : 'Has Expiry Date'}
                </button>
              </div>

              {hasExpiry ? (
                <input
                  type="date"
                  value={expiryDate}
                  onChange={(e) => setExpiryDate(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:border-blue-500"
                />
              ) : (
                <div className="px-3 py-2 rounded-xl bg-zinc-950 border border-zinc-800 text-xs text-zinc-400 font-mono">
                  Permanent / No Expiration
                </div>
              )}
            </div>
          </div>

          {/* Notes / Reference Number */}
          <div>
            <label className="block text-xs font-semibold text-zinc-300 mb-1">
              Certificate Ref # or Verification Notes
            </label>
            <textarea
              rows={2}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="e.g. OPITO Ref: #92841, OEUK Doctor Ref: Dr. Henderson Aberdeen Clinic"
              className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3.5 py-2 text-xs text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:border-blue-500"
            />
          </div>

          {/* Footer Submit */}
          <div className="pt-2 flex items-center justify-end gap-2.5">
            {uploadError && (
              <span className="text-[11px] text-rose-400 font-medium mr-auto flex items-center gap-1">
                <AlertCircle className="w-3.5 h-3.5" />
                {uploadError}
              </span>
            )}
            <button
              type="button"
              onClick={onClose}
              disabled={isUploading}
              className="px-4 py-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs font-medium transition-colors cursor-pointer disabled:opacity-50"
            >
              Cancel
            </button>

            <button
              type="submit"
              disabled={isUploading}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:opacity-60 text-white text-xs font-semibold transition-colors cursor-pointer shadow-md"
            >
              <CheckCircle2 className={`w-3.5 h-3.5 ${isUploading ? 'animate-pulse' : ''}`} />
              <span>{isUploading ? 'Uploading…' : 'Save to Compliance Vault'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
    ),
    document.body
  );
};
