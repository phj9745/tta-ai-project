import { createContext, useContext } from 'react'
import type { ReactNode } from 'react'

interface AppShellHeaderContextValue {
  setLeadingAction: (node: ReactNode | null) => void
}

const AppShellHeaderContext = createContext<AppShellHeaderContextValue | undefined>(undefined)

export function useAppShellHeader(): AppShellHeaderContextValue {
  const context = useContext(AppShellHeaderContext)

  if (!context) {
    throw new Error('useAppShellHeader must be used within an AppShell component')
  }

  return context
}

export { AppShellHeaderContext }
