"use client";

import { Eye, EyeOff, KeyRound } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { Alert } from "@/components/ui/Alert";
import { Button, IconButton } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Input";
import { setPassword as apiSetPassword } from "@/lib/api";
import { getStoredProfile, getToken, storeProfile } from "@/lib/auth";

function strength(pw: string): { score: number; label: string } {
  let s = 0;
  if (pw.length >= 8) s += 1;
  if (pw.length >= 12) s += 1;
  if (/[A-Z]/.test(pw) && /[a-z]/.test(pw)) s += 1;
  if (/\d/.test(pw)) s += 1;
  if (/[^A-Za-z0-9]/.test(pw)) s += 1;
  const label = s <= 1 ? "Weak" : s <= 3 ? "Fair" : "Strong";
  return { score: s, label };
}

export default function SetPasswordPage() {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [email, setEmail] = useState<string | null>(null);
  const [firstTime, setFirstTime] = useState(true);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login?next=%2Fset-password");
      return;
    }
    const p = getStoredProfile();
    setEmail(p?.email ?? null);
    setFirstTime(p ? p.must_set_password : true);
  }, [router]);

  const st = strength(password);
  const mismatch = confirm.length > 0 && confirm !== password;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const profile = await apiSetPassword({ password, current_password: null });
      storeProfile(profile);
      window.location.assign("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not set the password");
      setBusy(false);
    }
  };

  return (
    <div>
      <div className="mb-4 inline-flex size-11 items-center justify-center rounded-xl bg-brand-soft text-brand">
        <KeyRound className="size-5" />
      </div>
      <h1 className="text-[22px] font-semibold tracking-tight text-ink">{firstTime ? "Set your password" : "Choose a new password"}</h1>
      <p className="mt-1 text-[13.5px] text-muted">
        {firstTime ? "Your account was created with a temporary password. Choose your own to continue." : "Pick a strong password of at least 8 characters."}
        {email ? (
          <>
            {" "}
            Signed in as <span className="font-medium text-ink">{email}</span>.
          </>
        ) : null}
      </p>

      <form onSubmit={submit} className="mt-6 space-y-4" noValidate>
        {error ? (
          <Alert tone="danger" title="Could not set password">
            {error}
          </Alert>
        ) : null}
        <Field
          label="New password"
          required
          hint={
            password ? (
              <span className="flex items-center gap-2">
                <span className="flex h-1.5 w-24 overflow-hidden rounded-full bg-surface-3">
                  <span
                    className={st.score <= 1 ? "bg-danger" : st.score <= 3 ? "bg-warning" : "bg-success"}
                    style={{ width: `${(st.score / 5) * 100}%` }}
                  />
                </span>
                {st.label}
              </span>
            ) : (
              "At least 8 characters."
            )
          }
        >
          {(id) => (
            <Input
              id={id}
              type={show ? "text" : "password"}
              autoComplete="new-password"
              autoFocus
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              minLength={8}
              required
              rightSlot={
                <IconButton label={show ? "Hide password" : "Show password"} size="xs" onClick={() => setShow((v) => !v)} tabIndex={-1}>
                  {show ? <EyeOff /> : <Eye />}
                </IconButton>
              }
            />
          )}
        </Field>
        <Field label="Confirm password" required error={mismatch ? "Passwords do not match." : undefined}>
          {(id) => (
            <Input
              id={id}
              type={show ? "text" : "password"}
              autoComplete="new-password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              required
              invalid={mismatch}
            />
          )}
        </Field>
        <Button type="submit" size="lg" block loading={busy} disabled={password.length < 8 || password !== confirm}>
          Save password and continue
        </Button>
      </form>
    </div>
  );
}
