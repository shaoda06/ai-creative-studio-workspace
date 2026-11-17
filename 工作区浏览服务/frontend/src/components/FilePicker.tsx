import { useId, useRef } from 'react';
import './FilePicker.css';

export function FilePicker({ label, accept, fileName, onSelect, chooseLabel = '选择文件', disabled = false }: {
  label: string;
  accept?: string;
  fileName?: string;
  onSelect: (file: File) => void;
  chooseLabel?: string;
  disabled?: boolean;
}) {
  const input = useRef<HTMLInputElement>(null);
  const statusId = useId();
  return <div className="file-picker">
    <span className="file-picker-label">{label}</span>
    <input ref={input} type="file" aria-label={label} accept={accept} hidden disabled={disabled}
      onChange={event => {
        const file = event.currentTarget.files?.[0];
        event.currentTarget.value = '';
        if (file) onSelect(file);
      }} />
    <div className="file-picker-row">
      <span className={fileName ? 'file-picker-name' : 'file-picker-name muted'} id={statusId} role="status">
        {fileName || '未选择文件'}
      </span>
      <button type="button" aria-describedby={statusId} disabled={disabled} onClick={() => input.current?.click()}>
        {fileName ? '更换文件' : chooseLabel}
      </button>
    </div>
  </div>;
}
