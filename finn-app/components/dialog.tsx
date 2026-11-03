'use client';
import { useEffect, useRef, type ReactNode } from 'react';
import { X } from 'lucide-react';

export default function Dialog({ title, subtitle, close, children, wide = false }: { title: string; subtitle?: string; close: () => void; children: ReactNode; wide?: boolean }) {
  const reference = useRef<HTMLElement>(null);
  useEffect(() => {
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    reference.current?.querySelector<HTMLElement>('button, input, a[href]')?.focus();
    const handler = (event: KeyboardEvent) => {
      if (event.key === 'Escape') close();
      if (event.key !== 'Tab') return;
      const elements = Array.from(reference.current?.querySelectorAll<HTMLElement>('button:not([disabled]), a[href], input, select, summary, [tabindex="0"]') || []).filter(element => element.getClientRects().length > 0);
      if (!elements?.length) return;
      const first = elements[0], last = elements[elements.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener('keydown', handler);
    return () => { document.body.style.overflow = previousOverflow; document.removeEventListener('keydown', handler); previouslyFocused?.focus(); };
  }, [close]);
  return <div className="dialog-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) close(); }}><section ref={reference} role="dialog" aria-modal="true" aria-label={title} className={`dialog-panel ${wide ? 'dialog-wide' : ''}`}><header className="dialog-header"><div>{subtitle && <p className="eyebrow">{subtitle}</p>}<h2>{title}</h2></div><button className="icon-button" aria-label={`Close ${title}`} onClick={close}><X size={20}/></button></header><div className="dialog-content">{children}</div></section></div>;
}
