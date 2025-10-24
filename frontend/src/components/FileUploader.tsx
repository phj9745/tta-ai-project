import type { FileType } from './fileUploaderTypes'
import { Dropzone } from './file-uploader/Dropzone'
import { FileGrid } from './file-uploader/FileGrid'
import { FileList } from './file-uploader/FileList'
import { useFileUploader } from './file-uploader/useFileUploader'

export interface FileUploaderProps {
  allowedTypes: FileType[]
  files: File[]
  onChange: (files: File[]) => void
  disabled?: boolean
  multiple?: boolean
  hideDropzoneWhenFilled?: boolean
  maxFiles?: number
  variant?: 'default' | 'grid'
}

export function FileUploader(props: FileUploaderProps) {
  const { containerClassName, dropzone, error, grid, list } = useFileUploader(props)

  return (
    <div className={containerClassName}>
      <Dropzone {...dropzone} />

      {error && (
        <p className="file-uploader__error" role="alert">
          {error}
        </p>
      )}

      <FileGrid {...grid} />
      <FileList {...list} />
    </div>
  )
}
