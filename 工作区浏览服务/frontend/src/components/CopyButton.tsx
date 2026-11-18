import { useRef, useState } from 'react';
import { useNotify } from './Notifications';
import { LinkButton } from './LinkButton';

export async function copyText(text: string, buffer: HTMLTextAreaElement) {
  if (navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(text);
  else {
    buffer.select();
    if (!document.execCommand('copy')) throw new Error('当前浏览器不支持自动复制');
  }
}

export function CopyButton({ text, label, ariaLabel, appearance = 'button', successMessage = '已复制' }: {
  text: string; label: string; ariaLabel?: string; appearance?: 'button' | 'link'; successMessage?: string;
}) {
  const Button = appearance === 'link' ? LinkButton : 'button';
  const notify = useNotify();
  const [message, setMessage] = useState('');
  const buffer = useRef<HTMLTextAreaElement>(null);
  return <><Button aria-label={ariaLabel} onClick={async event => {
    const button = event.currentTarget;
    try { await copyText(text, buffer.current!); setMessage('已复制'); notify(successMessage); }
    catch (error) {
      const failure = `复制失败：${String(error)}；可选中下方文本复制。`;
      setMessage(failure);
      notify(failure, 'error');
    }
    button.focus();
  }}>{label}</Button><textarea ref={buffer} className="clipboard-buffer" aria-hidden="true" tabIndex={-1} readOnly value={text} />{message.includes('选中') && <textarea aria-label="手动复制内容" readOnly value={text} onFocus={event => event.currentTarget.select()} />}</>;
}
