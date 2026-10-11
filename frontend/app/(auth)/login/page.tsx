"use client";

import { Eye, EyeOff, Lock, Mail } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState, type FormEvent } from "react";
import { Alert } from "@/components/ui/Alert";
import { Button, IconButton } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Input";
import { login } from "@/lib/api";
import { safeNext, setSession } from "@/lib/auth";
import { errorMessage } from "@/lib/utils";

export default function LoginPage() {
  return (
    <Suspense fallback={<LoginForm nextPath="/" />}>
      <LoginWithParams />
    </Suspense>
  );
}

function LoginWithParams() {
  const params = useSearchParams();
  return <LoginForm nextPath={safeNext(params.get("next"))} />;
}

function LoginForm({ nextPath }: { nextPath: string }) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await login({ email: email.trim(), password });
      setSession(res.access_token, res.profile, res.expires_in);
      if (res.profile.must_set_password) {
        router.replace("/set-password");
        return;
      }
      window.location.assign(nextPath);
    } catch (err) {
      setError(errorMessage(err, "Sign in failed"));
      setBusy(false);
    }
  };

  return (
    <div>
      <h1 className="text-[22px] font-semibold tracking-tight text-ink">Sign in</h1>
      <p className="mt-1 text-[13.5px] text-muted">Use the account your administrator created for you.</p>

      <form onSubmit={submit} className="mt-6 space-y-4" noValidate>
        {error ? (
          <Alert tone="danger" title="Could not sign in">
            {error}
          </Alert>
        ) : null}
        <Field label="Email" required>
          {(id) => (
            <Input
              id={id}
              type="email"
              autoComplete="email"
              autoFocus
              leftIcon={<Mail />}
              placeholder="you@avighnagroup.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          )}
        </Field>
        <Field label="Password" required>
          {(id) => (
            <Input
              id={id}
              type={show ? "text" : "password"}
              autoComplete="current-password"
              leftIcon={<Lock />}
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              rightSlot={
                <IconButton label={show ? "Hide password" : "Show password"} size="xs" onClick={() => setShow((v) => !v)} tabIndex={-1}>
                  {show ? <EyeOff /> : <Eye />}
                </IconButton>
              }
            />
          )}
        </Field>
        <Button type="submit" size="lg" block loading={busy} disabled={!email || !password}>
          Sign in
        </Button>
      </form>

      <p className="mt-6 text-center text-[12.5px] text-muted">
        Forgot your password? Ask your admin to reset it.
      </p>
    </div>
  );
}
