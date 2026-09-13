export function numericExperience(value: number | null): number {
  return value ?? 0
}

export function formatExperience(value: number | null): string {
  return value == null ? 'Not recorded' : String(value)
}
