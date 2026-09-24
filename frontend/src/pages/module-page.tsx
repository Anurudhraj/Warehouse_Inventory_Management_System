import { Link } from 'react-router-dom';
import { ArrowLeft, CheckCircle2, Code2, Database, Route } from 'lucide-react';

import {
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  EmptyState,
  PageHeader,
} from '@/components/ui';
import type { ModuleDefinition } from '@/config/modules';
import { MODULES_BY_KEY } from '@/config/modules';

interface ModulePageProps {
  moduleKey: string;
}

const overview = [
  { key: 'orders', label: 'Orders' },
  { key: 'inventory', label: 'Inventory' },
  { key: 'warehouses', label: 'Warehouses' },
];

/**
 * Generic module landing page.
 *
 * Part 1 scaffolds the module (app, API mount, route, navigation entry);
 * the screens themselves are delivered with the module implementation in a
 * later part of the build plan.
 */
export function ModulePage({ moduleKey }: ModulePageProps) {
  const module: ModuleDefinition | undefined = MODULES_BY_KEY[moduleKey];

  if (!module) {
    return (
      <EmptyState
        title="Unknown module"
        description={`No module is registered under the key “${moduleKey}”.`}
        action={
          <Button variant="outline" icon={<ArrowLeft className="size-4" />}>
            <Link to="/">Back to dashboard</Link>
          </Button>
        }
      />
    );
  }

  const Icon = module.icon;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={module.group}
        title={module.name}
        description={module.summary}
        actions={
          <>
            <Badge variant="primary" dot>
              Scaffolded
            </Badge>
            <Badge variant="outline">Implementation in a later part</Badge>
          </>
        }
      />

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Planned capabilities</CardTitle>
            <CardDescription>Scope agreed for the {module.name} module</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {module.capabilities.map((capability) => (
              <div key={capability} className="flex items-start gap-2.5 text-sm">
                <CheckCircle2 className="text-success mt-0.5 size-4 shrink-0" aria-hidden="true" />
                <span>{capability}</span>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Wiring already in place</CardTitle>
            <CardDescription>What exists today for this module</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-xs">
            <div className="flex items-start gap-2.5">
              <Route className="text-muted-foreground mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
              <span>
                Frontend route <code className="font-mono">{module.path}</code> registered in the app
                router with lazy loading.
              </span>
            </div>
            <div className="flex items-start gap-2.5">
              <Code2 className="text-muted-foreground mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
              <span>
                Django app <code className="font-mono">apps.{module.key}</code> with
                models/serializers/views/services/tasks scaffolds and a DRF router.
              </span>
            </div>
            <div className="flex items-start gap-2.5">
              <Database className="text-muted-foreground mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
              <span>
                API mount <code className="font-mono">/api/v1/{module.key}/</code> with OpenAPI
                versioning.
              </span>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Derived from the shared module registry</CardTitle>
          <CardDescription>
            Additions to <code className="font-mono">src/config/modules.ts</code> automatically appear
            in the sidebar and router.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          {overview.map((item) => (
            <Link
              key={item.key}
              to={`/${item.key}`}
              className="border-border hover:border-primary/40 hover:bg-accent/40 flex items-center gap-2 rounded-md border px-3 py-1.5 text-xs transition-colors"
            >
              <Icon className="size-3.5" aria-hidden="true" />
              {item.label}
            </Link>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
