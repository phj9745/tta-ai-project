import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'

import { FileUploader, type FileUploaderProps } from '../FileUploader'

function StatefulFileUploader(props: Omit<FileUploaderProps, 'files' | 'onChange'>) {
  const [files, setFiles] = useState<File[]>([])
  return <FileUploader {...props} files={files} onChange={setFiles} />
}

describe('FileUploader', () => {
  it('handles uploads and validation in default variant', async () => {
    const user = userEvent.setup()
    const { container } = render(<StatefulFileUploader allowedTypes={['png']} />)

    const input = container.querySelector('input[type="file"]') as HTMLInputElement
    const validFile = new File(['hello'], 'preview.png', { type: 'image/png' })
    const invalidFile = new File(['oops'], 'document.pdf', { type: 'application/pdf' })

    await user.upload(input, [invalidFile])
    expect(await screen.findByRole('alert')).toHaveTextContent('허용되지 않은 형식입니다: document.pdf')

    await user.upload(input, [validFile])
    expect(await screen.findByText('preview.png')).toBeInTheDocument()
    expect(screen.getByText('5 B')).toBeInTheDocument()

    const removeButton = screen.getByRole('button', { name: 'preview.png 삭제' })
    await user.click(removeButton)
    expect(screen.queryByText('preview.png')).not.toBeInTheDocument()
  })

  it('renders grid variant with image previews', async () => {
    const user = userEvent.setup()
    const { container } = render(
      <StatefulFileUploader allowedTypes={['jpg', 'png']} variant="grid" hideDropzoneWhenFilled={false} />,
    )

    const input = container.querySelector('input[type="file"]') as HTMLInputElement
    const imageFile = new File(['hello'], 'grid.jpg', { type: 'image/jpeg', lastModified: Date.now() })

    await user.upload(input, [imageFile])

    const grid = await screen.findByRole('list')
    expect(grid).toHaveClass('file-uploader__files--grid')

    const gridItem = within(grid).getByText('grid.jpg').closest('li')
    expect(gridItem).toHaveClass('file-uploader__file--grid')

    expect(container.querySelector('.file-uploader')).toHaveClass('file-uploader--grid')
  })
})
