import { clearDriveRootFolderId } from './drive'

export type AuthStatus = 'authenticated' | 'unauthenticated'

const AUTH_STATUS_STORAGE_KEY = 'tta-ai.authStatus'

const subscribers = new Set<(status: AuthStatus) => void>()
let storageListenerRegistered = false

function readAuthStatus(): AuthStatus {
  if (typeof window === 'undefined') {
    return 'unauthenticated'
  }

  try {
    const stored = sessionStorage.getItem(AUTH_STATUS_STORAGE_KEY)
    return stored === 'authenticated' ? 'authenticated' : 'unauthenticated'
  } catch (error) {
    console.error('failed to read auth status from storage', error)
    return 'unauthenticated'
  }
}

function notify(status: AuthStatus) {
  subscribers.forEach((listener) => {
    try {
      listener(status)
    } catch (error) {
      console.error('auth listener threw an error', error)
    }
  })
}

function ensureStorageListener() {
  if (storageListenerRegistered || typeof window === 'undefined') {
    return
  }
  storageListenerRegistered = true

  window.addEventListener('storage', (event) => {
    if (event.key !== AUTH_STATUS_STORAGE_KEY) {
      return
    }
    notify(readAuthStatus())
  })
}

export function getAuthStatus(): AuthStatus {
  return readAuthStatus()
}

export function markAuthenticated() {
  if (typeof window !== 'undefined') {
    try {
      sessionStorage.setItem(AUTH_STATUS_STORAGE_KEY, 'authenticated')
    } catch (error) {
      console.error('failed to persist auth status', error)
    }
  }
  try {
    notify('authenticated')
  } catch (error) {
    console.error('failed to notify auth subscribers', error)
  }
}

export function clearAuthentication() {
  if (typeof window !== 'undefined') {
    try {
      sessionStorage.removeItem(AUTH_STATUS_STORAGE_KEY)
    } catch (error) {
      console.error('failed to clear auth status', error)
    }
  }
  try {
    clearDriveRootFolderId()
  } catch (error) {
    console.error('failed to clear drive folder id', error)
  }
  notify('unauthenticated')
}

export function subscribeToAuth(listener: (status: AuthStatus) => void): () => void {
  ensureStorageListener()
  subscribers.add(listener)
  return () => {
    subscribers.delete(listener)
  }
}
