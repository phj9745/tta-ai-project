import type { PropsWithChildren } from 'react'

type DriveCardVariant = 'default' | 'loading' | 'error'
type DriveCardBannerVariant = 'success' | 'error'

interface DriveCardProps extends PropsWithChildren {
  variant?: DriveCardVariant
  banner?: string | null
  bannerVariant?: DriveCardBannerVariant
  role?: string
  ariaBusy?: boolean
}

export function DriveCard({
  variant = 'default',
  banner,
  bannerVariant = 'success',
  role,
  ariaBusy,
  children,
}: DriveCardProps) {
  const classes = ['drive-card']
  if (variant === 'loading') {
    classes.push('drive-card--loading')
  }
  if (variant === 'error') {
    classes.push('drive-card--error')
  }

  return (
    <section className={classes.join(' ')} role={role} aria-busy={ariaBusy}>
      {banner && (
        <div className={`drive-card__banner drive-card__banner--${bannerVariant}`}>{banner}</div>
      )}
      {children}
    </section>
  )
}
