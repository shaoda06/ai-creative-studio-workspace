export function SearchField({ label, placeholder, value, onChange, disabled = false, size = 'default', focusStyle }: { label: string; placeholder: string; value: string; onChange: (value: string) => void; disabled?: boolean; size?: 'default' | 'compact'; focusStyle?: 'inset' }) {
  return <input type="search" className={`search-field${size === 'compact' ? ' search-field-compact' : ''}`} data-focus-style={focusStyle}
    aria-label={label} placeholder={placeholder} value={value} disabled={disabled} onChange={event => onChange(event.target.value)} />;
}
