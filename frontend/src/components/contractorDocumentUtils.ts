export function formatExpiryTime(isoString: string): { relative: string; full: string } {
  try {
    const expiry = new Date(isoString)
    if (Number.isNaN(expiry.getTime())) {
      return { relative: 'Expiry unavailable', full: 'Expiry date could not be read' }
    }
    const now = new Date()
    const diffMs = expiry.getTime() - now.getTime()
    const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24))

    const full = expiry.toLocaleDateString(undefined, {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      timeZoneName: 'short',
    })

    if (diffDays <= 0) return { relative: 'Expires soon', full }
    if (diffDays === 1) return { relative: 'Expires in 1 day', full }
    return { relative: `Valid for ${diffDays} days`, full }
  } catch {
    return { relative: 'Expiring bearer link', full: '14-day security window' }
  }
}
