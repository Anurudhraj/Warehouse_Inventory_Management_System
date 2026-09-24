import { Badge, Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui';
import { recentActivity } from '@/features/dashboard/sample-data';
import { formatRelativeTime, initials } from '@/lib/utils/format';

export function ActivityFeed() {
  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle>Recent activity</CardTitle>
        <CardDescription>Audit stream preview · populated by the Audit module</CardDescription>
      </CardHeader>
      <CardContent>
        <ol className="relative space-y-4 ps-5">
          <span className="bg-border absolute inset-y-1 start-[7px] w-px" aria-hidden="true" />
          {recentActivity.map((entry) => (
            <li key={entry.id} className="relative">
              <span
                className="bg-card border-primary absolute -start-5 top-1 size-3.5 rounded-full border-2"
                aria-hidden="true"
              />
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                <span className="bg-muted flex size-6 items-center justify-center rounded-full text-[10px] font-semibold">
                  {initials(entry.actor)}
                </span>
                <span className="text-[13px] font-medium">{entry.actor}</span>
                <span className="text-muted-foreground text-[13px]">{entry.action}</span>
                <Badge variant="outline">{entry.module}</Badge>
                <span className="text-muted-foreground ms-auto text-[11px]">
                  {formatRelativeTime(entry.timestamp)}
                </span>
              </div>
              <p className="text-muted-foreground mt-1 text-xs">{entry.subject}</p>
            </li>
          ))}
        </ol>
      </CardContent>
    </Card>
  );
}
