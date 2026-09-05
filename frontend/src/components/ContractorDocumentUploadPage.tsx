import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from 'react'
import { CheckCircle2, FileUp, Loader2, ShieldCheck } from 'lucide-react'
import { publicDocumentRequest, uploadRequestedDocument } from '../lib/documentsApi'

interface ContractorDocumentUploadPageProps {
  token: string
}

export function ContractorDocumentUploadPage({ token }: ContractorDocumentUploadPageProps) {
  const [state, setState] = useState<'loading' | 'ready' | 'invalid' | 'uploading' | 'complete'>('loading')
  const [message, setMessage] = useState('Checking your secure upload link…')
  const [file, setFile] = useState<File | null>(null)
  const idempotencyKey = useMemo(() => crypto.randomUUID(), [])

  useEffect(() => {
    let active = true
    void publicDocumentRequest(token)
      .then(() => { if (active) { setState('ready'); setMessage('Upload the documents requested by your Hydenlyne contact.') } })
      .catch(() => { if (active) { setState('invalid'); setMessage('This upload link is invalid or has expired.') } })
    return () => { active = false }
  }, [token])

  const onFileChange = (event: ChangeEvent<HTMLInputElement>) => setFile(event.target.files?.[0] ?? null)
  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!file) return
    setState('uploading')
    try {
      await uploadRequestedDocument(token, file, idempotencyKey)
      setState('complete')
      setMessage('Your document has been received. The Hydenlyne team will review it shortly.')
    } catch (error) {
      setState('ready')
      setMessage(error instanceof Error ? error.message : 'We could not upload that document. Please try again.')
    }
  }

  const busy = state === 'loading' || state === 'uploading'
  return <main className="min-h-dvh bg-canvas px-4 py-10 text-primary sm:px-6">
    <section className="mx-auto w-full max-w-lg rounded-[14px] border border-border-subtle bg-surface p-5 shadow-2xl sm:p-6" aria-labelledby="document-upload-title">
      <div className="mb-5 flex h-11 w-11 items-center justify-center rounded-lg bg-accent-soft text-accent"><ShieldCheck aria-hidden="true" className="h-5 w-5" /></div>
      <h1 id="document-upload-title" className="text-lg font-semibold text-primary">Secure document upload</h1>
      <p className="mt-2 text-sm text-secondary" role="status" aria-live="polite">{message}</p>
      {state === 'ready' && <form className="mt-6 space-y-4" onSubmit={(event) => void onSubmit(event)}>
        <label className="block text-sm font-medium text-primary">Document
          <input className="mt-2 block min-h-11 w-full rounded-lg border border-border-strong bg-canvas px-3 py-2 text-sm text-primary file:mr-3 file:rounded-md file:border-0 file:bg-accent-soft file:px-3 file:py-1.5 file:text-sm file:font-semibold file:text-accent focus:outline-hidden focus:ring-2 focus:ring-focus" type="file" accept=".pdf,.doc,.docx,.jpg,.jpeg,.png" onChange={onFileChange} required />
        </label>
        <p className="text-xs text-muted">PDF, Word, JPG, or PNG. Maximum 50MB. Your document will be reviewed before it is accepted.</p>
        <button className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg bg-action px-4 text-sm font-semibold text-on-action hover:bg-action-hover focus-visible:ring-2 focus-visible:ring-focus" type="submit" disabled={!file}><FileUp className="h-4 w-4" />Send document</button>
      </form>}
      {busy && <div className="mt-6 flex items-center gap-2 text-sm text-secondary"><Loader2 className="h-4 w-4 animate-spin" />{state === 'uploading' ? 'Uploading your document securely…' : 'Loading…'}</div>}
      {state === 'complete' && <div className="mt-6 flex items-center gap-2 rounded-lg border border-positive-border bg-positive-soft p-3 text-sm text-positive"><CheckCircle2 className="h-5 w-5" />Document received</div>}
    </section>
  </main>
}
