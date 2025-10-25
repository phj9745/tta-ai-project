import { Dropzone } from './file-uploader/Dropzone'
import { FileGrid } from './file-uploader/FileGrid'
import { FileList } from './file-uploader/FileList'
import { useFileUploader, type UseFileUploaderOptions } from './file-uploader/useFileUploader'

export interface FileUploaderProps extends UseFileUploaderOptions {}

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
