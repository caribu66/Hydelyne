/** Decode a public upload path segment without allowing malformed URL input to crash the app. */
export function decodeUploadTokenSegment(value: string): string {
  try {
    return decodeURIComponent(value)
  } catch {
    // Preserve the opaque segment so the API can reject it as an invalid
    // token and the user sees the normal expired-link state.
    return value
  }
}
