import { Loader2 } from 'lucide-react';

import { cn } from '@/lib/utils/cn';

export function Spinner({ className }: { className?: string }) {
  return (
    <Loader2
      className={cn('text-muted-foreground size-4 animate-spin', className)}
      aria-hidden="true"
    />
  );
}

export function LoadingOverlay({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="text-muted-foreground flex items-center justify-center gap-2 py-12 text-sm" role="status">
      <Spinner />
      {label}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn('bg-muted animate-pulse rounded-md', className)} aria-hidden="true" />;
}
