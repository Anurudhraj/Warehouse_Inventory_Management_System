import { Card, CardContent, CardDescription, CardHeader, CardTitle, Progress } from '@/components/ui';
import { warehouseUtilization } from '@/features/dashboard/sample-data';
import { formatNumber } from '@/lib/utils/format';

export function WarehouseUtilizationPanel() {
  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle>Warehouse utilization</CardTitle>
        <CardDescription>Storage capacity and SKU spread · sample data</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {warehouseUtilization.map((warehouse) => (
          <div key={warehouse.code} className="space-y-1.5">
            <div className="flex items-baseline justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate text-[13px] font-medium">{warehouse.name}</p>
                <p className="text-muted-foreground text-[11px]">
                  {warehouse.code} · {formatNumber(warehouse.bins)} bins ·{' '}
                  {formatNumber(warehouse.skus)} SKUs
                </p>
              </div>
              <span className="text-xs font-medium tabular-nums">{warehouse.utilization}%</span>
            </div>
            <Progress
              value={warehouse.utilization}
              tone={
                warehouse.utilization >= 90
                  ? 'danger'
                  : warehouse.utilization >= 80
                    ? 'warning'
                    : 'success'
              }
            />
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
