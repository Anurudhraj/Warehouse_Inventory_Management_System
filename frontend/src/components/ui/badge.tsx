import type { HTMLAttributes } from 'react';

import { cn } from '@/lib/utils/cn';

export type BadgeVariant =
  | 'neutral'
  | 'primary'
  | 'success'
  | 'warning'
  | 'danger'
  | 'info'
  | 'outline';

const variants: Record<BadgeVariant, string> = {
  neutral: 'bg-muted text-secondary-foreground border-transparent',
  primary: 'bg-accent text-accent-foreground border-transparent',
  success: 'bg-success-soft text-success-foreground border-transparent',
  warning: 'bg-warning-soft text-warning-foreground border-transparent',
  danger: 'bg-danger-soft text-danger-foreground border-transparent',
  info: 'bg-info-soft text-info-foreground border-transparent',
  outline: 'border-border-strong text-muted-foreground',
};

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
  dot?: boolean;
}

export function Badge({ className, variant = 'neutral', dot = false, children, ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-medium',
        'whitespace-nowrap leading-5',
        variants[variant],
        className,
      )}
      {...props}
    >
      {dot ? <span className="size-1.5 rounded-full bg-current" aria-hidden="true" /> : null}
      {children}
    </span>
  );
}
