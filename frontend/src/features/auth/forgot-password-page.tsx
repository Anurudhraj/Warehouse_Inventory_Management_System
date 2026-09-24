/**
 * Password reset request.
 *
 * The endpoint always answers the same way (account-enumeration defence), so
 * the screen always shows the same confirmation.
 */
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { MailCheck, Send } from 'lucide-react';

import { Alert, Button, Card, CardContent, Field, Input } from '@/components/ui';
import { env } from '@/config/env';
import { isApiError } from '@/lib/api/errors';

import { authApi } from './api';

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await authApi.requestPasswordReset(email);
      setSent(true);
    } catch (caught) {
      setError(
        isApiError(caught) ? caught.message : 'The request could not be sent. Please try again.',
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="bg-canvas flex min-h-dvh items-center justify-center px-4 py-10">
      <div className="w-full max-w-sm space-y-6">
        <div className="flex flex-col items-center gap-2 text-center">
          <img src="/favicon.svg" alt="" className="size-10" aria-hidden="true" />
          <h1 className="text-xl font-semibold tracking-tight">Reset your {env.appName} password</h1>
          <p className="text-muted-foreground text-sm">
            We will email a single-use link that expires after an hour.
          </p>
        </div>

        <Card>
          <CardContent className="space-y-4 pt-4">
            {sent ? (
              <Alert variant="success" title="Check your inbox">
                If an account exists for <strong>{email}</strong>, a reset link is on
                its way. The link can only be used once.
              </Alert>
            ) : (
              <form className="space-y-4" onSubmit={handleSubmit} noValidate>
                {error ? (
                  <Alert variant="danger" title="Could not send the link">
                    {error}
                  </Alert>
                ) : null}

                <Field label="Email address" htmlFor="reset-email">
                  <Input
                    id="reset-email"
                    type="email"
                    autoComplete="username"
                    autoFocus
                    required
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    placeholder="you@company.com"
                  />
                </Field>

                <Button type="submit" className="w-full" loading={busy} icon={<Send className="size-4" />}>
                  Email me a reset link
                </Button>
              </form>
            )}

            <div className="text-center text-xs">
              <Link to="/login" className="text-primary inline-flex items-center gap-1.5 hover:underline">
                <MailCheck className="size-3" aria-hidden="true" />
                Back to sign in
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
