import { Link } from 'react-router-dom';
import { Database, Layers, RefreshCw, Server, Zap } from 'lucide-react';

import { Badge, Button, Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui';
import { useSystemHealth } from '@/features/health/hooks';
import { formatDateTime } from '@/lib/utils/format';
import { cn } from '@/lib/utils/cn';

function statusTone(status?: string) {
  if (status === 'ok' || status === 'alive' || status === 'ready') return 'success' as const;
  if (status === 'degraded') return 'warning' as const;
  return 'danger' as const;
}

export function SystemStatusPanel() {
  const health = useSystemHealth();

  const checks = [
    { key: 'database', label: 'PostgreSQL', icon: Database, check: health.data?.checks.database },
    { key: 'redis', label: 'Redis (broker/cache)', icon: Layers, check: health.data?.checks.redis },
  ];

  return (
    <Card className="h-full">
      <CardHeader className="flex-row items-center justify-between">
        <div>
          <CardTitle>Platform status</CardTitle>
          <CardDescription>Live dependency probe · /api/v1/health/</CardDescription>
        </div>
        <Button
          variant="ghost"
          size="icon"
          onClick={() => void health.refetch()}
          aria-label="Refresh health status"
        >
          <RefreshCw className={cn('size-4', health.isFetching && 'animate-spin')} />
        </Button>
      </CardHeader>

      <CardContent className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span
              className={cn(
                'size-2.5 rounded-full',
                health.isPending
                  ? 'bg-muted-foreground animate-pulse-ring'
                  : health.isError
                    ? 'bg-danger'
                    : health.data?.status === 'ok'
                      ? 'bg-success'
                      : 'bg-warning',
              )}
              aria-hidden="true"
            />
            <span className="text-sm font-medium">
              {health.isPending
                ? 'Checking dependencies…'
                : health.isError
                  ? 'API unreachable'
                  : health.data?.status === 'ok'
                    ? 'All systems operational'
                    : 'Degraded performance'}
            </span>
          </div>
          <Badge variant={health.isError ? 'danger' : statusTone(health.data?.status)} dot>
            {health.isError ? 'offline' : (health.data?.status ?? 'unknown')}
          </Badge>
        </div>

        <ul className="divide-border divide-y rounded-md border border-border">
          {checks.map(({ key, label, icon: Icon, check }) => (
            <li key={key} className="flex items-center justify-between px-3 py-2.5">
              <span className="flex items-center gap-2.5 text-[13px]">
                <Icon className="text-muted-foreground size-3.5" aria-hidden="true" />
                {label}
              </span>
              <span className="flex items-center gap-2 text-xs">
                <span className="text-muted-foreground font-mono tabular-nums">{check?.detail ?? '—'}</span>
                <Badge variant={check ? statusTone(check.status) : 'neutral'}>
                  {check?.status ?? 'unknown'}
                </Badge>
              </span>
            </li>
          ))}
          <li className="flex items-center justify-between px-3 py-2.5">
            <span className="flex items-center gap-2.5 text-[13px]">
              <Server className="text-muted-foreground size-3.5" aria-hidden="true" />
              Django / API version
            </span>
            <span className="text-muted-foreground text-xs">
              {health.data?.django_version ?? '—'} · {health.data?.version ?? 'v1'}
            </span>
          </li>
          <li className="flex items-center justify-between px-3 py-2.5">
            <span className="flex items-center gap-2.5 text-[13px]">
              <Zap className="text-muted-foreground size-3.5" aria-hidden="true" />
              Celery worker
            </span>
            <span className="text-muted-foreground text-xs">Configured (Part 1)</span>
          </li>
        </ul>

        <p className="text-muted-foreground text-xs">
          {health.dataUpdatedAt
            ? `Last checked ${formatDateTime(health.dataUpdatedAt)}`
            : 'Awaiting first probe…'}{' '}
          ·{' '}
          <Link to="/system/health" className="text-primary hover:underline">
            open health console
          </Link>
        </p>
      </CardContent>
    </Card>
  );
}
