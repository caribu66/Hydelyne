import { FC, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { AnimatePresence, motion } from 'motion/react'
import { Check, FileText, Loader2, X } from 'lucide-react'
import { useAccessibleDialog } from '../hooks/useAccessibleDialog'
import {
  IncomingDocumentReview,
  actionIncomingDocumentReview,
  incomingDocumentReviews,
} from '../lib/documentsApi'

interface DocumentReviewModalProps {
  isOpen: boolean
  sessionKey?: string | null
  onClose: () => void
  onOpenContractor: (crewId: string) => void | Promise<void>
  onShowToast: (message: string) => void
  onReviewResolved: () => void
}

export const DocumentReviewModal: FC<DocumentReviewModalProps> = ({
  isOpen,
  sessionKey = null,
  onClose,
  onOpenContractor,
  onShowToast,
  onReviewResolved,
}) => {
  const dialogRef = useRef<HTMLDivElement>(null)
  const [items, setItems] = useState<IncomingDocumentReview[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [actingId, setActingId] = useState<string | null>(null)
  const requestVersionRef = useRef(0)
  const currentSessionKeyRef = useRef(sessionKey)
  currentSessionKeyRef.current = sessionKey

  useAccessibleDialog(isOpen, dialogRef, onClose)

  useEffect(() => {
    requestVersionRef.current += 1
    setItems([])
    setError(null)
    setActingId(null)
    if (!isOpen || !sessionKey) {
      return
    }

    let active = true
    const requestVersion = requestVersionRef.current
    const load = async () => {
      setLoading(true)
      try {
        const reviews = await incomingDocumentReviews()
        if (active && requestVersion === requestVersionRef.current) {
          setItems(reviews)
          setError(null)
        }
      } catch (err) {
        if (active && requestVersion === requestVersionRef.current) {
          setError(err instanceof Error ? err.message : 'Could not load received documents.')
        }
      } finally {
        if (active && requestVersion === requestVersionRef.current) setLoading(false)
      }
    }

    void load()
    return () => {
      active = false
    }
  }, [isOpen, sessionKey])

  const handleAction = async (reviewId: string, action: 'approve' | 'reject', fileName: string) => {
    if (!sessionKey || currentSessionKeyRef.current !== sessionKey) return
    const requestVersion = requestVersionRef.current
    setActingId(reviewId)
    try {
      await actionIncomingDocumentReview(reviewId, action)
      if (
        requestVersion !== requestVersionRef.current ||
        currentSessionKeyRef.current !== sessionKey
      ) return
      setItems((currentItems) => currentItems.filter((item) => item.id !== reviewId))
      onReviewResolved()
      onShowToast(action === 'approve' ? `Approved “${fileName}” for compliance` : `Rejected “${fileName}”`)
    } catch (err) {
      if (requestVersion !== requestVersionRef.current) return
      onShowToast(err instanceof Error ? err.message : `Failed to ${action} document`)
    } finally {
      if (requestVersion === requestVersionRef.current) setActingId(null)
    }
  }

  const handleOpenContractor = (crewId: string) => {
    void onOpenContractor(crewId)
    onClose()
  }

  return createPortal(
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center overflow-y-auto p-4">
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
            role="dialog"
            aria-modal="true"
            aria-labelledby="document-review-title"
            aria-describedby="document-review-description"
            className="relative z-10 flex max-h-[90vh] w-full max-w-2xl flex-col overflow-hidden rounded-[14px] border border-border-strong/80 bg-surface shadow-2xl"
          >
            <header className="flex items-center justify-between gap-4 border-b border-border-subtle bg-canvas/60 px-5 py-4 sm:px-6">
              <div className="flex min-w-0 items-center gap-3">
                <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-[10px] border border-border-strong bg-accent-soft text-accent">
                  <FileText className="h-5 w-5" aria-hidden="true" />
                </span>
                <div>
                  <h2 id="document-review-title" className="text-base font-semibold text-primary">Documents pending review</h2>
                  <p id="document-review-description" className="text-sm text-secondary">
                    Review contractor uploads before relying on them for compliance.
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={onClose}
                aria-label="Close pending documents"
                className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-lg border border-border-subtle bg-surface text-secondary transition-colors hover:border-border-strong hover:bg-surface-raised hover:text-primary focus-visible:ring-2 focus-visible:ring-focus"
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </button>
            </header>

            <div className="min-h-0 overflow-y-auto p-4 sm:p-5">
              {loading ? (
                <p className="flex min-h-32 items-center justify-center gap-2 text-sm text-secondary" role="status">
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> Loading pending documents…
                </p>
              ) : error ? (
                <p className="rounded-[10px] border border-border-subtle bg-canvas/60 p-4 text-sm text-secondary">{error}</p>
              ) : items.length === 0 ? (
                <p className="rounded-[10px] border border-border-subtle bg-canvas/60 p-6 text-center text-sm text-muted">No documents are waiting for review.</p>
              ) : (
                <ul className="space-y-3" aria-label="Pending documents">
                  {items.map((item) => {
                    const isActing = actingId === item.id
                    const canApprove = item.extraction_status === 'extracted' || item.extraction_status === 'needs_review'
                    return (
                      <li key={item.id} className="flex flex-col gap-3 rounded-[10px] border border-border-subtle bg-canvas/60 p-3.5 sm:flex-row sm:items-center sm:justify-between">
                        <button
                          type="button"
                          onClick={() => handleOpenContractor(item.crew_member_id)}
                          className="flex min-w-0 flex-1 items-center gap-3 rounded-lg text-left focus-visible:ring-2 focus-visible:ring-focus"
                          aria-label={`Open ${item.contractor_name}'s dossier for ${item.file_name}`}
                        >
                          <FileText className="h-5 w-5 shrink-0 text-accent" aria-hidden="true" />
                          <span className="min-w-0">
                            <span className="block truncate text-sm font-semibold text-primary">{item.file_name}</span>
                            <span className="block truncate text-xs text-secondary">{item.contractor_name}</span>
                          </span>
                        </button>
                        <div className="flex shrink-0 gap-2">
                          <button type="button" disabled={isActing || !canApprove} title={canApprove ? 'Approve document' : 'Approval waits for extraction to finish'} onClick={() => void handleAction(item.id, 'approve', item.file_name)} className="inline-flex min-h-11 items-center justify-center gap-1.5 rounded-lg bg-positive-soft px-3 text-xs font-semibold text-positive transition-colors hover:bg-positive/20 focus-visible:ring-2 focus-visible:ring-focus disabled:opacity-50">
                            {isActing ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" /> : <Check className="h-3.5 w-3.5" aria-hidden="true" />}
                            Approve
                          </button>
                          <button type="button" disabled={isActing} onClick={() => void handleAction(item.id, 'reject', item.file_name)} className="inline-flex min-h-11 items-center justify-center rounded-lg border border-danger-soft bg-surface px-3 text-xs font-semibold text-danger transition-colors hover:bg-danger-soft focus-visible:ring-2 focus-visible:ring-focus disabled:opacity-50">
                            Reject
                          </button>
                        </div>
                      </li>
                    )
                  })}
                </ul>
              )}
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>,
    document.body,
  )
}
