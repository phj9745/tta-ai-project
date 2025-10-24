import type { DropzoneProps } from './useFileUploader'

export function Dropzone({
  shouldRender,
  className,
  inputProps,
  allowedLabels,
  files,
  onRemove,
  disabled,
  shouldRenderCompactPreview,
  onDragOver,
  onDragLeave,
  onDrop,
}: DropzoneProps) {
  if (!shouldRender) {
    return null
  }

  return (
    <label className={className} onDragOver={onDragOver} onDragLeave={onDragLeave} onDrop={onDrop}>
      <input type="file" className="file-uploader__input" {...inputProps} />
      {shouldRenderCompactPreview && files.length > 0 ? (
        <>
          <div className="file-uploader__preview-grid" aria-live="polite">
            {files.map((file) => (
              <div key={file.key} className="file-uploader__preview-item">
                {file.previewUrl ? (
                  <img src={file.previewUrl} alt="" />
                ) : (
                  <span className="file-uploader__preview-fallback">이미지</span>
                )}
                <button
                  type="button"
                  className="file-uploader__preview-remove"
                  onClick={(event) => {
                    event.preventDefault()
                    event.stopPropagation()
                    onRemove(file.index)
                  }}
                  aria-label={`${file.name} 삭제`}
                  disabled={disabled}
                >
                  삭제
                </button>
              </div>
            ))}
          </div>
          <div className="file-uploader__preview-helper" aria-hidden="true">
            이미지를 클릭해서 추가하거나 드래그 앤 드롭하세요.
          </div>
        </>
      ) : (
        <>
          <div className="file-uploader__prompt">
            <strong>파일을 드래그 앤 드롭</strong>하거나 클릭해서 선택하세요.
          </div>
          <div className="file-uploader__help">허용된 형식: {allowedLabels}</div>
        </>
      )}
    </label>
  )
}
