import type { ReactNode } from 'react';

export function PageHeader({ eyebrow, title, description, actions, children, eyebrowInline = false, stacked = false }: { eyebrow?: string; title: string; description?: string; actions?: ReactNode; children?: ReactNode; eyebrowInline?: boolean; stacked?: boolean }) {
  const heading = <>{eyebrow && !eyebrowInline && <p className="eyebrow">{eyebrow}</p>}<div className="page-title"><h1>{title}</h1>{eyebrow && eyebrowInline && <p className="eyebrow">{eyebrow}</p>}</div>{description && <p className="page-description">{description}</p>}</>;
  const actionRow = actions && <div className="page-actions">{actions}</div>;
  return stacked ? <div className="page-heading page-heading-stacked"><div>
    <div className="page-heading-title-row"><div>{heading}</div>{actionRow}</div>
    {children}
  </div></div> : <div className="page-heading"><div>{heading}{children}</div>{actionRow}</div>;
}
