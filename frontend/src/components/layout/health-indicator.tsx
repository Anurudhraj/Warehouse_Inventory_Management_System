import { Link } from 'react-router-dom';

import { Tooltip } from '@/components/ui/tooltip';
import { useSystemHealth } from '@/features/health/hooks';
import { cn } from '@/lib/utils/cn';

type HealthState = 'loading' | 'ok' | 'degraded' | 'offline';

const stateStyles: Record<HealthState, { dot: string; label: string; text: string }> = {
  loading: { dot: 'bg-muted-foreground animate-pulse-ring', label: 'Checking…', text: 'text-sidebar-muted' },
  ok: { dot: 'bg-emerald-400', label: 'API operational', text: 'text-emerald-300' },
  degraded: { dot: 'bg-amber-400', label: 'Degraded', text: 'text-amber-300' },
  offline: { dot: 'bg-rose-500', label: 'API unreachable', text: 'text-rose-300' },
};

export function HealthIndicator() {
  const health = useSystemHealth();

  const state: HealthState = health.isPending
    ? 'loading'
    : health.isError
      ? 'offline'
      : health.data?.status === 'ok'
        ? 'ok'
        : 'degraded';

  const style = stateStyles[state];
  const details =
    state === 'offline'
      ? 'The backend did not respond. Start the API or check the network.'
      : state === 'degraded'
        ? Object.entries(health.data?.checks ?? {})
            .filter(([, value]) => value.status !== 'ok')
            .map(([name, value]) => `${name}: ${value.detail ?? 'error'}`)
            .join(' · ') || 'A dependency is unhealthy.'
        : `Environment ${health.data?.environment ?? '—'} · API ${health.data?.version ?? 'v1'}`;

  return (
    <Tooltip content={details}>
      <Link
        to="/system/health"
        className="hover:bg-sidebar-accent flex items-center gap-2 rounded-md px-2.5 py-2 text-xs transition-colors"
        aria-label={`System health: ${style.label}`}
      >
        <span className={cn('size-2 rounded-full', style.dot)} aria-hidden="true" />
        <span className={cn('font-medium', style.text)}>{style.label}</span>
      </Link>
    </Tooltip>
  );
}
