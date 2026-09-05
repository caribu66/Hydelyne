import { useEffect, useState } from 'react'
import { Bell, FileText, Loader2 } from 'lucide-react'
import { IncomingDocumentReview, incomingDocumentReviews } from '../lib/documentsApi'

interface IncomingDocumentAlertProps {
  onOpenContractor: (crewId: string) => void
}

export function IncomingDocumentAlert({ onOpenContractor }: IncomingDocumentAlertProps) {
  const [items, setItems] = useState<IncomingDocumentReview[]>([])
  const [loading, setLoading] = useState(true)

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
    return () => { active = false; window.clearInterval(interval) }
  }, [])

  return <details className="relative">
    <summary className="inline-flex min-h-11 cursor-pointer list-none items-center gap-1.5 rounded-[10px] border border-border-subtle bg-surface px-3 py-1.5 text-xs font-semibold text-secondary transition-colors hover:border-border-strong hover:bg-surface-raised hover:text-primary focus-visible:ring-2 focus-visible:ring-focus">
      <Bell className="h-3.5 w-3.5" aria-hidden="true" />
      <span className="hidden sm:inline">Documents</span>
      {loading ? <Loader2 className="h-3 w-3 animate-spin" aria-label="Loading received documents" /> : items.length > 0 && <span className="rounded-full bg-action px-1.5 py-0.5 font-mono text-xs text-on-action">{items.length}</span>}
    </summary>
    <section className="absolute right-0 z-50 mt-2 w-[min(22rem,calc(100vw-2rem))] rounded-[14px] border border-border-subtle bg-surface p-3 shadow-2xl" aria-label="Received documents requiring review">
      <h2 className="text-sm font-semibold text-primary">Documents received</h2>
      <p className="mt-1 text-sm text-secondary">Review contractor uploads before relying on them for compliance.</p>
      {items.length === 0 ? <p className="py-5 text-center text-sm text-muted">No documents are waiting for review.</p> : <ul className="mt-3 max-h-72 space-y-2 overflow-y-auto">
        {items.map((item) => <li key={item.id}><button type="button" onClick={() => onOpenContractor(item.crew_member_id)} className="flex min-h-11 w-full items-center gap-2 rounded-lg border border-border-subtle bg-canvas/50 p-2 text-left hover:bg-surface-raised focus-visible:ring-2 focus-visible:ring-focus"><FileText className="h-4 w-4 shrink-0 text-accent" /><span className="min-w-0"><span className="block truncate text-sm font-semibold text-primary">{item.file_name}</span><span className="block truncate text-sm text-secondary">{item.contractor_name}</span></span></button></li>)}
      </ul>}
    </section>
  </details>
}
