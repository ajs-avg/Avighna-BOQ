"use client";

import { KeyRound } from "lucide-react";
import { useState, type FormEvent } from "react";
import { setPassword } from "@/lib/api";
import { useUser } from "@/lib/user-context";
import { errorMessage } from "@/lib/utils";
import { Button } from "./ui/Button";
import { Dialog } from "./ui/Dialog";
import { Field, Input } from "./ui/Input";
import { useToast } from "./ui/Toast";

export function ChangePasswordDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const toast = useToast();
  const { setProfile } = useUser();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reset = () => {
    setCurrent("");
    setNext("");
    setConfirm("");
    setError(null);
  };

  const close = () => {
    if (busy) return;
    reset();
    onClose();
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (next.length < 8) {
      setError("New password must be at least 8 characters.");
      return;
    }
    if (next !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const profile = await setPassword({ password: next, current_password: current });
      setProfile(profile);
      toast.success("Password updated");
      reset();
      onClose();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onClose={close} locked={busy} title="Change password" description="Choose a strong password of at least 8 characters." icon={<KeyRound />}>
      <form id="change-password-form" onSubmit={submit} className="space-y-4 pt-1">
        <Field label="Current password" required>
          {(id) => <Input id={id} type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} required />}
        </Field>
        <Field label="New password" required>
          {(id) => <Input id={id} type="password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} minLength={8} required />}
        </Field>
        <Field label="Confirm new password" required error={error}>
          {(id) => <Input id={id} type="password" autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} required invalid={!!error} />}
        </Field>
        <div className="flex justify-end gap-2 pt-1">
          <Button variant="secondary" onClick={close} disabled={busy}>
            Cancel
          </Button>
          <Button type="submit" loading={busy}>
            Update password
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
