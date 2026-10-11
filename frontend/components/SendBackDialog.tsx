"use client";

import { Undo2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { rejectJob } from "@/lib/api";
import type { JobRecord } from "@/lib/types";
import { cn, errorMessage } from "@/lib/utils";
import { Alert } from "./ui/Alert";
import { Button } from "./ui/Button";
import { Dialog } from "./ui/Dialog";
import { Field, Textarea } from "./ui/Input";

/** Mirrors `RejectRequest.reason` (3..500 chars) on the API. */
export const REJECT_REASON_MIN = 3;
export const REJECT_REASON_MAX = 500;

export interface SendBackDialogProps {
  job: JobRecord;
  open: boolean;
  onClose: () => void;
  /** Called with the refreshed job after the API accepted the rejection. */
  onSent: (job: JobRecord) => void;
}

/** Reviewer "Send back for rework" dialog: asks for a reason and POSTs /jobs/{id}/reject. */
export function SendBackDialog({ job, open, onClose, onSent }: SendBackDialogProps) {
  const [reason, setReason] = useState("");
  const [touched, setTouched] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const trimmed = reason.trim();
  const tooShort = trimmed.length < REJECT_REASON_MIN;
  const tooLong = trimmed.length > REJECT_REASON_MAX;
  const invalid = tooShort || tooLong;
  const validation = tooShort
    ? `Give at least ${REJECT_REASON_MIN} characters so the engineer knows what to fix.`
    : tooLong
      ? `Keep the reason under ${REJECT_REASON_MAX} characters.`
      : null;

  const reset = () => {
    setReason("");
    setTouched(false);
    setError(null);
  };

  const close = () => {
    if (busy) return;
    reset();
    onClose();
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setTouched(true);
    if (invalid) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await rejectJob(job.id, trimmed);
      reset();
      onSent(updated);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={close}
      locked={busy}
      title="Send back for rework"
      description={`${job.project_name} — ${job.level}. The job returns to "Ready for review"${job.status === "approved" ? ", the approval is cleared" : ""} and your reason is recorded in the timeline.`}
      icon={<Undo2 />}
    >
      <form onSubmit={submit} className="space-y-4 pt-1">
        {error ? (
          <Alert tone="danger" title="Could not send back">
            {error}
          </Alert>
        ) : null}
        <Field
          label="Reason"
          required
          error={touched && validation ? validation : undefined}
          hint={
            <span className="flex items-center justify-between gap-3">
              <span>Shown to the engineer in the pipeline timeline.</span>
              <span className={cn("tnum shrink-0", tooLong ? "text-danger" : undefined)}>
                {trimmed.length} / {REJECT_REASON_MAX}
              </span>
            </span>
          }
        >
          {(id, describedBy) => (
            <Textarea
              id={id}
              aria-describedby={describedBy}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              onBlur={() => setTouched(true)}
              placeholder="e.g. Beam B3 stirrup spacing does not match the revised drawing — re-check sheet S-102."
              minLength={REJECT_REASON_MIN}
              maxLength={REJECT_REASON_MAX + 50}
              rows={4}
              required
              disabled={busy}
              invalid={touched && invalid}
              autoFocus
            />
          )}
        </Field>
        <div className="flex justify-end gap-2 pt-1">
          <Button variant="secondary" onClick={close} disabled={busy}>
            Cancel
          </Button>
          <Button type="submit" leftIcon={<Undo2 />} loading={busy} disabled={touched && invalid}>
            Send back
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
