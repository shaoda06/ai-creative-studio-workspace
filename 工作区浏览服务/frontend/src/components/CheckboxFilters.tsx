import type { ReactNode } from 'react';
import { LinkButton } from './LinkButton';
import './CheckboxFilters.css';

export function CheckboxFilters({ options, selected, onChange, label = '按类型筛选', headerAction, renderOption }: {
  options: string[];
  selected: string[];
  onChange: (options: string[]) => void;
  label?: string;
  headerAction?: ReactNode;
  renderOption?: (option: string) => ReactNode;
}) {
  return <fieldset className="checkbox-filters" aria-label={label}>
    <legend>
      <span className="checkbox-filters-heading">
        <span>{label}</span>
        {headerAction}
        <LinkButton className="checkbox-filters-clear" disabled={!selected.length} onClick={() => onChange([])}>清空</LinkButton>
      </span>
    </legend>
    {options.map(option => <label key={option}>
      <input type="checkbox" checked={selected.includes(option)}
        onChange={event => onChange(event.target.checked ? [...selected, option] : selected.filter(value => value !== option))} />
      {renderOption ? renderOption(option) : option}
    </label>)}
  </fieldset>;
}
