import { useMemo, useState } from 'react'
import type { ChangeEvent, DragEvent } from 'react'

export type FileType = 'pdf' | 'txt' | 'jpg' | 'csv' | 'html'

interface FileTypeInfo {
  label: string
  accept: string[]
  extensions: string[]
}

export const FILE_TYPE_OPTIONS: Record<FileType, FileTypeInfo> = {
  pdf: {
    label: 'PDF',
    accept: ['.pdf', 'application/pdf'],
    extensions: ['pdf'],
  },
  txt: {
    label: 'TXT',
    accept: ['.txt', 'text/plain'],
    extensions: ['txt'],
  },
  jpg: {
    label: 'JPG',
    accept: ['.jpg', '.jpeg', 'image/jpeg'],
    extensions: ['jpg', 'jpeg'],
  },
  csv: {
    label: 'CSV',
    accept: ['.csv', 'text/csv'],
    extensions: ['csv'],
  },
  html: {
    label: 'HTML',
    accept: ['.html', '.htm', 'text/html'],
    extensions: ['html', 'htm'],
  },
}

export const ALL_FILE_TYPES = Object.keys(FILE_TYPE_OPTIONS) as FileType[]

interface FileUploaderProps {
  allowedTypes: FileType[]
  files: File[]
  onChange: (files: File[]) => void
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

export function FileUploader({ allowedTypes, files, onChange }: FileUploaderProps) {
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
    event.preventDefault()
    if (!isDragging) {
      setIsDragging(true)
    }
  }

  const handleDragLeave = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault()
    if (isDragging) {
      setIsDragging(false)
    }
  }

  const addFiles = (incoming: File[]) => {
    if (incoming.length === 0) {
      return
    }

    const allowed: File[] = []
    const rejected: string[] = []
    const existingKeys = new Set(files.map(createFileKey))

    incoming.forEach((file) => {
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
    event.preventDefault()
    setIsDragging(false)
    const droppedFiles = Array.from(event.dataTransfer?.files ?? [])
    addFiles(droppedFiles)
  }

  const handleInputChange = (event: ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(event.target.files ?? [])
    addFiles(selected)
    event.target.value = ''
  }

  const handleRemove = (index: number) => {
    const nextFiles = files.filter((_, currentIndex) => currentIndex !== index)
    onChange(nextFiles)
  }

  return (
    <div className="file-uploader">
      <label
        className={`file-uploader__dropzone${isDragging ? ' file-uploader__dropzone--active' : ''}`}
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
