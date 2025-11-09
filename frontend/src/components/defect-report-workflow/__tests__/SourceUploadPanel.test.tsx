import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'

vi.mock('../../FileUploader', () => ({
  FileUploader: ({ onChange }: { onChange: (files: File[]) => void }) => (
    <button type="button" onClick={() => onChange([])}>
      mock uploader
    </button>
  ),
}))

import { SourceUploadPanel } from '../SourceUploadPanel'

describe('SourceUploadPanel', () => {
  it('renders error message when status is error', () => {
    render(
      <SourceUploadPanel
        featureFiles={[]}
        sourceFiles={[]}
        status="error"
        error="Something went wrong"
        onChangeFeature={() => {}}
        onChangeSource={() => {}}
        onFormalize={() => {}}
        showReset={false}
        onReset={() => {}}
        isResetDisabled={false}
      />,
    )

    expect(screen.getByRole('alert')).toHaveTextContent('Something went wrong')
  })

  it('triggers handlers for formalize and reset actions', async () => {
    const user = userEvent.setup()
    const handleFormalize = vi.fn()
    const handleReset = vi.fn()

    render(
      <SourceUploadPanel
        featureFiles={[]}
        sourceFiles={[]}
        status="idle"
        error={null}
        onChangeFeature={() => {}}
        onChangeSource={() => {}}
        onFormalize={handleFormalize}
        showReset
        onReset={handleReset}
        isResetDisabled={false}
      />,
    )

    await user.click(screen.getByRole('button', { name: '결함 문장 다듬기' }))
    expect(handleFormalize).toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: '초기화' }))
    expect(handleReset).toHaveBeenCalled()
  })
})
