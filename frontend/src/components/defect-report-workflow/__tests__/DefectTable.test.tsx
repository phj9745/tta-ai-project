import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'

import { DefectTable } from '../DefectTable'

const createFile = (name: string) => new File(['data'], name, { type: 'image/png' })

describe('DefectTable', () => {
  it('renders defects and manages attachments', async () => {
    const user = userEvent.setup()
    const defect = { index: 1, originalText: 'original', polishedText: 'polished' }
    const attachments = { 1: [createFile('example.png')] }
    const handleUpdatePolished = vi.fn()
    const handleAddAttachments = vi.fn()
    const handleRemoveAttachment = vi.fn()
    const handleReset = vi.fn()

    render(
      <DefectTable
        defects={[defect]}
        attachments={attachments}
        onUpdatePolished={handleUpdatePolished}
        onAddAttachments={handleAddAttachments}
        onRemoveAttachment={handleRemoveAttachment}
        showReset
        onReset={handleReset}
        isResetDisabled={false}
      />,
    )

    expect(screen.getByText('#1')).toBeInTheDocument()
    await user.type(screen.getByLabelText('정제된 문장'), ' updated')
    expect(handleUpdatePolished).toHaveBeenCalled()

    const fileInput = screen.getByLabelText('증빙 이미지 (선택)')
    const newFile = createFile('new.png')
    fireEvent.change(fileInput, { target: { files: [newFile] } })
    expect(handleAddAttachments).toHaveBeenCalled()
    const addCall = handleAddAttachments.mock.calls[0]
    expect(addCall[0]).toBe(1)
    expect(Array.from(addCall[1] as FileList)[0]?.name).toBe('new.png')

    await user.click(screen.getByRole('button', { name: '제거' }))
    expect(handleRemoveAttachment).toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: '초기화' }))
    expect(handleReset).toHaveBeenCalled()
  })
})
