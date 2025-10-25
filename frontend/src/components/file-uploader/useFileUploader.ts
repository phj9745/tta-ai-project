import { useCallback, useEffect, useMemo, useState } from 'react'
import type { ChangeEvent, ClipboardEvent, DragEvent } from 'react'

import {
  ALL_FILE_TYPES,
  FILE_TYPE_OPTIONS,
  type FileType,
} from '../fileUploaderTypes'
import {
  createFileKey,
  formatBytes,
  isImageFile,
  isPreviewableImage,
} from './utils'

type FileUploaderVariant = 'default' | 'grid'
type DropzoneAppearance = 'default' | 'compact'

export interface FileItem {
  key: string
  index: number
  name: string
  sizeLabel: string
  previewUrl: string | null
}

export interface DropzoneProps {
  shouldRender: boolean
  className: string
  inputProps: {
    accept: string
    multiple: boolean
    onChange: (event: ChangeEvent<HTMLInputElement>) => void
    disabled: boolean
  }
  allowedLabels: string
  files: FileItem[]
  onRemove: (index: number) => void
  disabled: boolean
  shouldRenderCompactPreview: boolean
  onDragOver?: (event: DragEvent<HTMLLabelElement>) => void
  onDragLeave?: (event: DragEvent<HTMLLabelElement>) => void
  onDrop?: (event: DragEvent<HTMLLabelElement>) => void
  onPaste?: (event: ClipboardEvent<HTMLLabelElement>) => void
  enableDragAndDrop: boolean
  allowPaste: boolean
}

export interface FileListProps {
  shouldRender: boolean
  files: FileItem[]
  onRemove: (index: number) => void
  disabled: boolean
}

export interface UseFileUploaderResult {
  containerClassName: string
  dropzone: DropzoneProps
  error: string | null
  grid: FileListProps
  list: FileListProps
}

export interface UseFileUploaderOptions {
  allowedTypes: FileType[]
  files: File[]
  onChange: (files: File[]) => void
  disabled?: boolean
  multiple?: boolean
  hideDropzoneWhenFilled?: boolean
  maxFiles?: number
  variant?: FileUploaderVariant
  enableDragAndDrop?: boolean
  allowPaste?: boolean
  appearance?: DropzoneAppearance
}

export function useFileUploader({
  allowedTypes,
  files,
  onChange,
  disabled = false,
  multiple = true,
  hideDropzoneWhenFilled = false,
  maxFiles,
  variant = 'default',
  enableDragAndDrop = true,
  allowPaste = false,
  appearance = 'default',
}: UseFileUploaderOptions): UseFileUploaderResult {
  const [isDragging, setIsDragging] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const activeTypes = allowedTypes.length > 0 ? allowedTypes : ALL_FILE_TYPES

  const maxFileCount = useMemo(() => {
    if (typeof maxFiles === 'number' && Number.isFinite(maxFiles)) {
      return Math.max(0, Math.floor(maxFiles))
    }

    return undefined
  }, [maxFiles])

  const atCapacity = maxFileCount !== undefined && files.length >= maxFileCount
  const shouldHideForFilled =
    hideDropzoneWhenFilled && (maxFileCount !== undefined ? files.length >= maxFileCount : files.length > 0)
  const dropzoneDisabled = disabled || atCapacity || shouldHideForFilled
  const isGridVariant = variant === 'grid'

  const acceptValue = useMemo(() => {
    return activeTypes.flatMap((type) => FILE_TYPE_OPTIONS[type].accept).join(',')
  }, [activeTypes])

  const allowedLabels = useMemo(() => {
    return activeTypes.map((type) => FILE_TYPE_OPTIONS[type].label).join(', ')
  }, [activeTypes])

  const shouldUseCompactLayout = useMemo(() => {
    return multiple && files.length > 0 && files.every((file) => isImageFile(file))
  }, [files, multiple])

  const shouldRenderCompactPreview = shouldUseCompactLayout && hideDropzoneWhenFilled
  const shouldShowDropzone =
    !hideDropzoneWhenFilled || files.length === 0 || shouldRenderCompactPreview

  const shouldGeneratePreviews = shouldUseCompactLayout || shouldRenderCompactPreview

  const fileItems = useMemo<FileItem[]>(() => {
    return files.map((file, index) => {
      const key = createFileKey(file)
      const previewUrl =
        shouldGeneratePreviews && isPreviewableImage(file) &&
        typeof URL !== 'undefined' &&
        typeof URL.createObjectURL === 'function'
          ? URL.createObjectURL(file)
          : null

      return {
        key,
        index,
        name: file.name,
        sizeLabel: formatBytes(file.size),
        previewUrl,
      }
    })
  }, [files, shouldGeneratePreviews])

  useEffect(() => {
    return () => {
      fileItems.forEach((item) => {
        if (item.previewUrl) {
          URL.revokeObjectURL(item.previewUrl)
        }
      })
    }
  }, [fileItems])

  const removeFile = useCallback(
    (indexToRemove: number) => {
      if (disabled) {
        return
      }

      if (multiple) {
        const nextFiles = files.filter((_, index) => index !== indexToRemove)
        onChange(nextFiles)
      } else {
        onChange([])
      }
    },
    [disabled, files, multiple, onChange],
  )

  const addFiles = useCallback(
    (incoming: File[]) => {
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

      const normalizedIncoming = multiple ? incoming : incoming.slice(0, 1)

      let remainingSlots =
        maxFileCount !== undefined ? Math.max(0, maxFileCount - files.length) : Number.POSITIVE_INFINITY
      let limitedByCapacity = false

      const allowed: File[] = []
      const rejected: string[] = []
      const existingKeys = multiple ? new Set(files.map(createFileKey)) : null

      normalizedIncoming.forEach((file) => {
        if (remainingSlots <= 0) {
          limitedByCapacity = true
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

        if (existingKeys) {
          const key = createFileKey(file)
          if (existingKeys.has(key)) {
            return
          }

          existingKeys.add(key)
        }

        allowed.push(file)
        if (maxFileCount !== undefined && Number.isFinite(remainingSlots)) {
          remainingSlots = Math.max(0, remainingSlots - 1)
        }
      })

      if (rejected.length > 0) {
        setError(`허용되지 않은 형식입니다: ${rejected.join(', ')}`)
      } else if (limitedByCapacity) {
        setError(
          maxFileCount !== undefined
            ? `최대 ${maxFileCount}개의 파일까지 업로드할 수 있습니다.`
            : '업로드 가능한 파일 수를 모두 채웠습니다.',
        )
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
    },
    [activeTypes, atCapacity, disabled, files, maxFileCount, multiple, onChange],
  )

  const handleDragOver = useCallback(
    (event: DragEvent<HTMLLabelElement>) => {
      if (dropzoneDisabled || !enableDragAndDrop) {
        return
      }

      event.preventDefault()
      if (!isDragging) {
        setIsDragging(true)
      }
    },
    [dropzoneDisabled, enableDragAndDrop, isDragging],
  )

  const handleDragLeave = useCallback(
    (event: DragEvent<HTMLLabelElement>) => {
      if (dropzoneDisabled || !enableDragAndDrop) {
        return
      }

      event.preventDefault()
      if (isDragging) {
        setIsDragging(false)
      }
    },
    [dropzoneDisabled, enableDragAndDrop, isDragging],
  )

  const handleDrop = useCallback(
    (event: DragEvent<HTMLLabelElement>) => {
      if (dropzoneDisabled || !enableDragAndDrop) {
        return
      }

      event.preventDefault()
      setIsDragging(false)
      const droppedFiles = Array.from(event.dataTransfer?.files ?? [])
      addFiles(droppedFiles)
    },
    [addFiles, dropzoneDisabled, enableDragAndDrop],
  )

  const handlePaste = useCallback(
    (event: ClipboardEvent<HTMLLabelElement>) => {
      if (!allowPaste || dropzoneDisabled) {
        return
      }

      const pastedFiles = Array.from(event.clipboardData?.files ?? [])
      if (pastedFiles.length === 0) {
        return
      }

      event.preventDefault()
      addFiles(pastedFiles)
    },
    [addFiles, allowPaste, dropzoneDisabled],
  )

  const handleInputChange = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => {
      if (dropzoneDisabled) {
        event.target.value = ''
        return
      }

      const selected = Array.from(event.target.files ?? [])
      addFiles(selected)
      event.target.value = ''
    },
    [addFiles, dropzoneDisabled],
  )

  const dropzoneClassName = useMemo(() => {
    return [
      'file-uploader__dropzone',
      appearance === 'compact' ? 'file-uploader__dropzone--compact' : '',
      isDragging ? 'file-uploader__dropzone--active' : '',
      disabled ? 'file-uploader__dropzone--disabled' : '',
      shouldRenderCompactPreview && files.length > 0 ? 'file-uploader__dropzone--preview' : '',
      isGridVariant ? 'file-uploader__dropzone--grid' : '',
    ]
      .filter(Boolean)
      .join(' ')
  }, [appearance, disabled, files.length, isDragging, isGridVariant, shouldRenderCompactPreview])

  return {
    containerClassName: `file-uploader${isGridVariant ? ' file-uploader--grid' : ''}`,
    dropzone: {
      shouldRender: shouldShowDropzone,
      className: dropzoneClassName,
      inputProps: {
        accept: acceptValue,
        multiple,
        onChange: handleInputChange,
        disabled,
      },
      allowedLabels,
      files: fileItems,
      onRemove: removeFile,
      disabled,
      shouldRenderCompactPreview,
      onDragOver: enableDragAndDrop ? handleDragOver : undefined,
      onDragLeave: enableDragAndDrop ? handleDragLeave : undefined,
      onDrop: enableDragAndDrop ? handleDrop : undefined,
      onPaste: allowPaste ? handlePaste : undefined,
      enableDragAndDrop,
      allowPaste,
    },
    error,
    grid: {
      shouldRender: files.length > 0 && !shouldRenderCompactPreview && shouldUseCompactLayout,
      files: fileItems,
      onRemove: removeFile,
      disabled,
    },
    list: {
      shouldRender: files.length > 0 && !shouldRenderCompactPreview && !shouldUseCompactLayout,
      files: fileItems,
      onRemove: removeFile,
      disabled,
    },
  }
}
