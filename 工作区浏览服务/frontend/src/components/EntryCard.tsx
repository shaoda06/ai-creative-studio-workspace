import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import './EntryCard.css';

export function EntryCard({ to, title, description, icon, compact = false }: { to: string; title: string; description: string; icon?: ReactNode; compact?: boolean }) {
  return <Link className={`project-card${compact ? ' project-card-compact' : ''}`} to={to}>{icon && <span className="project-icon">{icon}</span>}<h3>{title}</h3><p>{description}<span>→</span></p></Link>;
}
