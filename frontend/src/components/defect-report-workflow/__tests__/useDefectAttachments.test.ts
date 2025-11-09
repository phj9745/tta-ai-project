import { renderHook, act } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { useDefectAttachments } from '../hooks'

describe('useDefectAttachments', () => {
  it('filters invalid files and avoids duplicates', () => {
    const { result } = renderHook(() => useDefectAttachments())

    const invalid = new File(['x'], 'note.pdf', { type: 'application/pdf' })
    act(() => {
      result.current.addAttachments(1, [invalid])
    })
    expect(result.current.attachments[1]).toBeUndefined()

    const image = new File(['data'], 'image.png', { type: 'image/png' })
    act(() => {
      result.current.addAttachments(1, [image, image])
    })
    expect(result.current.attachments[1]).toHaveLength(1)

    act(() => {
      result.current.removeAttachment(1, image)
    })
    expect(result.current.attachments[1]).toBeUndefined()
  })
})
