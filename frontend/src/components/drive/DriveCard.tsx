import type { PropsWithChildren } from 'react'

type DriveCardVariant = 'default' | 'loading' | 'error'

interface DriveCardProps extends PropsWithChildren {
  variant?: DriveCardVariant
  banner?: string | null
  role?: string
  ariaBusy?: boolean
}

export function DriveCard({ variant = 'default', banner, role, ariaBusy, children }: DriveCardProps) {
  const classes = ['drive-card']
  if (variant === 'loading') {
    classes.push('drive-card--loading')
  }
  if (variant === 'error') {
    classes.push('drive-card--error')
  }

  return (
    <section className={classes.join(' ')} role={role} aria-busy={ariaBusy}>
      {banner && <div className="drive-card__banner drive-card__banner--success">{banner}</div>}
      {children}
    </section>
  )
}
