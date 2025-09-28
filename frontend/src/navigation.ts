export type NavigationListener = (path: string) => void

const listeners = new Set<NavigationListener>()
let popstateRegistered = false

function getCurrentPathname(): string {
  return window.location.pathname || '/'
}

export function navigate(path: string, options?: { replace?: boolean }) {
  const normalized = path.startsWith('/') ? path : `/${path}`

  if (options?.replace) {
    window.history.replaceState({}, '', normalized)
  } else {
    window.history.pushState({}, '', normalized)
  }

  for (const listener of listeners) {
    listener(getCurrentPathname())
  }
}

export function listen(listener: NavigationListener): () => void {
  if (!popstateRegistered) {
    window.addEventListener('popstate', () => {
      const current = getCurrentPathname()
      for (const subscriber of listeners) {
        subscriber(current)
      }
    })
    popstateRegistered = true
  }

  listeners.add(listener)
  listener(getCurrentPathname())

  return () => {
    listeners.delete(listener)
  }
}
