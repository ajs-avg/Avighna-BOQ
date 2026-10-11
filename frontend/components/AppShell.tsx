"use client";

import {
  AlertTriangle,
  ChevronDown,
  FolderOpen,
  KeyRound,
  LayoutDashboard,
  LogOut,
  Menu as MenuIcon,
  Plus,
  Cpu,
  Upload,
  Users,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { getAIStatus } from "@/lib/api";
import { ROLE_META } from "@/lib/constants";
import { initials } from "@/lib/format";
import type { AIStatus } from "@/lib/types";
import { useUser } from "@/lib/user-context";
import { cn } from "@/lib/utils";
import { ChangePasswordDialog } from "./ChangePasswordDialog";
import { Logo, ProductTag } from "./Logo";
import { Badge } from "./ui/Badge";
import { ButtonLink, IconButton } from "./ui/Button";
import { Menu } from "./ui/Menu";

interface NavItem {
  href: string;
  label: string;
  icon: ReactNode;
  adminOnly?: boolean;
  exact?: boolean;
}

const NAV: NavItem[] = [
  { href: "/", label: "Dashboard", icon: <LayoutDashboard />, exact: true },
  { href: "/new", label: "New Measurement", icon: <Upload /> },
  { href: "/jobs", label: "Jobs", icon: <FolderOpen /> },
  { href: "/users", label: "Users", icon: <Users />, adminOnly: true },
];

function isActive(pathname: string, item: NavItem): boolean {
  if (item.exact) return pathname === item.href;
  return pathname === item.href || pathname.startsWith(`${item.href}/`);
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { profile, isAdmin } = useUser();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [ai, setAi] = useState<AIStatus | null>(null);

  useEffect(() => {
    setDrawerOpen(false);
  }, [pathname]);

  useEffect(() => {
    let cancelled = false;
    getAIStatus()
      .then((s) => {
        if (!cancelled) setAi(s);
      })
      .catch(() => {
        /* banner stays hidden if the endpoint is unavailable */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const nav = NAV.filter((n) => !n.adminOnly || isAdmin);

  const sidebar = (
    <div className="flex h-full flex-col">
      <div className="flex h-16 items-center gap-2 border-b border-line px-5">
        <Logo height={26} priority />
        <ProductTag />
      </div>
      <div className="px-3 pt-4">
        <ButtonLink href="/new" block leftIcon={<Plus />} size="md">
          New measurement
        </ButtonLink>
      </div>
      <nav className="mt-4 flex-1 space-y-0.5 px-3" aria-label="Primary">
        {nav.map((item) => {
          const active = isActive(pathname, item);
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "group relative flex h-10 items-center gap-3 rounded-lg px-3 text-[13.5px] font-medium transition-colors [&>svg]:size-[18px]",
                active ? "bg-brand-soft text-brand" : "text-ink/80 hover:bg-surface-2 hover:text-ink",
              )}
            >
              {active ? <span className="absolute left-0 top-2 bottom-2 w-[3px] rounded-r-full bg-brand" aria-hidden /> : null}
              <span className={cn("[&>svg]:size-[18px]", active ? "text-brand" : "text-muted group-hover:text-ink")}>{item.icon}</span>
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="border-t border-line p-3">
        <div className="flex items-center gap-3 rounded-lg px-2 py-2">
          <Avatar name={profile?.full_name} email={profile?.email} />
          <div className="min-w-0 flex-1">
            <p className="truncate text-[13px] font-semibold text-ink">{profile?.full_name || profile?.email || "—"}</p>
            <p className="truncate text-[11.5px] text-muted">{profile ? ROLE_META[profile.role].label : ""}</p>
          </div>
        </div>
        <p className="px-2 pt-1 text-[10.5px] text-muted/70">Avighna BOQ · v0.1</p>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-surface-2/40">
      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-60 border-r border-line bg-surface lg:block">{sidebar}</aside>

      {/* Mobile drawer */}
      {drawerOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
          <div className="absolute inset-0 bg-ink/40 animate-fade-in" onClick={() => setDrawerOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-72 max-w-[85vw] bg-surface shadow-modal animate-slide-in-left">
            <IconButton label="Close navigation" onClick={() => setDrawerOpen(false)} className="absolute right-2 top-3.5">
              <X />
            </IconButton>
            {sidebar}
          </aside>
        </div>
      ) : null}

      <div className="lg:pl-60">
        <header className="sticky top-0 z-30 border-b border-line bg-surface/95 backdrop-blur supports-[backdrop-filter]:bg-surface/80">
          {ai && !ai.enabled ? (
            <div className="flex items-center gap-2 border-b border-warning/30 bg-warning-soft px-4 py-1.5 text-[12.5px] text-ink">
              <AlertTriangle className="size-4 shrink-0 text-warning" />
              <span>
                <span className="font-semibold">AI reading is off</span> — add <code className="rounded bg-white/70 px-1 font-mono text-[11.5px]">GEMINI_API_KEY</code> to the backend{" "}
                <code className="rounded bg-white/70 px-1 font-mono text-[11.5px]">.env</code>
                {ai.message ? <span className="text-muted"> · {ai.message}</span> : null}
              </span>
            </div>
          ) : null}
          <div className="flex h-16 items-center gap-3 px-4 sm:px-6">
            <IconButton label="Open navigation" onClick={() => setDrawerOpen(true)} className="lg:hidden">
              <MenuIcon />
            </IconButton>
            <div className="flex items-center gap-2 lg:hidden">
              <Logo height={22} />
              <ProductTag />
            </div>
            <div className="ml-auto flex items-center gap-2 sm:gap-3">
              {ai?.enabled ? (
                <Badge tone="success" icon={<Cpu />} className="hidden sm:inline-flex" title={ai.model_fast ? `${ai.provider} · ${ai.model_fast}` : ai.provider}>
                  AI on
                </Badge>
              ) : null}
              <UserMenu />
            </div>
          </div>
        </header>
        <main className="mx-auto w-full max-w-[1400px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">{children}</main>
      </div>
    </div>
  );
}

function Avatar({ name, email, size = 32 }: { name?: string | null; email?: string | null; size?: number }) {
  return (
    <span
      className="inline-flex shrink-0 items-center justify-center rounded-full bg-ink text-[12px] font-semibold text-white"
      style={{ width: size, height: size }}
      aria-hidden
    >
      {initials(name, email)}
    </span>
  );
}

function UserMenu() {
  const { profile, logout } = useUser();
  const [pwOpen, setPwOpen] = useState(false);

  return (
    <>
      <Menu
        width={260}
        header={
          <div className="flex items-center gap-3">
            <Avatar name={profile?.full_name} email={profile?.email} size={36} />
            <div className="min-w-0">
              <p className="truncate text-[13px] font-semibold text-ink">{profile?.full_name || "—"}</p>
              <p className="truncate text-[12px] text-muted">{profile?.email}</p>
              {profile ? (
                <Badge tone={profile.role === "admin" ? "brand" : "neutral"} size="xs" className="mt-1">
                  {ROLE_META[profile.role].label}
                </Badge>
              ) : null}
            </div>
          </div>
        }
        items={[
          { key: "pw", label: "Change password", icon: <KeyRound />, onSelect: () => setPwOpen(true) },
          { key: "logout", label: "Log out", icon: <LogOut />, onSelect: logout, danger: true, separator: true },
        ]}
        trigger={({ open, toggle }) => (
          <button
            type="button"
            onClick={toggle}
            aria-haspopup="menu"
            aria-expanded={open}
            className={cn(
              "flex h-10 items-center gap-2 rounded-lg px-1.5 pr-2 transition-colors hover:bg-surface-2",
              open && "bg-surface-2",
            )}
          >
            <Avatar name={profile?.full_name} email={profile?.email} />
            <span className="hidden max-w-[160px] truncate text-[13px] font-medium text-ink sm:block">
              {profile?.full_name || profile?.email || "Account"}
            </span>
            <ChevronDown className={cn("size-4 text-muted transition-transform", open && "rotate-180")} />
          </button>
        )}
      />
      <ChangePasswordDialog open={pwOpen} onClose={() => setPwOpen(false)} />
    </>
  );
}

/** Page header block used at the top of every authenticated page. */
export function PageHeader({
  title,
  description,
  actions,
  breadcrumb,
  className,
}: {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  breadcrumb?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between", className)}>
      <div className="min-w-0">
        {breadcrumb ? <div className="mb-1.5 text-[12.5px] text-muted">{breadcrumb}</div> : null}
        <h1 className="text-[22px] font-semibold leading-7 tracking-tight text-ink sm:text-[24px]">{title}</h1>
        {description ? <p className="mt-1 text-[13.5px] text-muted">{description}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  );
}
