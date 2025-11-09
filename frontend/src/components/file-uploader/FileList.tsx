import type { FileListProps } from './useFileUploader'

export function FileList({ shouldRender, files, onRemove, disabled }: FileListProps) {
  if (!shouldRender) {
    return null
  }

  return (
    <ul className="file-uploader__files">
      {files.map((file) => (
        <li key={file.key} className="file-uploader__file">
          <div>
            <span className="file-uploader__file-name">{file.name}</span>
            <span className="file-uploader__file-size">{file.sizeLabel}</span>
          </div>
          <button
            type="button"
            className="file-uploader__remove"
            onClick={() => onRemove(file.index)}
            aria-label={`${file.name} 삭제`}
            disabled={disabled}
          >
            삭제
          </button>
        </li>
      ))}
    </ul>
  )
}
