import { renderHook, act } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { useDefectFinalize, type DefectFinalizeRow } from '../hooks'

function getFormDataEntries(body: FormData) {
  return Array.from(body.entries()).map(([key, value]) => {
    if (value instanceof File) {
      return [key, { name: value.name, size: value.size }]
    }
    return [key, value]
  })
}

describe('useDefectFinalize', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('submits rows and attachment stubs without summary file', async () => {
    const responsePayload = { fileId: 'spreadsheet', fileName: 'defect.xlsx' }
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(
        new Response(JSON.stringify(responsePayload), {
          status: 200,
          headers: new Headers({ 'content-type': 'application/json' }),
        }) as Response,
      )

    const { result } = renderHook(() => useDefectFinalize({ backendUrl: '/api', projectId: 'p' }))

    const rows: DefectFinalizeRow[] = [
      {
        order: '1',
        environment: '윈도우 11',
        summary: '요약',
        severity: 'H',
        frequency: 'A',
        quality: '신뢰성',
        description: '상세 설명',
        vendorResponse: '대기',
        fixStatus: '미해결',
        note: '이미지 참조',
      },
    ]

    const attachments = {
      1: [new File(['image'], '첨부.png', { type: 'image/png' })],
    }

    await act(async () => {
      const payload = await result.current.finalize(rows, attachments)
      expect(payload).toEqual(responsePayload)
    })

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [, options] = fetchMock.mock.calls[0]
    const formData = options?.body as FormData
    const entries = getFormDataEntries(formData)

    expect(entries.some(([key]) => key === 'menu_id')).toBe(true)
    expect(entries.some(([key]) => key === 'rows')).toBe(true)
    expect(entries.some(([key]) => key === 'attachment_names')).toBe(true)
    expect(entries.some(([key]) => key === 'files')).toBe(false)

    const rowsEntry = entries.find(([key]) => key === 'rows')
    expect(rowsEntry).toBeDefined()
    const parsedRows = JSON.parse(rowsEntry?.[1] as string)
    expect(parsedRows).toEqual([
      {
        order: '1',
        environment: '윈도우 11',
        summary: '요약',
        severity: 'H',
        frequency: 'A',
        quality: '신뢰성',
        description: '상세 설명',
        vendorResponse: '대기',
        fixStatus: '미해결',
        note: '이미지 참조',
      },
    ])

    const attachmentsEntry = entries.find(([key]) => key === 'attachment_names')
    expect(attachmentsEntry).toBeDefined()
    const parsedAttachments = JSON.parse(attachmentsEntry?.[1] as string)
    expect(parsedAttachments).toEqual([
      { defect_index: 1, fileName: 'defect-01-첨부.png' },
    ])
  })
})
