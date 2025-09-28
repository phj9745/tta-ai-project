export const DEFAULT_BACKEND_URL = 'http://localhost:8000'

const BACKEND_URL_KEY = 'VITE_BACKEND_URL'

export function getBackendUrl(): string {
  const envValue = (import.meta.env as Record<string, unknown>)[BACKEND_URL_KEY]
  if (typeof envValue === 'string' && envValue.trim().length > 0) {
    return envValue.trim().replace(/\/$/, '')
  }

  return DEFAULT_BACKEND_URL
}

export const DRIVE_AUTH_STORAGE_KEY = 'tta-ai.driveAuthInfo'
export const DRIVE_ROOT_FOLDER_STORAGE_KEY = 'tta-ai.driveRootFolderId'
