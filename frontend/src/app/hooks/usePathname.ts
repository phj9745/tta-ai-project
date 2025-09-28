import { useEffect, useState } from 'react'

import { listen } from '../../navigation'

function readInitialPathname(): string {
  if (typeof window === 'undefined') {
    return '/'
  }
  return window.location.pathname || '/'
}

export function usePathname(): string {
  const [pathname, setPathname] = useState<string>(() => readInitialPathname())

  useEffect(() => {
    if (typeof window === 'undefined') {
      return
    }

    const unsubscribe = listen((nextPath) => {
      setPathname(nextPath)
    })

    return unsubscribe
  }, [])

  return pathname
}
