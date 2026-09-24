import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui';
import { MODULES } from '@/config/modules';

/** Quick access to the modules scaffolded in this part of the build. */
export function ModuleLaunchpad({ limit = 8 }: { limit?: number }) {
  const modules = MODULES.slice(0, limit);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Module launchpad</CardTitle>
        <CardDescription>
          Every domain module is routed and API-mounted; screens ship in later parts.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        {modules.map((module) => {
          const Icon = module.icon;
          return (
            <Link
              key={module.key}
              to={module.path}
              className="group border-border hover:border-primary/40 hover:bg-accent/40 flex items-center gap-3 rounded-md border px-3 py-2.5 transition-colors"
            >
              <span className="bg-muted text-muted-foreground group-hover:bg-primary/10 group-hover:text-primary flex size-8 items-center justify-center rounded-md transition-colors">
                <Icon className="size-4" aria-hidden="true" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[13px] font-medium">{module.name}</span>
                <span className="text-muted-foreground block text-[10px]">/api/v1/{module.key}/</span>
              </span>
              <ArrowRight className="text-muted-foreground size-3.5 opacity-0 transition-opacity group-hover:opacity-100" />
            </Link>
          );
        })}
        <div className="flex items-center justify-center rounded-md border border-dashed border-border px-3 py-2.5">
          <Link to="/system/health" className="text-muted-foreground hover:text-foreground text-xs">
            + System &amp; health
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}
