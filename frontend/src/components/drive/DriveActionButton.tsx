import type { ButtonHTMLAttributes } from 'react'

type DriveActionVariant = 'primary' | 'compact'

interface DriveActionButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: DriveActionVariant
}

export function DriveActionButton({ variant = 'primary', className, ...props }: DriveActionButtonProps) {
  const classes = ['drive-create']
  if (variant === 'primary') {
    classes.push('drive-create--primary')
  }
  if (variant === 'compact') {
    classes.push('drive-create--compact')
  }
  if (className) {
    classes.push(className)
  }
  return <button type="button" {...props} className={classes.join(' ')} />
}
