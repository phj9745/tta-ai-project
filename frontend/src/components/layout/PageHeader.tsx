interface PageHeaderProps {
  eyebrow?: string
  title: string
  subtitle?: string
}

export function PageHeader({ eyebrow, title, subtitle }: PageHeaderProps) {
  return (
    <header className="page__header">
      {eyebrow && <span className="page__eyebrow">{eyebrow}</span>}
      <h1 className="page__title">{title}</h1>
      {subtitle && <p className="page__subtitle">{subtitle}</p>}
    </header>
  )
}
