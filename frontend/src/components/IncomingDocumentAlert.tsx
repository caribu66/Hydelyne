import { useEffect, useState } from 'react'
import { Bell, Check, FileText, Loader2, X } from 'lucide-react'
import {
  IncomingDocumentReview,
  actionIncomingDocumentReview,
  incomingDocumentReviews,
} from '../lib/documentsApi'

interface IncomingDocumentAlertProps {
  onOpenContractor: (crewId: string) => void
  onShowToast?: (msg: string) => void
  onReviewResolved?: () => void
}

export function IncomingDocumentAlert({
  onOpenContractor,
  onShowToast,
  onReviewResolved,
}: IncomingDocumentAlertProps) {
  const [items, setItems] = useState<IncomingDocumentReview[]>([])
  const [loading, setLoading] = useState(true)
  const [actingId, setActingId] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    const load = async () => {
      try {
        const next = await incomingDocumentReviews()
        if (active) setItems(next)
      } finally {
        if (active) setLoading(false)
      }
    }
    void load()
    const interval = window.setInterval(() => void load(), 30_000)
    return () => {
      active = false
      window.clearInterval(interval)
    }
  }, [])

  const handleAction = async (reviewId: string, action: 'approve' | 'reject', fileName: string) => {
    setActingId(reviewId)
    try {
      await actionIncomingDocumentReview(reviewId, action)
      setItems((prev) => prev.filter((item) => item.id !== reviewId))
      onShowToast?.(
        action === 'approve'
          ? `Approved “${fileName}” for compliance`
          : `Rejected “${fileName}”`,
      )
      onReviewResolved?.()
    } catch (err) {
      onShowToast?.(err instanceof Error ? err.message : `Failed to ${action} document`)
    } finally {
      setActingId(null)
    }
  }

  return (
    <details className="relative">
      <summary className="inline-flex min-h-11 cursor-pointer list-none items-center gap-1.5 rounded-[10px] border border-border-subtle bg-surface px-3 py-1.5 text-xs font-semibold text-secondary transition-colors hover:border-border-strong hover:bg-surface-raised hover:text-primary focus-visible:ring-2 focus-visible:ring-focus">
        <Bell className="h-3.5 w-3.5" aria-hidden="true" />
        <span className="hidden sm:inline">Documents</span>
        {loading ? (
          <Loader2 className="h-3 w-3 animate-spin" aria-label="Loading received documents" />
        ) : (
          items.length > 0 && (
            <span className="rounded-full bg-action px-1.5 py-0.5 font-mono text-xs text-on-action">
              {items.length}
            </span>
          )
        )}
      </summary>
      <section
        className="absolute right-0 z-50 mt-2 w-[min(24rem,calc(100vw-2rem))] rounded-[14px] border border-border-subtle bg-surface p-4 shadow-2xl"
        aria-label="Received documents requiring review"
      >
        <div className="flex items-center justify-between border-b border-border-subtle pb-2.5">
          <h2 className="text-sm font-semibold text-primary">Documents received</h2>
          <span className="font-mono text-xs text-secondary">{items.length} pending</span>
        </div>
        <p className="mt-1 text-xs text-secondary">
          Review contractor uploads before relying on them for compliance.
        </p>
        {items.length === 0 ? (
          <p className="py-6 text-center text-xs text-muted">No documents are waiting for review.</p>
        ) : (
          <ul className="mt-3 max-h-80 space-y-2 overflow-y-auto">
            {items.map((item) => {
              const isActing = actingId === item.id
              return (
                <li
                  key={item.id}
                  className="flex items-center justify-between gap-2 rounded-lg border border-border-subtle bg-canvas/60 p-2.5 transition-colors hover:bg-surface-raised"
                >
                  <button
                    type="button"
                    onClick={() => onOpenContractor(item.crew_member_id)}
                    className="flex min-w-0 flex-1 items-center gap-2.5 text-left focus-visible:outline-hidden"
                    title={`Open ${item.contractor_name}'s dossier`}
                  >
                    <FileText className="h-4 w-4 shrink-0 text-accent" />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-xs font-semibold text-primary">
                        {item.file_name}
                      </span>
                      <span className="block truncate text-xs text-secondary">
                        {item.contractor_name}
                      </span>
                    </span>
                  </button>

                  <div className="flex items-center gap-1 shrink-0">
                    <button
                      type="button"
                      disabled={isActing}
                      onClick={() => void handleAction(item.id, 'approve', item.file_name)}
                      className="inline-flex h-8 w-8 items-center justify-center rounded-md bg-positive-soft text-positive hover:bg-positive/20 focus-visible:ring-2 focus-visible:ring-focus disabled:opacity-50 cursor-pointer"
                      title="Approve document"
                      aria-label={`Approve ${item.file_name}`}
                    >
                      {isActing ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Check className="h-3.5 w-3.5" />
                      )}
                    </button>
                    <button
                      type="button"
                      disabled={isActing}
                      onClick={() => void handleAction(item.id, 'reject', item.file_name)}
                      className="inline-flex h-8 w-8 items-center justify-center rounded-md bg-danger-soft/60 text-danger hover:bg-danger-soft focus-visible:ring-2 focus-visible:ring-focus disabled:opacity-50 cursor-pointer"
                      title="Reject document"
                      aria-label={`Reject ${item.file_name}`}
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </li>
              )
            })}
          </ul>
        )}
      </section>
    </details>
  )
}
