import type { FileListProps } from './useFileUploader'

export function FileGrid({ shouldRender, files, onRemove, disabled }: FileListProps) {
  if (!shouldRender) {
    return null
  }

  return (
    <ul className="file-uploader__files file-uploader__files--grid">
      {files.map((file) => (
        <li key={file.key} className="file-uploader__file file-uploader__file--grid">
          {file.previewUrl ? (
            <div className="file-uploader__thumbnail" aria-hidden="true">
              <img src={file.previewUrl} alt="" />
            </div>
          ) : (
            <div className="file-uploader__thumbnail file-uploader__thumbnail--placeholder">
              <span className="file-uploader__thumbnail-label">이미지</span>
            </div>
          )}
          <div className="file-uploader__file-details">
            <span className="file-uploader__file-name">{file.name}</span>
            <span className="file-uploader__file-size">{file.sizeLabel}</span>
          </div>
          <button
            type="button"
            className="file-uploader__remove file-uploader__remove--block"
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
