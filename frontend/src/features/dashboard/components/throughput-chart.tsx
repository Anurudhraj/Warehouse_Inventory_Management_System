import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui';
import { throughputSeries } from '@/features/dashboard/sample-data';
import { formatNumber } from '@/lib/utils/format';

/** Dependency-free bar chart — renders from CSS, scales to its container. */
export function ThroughputChart() {
  const max = Math.max(...throughputSeries.map((point) => point.value));
  const total = throughputSeries.reduce((sum, point) => sum + point.value, 0);

  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle>Order lines processed</CardTitle>
        <CardDescription>
          {formatNumber(total)} lines in the last 24h · sample data until the Orders module lands
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex h-44 items-end gap-1.5" role="img" aria-label="Hourly throughput bar chart">
          {throughputSeries.map((point) => (
            <div key={point.label} className="group flex h-full flex-1 flex-col justify-end gap-1.5">
              <div
                className="bg-primary/80 group-hover:bg-primary w-full rounded-t-sm transition-colors"
                style={{ height: `${Math.max((point.value / max) * 100, 2)}%` }}
                title={`${point.label}:00 — ${formatNumber(point.value)} lines`}
              />
              <span className="text-muted-foreground text-center text-[10px] tabular-nums">
                {point.label}
              </span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
