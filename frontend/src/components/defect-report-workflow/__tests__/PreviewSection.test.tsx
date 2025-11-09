import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'

import { PreviewSection } from '../PreviewSection'
import { DEFECT_REPORT_COLUMNS } from '../types'

describe('PreviewSection', () => {
  it('renders loading state when no rows are available', () => {
    const ref = { current: null }
    render(
      <PreviewSection
        columns={DEFECT_REPORT_COLUMNS}
        tableRows={[]}
        selectedCell={null}
        onSelectCell={() => {}}
        selectedRow={null}
        selectedColumn={null}
        selectedValue=""
        onUpdateSelectedValue={() => {}}
        rewriteMessages={[]}
        rewriteStatus="idle"
        rewriteError={null}
        rewriteInput=""
        onRewriteInputChange={() => {}}
        onRewriteSubmit={() => {}}
        isGenerating
        showReset={false}
        onReset={() => {}}
        isResetDisabled={false}
        sectionRef={ref}
      />,
    )

    expect(screen.getByRole('status')).toHaveTextContent('결함 리포트를 생성하는 중입니다…')
  })

  it('allows cell selection and passes data to sidebar', async () => {
    const user = userEvent.setup()
    const ref = { current: null }
    const handleSelectCell = vi.fn()
    const handleUpdate = vi.fn()
    const handleRewrite = vi.fn()

    render(
      <PreviewSection
        columns={DEFECT_REPORT_COLUMNS}
        tableRows={[{ rowNumber: 6, cells: { [DEFECT_REPORT_COLUMNS[0].key]: 'value' } }]}
        selectedCell={{ rowIndex: 0, columnKey: DEFECT_REPORT_COLUMNS[0].key }}
        onSelectCell={handleSelectCell}
        selectedRow={{ rowNumber: 6, cells: { [DEFECT_REPORT_COLUMNS[0].key]: 'value' } }}
        selectedColumn={DEFECT_REPORT_COLUMNS[0]}
        selectedValue="value"
        onUpdateSelectedValue={handleUpdate}
        rewriteMessages={[]}
        rewriteStatus="idle"
        rewriteError={null}
        rewriteInput=""
        onRewriteInputChange={() => {}}
        onRewriteSubmit={handleRewrite}
        isGenerating={false}
        showReset={false}
        onReset={() => {}}
        isResetDisabled={false}
        sectionRef={ref}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'value' }))
    expect(handleSelectCell).toHaveBeenCalled()

    await user.type(screen.getByLabelText('직접 수정'), ' updated')
    expect(handleUpdate).toHaveBeenCalled()
  })
})
