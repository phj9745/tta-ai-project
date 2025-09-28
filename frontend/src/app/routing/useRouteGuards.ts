import { useEffect } from 'react'

import type { AuthStatus } from '../../auth'
import { navigate } from '../../navigation'

const PROJECT_PATH_PATTERN = /^\/projects\/(.+)$/

function isKnownPathname(pathname: string): boolean {
  if (pathname === '/' || pathname === '/drive') {
    return true
  }
  return PROJECT_PATH_PATTERN.test(pathname)
}

export function useRouteGuards(pathname: string, authStatus: AuthStatus) {
  useEffect(() => {
    if (!isKnownPathname(pathname)) {
      navigate('/', { replace: true })
    }
  }, [pathname])

  useEffect(() => {
    if (authStatus !== 'authenticated' && pathname !== '/') {
      navigate('/', { replace: true })
    }
  }, [authStatus, pathname])

  useEffect(() => {
    if (authStatus === 'authenticated' && pathname === '/') {
      navigate('/drive', { replace: true })
    }
  }, [authStatus, pathname])
}
