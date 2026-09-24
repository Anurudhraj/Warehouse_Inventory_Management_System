import { Link, useLocation } from 'react-router-dom';
import { Compass } from 'lucide-react';

import { Button, Card, CardContent, EmptyState } from '@/components/ui';

export function NotFoundPage() {
  const { pathname } = useLocation();

  return (
    <Card>
      <CardContent className="py-16">
        <EmptyState
          icon={<Compass className="size-5" />}
          title="Page not found"
          description={`Nothing is routed at “${pathname}”. It may have moved, or it belongs to a module that arrives in a later part of the build.`}
          action={
            <Button variant="primary">
              <Link to="/">Return to the dashboard</Link>
            </Button>
          }
        />
      </CardContent>
    </Card>
  );
}
