import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'

import { FeatureListEditPage } from '../FeatureListEditPage'

const originalFetch = global.fetch

describe('FeatureListEditPage grouping behaviour', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    global.fetch = originalFetch
  })

  it('merges contiguous categories and propagates edits across the group', async () => {
    const fetchMock = vi.fn()

    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        headers: ['대분류', '중분류', '소분류', '기능 설명'],
        rows: [
          {
            majorCategory: '대1',
            middleCategory: '중1',
            minorCategory: '소1',
            featureDescription: '설명1',
          },
          {
            majorCategory: '대1',
            middleCategory: '중1',
            minorCategory: '소2',
            featureDescription: '설명2',
          },
          {
            majorCategory: '대1',
            middleCategory: '중2',
            minorCategory: '소3',
            featureDescription: '설명3',
          },
        ],
      }),
      headers: { get: () => null },
    } as Response)

    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ modifiedTime: '2024-12-31T15:00:00Z' }),
      headers: { get: () => null },
    } as Response)

    global.fetch = fetchMock as unknown as typeof fetch

    const user = userEvent.setup()
    render(<FeatureListEditPage projectId="proj-1" />)

    const majorInput = await screen.findByDisplayValue('대1')
    expect(majorInput.closest('td')).toHaveAttribute('rowspan', '3')

    const middleInput = screen.getByDisplayValue('중1')
    expect(middleInput.closest('td')).toHaveAttribute('rowspan', '2')

    await user.clear(majorInput)
    await user.type(majorInput, '대-업데이트')

    await user.clear(middleInput)
    await user.type(middleInput, '중-업데이트')

    const saveButton = screen.getByRole('button', { name: '수정 완료' })
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
