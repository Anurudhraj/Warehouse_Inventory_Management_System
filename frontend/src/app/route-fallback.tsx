import { Spinner } from '@/components/ui';

/** Suspense fallback shown while a lazily-loaded route chunk resolves. */
export function RouteFallback() {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-3" role="status">
      <Spinner className="size-5" />
      <p className="text-muted-foreground text-xs">Loading workspace…</p>
    </div>
  );
}
