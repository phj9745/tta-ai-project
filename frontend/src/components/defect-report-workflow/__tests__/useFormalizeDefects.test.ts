import { renderHook, act } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { useFormalizeDefects } from '../hooks'

describe('useFormalizeDefects', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('returns error when no source file is provided', async () => {
    const { result } = renderHook(() => useFormalizeDefects({ backendUrl: '/api', projectId: 'p' }))

    await act(async () => {
      const success = await result.current.formalize()
      expect(success).toBe(false)
    })

    expect(result.current.formalizeStatus).toBe('error')
    expect(result.current.formalizeError).toBe('기능리스트 파일과 TXT 파일을 모두 업로드해 주세요.')
  })

  it('returns error when feature list is missing', async () => {
    const defectFile = new File(['content'], 'sample.txt', { type: 'text/plain' })
    const { result } = renderHook(() => useFormalizeDefects({ backendUrl: '/api', projectId: 'p' }))

    act(() => {
      result.current.changeSource([defectFile])
    })

    await act(async () => {
      const success = await result.current.formalize()
      expect(success).toBe(false)
    })

    expect(result.current.formalizeStatus).toBe('error')
    expect(result.current.formalizeError).toBe('기능리스트 파일을 업로드해 주세요.')
  })

  it('parses defects from the backend response', async () => {
    const file = new File(['content'], 'sample.txt', { type: 'text/plain' })
    const feature = new File(['feature'], 'feature.xlsx', { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
    const mockFetch = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          defects: [
            { index: 2, originalText: 'orig', polishedText: 'polished' },
            { index: 1, originalText: 'orig1', polishedText: 'polished1' },
          ],
        }),
        { status: 200 },
      ) as Response,
    )

    const { result } = renderHook(() => useFormalizeDefects({ backendUrl: '/api', projectId: 'p' }))

    act(() => {
      result.current.changeFeature([feature])
      result.current.changeSource([file])
    })

    await act(async () => {
      const success = await result.current.formalize()
      expect(success).toBe(true)
    })

    expect(mockFetch).toHaveBeenCalled()
    expect(result.current.defects.map((item) => item.index)).toEqual([1, 2])
    expect(result.current.formalizeStatus).toBe('success')
  })
})
