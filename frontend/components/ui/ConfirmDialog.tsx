"use client";

import { AlertTriangle, HelpCircle } from "lucide-react";
import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";
import { Button } from "./Button";
import { Dialog } from "./Dialog";

export interface ConfirmOptions {
  title: ReactNode;
  message?: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
  /** Async work to run on confirm; the dialog stays open (locked) until it settles. */
  onConfirm?: () => Promise<void> | void;
}

type ConfirmFn = (options: ConfirmOptions) => Promise<boolean>;

const ConfirmContext = createContext<ConfirmFn | null>(null);

export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [options, setOptions] = useState<ConfirmOptions | null>(null);
  const [busy, setBusy] = useState(false);
  const resolver = useRef<((v: boolean) => void) | null>(null);

  const confirm = useCallback<ConfirmFn>((opts) => {
    return new Promise<boolean>((resolve) => {
      resolver.current = resolve;
      setOptions(opts);
    });
  }, []);

  const settle = useCallback((value: boolean) => {
    resolver.current?.(value);
    resolver.current = null;
    setOptions(null);
    setBusy(false);
  }, []);

  const handleConfirm = useCallback(async () => {
    if (!options) return;
    if (options.onConfirm) {
      setBusy(true);
      try {
        await options.onConfirm();
        settle(true);
      } catch {
        setBusy(false);
        settle(false);
      }
      return;
    }
    settle(true);
  }, [options, settle]);

  const value = useMemo(() => confirm, [confirm]);

  return (
    <ConfirmContext.Provider value={value}>
      {children}
      <Dialog
        open={options !== null}
        onClose={() => settle(false)}
        locked={busy}
        size="sm"
        title={options?.title}
        description={options?.message}
        icon={options?.danger ? <AlertTriangle /> : <HelpCircle />}
        tone={options?.danger ? "danger" : "default"}
        footer={
          <>
            <Button variant="secondary" onClick={() => settle(false)} disabled={busy}>
              {options?.cancelLabel ?? "Cancel"}
            </Button>
            <Button variant={options?.danger ? "danger" : "primary"} onClick={handleConfirm} loading={busy} data-autofocus>
              {options?.confirmLabel ?? "Confirm"}
            </Button>
          </>
        }
      />
    </ConfirmContext.Provider>
  );
}

export function useConfirm(): ConfirmFn {
  const ctx = useContext(ConfirmContext);
  if (!ctx) throw new Error("useConfirm must be used inside <ConfirmProvider>");
  return ctx;
}
