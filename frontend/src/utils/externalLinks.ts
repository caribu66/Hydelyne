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
  return `mailto:${encodeURIComponent(email)}?subject=${encodeURIComponent(
    `Hydenlyne Mobilization Request - ${title}`,
  )}`;
}
