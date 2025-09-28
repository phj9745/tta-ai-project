interface DriveAccountBadgeProps {
  displayName: string
  email?: string | null
}

export function DriveAccountBadge({ displayName, email }: DriveAccountBadgeProps) {
  return (
    <div className="drive-page__account" role="note">
      <span className="drive-page__account-name">{displayName}</span>
      {email && <span className="drive-page__account-email">{email}</span>}
    </div>
  )
}
