const UNITS = ['B', 'KB', 'MB', 'GB'] as const

export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) {
    return '0 B'
  }

  const exponent = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), UNITS.length - 1)
  const value = bytes / 1024 ** exponent
  const decimals = value >= 10 || exponent === 0 ? 0 : 1
  return `${value.toFixed(decimals)} ${UNITS[exponent]}`
}

export function createFileKey(file: File): string {
  return `${file.name}-${file.size}-${file.lastModified}`
}

const IMAGE_FILE_PATTERN = /\.(png|jpe?g|gif|webp|bmp|heic|heif)$/i

export function isImageFile(file: File): boolean {
  if (file.type.startsWith('image/')) {
    return true
  }

  return IMAGE_FILE_PATTERN.test(file.name)
}

export function isPreviewableImage(file: File): boolean {
  return isImageFile(file)
}
