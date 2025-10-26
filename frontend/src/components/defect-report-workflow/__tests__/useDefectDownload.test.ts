import { renderHook, act } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { useDefectDownload } from '../hooks'
import { DEFECT_REPORT_COLUMNS } from '../types'

describe('useDefectDownload', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('validates generation preconditions and download availability', async () => {
    const { result } = renderHook(() => useDefectDownload({ backendUrl: '/api', projectId: 'p' }))

    await act(async () => {
      const success = await result.current.generateReport([], {}, false)
      expect(success).toBe(false)
    })

    expect(result.current.generateStatus).toBe('error')
    expect(result.current.generateError).toBe('먼저 결함 문장을 정제해 주세요.')

    await act(async () => {
      const success = await result.current.downloadReport({})
      expect(success).toBe(false)
    })

    expect(result.current.downloadStatus).toBe('error')
    expect(result.current.downloadError).toBe('다운로드할 리포트가 없습니다.')
  })

  it('stores generated rows and downloads compiled workbook', async () => {
    const generatePayload = {
      fileName: 'defect.xlsx',
      headers: DEFECT_REPORT_COLUMNS.map((column) => column.key),
      rows: [
        {
          order: '1',
          summary: 'Issue',
          severity: 'H',
          frequency: 'A',
          quality: '기능적합성',
          description: '상세 설명',
        },
      ],
    }
    const generateResponse = new Response(JSON.stringify(generatePayload), {
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
    })

    const csvHeader = ['순번', DEFECT_REPORT_COLUMNS[1].key].join(',')
    const csv = `${csvHeader}\n1,Issue\n`
    const base64 = Buffer.from(csv, 'utf-8').toString('base64')
    const downloadResponse = new Response('file', {
      status: 200,
      headers: new Headers({
        'content-disposition': "attachment; filename=\"defect.xlsx\"",
        'x-defect-table': base64,
      }),
    })

    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockImplementationOnce(async () => generateResponse as Response)
      .mockImplementationOnce(async () => downloadResponse as Response)
    const createObjectURLMock = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:mock-url')
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})

    const { result } = renderHook(() => useDefectDownload({ backendUrl: '/api', projectId: 'p' }))

    await act(async () => {
      const success = await result.current.generateReport(
        [
          { index: 1, originalText: 'orig', polishedText: 'polished' },
        ],
        {},
        true,
      )
      expect(success).toBe(true)
    })

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(createObjectURLMock).not.toHaveBeenCalled()
    expect(result.current.tableRows).toHaveLength(1)

    await act(async () => {
      const success = await result.current.downloadReport({})
      expect(success).toBe(true)
    })

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(createObjectURLMock).toHaveBeenCalled()
    expect(result.current.downloadStatus).toBe('success')
  })
})
