"use client";

import { RefreshCw } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { AppShell } from "@/components/AppShell";
import { Logo } from "@/components/Logo";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import { UserProvider, useUser } from "@/lib/user-context";

export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <UserProvider>
      <Gate>{children}</Gate>
    </UserProvider>
  );
}

function Gate({ children }: { children: ReactNode }) {
  const { profile, loading, error, refresh, logout } = useUser();
  const router = useRouter();

  useEffect(() => {
    if (profile?.must_set_password) router.replace("/set-password");
  }, [profile, router]);

  if (!profile) {
    if (error && !loading) {
      return (
        <div className="flex min-h-screen items-center justify-center p-6">
          <div className="w-full max-w-md space-y-4">
            <Logo height={26} href={null} />
            <Alert tone="danger" title="Could not load your profile">
              {error}
            </Alert>
            <div className="flex gap-2">
              <Button leftIcon={<RefreshCw />} onClick={() => void refresh()}>
                Retry
              </Button>
              <Button variant="secondary" onClick={logout}>
                Sign in again
              </Button>
            </div>
          </div>
        </div>
      );
    }
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4">
        <Logo height={28} href={null} priority />
        <div className="flex items-center gap-2 text-[13px] text-muted">
          <Spinner size={16} className="text-brand" /> Loading your workspace…
        </div>
      </div>
    );
  }

  if (profile.must_set_password) return null;

  return <AppShell>{children}</AppShell>;
}
