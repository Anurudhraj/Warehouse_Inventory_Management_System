import { Link, useRouteError } from 'react-router-dom';
import { RefreshCw, TriangleAlert } from 'lucide-react';

import { Alert, Button, Card, CardContent, EmptyState } from '@/components/ui';

/** Router-level error boundary for render/loader failures. */
export function ServerErrorPage() {
  const error = useRouteError();
  const message =
    error instanceof Error ? error.message : typeof error === 'string' ? error : 'Unexpected error';

  return (
    <Card>
      <CardContent className="space-y-4 py-16">
        <EmptyState
          icon={<TriangleAlert className="size-5" />}
          title="Something went wrong"
          description="The page failed to render. Reload to try again — if the problem persists, check the API health console."
          action={
            <div className="flex gap-2">
              <Button
                variant="primary"
                icon={<RefreshCw className="size-4" />}
                onClick={() => window.location.reload()}
              >
                Reload
              </Button>
              <Button variant="outline">
                <Link to="/">Dashboard</Link>
              </Button>
            </div>
          }
        />
        {import.meta.env.DEV ? <Alert variant="danger" title="Error detail (dev only)">{message}</Alert> : null}
      </CardContent>
    </Card>
  );
}
