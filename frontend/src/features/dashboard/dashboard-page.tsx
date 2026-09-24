import { Boxes, ClipboardList, PackageCheck, Truck } from 'lucide-react';

import { Badge, PageHeader, StatCard } from '@/components/ui';
import { ActivityFeed } from '@/features/dashboard/components/activity-feed';
import { ModuleLaunchpad } from '@/features/dashboard/components/module-launchpad';
import { SystemStatusPanel } from '@/features/dashboard/components/system-status-panel';
import { ThroughputChart } from '@/features/dashboard/components/throughput-chart';
import { WarehouseUtilizationPanel } from '@/features/dashboard/components/warehouse-utilization';

export function DashboardPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Operations overview"
        title="Warehouse control tower"
        description="A single pane for inventory health, inbound/outbound flow and platform status across every facility."
        actions={
          <>
            <Badge variant="outline" dot>
              Sample data · Part 1
            </Badge>
          </>
        }
      />

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Key metrics">
        <StatCard
          label="Active SKUs"
          value="3,142"
          icon={<Boxes className="size-4" />}
          delta={{ value: '+42', direction: 'up', label: 'vs. last week' }}
        />
        <StatCard
          label="Open orders"
          value="1,286"
          icon={<ClipboardList className="size-4" />}
          delta={{ value: '+8.4%', direction: 'up', label: 'vs. yesterday' }}
          hint="Awaiting allocation"
        />
        <StatCard
          label="Receipts today"
          value="27"
          unit="POs"
          icon={<PackageCheck className="size-4" />}
          delta={{ value: '-3', direction: 'down', label: 'vs. yesterday' }}
        />
        <StatCard
          label="On-time dispatch"
          value="96.4%"
          icon={<Truck className="size-4" />}
          delta={{ value: '+1.2 pts', direction: 'up', label: 'SLA target 95%' }}
        />
      </section>

      <section className="grid gap-4 lg:grid-cols-3" aria-label="Flow and platform status">
        <div className="lg:col-span-2">
          <ThroughputChart />
        </div>
        <SystemStatusPanel />
      </section>

      <section className="grid gap-4 lg:grid-cols-2" aria-label="Capacity and activity">
        <WarehouseUtilizationPanel />
        <ActivityFeed />
      </section>

      <ModuleLaunchpad limit={8} />
    </div>
  );
}
