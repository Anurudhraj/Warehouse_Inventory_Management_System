import type { HTMLAttributes, ReactNode } from 'react';
import { AlertTriangle, CheckCircle2, Info, OctagonAlert } from 'lucide-react';

import { cn } from '@/lib/utils/cn';

export type AlertVariant = 'info' | 'success' | 'warning' | 'danger';

const variants: Record<AlertVariant, { wrapper: string; icon: ReactNode }> = {
  info: {
    wrapper: 'border-info/30 bg-info-soft text-info-foreground',
    icon: <Info className="size-4 shrink-0" aria-hidden="true" />,
  },
  success: {
    wrapper: 'border-success/30 bg-success-soft text-success-foreground',
    icon: <CheckCircle2 className="size-4 shrink-0" aria-hidden="true" />,
  },
  warning: {
    wrapper: 'border-warning/30 bg-warning-soft text-warning-foreground',
    icon: <AlertTriangle className="size-4 shrink-0" aria-hidden="true" />,
  },
  danger: {
    wrapper: 'border-danger/30 bg-danger-soft text-danger-foreground',
    icon: <OctagonAlert className="size-4 shrink-0" aria-hidden="true" />,
  },
};

export interface AlertProps extends HTMLAttributes<HTMLDivElement> {
  variant?: AlertVariant;
  title?: string;
  icon?: ReactNode;
}

export function Alert({ className, variant = 'info', title, icon, children, ...props }: AlertProps) {
  return (
    <div
      role={variant === 'danger' ? 'alert' : 'status'}
      className={cn('flex items-start gap-3 rounded-lg border px-4 py-3 text-sm', variants[variant].wrapper, className)}
      {...props}
    >
      {icon ?? variants[variant].icon}
      <div className="flex flex-col gap-0.5">
        {title ? <p className="font-semibold">{title}</p> : null}
        {children ? <div className="text-[13px] leading-relaxed opacity-90">{children}</div> : null}
      </div>
    </div>
  );
}
