import { FC } from 'react'
import { Loader2 } from 'lucide-react'

interface OperationsMetricsProps {
  available: number | null
  onAssignment: number | null
  unavailable: number | null
  total: number | null
  loading: boolean
  error: string | null
  onSelectStatus?: (status: string) => void
}

function MetricCard({
  label,
  value,
  hint,
  loading,
  indicatorColor,
  onClick,
}: {
  label: string
  value: number | null
  hint: string
  loading: boolean
  indicatorColor?: string
  onClick?: () => void
}) {
  const content = (
    <>
      <p className="text-xs font-medium uppercase tracking-wider text-muted">{label}</p>
      <div className="mt-2 flex items-baseline justify-between gap-2">
        <div className="flex items-baseline gap-2">
          {loading ? (
            <Loader2 className="h-5 w-5 animate-spin text-muted" aria-label="Loading metric" />
          ) : (
            <span className="font-mono text-2xl font-semibold tracking-tight text-primary">
              {value ?? '—'}
            </span>
          )}
        </div>
        {indicatorColor && (
          <span className={`h-2 w-2 rounded-full ${indicatorColor} shrink-0`} aria-hidden="true" />
        )}
      </div>
      <p className="mt-1 text-xs text-secondary">{hint}</p>
    </>
  )

  if (onClick && !loading) {
    return (
      <button
        type="button"
        onClick={onClick}
        className="group text-left rounded-[10px] border border-border-subtle bg-surface p-4 hover:border-border-strong hover:bg-surface-raised/40 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus cursor-pointer"
        aria-label={`Filter by ${label}`}
      >
        {content}
      </button>
    )
  }

  return (
    <div className="rounded-[10px] border border-border-subtle bg-surface p-4">
      {content}
    </div>
  )
}

export const OperationsMetrics: FC<OperationsMetricsProps> = ({
  available,
  onAssignment,
  unavailable,
  total,
  loading,
  error,
  onSelectStatus,
}) => {
  if (error) {
    return (
      <section aria-labelledby="readiness-heading" className="rounded-[14px] border border-border-subtle bg-surface p-4 sm:p-5">
        <h2 id="readiness-heading" className="text-sm font-semibold text-primary">
          Crew readiness
        </h2>
        <p className="mt-3 rounded-[10px] border border-border-subtle bg-surface-raised/40 px-3 py-4 text-center text-sm text-muted">
          Crew data is unavailable
        </p>
      </section>
    )
  }

  return (
    <section aria-labelledby="readiness-heading" className="rounded-[14px] border border-border-subtle bg-surface p-4 sm:p-5">
      <div className="mb-3 flex items-center justify-between">
        <h2 id="readiness-heading" className="text-sm font-semibold text-primary">
          Crew readiness
        </h2>
        <span className="font-mono text-xs text-muted">Live roster</span>
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Available now"
          value={available}
          hint="Ready to mobilise"
          loading={loading}
          indicatorColor="bg-positive"
          onClick={onSelectStatus ? () => onSelectStatus('available') : undefined}
        />
        <MetricCard
          label="On assignment"
          value={onAssignment}
          hint="Currently deployed"
          loading={loading}
          indicatorColor="bg-accent"
          onClick={onSelectStatus ? () => onSelectStatus('on assignment') : undefined}
        />
        <MetricCard
          label="Unavailable"
          value={unavailable}
          hint="Not currently available"
          loading={loading}
          indicatorColor="bg-muted"
          onClick={onSelectStatus ? () => onSelectStatus('unavailable') : undefined}
        />
        <MetricCard
          label="Total specialists"
          value={total}
          hint="Approved profiles"
          loading={loading}
          indicatorColor="bg-primary"
          onClick={onSelectStatus ? () => onSelectStatus('') : undefined}
        />
      </div>
      {total === 0 && !loading && (
        <p className="mt-3 text-center text-xs text-muted">No contractors in the network yet</p>
      )}
    </section>
  )
}
