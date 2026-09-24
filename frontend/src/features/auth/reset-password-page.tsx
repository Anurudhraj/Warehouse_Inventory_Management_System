/**
 * Consume a password reset link.
 *
 * The token is validated *before* the form is shown (so an expired link gets a
 * clear message rather than a rejected submission) and consumed exactly once.
 */
import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ShieldCheck, TriangleAlert } from 'lucide-react';

import { Alert, Button, Card, CardContent, Field, Input } from '@/components/ui';
import { Spinner } from '@/components/ui/spinner';
import { isApiError } from '@/lib/api/errors';

import { authApi } from './api';

type TokenState = 'checking' | 'valid' | 'invalid';

export function ResetPasswordPage() {
  const [params] = useSearchParams();
  const token = params.get('token') ?? '';

  const [tokenState, setTokenState] = useState<TokenState>('checking');
  const [tokenError, setTokenError] = useState('This link is invalid or has expired.');
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function validate() {
      if (!token) {
        setTokenState('invalid');
        setTokenError('This link is missing its token. Request a new reset email.');
        return;
      }
      try {
        await authApi.validateResetToken(token);
        if (!cancelled) setTokenState('valid');
      } catch (caught) {
        if (cancelled) return;
        setTokenError(
          isApiError(caught) ? caught.message : 'This link is invalid or has expired.',
        );
        setTokenState('invalid');
      }
    }

    void validate();
    return () => {
      cancelled = true;
    };
  }, [token]);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (password !== confirmation) {
      setError('The two passwords do not match.');
      return;
    }

    setBusy(true);
    try {
      await authApi.confirmPasswordReset(token, password);
      setDone(true);
    } catch (caught) {
      setError(isApiError(caught) ? caught.message : 'The password could not be reset.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="bg-canvas flex min-h-dvh items-center justify-center px-4 py-10">
      <div className="w-full max-w-sm space-y-6">
        <div className="flex flex-col items-center gap-2 text-center">
          <img src="/favicon.svg" alt="" className="size-10" aria-hidden="true" />
          <h1 className="text-xl font-semibold tracking-tight">Choose a new password</h1>
        </div>

        <Card>
          <CardContent className="space-y-4 pt-4">
            {tokenState === 'checking' ? (
              <div className="flex items-center justify-center gap-2 py-6" role="status">
                <Spinner className="size-5" />
                <span className="text-muted-foreground text-sm">Checking your link…</span>
              </div>
            ) : null}

            {tokenState === 'invalid' ? (
              <>
                <Alert variant="danger" title="This link cannot be used">
                  {tokenError}
                </Alert>
                <p className="text-center text-sm">
                  <Link to="/forgot-password" className="text-primary hover:underline">
                    Request a new link
                  </Link>
                </p>
              </>
            ) : null}

            {tokenState === 'valid' && done ? (
              <Alert variant="success" title="Password updated">
                You can now <Link to="/login" className="underline">sign in</Link> with your new
                password. Other sessions were signed out.
              </Alert>
            ) : null}

            {tokenState === 'valid' && !done ? (
              <form className="space-y-4" onSubmit={handleSubmit} noValidate>
                {error ? (
                  <Alert variant="danger" title="Password not changed">
                    {error}
                  </Alert>
                ) : null}

                <Field
                  label="New password"
                  htmlFor="new-password"
                  hint="At least 12 characters; not a commonly used password."
                >
                  <Input
                    id="new-password"
                    type="password"
                    autoComplete="new-password"
                    autoFocus
                    required
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                  />
                </Field>

                <Field label="Confirm password" htmlFor="confirm-password">
                  <Input
                    id="confirm-password"
                    type="password"
                    autoComplete="new-password"
                    required
                    value={confirmation}
                    onChange={(event) => setConfirmation(event.target.value)}
                  />
                </Field>

                <Button
                  type="submit"
                  className="w-full"
                  loading={busy}
                  icon={<ShieldCheck className="size-4" />}
                >
                  Set new password
                </Button>

                <p className="text-muted-foreground flex items-start gap-1.5 text-xs">
                  <TriangleAlert className="mt-0.5 size-3 shrink-0" aria-hidden="true" />
                  A rejected password does not consume the link — you can try again.
                </p>
              </form>
            ) : null}
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
