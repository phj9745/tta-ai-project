import { describe, expect, it } from 'vitest'

import { createFileKey, formatBytes, isImageFile, isPreviewableImage } from './utils'

describe('formatBytes', () => {
  it('returns 0 B for invalid values', () => {
    expect(formatBytes(NaN)).toBe('0 B')
    expect(formatBytes(-10)).toBe('0 B')
  })

  it('formats bytes into human readable strings', () => {
    expect(formatBytes(1)).toBe('1 B')
    expect(formatBytes(1024)).toBe('1 KB')
    expect(formatBytes(1536)).toBe('1.5 KB')
    expect(formatBytes(5 * 1024 * 1024)).toBe('5 MB')
  })
})

describe('createFileKey', () => {
  it('creates a unique key from file metadata', () => {
    const fileA = new File(['hello'], 'example.txt', { type: 'text/plain', lastModified: 100 })
    const fileB = new File(['hello'], 'example.txt', { type: 'text/plain', lastModified: 200 })

    expect(createFileKey(fileA)).not.toBe(createFileKey(fileB))
  })
})

describe('image detection', () => {
  it('identifies images based on mime type', () => {
    const file = new File([''], 'photo', { type: 'image/png' })
    expect(isImageFile(file)).toBe(true)
    expect(isPreviewableImage(file)).toBe(true)
  })

  it('identifies images based on extension when mime is missing', () => {
    const file = new File([''], 'photo.jpeg', { type: '' })
    expect(isImageFile(file)).toBe(true)
  })

  it('returns false for non-image files', () => {
    const file = new File([''], 'document.pdf', { type: 'application/pdf' })
    expect(isImageFile(file)).toBe(false)
  })
})
