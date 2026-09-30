const LINKEDIN_HOSTS = new Set(['linkedin.com', 'www.linkedin.com']);

export function safeLinkedInUrl(candidate: string | undefined, profileName: string): string {
  const fallback = `https://www.linkedin.com/search/results/all/?keywords=${encodeURIComponent(
    `${profileName} Hydenlyne`,
  )}`;
  if (!candidate) return fallback;

  try {
    const url = new URL(candidate);
    return url.protocol === 'https:' && LINKEDIN_HOSTS.has(url.hostname.toLowerCase())
      ? url.toString()
      : fallback;
  } catch {
    return fallback;
  }
}

export function mobilizationMailto(email: string, title: string): string {
  // The recipient is an addr-spec, not a query component: encoding it breaks
  // `@`/`+` and lets a stored `?`/`#` split the subject we append. Strip any
  // query/fragment smuggled into the stored value; only the subject is encoded.
  const recipient = email.trim().split(/[?#]/, 1)[0]?.trim() ?? '';
  return `mailto:${recipient}?subject=${encodeURIComponent(
    `Hydenlyne Mobilization Request - ${title}`,
  )}`;
}
