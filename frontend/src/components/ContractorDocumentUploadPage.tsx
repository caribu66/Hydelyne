import { ChangeEvent, DragEvent, FormEvent, useEffect, useId, useMemo, useRef, useState } from 'react'
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  Clock,
  FileText,
  FileUp,
  Loader2,
  Lock,
  Moon,
  RefreshCw,
  ShieldCheck,
  Sun,
  UploadCloud,
  X,
} from 'lucide-react'
import { publicDocumentRequest, uploadRequestedDocument } from '../lib/documentsApi'
import { HydenlyneAnimatedLogo } from './HydenlyneAnimatedLogo'
import { useTheme } from '../hooks/useTheme'
import { formatExpiryTime } from './contractorDocumentUtils'

interface ContractorDocumentUploadPageProps {
  token: string
}

type PageState = 'loading' | 'ready' | 'invalid' | 'uploading' | 'complete'

type DocumentClassification = 'cert' | 'medical' | 'seamans_book' | 'identity' | 'other'

interface CategoryOption {
  id: DocumentClassification
  label: string
  description: string
}

const CATEGORIES: CategoryOption[] = [
  { id: 'cert', label: 'Certificates & Accreditations', description: 'BOSIET, FOET, OPITO, technical or survey certificates' },
  { id: 'medical', label: 'Medical Fitness', description: 'ENG1, OGUK, OEUK, or offshore medical certificates' },
  { id: 'seamans_book', label: "Seaman's Book / STCW", description: "Discharge book, basic safety, STCW tickets" },
  { id: 'identity', label: 'Passport & Identity', description: 'Passport bio page, national ID, or work visa' },
  { id: 'other', label: 'Other Compliance Evidence', description: 'Safety induction, insurance, or project evidence' },
]

const MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024 // 50MB
const ALLOWED_EXTENSIONS = ['.pdf', '.docx', '.jpg', '.jpeg', '.png']

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function ContractorDocumentUploadPage({ token }: ContractorDocumentUploadPageProps) {
  const { theme, toggleTheme } = useTheme()
  const [state, setState] = useState<PageState>('loading')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [expiresAt, setExpiresAt] = useState<string | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [fileValidationError, setFileValidationError] = useState<string | null>(null)
  const [category, setCategory] = useState<DocumentClassification>('cert')
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [idempotencyKey, setIdempotencyKey] = useState(() => crypto.randomUUID())

  const fileInputRef = useRef<HTMLInputElement>(null)
  const uploadEpochRef = useRef(0)
  const fileInputId = useId()

  useEffect(() => {
    uploadEpochRef.current += 1
    let active = true
    setState('loading')
    setErrorMessage(null)
    setExpiresAt(null)
    setFile(null)
    setFileValidationError(null)
    setUploadedFileName(null)
    setIsDragging(false)
    setIdempotencyKey(crypto.randomUUID())
    if (fileInputRef.current) fileInputRef.current.value = ''
    publicDocumentRequest(token)
      .then((data) => {
        if (active) {
          setExpiresAt(data.expires_at)
          setState('ready')
        }
      })
      .catch((err: unknown) => {
        if (active) {
          setState('invalid')
          setErrorMessage(err instanceof Error ? err.message : 'This upload link is invalid or has expired.')
        }
      })
    return () => {
      active = false
    }
  }, [token])

  const validateAndSetFile = (candidate: File | null) => {
    setFileValidationError(null)
    if (!candidate) {
      setFile(null)
      return
    }

    const isDifferentFile = !file
      || file.name !== candidate.name
      || file.size !== candidate.size
      || file.lastModified !== candidate.lastModified
    if (isDifferentFile) {
      setIdempotencyKey(crypto.randomUUID())
    }

    const lowerName = candidate.name.toLowerCase()
    const hasValidExt = ALLOWED_EXTENSIONS.some((ext) => lowerName.endsWith(ext))
    if (!hasValidExt) {
      setFileValidationError('Unsupported format. Please select a PDF, Word document (.docx), or image (.jpg, .png).')
      setFile(null)
      return
    }

    if (candidate.size > MAX_FILE_SIZE_BYTES) {
      setFileValidationError(`File is too large (${formatFileSize(candidate.size)}). Maximum permitted file size is 50MB.`)
      setFile(null)
      return
    }

    // Auto-suggest category based on file name if user hasn't changed it
    if (lowerName.includes('med') || lowerName.includes('eng1') || lowerName.includes('oguk') || lowerName.includes('oeuk')) {
      setCategory('medical')
    } else if (lowerName.includes('seaman') || lowerName.includes('discharge') || lowerName.includes('stcw')) {
      setCategory('seamans_book')
    } else if (lowerName.includes('pass') || lowerName.includes('id') || lowerName.includes('visa')) {
      setCategory('identity')
    }

    setFile(candidate)
  }

  const onFileInputChange = (event: ChangeEvent<HTMLInputElement>) => {
    validateAndSetFile(event.target.files?.[0] ?? null)
  }

  const onDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(true)
  }

  const onDragLeave = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)
  }

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      validateAndSetFile(e.dataTransfer.files[0] ?? null)
    }
  }

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!file || state === 'uploading') return

    const requestEpoch = uploadEpochRef.current
    setState('uploading')
    setErrorMessage(null)

    try {
      await uploadRequestedDocument(token, file, idempotencyKey, category)
      if (requestEpoch !== uploadEpochRef.current) return
      setUploadedFileName(file.name)
      setState('complete')
    } catch (error) {
      if (requestEpoch !== uploadEpochRef.current) return
      setState('ready')
      setErrorMessage(error instanceof Error ? error.message : 'Could not upload that document. Please try again.')
    }
  }

  const handleUploadAnother = () => {
    setFile(null)
    setUploadedFileName(null)
    setFileValidationError(null)
    setErrorMessage(null)
    setIdempotencyKey(crypto.randomUUID())
    setState('ready')
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const expiryInfo = useMemo(() => {
    if (!expiresAt) return null
    return formatExpiryTime(expiresAt)
  }, [expiresAt])

  return (
    <div className="min-h-dvh bg-canvas text-primary font-sans flex flex-col justify-between selection:bg-surface-selected">
      {/* Top Header Navigation */}
      <header className="border-b border-border-subtle bg-surface/80 backdrop-blur-xs sticky top-0 z-20">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <HydenlyneAnimatedLogo />
          </div>

          <div className="flex items-center gap-2 sm:gap-3">
            {/* End-to-end encrypted pill */}
            <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-surface-raised border border-border-subtle text-xs text-secondary">
              <Lock aria-hidden="true" className="h-3.5 w-3.5 text-brand-pulse" />
              <span>256-Bit Encrypted</span>
            </div>

            {/* Theme Toggle Button */}
            <button
              type="button"
              onClick={toggleTheme}
              className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-border-subtle bg-surface-raised text-secondary hover:text-primary hover:bg-surface-selected focus-visible:ring-2 focus-visible:ring-focus transition-colors"
              aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
            >
              {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </button>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 flex items-center justify-center px-4 py-8 sm:py-12 sm:px-6">
        <div className="w-full max-w-xl">
          {/* Card Container */}
          <section
            className="rounded-[14px] border border-border-subtle bg-surface shadow-2xl overflow-hidden p-5 sm:p-8"
            aria-labelledby="document-upload-title"
          >
            {/* STATE: LOADING */}
            {state === 'loading' && (
              <div className="py-12 flex flex-col items-center justify-center text-center space-y-4">
                <div className="relative flex items-center justify-center">
                  <div className="h-12 w-12 rounded-full border-2 border-border-subtle border-t-brand-pulse animate-spin" />
                  <ShieldCheck className="h-6 w-6 text-brand-pulse absolute" />
                </div>
                <div>
                  <h2 className="text-base font-semibold text-primary">Verifying secure upload link</h2>
                  <p className="mt-1 text-xs text-secondary">Establishing encrypted session with Hydenlyne compliance servers…</p>
                </div>
              </div>
            )}

            {/* STATE: INVALID / EXPIRED */}
            {state === 'invalid' && (
              <div className="py-4 text-center space-y-5">
                <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-danger-soft border border-danger-border text-danger">
                  <AlertTriangle aria-hidden="true" className="h-7 w-7" />
                </div>
                <div className="space-y-2">
                  <h2 id="document-upload-title" className="text-lg font-semibold text-primary">
                    Upload Link Inactive or Expired
                  </h2>
                  <p className="text-sm text-secondary max-w-md mx-auto">
                    {errorMessage || 'This upload link is no longer valid or has expired for security.'}
                  </p>
                </div>

                <div className="rounded-lg bg-surface-raised border border-border-subtle p-4 text-left text-xs text-secondary space-y-2">
                  <p className="font-semibold text-primary">Why did this happen?</p>
                  <p>
                    Hydenlyne bearer links expire automatically after 14 days to protect sensitive maritime credentials and GDPR compliance.
                  </p>
                  <p className="pt-1">
                    To request a new secure link, please reach out directly to your Hydenlyne operational coordinator or contact our team at{' '}
                    <span className="font-mono text-primary font-medium">operations@hydenlyne.com</span>.
                  </p>
                </div>
              </div>
            )}

            {/* STATE: READY & UPLOADING */}
            {(state === 'ready' || state === 'uploading') && (
              <div>
                {/* Header Badge & Title */}
                <div className="flex items-start justify-between gap-4 pb-5 border-b border-border-subtle">
                  <div>
                    <div className="inline-flex items-center gap-1.5 rounded-full bg-surface-raised border border-border-subtle px-2.5 py-0.5 text-xs text-secondary mb-2">
                      <ShieldCheck className="h-3.5 w-3.5 text-brand-pulse" />
                      <span>Verified Document Request</span>
                    </div>
                    <h1 id="document-upload-title" className="text-xl font-semibold text-primary tracking-tight">
                      Secure Document Upload
                    </h1>
                    <p className="mt-1 text-xs sm:text-sm text-secondary">
                      Hydenlyne Operations has requested documentation to verify your crew certifications.
                    </p>
                  </div>

                  {expiryInfo && (
                    <div
                      className="hidden sm:flex flex-col items-end text-right shrink-0"
                      title={expiryInfo.full}
                    >
                      <div className="inline-flex items-center gap-1 text-xs text-muted font-mono">
                        <Clock className="h-3 w-3" />
                        <span>{expiryInfo.relative}</span>
                      </div>
                      <span className="text-xs text-muted">{expiryInfo.full}</span>
                    </div>
                  )}
                </div>

                {/* Optional Error Banner */}
                {errorMessage && (
                  <div
                    className="mt-4 flex items-center gap-2 rounded-lg border border-danger-border bg-danger-soft p-3 text-xs text-danger"
                    role="alert"
                  >
                    <AlertTriangle className="h-4 w-4 shrink-0" />
                    <span>{errorMessage}</span>
                  </div>
                )}

                <form className="mt-6 space-y-6" onSubmit={(e) => void onSubmit(e)}>
                  {/* Category Selection */}
                  <div>
                    <span className="block text-xs font-semibold text-primary uppercase tracking-wider mb-2">
                      Document Classification
                    </span>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      {CATEGORIES.map((item) => {
                        const isSelected = category === item.id
                        return (
                          <button
                            key={item.id}
                            type="button"
                            onClick={() => setCategory(item.id)}
                            disabled={state === 'uploading'}
                            className={`flex flex-col text-left p-3 rounded-lg border transition-all cursor-pointer focus-visible:ring-2 focus-visible:ring-focus ${
                              isSelected
                                ? 'border-brand-pulse bg-surface-raised shadow-xs'
                                : 'border-border-subtle bg-surface hover:bg-surface-raised hover:border-border-strong text-secondary'
                            }`}
                          >
                            <div className="flex items-center justify-between w-full">
                              <span className={`text-xs font-medium ${isSelected ? 'text-primary' : 'text-secondary'}`}>
                                {item.label}
                              </span>
                              {isSelected && <Check className="h-3.5 w-3.5 text-brand-pulse" />}
                            </div>
                            <span className="text-xs text-muted mt-0.5 line-clamp-1">
                              {item.description}
                            </span>
                          </button>
                        )
                      })}
                    </div>
                  </div>

                  {/* Drag & Drop File Zone */}
                  <div>
                    <span className="block text-xs font-semibold text-primary uppercase tracking-wider mb-2">
                      File Attachment
                    </span>

                    {/* Hidden Native File Input */}
                    <input
                      ref={fileInputRef}
                      id={fileInputId}
                      type="file"
                      accept=".pdf,.docx,.jpg,.jpeg,.png"
                      onChange={onFileInputChange}
                      disabled={state === 'uploading'}
                      className="sr-only"
                    />

                    {!file ? (
                      <div
                        onDragOver={onDragOver}
                        onDragLeave={onDragLeave}
                        onDrop={onDrop}
                        onClick={() => fileInputRef.current?.click()}
                        className={`group relative flex flex-col items-center justify-center rounded-[14px] border-2 border-dashed p-6 sm:p-8 text-center transition-all cursor-pointer focus-visible:ring-2 focus-visible:ring-focus ${
                          isDragging
                            ? 'border-brand-pulse bg-surface-raised scale-[1.01]'
                            : 'border-border-subtle hover:border-border-strong hover:bg-surface-raised/50 bg-canvas/60'
                        }`}
                        tabIndex={0}
                        role="button"
                        aria-label="Upload document file dropzone. Click or drag and drop to select a file."
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault()
                            fileInputRef.current?.click()
                          }
                        }}
                      >
                        <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-surface-raised border border-border-subtle text-brand-pulse group-hover:scale-105 transition-transform">
                          <UploadCloud className="h-6 w-6" />
                        </div>
                        <p className="text-sm font-medium text-primary">
                          <span className="text-brand-pulse underline decoration-brand-pulse/50 underline-offset-2">
                            Browse files
                          </span>{' '}
                          or drag and drop here
                        </p>
                        <p className="mt-1 text-xs text-muted">
                          PDF, Word (.docx), or Image (.jpg, .png)
                        </p>

                        <div className="mt-4 flex flex-wrap items-center justify-center gap-1.5">
                          <span className="inline-flex items-center px-2 py-0.5 rounded-md bg-surface-raised text-xs font-mono text-muted border border-border-subtle">
                            PDF
                          </span>
                          <span className="inline-flex items-center px-2 py-0.5 rounded-md bg-surface-raised text-xs font-mono text-muted border border-border-subtle">
                            DOCX
                          </span>
                          <span className="inline-flex items-center px-2 py-0.5 rounded-md bg-surface-raised text-xs font-mono text-muted border border-border-subtle">
                            JPG
                          </span>
                          <span className="inline-flex items-center px-2 py-0.5 rounded-md bg-surface-raised text-xs font-mono text-muted border border-border-subtle">
                            PNG
                          </span>
                          <span className="inline-flex items-center px-2 py-0.5 rounded-md bg-surface-raised text-xs font-mono text-muted border border-border-subtle">
                            Max 50MB
                          </span>
                        </div>
                      </div>
                    ) : (
                      /* Selected File Card */
                      <div className="rounded-lg border border-border-subtle bg-surface-raised p-4">
                        <div className="flex items-center justify-between gap-3">
                          <div className="flex items-center gap-3 min-w-0">
                            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-surface border border-border-subtle text-brand-pulse">
                              <FileText className="h-5 w-5" />
                            </div>
                            <div className="min-w-0">
                              <p className="text-sm font-medium text-primary truncate" title={file.name}>
                                {file.name}
                              </p>
                              <div className="flex items-center gap-2 text-xs text-muted font-mono">
                                <span>{formatFileSize(file.size)}</span>
                                <span>•</span>
                                <span className="inline-flex items-center gap-1 text-positive font-sans">
                                  <Check className="h-3 w-3" /> Ready
                                </span>
                              </div>
                            </div>
                          </div>

                          {state !== 'uploading' && (
                            <button
                              type="button"
                              onClick={() => {
                                setFile(null)
                                setFileValidationError(null)
                                if (fileInputRef.current) fileInputRef.current.value = ''
                              }}
                              className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-secondary hover:text-primary hover:bg-surface-selected focus-visible:ring-2 focus-visible:ring-focus transition-colors"
                              aria-label="Remove selected file"
                            >
                              <X className="h-4 w-4" />
                            </button>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Validation Error */}
                    {fileValidationError && (
                      <p className="mt-2 text-xs text-danger flex items-center gap-1.5" role="alert">
                        <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
                        {fileValidationError}
                      </p>
                    )}
                  </div>

                  {/* Notice regarding CVs */}
                  <div className="rounded-lg bg-surface-raised border border-border-subtle p-3 text-xs text-muted">
                    <p>
                      <strong className="text-secondary">Note:</strong> CVs and resumes require staff onboarding review and must be submitted through your operational contact. Direct link uploads are intended for compliance certificates and credentials.
                    </p>
                  </div>

                  {/* Submission Action Button */}
                  <button
                    type="submit"
                    disabled={!file || state === 'uploading'}
                    className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg bg-action px-5 text-sm font-semibold text-on-action hover:bg-action-hover focus-visible:ring-2 focus-visible:ring-focus transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-sm cursor-pointer"
                  >
                    {state === 'uploading' ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin text-on-action" />
                        <span>Encrypting & uploading document…</span>
                      </>
                    ) : (
                      <>
                        <FileUp className="h-4 w-4" />
                        <span>Securely Submit Document</span>
                      </>
                    )}
                  </button>
                </form>
              </div>
            )}

            {/* STATE: COMPLETE / SUCCESS */}
            {state === 'complete' && (
              <div className="py-4 text-center space-y-6">
                <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-positive-soft border border-positive-border text-positive">
                  <CheckCircle2 aria-hidden="true" className="h-8 w-8" />
                </div>

                <div className="space-y-2">
                  <h2 id="document-upload-title" className="text-xl font-semibold text-primary tracking-tight">
                    Document Successfully Received
                  </h2>
                  <p className="text-sm text-secondary max-w-md mx-auto">
                    Your document has been encrypted and securely delivered to the Hydenlyne compliance review queue.
                  </p>
                </div>

                {/* Upload Receipt Details */}
                <div className="rounded-lg border border-border-subtle bg-surface-raised p-4 text-left space-y-3">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-muted">Document:</span>
                    <span className="font-medium text-primary truncate max-w-[200px] sm:max-w-[280px]" title={uploadedFileName ?? ''}>
                      {uploadedFileName}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-muted">Classification:</span>
                    <span className="font-medium text-primary">
                      {CATEGORIES.find((c) => c.id === category)?.label ?? 'Certificate'}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-muted">Verification Status:</span>
                    <span className="inline-flex items-center gap-1 text-positive font-medium">
                      <Clock className="h-3 w-3" /> Queued for Staff Review
                    </span>
                  </div>
                </div>

                {/* What Happens Next Guidance */}
                <div className="rounded-lg bg-surface-raised border border-border-subtle p-4 text-left text-xs text-secondary space-y-1.5">
                  <p className="font-semibold text-primary">What happens next?</p>
                  <p>
                    Hydenlyne operations staff will inspect your document, verify credentials against active assignment standards, and update your specialist dossier.
                  </p>
                </div>

                {/* Action to upload another file */}
                <div className="pt-2">
                  <button
                    type="button"
                    onClick={handleUploadAnother}
                    className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg border border-border-strong bg-surface hover:bg-surface-raised px-4 text-sm font-semibold text-primary focus-visible:ring-2 focus-visible:ring-focus transition-colors cursor-pointer"
                  >
                    <RefreshCw className="h-4 w-4" />
                    <span>Upload Another Document</span>
                  </button>
                </div>
              </div>
            )}
          </section>

          {/* Compliance & Maritime Trust Footer */}
          <footer className="mt-8 text-center space-y-4">
            <div className="flex flex-wrap items-center justify-center gap-4 sm:gap-6 text-xs text-muted">
              <span className="inline-flex items-center gap-1.5">
                <ShieldCheck className="h-3.5 w-3.5 text-secondary" /> ISO 9001 Assured
              </span>
              <span className="inline-flex items-center gap-1.5">
                <Lock className="h-3.5 w-3.5 text-secondary" /> Cyber Essentials
              </span>
              <span className="inline-flex items-center gap-1.5">
                <CheckCircle2 className="h-3.5 w-3.5 text-secondary" /> UK GDPR Compliant
              </span>
            </div>

            <p className="text-xs text-muted">
              Hydenlyne Crew DMS • Maritime &amp; Geophysical Operational Support
            </p>
          </footer>
        </div>
      </main>
    </div>
  )
}
