import { FC } from 'react'
import { FileText, ShieldAlert, ChevronRight, Loader2 } from 'lucide-react'

interface AttentionItem {
  count: number | null
  loading: boolean
  error: string | null
}

interface OperationsAttentionProps {
  documents: AttentionItem
  expiring: AttentionItem
  onOpenDocuments: () => void
  onOpenExpiring: () => void
}

function AttentionRow({
  icon: Icon,
  label,
  count,
  loading,
  error,
  emptyText,
  actionLabel,
  onAction,
}: {
  icon: typeof FileText
  label: string
  count: number | null
  loading: boolean
  error: string | null
  emptyText: string
  actionLabel: string
  onAction: () => void
}) {
  const showCount = !loading && !error && count !== null
  const isEmpty = showCount && count === 0
  return (
    <li className="flex items-center justify-between gap-3 rounded-[10px] border border-border-subtle bg-surface p-3 transition-colors hover:border-border-strong hover:bg-surface-raised/40">
      <div className="flex min-w-0 items-center gap-3">
        <span className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-[10px] border border-border-subtle bg-surface-raised text-secondary">
          <Icon className="h-4 w-4" aria-hidden="true" />
        </span>
        <div className="min-w-0">
          <p className="text-sm font-semibold text-primary">{label}</p>
          {loading ? (
            <span className="inline-flex items-center gap-1.5 text-xs text-muted">
              <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />
              Loading…
            </span>
          ) : error ? (
            <p className="text-xs text-muted">Data is unavailable</p>
          ) : isEmpty ? (
            <p className="text-xs text-muted">{emptyText}</p>
          ) : (
            <p className="text-xs text-secondary">
              <span className="font-mono font-semibold text-primary">{count}</span>{' '}
              {count === 1 ? 'item needs attention' : 'items need attention'}
            </p>
          )}
        </div>
      </div>
      <button
        type="button"
        onClick={onAction}
        className="inline-flex min-h-9 shrink-0 items-center gap-1 rounded-lg border border-border-subtle bg-surface px-2.5 text-xs font-semibold text-secondary transition-colors hover:border-border-strong hover:bg-surface-raised hover:text-primary focus-visible:ring-2 focus-visible:ring-focus"
        aria-label={actionLabel}
      >
        <span className="hidden sm:inline">{actionLabel}</span>
        <ChevronRight className="h-3.5 w-3.5" aria-hidden="true" />
      </button>
    </li>
  )
}

export const OperationsAttention: FC<OperationsAttentionProps> = ({
  documents,
  expiring,
  onOpenDocuments,
  onOpenExpiring,
}) => {
  return (
    <section aria-labelledby="attention-heading" className="rounded-[14px] border border-border-subtle bg-surface p-4 sm:p-5">
      <div className="mb-3 flex items-center justify-between">
        <h2 id="attention-heading" className="text-sm font-semibold text-primary">
          Needs attention
        </h2>
        <span className="font-mono text-xs text-muted">Review before mobilising</span>
      </div>
      <ul className="space-y-2.5">
        <AttentionRow
          icon={FileText}
          label="Documents ready for review"
          count={documents.count}
          loading={documents.loading}
          error={documents.error}
          emptyText="No documents await review"
          actionLabel="Review documents"
          onAction={onOpenDocuments}
        />
        <AttentionRow
          icon={ShieldAlert}
          label="Certificates expiring"
          count={expiring.count}
          loading={expiring.loading}
          error={expiring.error}
          emptyText="No certificates expiring soon"
          actionLabel="View certificates"
          onAction={onOpenExpiring}
        />
      </ul>
    </section>
  )
}
