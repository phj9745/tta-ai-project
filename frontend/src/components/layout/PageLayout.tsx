import type { PropsWithChildren } from 'react'

type PageLayoutVariant = 'default' | 'wide'

interface PageLayoutProps extends PropsWithChildren {
  variant?: PageLayoutVariant
}

export function PageLayout({ children, variant = 'default' }: PageLayoutProps) {
  const className = variant === 'wide' ? 'page page--wide' : 'page'

  return <div className={className}>{children}</div>
}
