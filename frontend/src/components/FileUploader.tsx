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
  maxFiles?: number
  variant?: 'list' | 'grid'
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

function isPreviewableImage(file: File): boolean {
  if (file.type.startsWith('image/')) {
    return true
  }

  const extension = file.name.split('.').pop()?.toLowerCase() ?? ''
  return ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'heic', 'heif'].includes(extension)
}

export function FileUploader({
  allowedTypes,
  files,
  onChange,
  disabled = false,
  maxFiles,
  variant = 'list',
  hideDropzoneWhenFilled = false,
}: FileUploaderProps) {
  const [isDragging, setIsDragging] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const activeTypes = allowedTypes.length > 0 ? allowedTypes : ALL_FILE_TYPES

  const maxFileCount = Number.isFinite(maxFiles) && maxFiles !== undefined ? Math.max(0, Math.floor(maxFiles)) : undefined
  const shouldHideForFilled = hideDropzoneWhenFilled && files.length > 0
  const atCapacity = maxFileCount !== undefined && files.length >= maxFileCount
  const dropzoneDisabled = disabled || atCapacity || shouldHideForFilled
  const shouldRenderDropzone = !atCapacity && !shouldHideForFilled
  const isGridVariant = variant === 'grid'

  const acceptValue = useMemo(() => {
    return activeTypes.flatMap((type) => FILE_TYPE_OPTIONS[type].accept).join(',')
  }, [activeTypes])

  const allowedLabels = useMemo(() => {
    return activeTypes.map((type) => FILE_TYPE_OPTIONS[type].label).join(', ')
  }, [activeTypes])

  const previewItems = useMemo(() => {
    return files.map((file) => ({
      key: createFileKey(file),
      url: isPreviewableImage(file) ? URL.createObjectURL(file) : null,
    }))
  }, [files])

  const previewMap = useMemo(() => {
    const map = new Map<string, string>()
    previewItems.forEach((item) => {
      if (item.url) {
        map.set(item.key, item.url)
      }
    })
    return map
  }, [previewItems])

  useEffect(() => {
    return () => {
      previewItems.forEach((item) => {
        if (item.url) {
          URL.revokeObjectURL(item.url)
        }
      })
    }
  }, [previewItems])

  const handleDragOver = (event: DragEvent<HTMLLabelElement>) => {
    if (dropzoneDisabled) {
      return
    }

    event.preventDefault()
    if (!isDragging) {
      setIsDragging(true)
    }
  }

  const handleDragLeave = (event: DragEvent<HTMLLabelElement>) => {
    if (dropzoneDisabled) {
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

    if (atCapacity) {
      setError('업로드 가능한 파일 수를 모두 채웠습니다.')
      return
    }

    if (incoming.length === 0) {
      return
    }

    const allowed: File[] = []
    const rejected: string[] = []
    const existingKeys = new Set(files.map(createFileKey))
    let remaining = maxFileCount !== undefined ? maxFileCount - files.length : Number.POSITIVE_INFINITY

    incoming.forEach((file) => {
      if (remaining <= 0) {
        return
      }

      const extension = file.name.split('.').pop()?.toLowerCase() ?? ''
      const matchesType = activeTypes.some((type) => {
        const info = FILE_TYPE_OPTIONS[type]
        return info.extensions.includes(extension) || info.accept.includes(file.type)
      })

      if (!matchesType) {
        rejected.push(file.name)
        return
      }

      const key = createFileKey(file)
      if (existingKeys.has(key)) {
        return
      }

      existingKeys.add(key)
      allowed.push(file)
      remaining -= 1
    })

    if (rejected.length > 0) {
      setError(`허용되지 않은 형식입니다: ${rejected.join(', ')}`)
    } else {
      setError(null)
    }

    if (allowed.length > 0) {
      onChange([...files, ...allowed])
    }
  }

  const handleDrop = (event: DragEvent<HTMLLabelElement>) => {
    if (dropzoneDisabled) {
      return
    }

    event.preventDefault()
    setIsDragging(false)
    const droppedFiles = Array.from(event.dataTransfer?.files ?? [])
    addFiles(droppedFiles)
  }

  const handleInputChange = (event: ChangeEvent<HTMLInputElement>) => {
    if (dropzoneDisabled) {
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

    const nextFiles = files.filter((_, currentIndex) => currentIndex !== index)
    onChange(nextFiles)
    setError(null)
  }

  const dropzone = shouldRenderDropzone ? (
    <label
      className={`file-uploader__dropzone${
        isDragging ? ' file-uploader__dropzone--active' : ''
      }${dropzoneDisabled ? ' file-uploader__dropzone--disabled' : ''}${
        isGridVariant ? ' file-uploader__dropzone--grid' : ''
      }`}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      <input
        type="file"
        className="file-uploader__input"
        accept={acceptValue}
        multiple
        onChange={handleInputChange}
        disabled={dropzoneDisabled}
      />
      {isGridVariant ? (
        <div className="file-uploader__dropzone-grid">
          <span aria-hidden="true" className="file-uploader__dropzone-icon">
            +
          </span>
          <span className="file-uploader__dropzone-text">이미지를 추가하세요</span>
          <span className="file-uploader__dropzone-subtext">허용된 형식: {allowedLabels}</span>
          {maxFileCount !== undefined && (
            <span className="file-uploader__dropzone-counter">
              {files.length}/{maxFileCount}
            </span>
          )}
        </div>
      ) : (
        <>
          <div className="file-uploader__prompt">
            <strong>파일을 드래그 앤 드롭</strong>하거나 클릭해서 선택하세요.
          </div>
          <div className="file-uploader__help">허용된 형식: {allowedLabels}</div>
        </>
      )}
    </label>
  ) : null

  return (
    <div className={`file-uploader${isGridVariant ? ' file-uploader--grid' : ''}`}>
      {isGridVariant ? (
        <div className="file-uploader__grid">
          {files.map((file, index) => {
            const key = createFileKey(file)
            const previewUrl = previewMap.get(key)
            return (
              <div key={key} className="file-uploader__grid-item">
                {previewUrl ? (
                  <img src={previewUrl} alt="업로드된 이미지 미리보기" className="file-uploader__grid-preview" />
                ) : (
                  <div className="file-uploader__grid-fallback">
                    <span className="file-uploader__grid-fallback-icon" aria-hidden="true">
                      📄
                    </span>
                    <span className="file-uploader__grid-fallback-label">{formatBytes(file.size)}</span>
                  </div>
                )}
                <span className="file-uploader__grid-name" title={file.name}>
                  {file.name}
                </span>
                <button
                  type="button"
                  className="file-uploader__grid-remove"
                  onClick={() => handleRemove(index)}
                  aria-label={`${file.name} 삭제`}
                  disabled={disabled}
                >
                  삭제
                </button>
              </div>
            )
          })}
          {dropzone}
        </div>
      ) : (
        <>
          {dropzone}
          {error && <p className="file-uploader__error" role="alert">{error}</p>}
          {files.length > 0 && (
            <ul className="file-uploader__files">
              {files.map((file, index) => (
                <li key={createFileKey(file)} className="file-uploader__file">
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
              ))}
            </ul>
          )}
        </>
      )}
      {isGridVariant && error && <p className="file-uploader__error" role="alert">{error}</p>}
      {isGridVariant && !shouldRenderDropzone && maxFileCount !== undefined && (
        <p className="file-uploader__grid-helper">최대 {maxFileCount}개의 이미지를 업로드할 수 있습니다.</p>
      )}
      {isGridVariant && shouldRenderDropzone && (
        <p className="file-uploader__grid-helper">허용된 형식: {allowedLabels}</p>
      )}
    </div>
  )
}
