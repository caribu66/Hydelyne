export function toDisplayStringRecord(value: unknown): Record<string, string> | undefined {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return undefined;

  const entries = Object.entries(value).flatMap(([key, item]) => {
    if (typeof item === 'string' || typeof item === 'boolean') return [[key, String(item)] as const];
    if (typeof item === 'number' && Number.isFinite(item)) return [[key, String(item)] as const];
    return [];
  });

  return Object.fromEntries(entries);
}
