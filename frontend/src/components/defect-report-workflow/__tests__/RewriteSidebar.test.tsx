import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'

import { RewriteSidebar } from '../RewriteSidebar'

describe('RewriteSidebar', () => {
  it('shows placeholder messages when no data is available', () => {
    render(
      <RewriteSidebar
        selectedRow={null}
        selectedColumn={null}
        selectedValue=""
        onUpdateValue={() => {}}
        rewriteMessages={[]}
        rewriteStatus="idle"
        rewriteError={null}
        rewriteInput=""
        onRewriteInputChange={() => {}}
        onRewriteSubmit={() => {}}
        isGenerating={false}
        tableHasRows={false}
      />,
    )

    expect(screen.getByText('생성된 리포트 데이터를 불러오지 못했습니다.')).toBeInTheDocument()
  })

  it('allows direct edits and rewrite submissions', async () => {
    const user = userEvent.setup()
    const handleUpdateValue = vi.fn()
    const handleInputChange = vi.fn()
    const handleSubmit = vi.fn()

    render(
      <RewriteSidebar
        selectedRow={{ rowNumber: 6, cells: { col: 'value' } }}
        selectedColumn={{ key: 'col', label: '레이블' }}
        selectedValue="value"
        onUpdateValue={handleUpdateValue}
        rewriteMessages={[]}
        rewriteStatus="idle"
        rewriteError={null}
        rewriteInput=""
        onRewriteInputChange={handleInputChange}
        onRewriteSubmit={handleSubmit}
        isGenerating={false}
        tableHasRows
      />,
    )

    await user.type(screen.getByLabelText('직접 수정'), ' updated')
    expect(handleUpdateValue).toHaveBeenCalled()

    await user.type(screen.getByPlaceholderText('예: 문장을 더 간결하고 정중하게 바꿔줘'), 'prompt')
    expect(handleInputChange).toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'GPT에게 수정 요청' }))
    expect(handleSubmit).toHaveBeenCalled()
  })
})
