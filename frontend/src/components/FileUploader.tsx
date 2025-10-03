import { useEffect, useMemo, useState } from 'react'
import type { ChangeEvent, DragEvent } from 'react'

import {
  ALL_FILE_TYPES,
  FILE_TYPE_OPTIONS,
  type FileType,
} from './fileUploaderTypes'

interface FileUploaderProps {
  allowedTypes: FileType[]
  files: File[]
  onChange: (files: File[]) => void
  disabled?: boolean
  multiple?: boolean
  hideDropzoneWhenFilled?: boolean
}

function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) {
    return '0 B'
  }

  const units = ['B', 'KB', 'MB', 'GB']
  const exponent = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  const value = bytes / 1024 ** exponent
  return `${value.toFixed(value >= 10 || exponent === 0 ? 0 : 1)} ${units[exponent]}`
}

function createFileKey(file: File) {
  return `${file.name}-${file.size}-${file.lastModified}`
}

const IMAGE_FILE_PATTERN = /\.(png|jpe?g|gif|webp|bmp|heic|heif)$/i

function isImageFile(file: File) {
  if (file.type.startsWith('image/')) {
    return true
  }

  return IMAGE_FILE_PATTERN.test(file.name)
}

export function FileUploader({
  allowedTypes,
  files,
  onChange,
  disabled = false,
  multiple = true,
  hideDropzoneWhenFilled = false,
}: FileUploaderProps) {
  const [isDragging, setIsDragging] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const activeTypes = allowedTypes.length > 0 ? allowedTypes : ALL_FILE_TYPES

  const acceptValue = useMemo(() => {
    return activeTypes.flatMap((type) => FILE_TYPE_OPTIONS[type].accept).join(',')
  }, [activeTypes])

  const allowedLabels = useMemo(() => {
    return activeTypes.map((type) => FILE_TYPE_OPTIONS[type].label).join(', ')
  }, [activeTypes])

  const handleDragOver = (event: DragEvent<HTMLLabelElement>) => {
    if (disabled) {
      return
    }

    event.preventDefault()
    if (!isDragging) {
      setIsDragging(true)
    }
  }

  const handleDragLeave = (event: DragEvent<HTMLLabelElement>) => {
    if (disabled) {
      return
    }

    event.preventDefault()
    if (isDragging) {
      setIsDragging(false)
    }
  }

  const addFiles = (incoming: File[]) => {
    if (disabled) {
      return
    }

    if (incoming.length === 0) {
      return
    }

    const normalizedIncoming = multiple ? incoming : incoming.slice(0, 1)

    const allowed: File[] = []
    const rejected: string[] = []
    const existingKeys = multiple ? new Set(files.map(createFileKey)) : null

    normalizedIncoming.forEach((file) => {
      const extension = file.name.split('.').pop()?.toLowerCase() ?? ''
      const matchesType = activeTypes.some((type) => {
        const info = FILE_TYPE_OPTIONS[type]
        return info.extensions.includes(extension) || info.accept.includes(file.type)
      })

      if (!matchesType) {
        rejected.push(file.name)
        return
      }

      if (existingKeys) {
        const key = createFileKey(file)
        if (existingKeys.has(key)) {
          return
        }

        existingKeys.add(key)
      }

      allowed.push(file)
    })

    if (rejected.length > 0) {
      setError(`허용되지 않은 형식입니다: ${rejected.join(', ')}`)
    } else {
      setError(null)
    }

    if (allowed.length > 0) {
      if (multiple) {
        onChange([...files, ...allowed])
      } else {
        onChange([allowed[allowed.length - 1]])
      }
    }
  }

  const handleDrop = (event: DragEvent<HTMLLabelElement>) => {
    if (disabled) {
      return
    }

    event.preventDefault()
    setIsDragging(false)
    const droppedFiles = Array.from(event.dataTransfer?.files ?? [])
    addFiles(droppedFiles)
  }

  const handleInputChange = (event: ChangeEvent<HTMLInputElement>) => {
    if (disabled) {
      event.target.value = ''
      return
    }

    const selected = Array.from(event.target.files ?? [])
    addFiles(selected)
    event.target.value = ''
  }

  const handleRemove = (index: number) => {
    if (disabled) {
      return
    }

    if (multiple) {
      const nextFiles = files.filter((_, currentIndex) => currentIndex !== index)
      onChange(nextFiles)
    } else {
      onChange([])
    }
  }

  const shouldUseCompactLayout = useMemo(() => {
    return multiple && files.length > 0 && files.every((file) => isImageFile(file))
  }, [files, multiple])

  const shouldRenderCompactPreview = shouldUseCompactLayout && hideDropzoneWhenFilled

  const shouldShowDropzone =
    !hideDropzoneWhenFilled || files.length === 0 || shouldRenderCompactPreview

  const imagePreviewMap = useMemo(() => {
    const canCreateObjectUrl =
      typeof URL !== 'undefined' && typeof URL.createObjectURL === 'function'

    if (!shouldUseCompactLayout || !canCreateObjectUrl) {
      return new Map<string, string>()
    }

    const previews = new Map<string, string>()
    files.forEach((file) => {
      const key = createFileKey(file)
      previews.set(key, URL.createObjectURL(file))
    })
    return previews
  }, [files, shouldUseCompactLayout])

  useEffect(() => {
    return () => {
      imagePreviewMap.forEach((url) => {
        URL.revokeObjectURL(url)
      })
    }
  }, [imagePreviewMap])

  return (
    <div className="file-uploader">
      {shouldShowDropzone && (
        <label
          className={`file-uploader__dropzone${
            isDragging ? ' file-uploader__dropzone--active' : ''
          }${disabled ? ' file-uploader__dropzone--disabled' : ''}${
            shouldRenderCompactPreview && files.length > 0
              ? ' file-uploader__dropzone--preview'
              : ''
          }`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          <input
            type="file"
            className="file-uploader__input"
            accept={acceptValue}
            multiple={multiple}
            onChange={handleInputChange}
            disabled={disabled}
          />
          {shouldRenderCompactPreview && files.length > 0 ? (
            <>
              <div className="file-uploader__preview-grid" aria-live="polite">
                {files.map((file, index) => {
                  const key = createFileKey(file)
                  const previewUrl = imagePreviewMap.get(key)

                  return (
                    <div key={key} className="file-uploader__preview-item">
                      {previewUrl ? (
                        <img src={previewUrl} alt="" />
                      ) : (
                        <span className="file-uploader__preview-fallback">이미지</span>
                      )}
                      <button
                        type="button"
                        className="file-uploader__preview-remove"
                        onClick={(event) => {
                          event.preventDefault()
                          event.stopPropagation()
                          handleRemove(index)
                        }}
                        aria-label={`${file.name} 삭제`}
                        disabled={disabled}
                      >
                        삭제
                      </button>
                    </div>
                  )
                })}
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
      )}

      {error && <p className="file-uploader__error" role="alert">{error}</p>}

      {files.length > 0 && !shouldRenderCompactPreview && (
        <ul
          className={`file-uploader__files${
            shouldUseCompactLayout ? ' file-uploader__files--grid' : ''
          }`}
        >
          {files.map((file, index) => {
            const key = createFileKey(file)
            const previewUrl = shouldUseCompactLayout ? imagePreviewMap.get(key) : null

            if (shouldUseCompactLayout) {
              return (
                <li key={key} className="file-uploader__file file-uploader__file--grid">
                  {previewUrl ? (
                    <div className="file-uploader__thumbnail" aria-hidden="true">
                      <img src={previewUrl} alt="" />
                    </div>
                  ) : (
                    <div className="file-uploader__thumbnail file-uploader__thumbnail--placeholder">
                      <span className="file-uploader__thumbnail-label">이미지</span>
                    </div>
                  )}
                  <div className="file-uploader__file-details">
                    <span className="file-uploader__file-name">{file.name}</span>
                    <span className="file-uploader__file-size">{formatBytes(file.size)}</span>
                  </div>
                  <button
                    type="button"
                    className="file-uploader__remove file-uploader__remove--block"
                    onClick={() => handleRemove(index)}
                    aria-label={`${file.name} 삭제`}
                    disabled={disabled}
                  >
                    삭제
                  </button>
                </li>
              )
            }

            return (
              <li key={key} className="file-uploader__file">
                <div>
                  <span className="file-uploader__file-name">{file.name}</span>
                  <span className="file-uploader__file-size">{formatBytes(file.size)}</span>
                </div>
                <button
                  type="button"
                  className="file-uploader__remove"
                  onClick={() => handleRemove(index)}
                  aria-label={`${file.name} 삭제`}
                  disabled={disabled}
                >
                  삭제
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
