import type { PropsWithChildren } from 'react'

export function PageLayout({ children }: PropsWithChildren) {
  return <div className="page">{children}</div>
}
