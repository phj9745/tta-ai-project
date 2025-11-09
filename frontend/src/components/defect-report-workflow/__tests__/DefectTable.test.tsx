import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'

import { DefectTable } from '../DefectTable'
import type { DefectWorkItem } from '../types'

const createFile = (name: string) => new File(['data'], name, { type: 'image/png' })

describe('DefectTable', () => {
  it('renders defect cards and triggers handlers', async () => {
    const user = userEvent.setup()
    const item: DefectWorkItem = {
      entry: { index: 1, originalText: 'original', polishedText: 'polished' },
      attachments: [createFile('example.png')],
      status: 'idle',
      error: null,
      result: { 결함요약: '요약' },
      messages: [],
      input: '',
      inputError: null,
      isCollapsed: false,
    }

    const handlePolishedChange = vi.fn()
    const handleAddAttachments = vi.fn()
    const handleRemoveAttachment = vi.fn()
    const handleGenerate = vi.fn()
    const handleChatInputChange = vi.fn()
    const handleChatSubmit = vi.fn()
    const handleResultChange = vi.fn()
    const handleComplete = vi.fn()
    const handleResume = vi.fn()

    render(
      <DefectTable
        items={[item]}
        onPolishedChange={handlePolishedChange}
        onAddAttachments={handleAddAttachments}
        onRemoveAttachment={handleRemoveAttachment}
        onGenerate={handleGenerate}
        onChatInputChange={handleChatInputChange}
        onChatSubmit={handleChatSubmit}
        onResultChange={handleResultChange}
        onComplete={handleComplete}
        onResume={handleResume}
      />,
    )

    expect(screen.getByText('결함 1')).toBeInTheDocument()
    await user.type(screen.getByLabelText('정제된 문장'), ' updated')
    expect(handlePolishedChange).toHaveBeenCalledWith(1, expect.stringContaining('updated'))

    const fileInput = screen.getByLabelText('증빙 이미지 (선택)')
    const newFile = createFile('new.png')
    fireEvent.change(fileInput, { target: { files: [newFile] } })
    expect(handleAddAttachments).toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: '제거' }))
    expect(handleRemoveAttachment).toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: '결함 생성' }))
    expect(handleGenerate).toHaveBeenCalledWith(1)

    await user.type(screen.getByLabelText('결함요약'), ' 수정')
    expect(handleResultChange).toHaveBeenCalledWith(1, '결함요약', expect.stringContaining('수정'))

    await user.type(screen.getByPlaceholderText('예: 결함 요약을 두 문장으로 줄여줘'), '조정')
    expect(handleChatInputChange).toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'GPT에게 수정 요청' }))
    expect(handleChatSubmit).toHaveBeenCalledWith(1)

    await user.click(screen.getByRole('button', { name: '완료' }))
    expect(handleComplete).toHaveBeenCalledWith(1)

    // Render collapsed state
    cleanup()
    render(
      <DefectTable
        items={[{ ...item, isCollapsed: true }]}
        onPolishedChange={handlePolishedChange}
        onAddAttachments={handleAddAttachments}
        onRemoveAttachment={handleRemoveAttachment}
        onGenerate={handleGenerate}
        onChatInputChange={handleChatInputChange}
        onChatSubmit={handleChatSubmit}
        onResultChange={handleResultChange}
        onComplete={handleComplete}
        onResume={handleResume}
      />,
    )

    await user.click(screen.getByRole('button', { name: '수정' }))
    expect(handleResume).toHaveBeenCalledWith(1)
  })

  it('hides generated sections before GPT creates a result', () => {
    const item: DefectWorkItem = {
      entry: { index: 2, originalText: '원문', polishedText: '정제' },
      attachments: [],
      status: 'idle',
      error: null,
      result: {},
      messages: [],
      input: '',
      inputError: null,
      isCollapsed: false,
    }

    render(
      <DefectTable
        items={[item]}
        onPolishedChange={vi.fn()}
        onAddAttachments={vi.fn()}
        onRemoveAttachment={vi.fn()}
        onGenerate={vi.fn()}
        onChatInputChange={vi.fn()}
        onChatSubmit={vi.fn()}
        onResultChange={vi.fn()}
        onComplete={vi.fn()}
        onResume={vi.fn()}
      />,
    )

    expect(screen.queryByText('생성된 결함 요약')).not.toBeInTheDocument()
    expect(screen.queryByText('GPT와 결함 요약 다듬기')).not.toBeInTheDocument()
  })
})
