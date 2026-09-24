
import { Activity, Database, Layers, RefreshCw, ShieldCheck, Timer, Wifi } from 'lucide-react';

import {
  Alert,
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  PageHeader,
  Skeleton,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui';
import { useLiveness, useReadiness, useSystemHealth } from '@/features/health/hooks';
import { env } from '@/config/env';
import { formatDateTime } from '@/lib/utils/format';
import { cn } from '@/lib/utils/cn';

function StatusPill({ status }: { status?: string }) {
  const variant =
    status === 'ok' || status === 'alive' || status === 'ready'
      ? 'success'
      : status === 'degraded'
        ? 'warning'
        : 'danger';
  return (
    <Badge variant={variant} dot>
      {status ?? 'unknown'}
    </Badge>
  );
}

export function SystemHealthPage() {
  const health = useSystemHealth();
  const liveness = useLiveness();
  const readiness = useReadiness();

  const probes = [
    {
      name: 'Liveness',
      path: '/api/v1/health/live/',
      icon: Activity,
      query: liveness,
      description: 'Process is up and serving requests.',
    },
    {
      name: 'Readiness',
      path: '/api/v1/health/ready/',
      icon: ShieldCheck,
      query: readiness,
      description: 'Database reachable — safe to route traffic here.',
    },
    {
      name: 'Deep health',
      path: '/api/v1/health/',
      icon: Wifi,
      query: health,
      description: 'PostgreSQL and Redis connectivity with latency.',
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Platform"
        title="System health"
        description="Probes exposed by the backend for orchestrators, load balancers and uptime monitoring."
        actions={
          <Button
            variant="outline"
            icon={<RefreshCw className={cn('size-4', health.isFetching && 'animate-spin')} />}
            onClick={() => {
              void health.refetch();
              void liveness.refetch();
              void readiness.refetch();
            }}
          >
            Re-probe now
          </Button>
        }
      />

      {health.isError ? (
        <Alert variant="danger" title="Backend unreachable">
          No response from <code className="font-mono">{env.apiBaseUrl}/health/</code>. Start the
          API (<code className="font-mono">docker compose up api</code> or{' '}
          <code className="font-mono">python manage.py runserver</code>) and re-probe.
        </Alert>
      ) : null}

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Card className="p-5">
          <p className="text-muted-foreground text-xs font-medium tracking-wide uppercase">
            API status
          </p>
          <div className="mt-3 flex items-center gap-2">
            {health.isPending ? <Skeleton className="h-5 w-24" /> : <StatusPill status={health.data?.status ?? (health.isError ? 'error' : undefined)} />}
          </div>
          <p className="text-muted-foreground mt-2 text-xs">
            {health.dataUpdatedAt ? `Checked ${formatDateTime(health.dataUpdatedAt)}` : '—'}
          </p>
        </Card>

        <Card className="p-5">
          <p className="text-muted-foreground text-xs font-medium tracking-wide uppercase">
            Environment
          </p>
          <p className="mt-3 text-lg font-semibold">{health.data?.environment ?? '—'}</p>
          <p className="text-muted-foreground mt-2 text-xs">API version {health.data?.version ?? 'v1'}</p>
        </Card>

        <Card className="p-5">
          <p className="text-muted-foreground text-xs font-medium tracking-wide uppercase">Runtime</p>
          <p className="mt-3 flex items-center gap-2 text-lg font-semibold">
            <Timer className="text-muted-foreground size-4" aria-hidden="true" />
            Django {health.data?.django_version ?? '—'}
          </p>
          <p className="text-muted-foreground mt-2 text-xs">Celery &amp; Redis configured for async work</p>
        </Card>

        <Card className="p-5">
          <p className="text-muted-foreground text-xs font-medium tracking-wide uppercase">
            Base URL
          </p>
          <p className="mt-3 truncate font-mono text-sm">{env.apiBaseUrl}</p>
          <p className="text-muted-foreground mt-2 text-xs">
            Same-origin requests · X-Request-ID echoed on every response
          </p>
        </Card>
      </section>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Dependencies</CardTitle>
            <CardDescription>Connectivity verified from the API process</CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Dependency</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Latency</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow>
                  <TableCell className="flex items-center gap-2.5">
                    <Database className="text-muted-foreground size-4" aria-hidden="true" />
                    PostgreSQL
                  </TableCell>
                  <TableCell>
                    <StatusPill status={health.data?.checks.database?.status} />
                  </TableCell>
                  <TableCell className="text-right font-mono text-xs tabular-nums">
                    {health.data?.checks.database?.detail ?? '—'}
                  </TableCell>
                </TableRow>
                <TableRow>
                  <TableCell className="flex items-center gap-2.5">
                    <Layers className="text-muted-foreground size-4" aria-hidden="true" />
                    Redis
                  </TableCell>
                  <TableCell>
                    <StatusPill status={health.data?.checks.redis?.status} />
                  </TableCell>
                  <TableCell className="text-right font-mono text-xs tabular-nums">
                    {health.data?.checks.redis?.detail ?? '—'}
                  </TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Probe endpoints</CardTitle>
            <CardDescription>Use these from Kubernetes, ECS or your uptime monitor</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {probes.map(({ name, path, icon: Icon, query, description }) => (
              <div key={name} className="flex items-start justify-between gap-3 rounded-md border border-border px-3 py-2.5">
                <div className="flex min-w-0 items-start gap-2.5">
                  <Icon className="text-muted-foreground mt-0.5 size-4 shrink-0" aria-hidden="true" />
                  <div className="min-w-0">
                    <p className="text-[13px] font-medium">{name}</p>
                    <p className="text-muted-foreground truncate font-mono text-[11px]">{path}</p>
                    <p className="text-muted-foreground mt-1 text-[11px]">{description}</p>
                  </div>
                </div>
                <StatusPill status={query.isError ? 'error' : query.data?.status} />
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Operations runbook</CardTitle>
          <CardDescription>Common actions while the platform is being built</CardDescription>
        </CardHeader>
        <CardContent className="text-muted-foreground grid gap-3 text-xs sm:grid-cols-2">
          <p>
            API docs:{' '}
            <a
              href="/api/v1/docs/"
              target="_blank"
              rel="noreferrer"
              className="text-primary hover:underline"
            >
              Swagger UI
            </a>{' '}
            is served at <code className="font-mono">/api/v1/docs/</code> and ReDoc at{' '}
            <code className="font-mono">/api/v1/redoc/</code>.
          </p>
          <p>
            Apply migrations:{' '}
            <code className="font-mono">docker compose exec api python manage.py migrate</code>
          </p>
          <p>
            Tail worker logs: <code className="font-mono">docker compose logs -f worker</code>
          </p>
          <p>
            Restart the stack: <code className="font-mono">docker compose restart api worker</code>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
