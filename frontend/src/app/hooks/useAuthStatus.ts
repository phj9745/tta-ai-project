import { useEffect, useState } from 'react'

import type { AuthStatus } from '../../auth'
import { getAuthStatus, subscribeToAuth } from '../../auth'

export function useAuthStatus(): AuthStatus {
  const [authStatus, setAuthStatus] = useState<AuthStatus>(() => getAuthStatus())

  useEffect(() => {
    const unsubscribe = subscribeToAuth(setAuthStatus)
    return unsubscribe
  }, [])

  return authStatus
}
