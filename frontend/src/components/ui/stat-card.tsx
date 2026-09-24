import type { ReactNode } from 'react';
import { ArrowDownRight, ArrowUpRight, Minus } from 'lucide-react';

import { Card } from '@/components/ui/card';
import { cn } from '@/lib/utils/cn';

export type TrendDirection = 'up' | 'down' | 'flat';

export interface StatCardProps {
  label: string;
  value: string | number;
  unit?: string;
  icon?: ReactNode;
  delta?: { value: string; direction: TrendDirection; label?: string };
  hint?: string;
  className?: string;
}

const trendStyles: Record<TrendDirection, { className: string; icon: ReactNode }> = {
  up: { className: 'text-success-foreground', icon: <ArrowUpRight className="size-3.5" /> },
  down: { className: 'text-danger-foreground', icon: <ArrowDownRight className="size-3.5" /> },
  flat: { className: 'text-muted-foreground', icon: <Minus className="size-3.5" /> },
};

export function StatCard({ label, value, unit, icon, delta, hint, className }: StatCardProps) {
  return (
    <Card className={cn('p-5', className)}>
      <div className="flex items-start justify-between gap-3">
        <p className="text-muted-foreground text-xs font-medium tracking-wide uppercase">{label}</p>
        {icon ? (
          <span className="bg-accent text-accent-foreground flex size-8 items-center justify-center rounded-md">
            {icon}
          </span>
        ) : null}
      </div>
      <div className="mt-3 flex items-baseline gap-1.5">
        <span className="text-2xl font-semibold tracking-tight tabular-nums">{value}</span>
        {unit ? <span className="text-muted-foreground text-xs font-medium">{unit}</span> : null}
      </div>
      <div className="mt-2 flex items-center gap-3">
        {delta ? (
          <span className={cn('inline-flex items-center gap-1 text-xs font-medium', trendStyles[delta.direction].className)}>
            {trendStyles[delta.direction].icon}
            {delta.value}
            {delta.label ? <span className="text-muted-foreground font-normal">{delta.label}</span> : null}
          </span>
        ) : null}
        {hint ? <span className="text-muted-foreground text-xs">{hint}</span> : null}
      </div>
    </Card>
  );
}
