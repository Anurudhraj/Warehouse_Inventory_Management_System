import { cn } from '@/lib/utils/cn';

export interface ProgressProps {
  value: number;
  max?: number;
  label?: string;
  className?: string;
  tone?: 'primary' | 'success' | 'warning' | 'danger';
}

const tones = {
  primary: 'bg-primary',
  success: 'bg-success',
  warning: 'bg-warning',
  danger: 'bg-danger',
} as const;

export function Progress({ value, max = 100, label, className, tone = 'primary' }: ProgressProps) {
  const clamped = Math.max(0, Math.min(value, max));
  const percent = max === 0 ? 0 : (clamped / max) * 100;

  return (
    <div className={cn('flex flex-col gap-1.5', className)}>
      {label ? (
        <div className="flex items-center justify-between text-xs">
          <span className="text-muted-foreground">{label}</span>
          <span className="font-medium tabular-nums">{percent.toFixed(0)}%</span>
        </div>
      ) : null}
      <div
        className="bg-muted h-1.5 w-full overflow-hidden rounded-full"
        role="progressbar"
        aria-valuenow={Math.round(percent)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label}
      >
        <div
          className={cn('h-full rounded-full transition-[width] duration-300', tones[tone])}
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}
