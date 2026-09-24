import { useId, useState, type ReactNode } from 'react';

import { cn } from '@/lib/utils/cn';

export interface TooltipProps {
  content: ReactNode;
  children: ReactNode;
  side?: 'top' | 'right' | 'bottom';
  className?: string;
}

/**
 * Lightweight, dependency-free tooltip: shows on hover and keyboard focus.
 * Uses `aria-describedby` so screen readers announce the same content.
 */
export function Tooltip({ content, children, side = 'right', className }: TooltipProps) {
  const [open, setOpen] = useState(false);
  const id = useId();

  const positions = {
    top: 'bottom-full left-1/2 -translate-x-1/2 mb-2',
    right: 'left-full top-1/2 -translate-y-1/2 ml-2',
    bottom: 'top-full left-1/2 -translate-x-1/2 mt-2',
  } as const;

  return (
    <span
      className={cn('relative inline-flex', className)}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
    >
      <span aria-describedby={open ? id : undefined}>{children}</span>
      {open && content ? (
        <span
          role="tooltip"
          id={id}
          className={cn(
            'bg-popover text-popover-foreground border-border animate-fade-in z-50 max-w-xs rounded-md border',
            'px-2.5 py-1.5 text-xs leading-relaxed shadow-overlay',
            positions[side],
          )}
        >
          {content}
        </span>
      ) : null}
    </span>
  );
}
