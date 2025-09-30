import { GOOGLE_DRIVE_HOME_URL } from './constants'
import { DRIVE_ROOT_FOLDER_STORAGE_KEY } from './config'

const GOOGLE_DRIVE_FOLDER_BASE_URL = 'https://drive.google.com/drive/folders'
const DRIVE_WINDOW_FEATURES = 'noopener,noreferrer'

export function storeDriveRootFolderId(folderId: string | null | undefined) {
  if (typeof window === 'undefined') {
    return
  }

  try {
    if (folderId && folderId.trim().length > 0) {
      sessionStorage.setItem(DRIVE_ROOT_FOLDER_STORAGE_KEY, folderId)
    } else {
      sessionStorage.removeItem(DRIVE_ROOT_FOLDER_STORAGE_KEY)
    }
  } catch (error) {
    console.error('failed to persist drive folder id', error)
  }
}

export function readDriveRootFolderId(): string | null {
  if (typeof window === 'undefined') {
    return null
  }

  try {
    const stored = sessionStorage.getItem(DRIVE_ROOT_FOLDER_STORAGE_KEY)
    if (stored && stored.trim().length > 0) {
      return stored
    }
    return null
  } catch (error) {
    console.error('failed to read drive folder id', error)
    return null
  }
}

export function clearDriveRootFolderId() {
  storeDriveRootFolderId(null)
}

export function getDriveFolderUrl(folderId: string): string {
  return `${GOOGLE_DRIVE_FOLDER_BASE_URL}/${encodeURIComponent(folderId)}`
}

export function openGoogleDriveWorkspace() {
  if (typeof window === 'undefined') {
    return
  }

  window.open(GOOGLE_DRIVE_HOME_URL, 'ttaGoogleDriveHome', DRIVE_WINDOW_FEATURES)

  const folderId = readDriveRootFolderId()
  if (folderId) {
    const folderUrl = getDriveFolderUrl(folderId)
    window.open(folderUrl, 'ttaGoogleDriveGs', DRIVE_WINDOW_FEATURES)
  }
}
