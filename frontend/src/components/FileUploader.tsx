import { useMemo, useState } from 'react'
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

export function FileUploader({
  allowedTypes,
  files,
  onChange,
  disabled = false,
  multiple = true,
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

  return (
    <div className="file-uploader">
      <label
        className={`file-uploader__dropzone${
          isDragging ? ' file-uploader__dropzone--active' : ''
        }${disabled ? ' file-uploader__dropzone--disabled' : ''}`}
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
        <div className="file-uploader__prompt">
          <strong>파일을 드래그 앤 드롭</strong>하거나 클릭해서 선택하세요.
        </div>
        <div className="file-uploader__help">허용된 형식: {allowedLabels}</div>
      </label>

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
    </div>
  )
}
