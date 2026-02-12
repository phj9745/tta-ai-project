export const DEFAULT_BACKEND_URL = 'http://localhost:8000'

export function getBackendUrl(): string {
  // Try multiple common environment variable names
  const keys = ['VITE_BACKEND_URL', 'VITE_API_BASE_URL']

  for (const key of keys) {
    const value = (import.meta as any).env?.[key]
    if (typeof value === 'string' && value.trim().length > 0) {
      return value.trim().replace(/\/$/, '')
    }
  }

  return DEFAULT_BACKEND_URL
}

export const DRIVE_AUTH_STORAGE_KEY = 'tta-ai.driveAuthInfo'
export const DRIVE_ROOT_FOLDER_STORAGE_KEY = 'tta-ai.driveRootFolderId'
