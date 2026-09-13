export function availabilityLabel(value: string | null | undefined): string {
  return value?.trim() || 'Availability not recorded'
}
