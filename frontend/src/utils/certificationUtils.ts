export type CertificationExpiryStatus = 'valid' | 'expiring_soon' | 'expired' | 'invalid' | null

export function certificationExpiryStatus(value?: string | null): CertificationExpiryStatus {
  if (!value) return null
  const dateOnlyMatch = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  const isDateOnly = dateOnlyMatch !== null
  let expiry: Date
  if (dateOnlyMatch) {
    const year = Number(dateOnlyMatch[1])
    const month = Number(dateOnlyMatch[2])
    const day = Number(dateOnlyMatch[3])
    expiry = new Date(Date.UTC(year, month - 1, day))
    if (
      expiry.getUTCFullYear() !== year
      || expiry.getUTCMonth() !== month - 1
      || expiry.getUTCDate() !== day
    ) return 'invalid'
  } else {
    expiry = new Date(value)
  }
  if (Number.isNaN(expiry.getTime())) return 'invalid'

  const now = new Date()
  const todayUtc = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate())
  const expiryUtc = isDateOnly
    ? Date.UTC(expiry.getUTCFullYear(), expiry.getUTCMonth(), expiry.getUTCDate())
    : expiry.getTime()
  const daysLeft = Math.ceil((expiryUtc - todayUtc) / (1000 * 60 * 60 * 24))
  if (daysLeft < 0) return 'expired'
  if (daysLeft <= 30) return 'expiring_soon'
  return 'valid'
}
