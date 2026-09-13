export async function copyTextToClipboard(value: string): Promise<boolean> {
  if (!navigator.clipboard) return false
  try {
    await navigator.clipboard.writeText(value)
    return true
  } catch {
    return false
  }
}
