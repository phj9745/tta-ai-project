import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'

import { TestcaseEditPage } from '../TestcaseEditPage'

const originalFetch = global.fetch

describe('TestcaseEditPage grouped editing', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    global.fetch = originalFetch
  })

  it('applies updates to every row within a merged 대/중분류 block', async () => {
    const fetchMock = vi.fn()

    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        headers: [
          '대분류',
          '중분류',
          '소분류',
          '테스트 케이스 ID',
          '테스트 시나리오',
          '입력(사전조건 포함)',
          '기대 출력(사후조건 포함)',
          '테스트 결과',
          '상세 테스트 결과',
          '비고',
        ],
        rows: [
          {
            majorCategory: '헤더',
            middleCategory: '헤더',
            minorCategory: '헤더',
            testcaseId: '헤더',
            scenario: '헤더',
            input: '헤더',
            expected: '헤더',
            result: 'P',
            detail: '헤더',
            note: '헤더',
          },
          {
            majorCategory: '대1',
            middleCategory: '중1',
            minorCategory: '소1',
            testcaseId: 'TC-1',
            scenario: '시나리오1',
            input: '입력1',
            expected: '결과1',
            result: 'P',
            detail: '세부1',
            note: '비고1',
          },
          {
            majorCategory: '대1',
            middleCategory: '중1',
            minorCategory: '소2',
            testcaseId: 'TC-2',
            scenario: '시나리오2',
            input: '입력2',
            expected: '결과2',
            result: 'P',
            detail: '세부2',
            note: '비고2',
          },
          {
            majorCategory: '대1',
            middleCategory: '중2',
            minorCategory: '소3',
            testcaseId: 'TC-3',
            scenario: '시나리오3',
            input: '입력3',
            expected: '결과3',
            result: 'P',
            detail: '세부3',
            note: '비고3',
          },
        ],
      }),
      headers: { get: () => null },
    } as Response)

    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ modifiedTime: '2025-01-01T12:00:00Z' }),
      headers: { get: () => null },
    } as Response)

    global.fetch = fetchMock as unknown as typeof fetch

    const user = userEvent.setup()
    render(<TestcaseEditPage projectId="proj-2" />)

    const majorInput = await screen.findByDisplayValue('대1')
    expect(majorInput.closest('td')).toHaveAttribute('rowspan', '3')

    const middleInput = screen.getByDisplayValue('중1')
    expect(middleInput.closest('td')).toHaveAttribute('rowspan', '2')

    await user.clear(majorInput)
    await user.type(majorInput, '대-업데이트')

    await user.clear(middleInput)
    await user.type(middleInput, '중-업데이트')

    const saveButton = screen.getByRole('button', { name: '변경 사항 저장' })
    await waitFor(() => expect(saveButton).toBeEnabled())
    await user.click(saveButton)

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))

    const body = fetchMock.mock.calls[1]?.[1]?.body as string
    const payload = JSON.parse(body)

    expect(payload.rows[0].majorCategory).toBe('대-업데이트')
    expect(payload.rows[1].majorCategory).toBe('대-업데이트')
    expect(payload.rows[2].majorCategory).toBe('대-업데이트')

    expect(payload.rows[0].middleCategory).toBe('중-업데이트')
    expect(payload.rows[1].middleCategory).toBe('중-업데이트')
    expect(payload.rows[2].middleCategory).toBe('중2')
  })
})
