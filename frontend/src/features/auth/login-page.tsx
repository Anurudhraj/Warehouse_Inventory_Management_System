/** Sign-in screen: password step, then the MFA step when the API asks for it. */
import { useState } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { KeyRound, LockKeyhole, ShieldCheck } from 'lucide-react';

import { Alert, Button, Card, CardContent, Field, Input } from '@/components/ui';
import { env } from '@/config/env';
import { isApiError } from '@/lib/api/errors';

import { useAuth } from './auth-context';

interface LocationState {
  from?: string;
}

export function LoginPage() {
  const { status, signIn, completeMfa } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const redirectTo = (location.state as LocationState | null)?.from ?? '/';

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [code, setCode] = useState('');
  const [challengeToken, setChallengeToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (status === 'authenticated') return <Navigate to={redirectTo} replace />;

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (challengeToken) {
        await completeMfa(challengeToken, code);
        navigate(redirectTo, { replace: true });
        return;
      }
      const response = await signIn(email, password);
      if (response.mfa_required && response.challenge_token) {
        setChallengeToken(response.challenge_token);
        return;
      }
      navigate(redirectTo, { replace: true });
    } catch (caught) {
      setError(
        isApiError(caught)
          ? caught.message
          : 'Sign-in failed. Check your connection and try again.',
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
          <h1 className="text-xl font-semibold tracking-tight">
            Sign in to {env.appName}
          </h1>
          <p className="text-muted-foreground text-sm">
            {challengeToken
              ? 'Enter the code from your authenticator app.'
              : 'Use your work email address and password.'}
          </p>
        </div>

        <Card>
          <CardContent className="pt-4">
            <form className="space-y-4" onSubmit={handleSubmit} noValidate>
              {error ? (
                <Alert variant="danger" title="Sign-in failed">
                  {error}
                </Alert>
              ) : null}

              {challengeToken ? (
                <Field label="Verification code" htmlFor="mfa-code" hint="6-digit code or a recovery code">
                  <Input
                    id="mfa-code"
                    name="code"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    autoFocus
                    required
                    value={code}
                    onChange={(event) => setCode(event.target.value)}
                  />
                </Field>
              ) : (
                <>
                  <Field label="Email address" htmlFor="email">
                    <Input
                      id="email"
                      name="email"
                      type="email"
                      autoComplete="username"
                      autoFocus
                      required
                      value={email}
                      onChange={(event) => setEmail(event.target.value)}
                      placeholder="you@company.com"
                    />
                  </Field>

                  <Field label="Password" htmlFor="password">
                    <Input
                      id="password"
                      name="password"
                      type="password"
                      autoComplete="current-password"
                      required
                      value={password}
                      onChange={(event) => setPassword(event.target.value)}
                    />
                  </Field>
                </>
              )}

              <Button
                type="submit"
                className="w-full"
                loading={busy}
                icon={challengeToken ? <ShieldCheck className="size-4" /> : <KeyRound className="size-4" />}
              >
                {challengeToken ? 'Verify and continue' : 'Sign in'}
              </Button>

              {challengeToken ? (
                <Button
                  type="button"
                  variant="ghost"
                  className="w-full"
                  onClick={() => {
                    setChallengeToken(null);
                    setCode('');
                    setPassword('');
                  }}
                >
                  Start over
                </Button>
              ) : (
                <div className="flex items-center justify-between text-xs">
                  <Link to="/forgot-password" className="text-primary hover:underline">
                    Forgot your password?
                  </Link>
                  <span className="text-muted-foreground flex items-center gap-1">
                    <LockKeyhole className="size-3" aria-hidden="true" />
                    Session protected
                  </span>
                </div>
              )}
            </form>
          </CardContent>
        </Card>

        <p className="text-muted-foreground text-center text-xs">
          Access is role-based and enforced by the API. Repeated failures lock the
          account temporarily.
        </p>
      </div>
    </main>
  );
}
