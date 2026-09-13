import { afterEach, describe, expect, it, vi } from 'vitest'
import { copyTextToClipboard } from './clipboard'

describe('copyTextToClipboard', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('reports successful clipboard writes', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal('navigator', { clipboard: { writeText } })

    await expect(copyTextToClipboard('hello')).resolves.toBe(true)
    expect(writeText).toHaveBeenCalledWith('hello')
  })

  it('reports unavailable or rejected clipboard writes', async () => {
    vi.stubGlobal('navigator', {})
    await expect(copyTextToClipboard('hello')).resolves.toBe(false)

    const writeText = vi.fn().mockRejectedValue(new Error('denied'))
    vi.stubGlobal('navigator', { clipboard: { writeText } })
    await expect(copyTextToClipboard('hello')).resolves.toBe(false)
  })
})
