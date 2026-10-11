"use client";

import { Armchair, ArrowRight, BadgeCheck, Clock, FolderOpen, Layers, Plus, Ruler, Upload } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { PageHeader } from "@/components/AppShell";
import { ModuleBadge } from "@/components/ModuleBadge";
import { StatTile } from "@/components/StatTile";
import { SystemCard } from "@/components/SystemCard";
import { Alert } from "@/components/ui/Alert";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { StatusPill } from "@/components/ui/StatusPill";
import { EmptyRow, SkeletonRows, Table, TableWrap } from "@/components/ui/Table";
import { listJobs } from "@/lib/api";
import { isProcessing } from "@/lib/constants";
import { formatInt, formatRelative, formatTons } from "@/lib/format";
import type { JobSummaryRecord } from "@/lib/types";
import { useUser } from "@/lib/user-context";
import { errorMessage } from "@/lib/utils";

export default function DashboardPage() {
  const { profile } = useUser();
  const router = useRouter();
  const [jobs, setJobs] = useState<JobSummaryRecord[] | null>(null);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listJobs({ limit: 100, offset: 0 })
      .then((res) => {
        if (cancelled) return;
        setJobs(res.items);
        setTotal(res.total);
      })
      .catch((err) => {
        if (!cancelled) setError(errorMessage(err));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const stats = useMemo(() => {
    const now = new Date();
    const list = jobs ?? [];
    const thisMonth = list.filter((j) => {
      const d = new Date(j.created_at);
      return d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth();
    }).length;
    const steel = list
      .filter((j) => j.module === "structural" && (j.status === "ready" || j.status === "approved"))
      .reduce((s, j) => s + (j.grand_total_t ?? 0), 0);
    const boqLines = list
      .filter((j) => j.module === "fitout" && (j.status === "ready" || j.status === "approved"))
      .reduce((s, j) => s + (j.member_count ?? 0), 0);
    const awaiting = list.filter((j) => j.status === "ready").length;
    const approved = list.filter((j) => j.status === "approved").length;
    return { thisMonth, steel, boqLines, awaiting, approved };
  }, [jobs]);

  const recent = (jobs ?? []).slice(0, 8);
  const loading = jobs === null && !error;
  const firstName = profile?.full_name?.split(" ")[0];

  return (
    <div>
      <PageHeader
        title={firstName ? `Welcome back, ${firstName}` : "Dashboard"}
        description="Measurement jobs across structural BBS and interior fit-out BOQ."
        actions={
          <ButtonLink href="/new" leftIcon={<Plus />} size="lg">
            New measurement
          </ButtonLink>
        }
      />

      {error ? (
        <Alert tone="danger" title="Could not load jobs" className="mb-6">
          {error}
        </Alert>
      ) : null}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <StatTile label="Jobs this month" value={formatInt(stats.thisMonth)} icon={<FolderOpen />} loading={loading} hint={`${formatInt(total)} total`} />
        <StatTile label="Steel quantified" value={formatTons(stats.steel, false)} unit="t" icon={<Layers />} loading={loading} hint="Ready + approved, structural" />
        <StatTile label="BOQ lines measured" value={formatInt(stats.boqLines)} icon={<Ruler />} loading={loading} hint="Ready + approved, fit-out" />
        <StatTile label="Awaiting review" value={formatInt(stats.awaiting)} icon={<Clock />} loading={loading} tone={stats.awaiting > 0 ? "brand" : "default"} hint="Ready for review" />
        <StatTile label="Approved" value={formatInt(stats.approved)} icon={<BadgeCheck />} loading={loading} hint="Signed off" />
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-[1fr_340px]">
        <Card className="overflow-hidden">
          <CardHeader
            title="Recent jobs"
            description="Latest measurement runs across all modules."
            actions={
              <ButtonLink href="/jobs" variant="ghost" size="sm" rightIcon={<ArrowRight />}>
                View all
              </ButtonLink>
            }
          />
          <TableWrap flush>
            <Table>
              <thead>
                <tr>
                  <th>Module</th>
                  <th>Project</th>
                  <th>Status</th>
                  <th>Result</th>
                  <th>By</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <SkeletonRows rows={5} cols={6} />
                ) : recent.length === 0 ? (
                  <EmptyRow colSpan={6}>
                    <EmptyState
                      compact
                      icon={<Upload />}
                      title="No jobs yet"
                      description="Upload your first set of drawings to generate a measurement sheet."
                      action={
                        <ButtonLink href="/new" leftIcon={<Plus />} size="sm">
                          New measurement
                        </ButtonLink>
                      }
                    />
                  </EmptyRow>
                ) : (
                  recent.map((j) => (
                    <tr key={j.id} className="row-hover cursor-pointer" onClick={() => router.push(`/jobs/${j.id}`)}>
                      <td>
                        <ModuleBadge module={j.module} />
                      </td>
                      <td>
                        <Link href={`/jobs/${j.id}`} className="font-medium text-ink hover:text-brand" onClick={(e) => e.stopPropagation()}>
                          {j.project_name}
                        </Link>
                        <p className="text-[12px] text-muted">{j.level}</p>
                      </td>
                      <td>
                        <StatusPill status={j.status} progress={j.progress} />
                        {isProcessing(j.status) ? <ProgressBar value={j.progress} size="xs" className="mt-1.5 w-24" /> : null}
                      </td>
                      <td className="text-[12.5px] text-ink">{j.headline || "—"}</td>
                      <td className="max-w-[160px] truncate text-[12.5px] text-muted" title={j.created_by_email ?? undefined}>
                        {j.created_by_email ?? "—"}
                      </td>
                      <td className="whitespace-nowrap text-[12.5px] text-muted">{formatRelative(j.created_at)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </Table>
          </TableWrap>
        </Card>

        <div className="space-y-4">
          <div className="card relative overflow-hidden border-brand/30 bg-gradient-to-br from-brand to-brand-dark p-6 text-white shadow-[0_12px_32px_-12px_rgba(237,28,36,0.55)]">
            <div className="pointer-events-none absolute -right-10 -top-10 size-40 rounded-full bg-white/10 blur-2xl" aria-hidden />
            <p className="text-[12px] font-semibold uppercase tracking-[0.08em] text-white/80">Start here</p>
            <h2 className="mt-2 text-[22px] font-semibold leading-7 tracking-tight">Drop a drawing, get a measurement sheet.</h2>
            <p className="mt-2 text-[13px] text-white/85">
              Upload DWG, DXF, PDF or images. The engine reads them, quantifies and produces the Excel in Avighna&apos;s format.
            </p>
            <Button
              size="lg"
              block
              className="mt-5 !bg-white !text-brand hover:!bg-white/90"
              leftIcon={<Upload />}
              onClick={() => router.push("/new")}
            >
              New measurement
            </Button>
          </div>

          <Card className="p-1">
            <Link href="/new?module=structural" className="flex items-center gap-3 rounded-lg px-4 py-3 transition-colors hover:bg-surface-2">
              <span className="inline-flex size-9 items-center justify-center rounded-lg bg-surface-2 text-ink">
                <Layers className="size-4" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-[13.5px] font-semibold text-ink">Structural — Reinforcement BBS</span>
                <span className="block text-[12px] text-muted">Beams, slabs, columns, walls, stairs → tons</span>
              </span>
              <ArrowRight className="size-4 text-muted" />
            </Link>
            <div className="mx-4 border-t border-line" />
            <Link href="/new?module=fitout" className="flex items-center gap-3 rounded-lg px-4 py-3 transition-colors hover:bg-surface-2">
              <span className="inline-flex size-9 items-center justify-center rounded-lg bg-brand-soft text-brand">
                <Armchair className="size-4" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-[13.5px] font-semibold text-ink">Interior Fit-out — BOQ</span>
                <span className="block text-[12px] text-muted">Finishes, joinery, doors, lighting, FF&amp;E → m² / lm / nos</span>
              </span>
              <ArrowRight className="size-4 text-muted" />
            </Link>
          </Card>

          <SystemCard />
        </div>
      </div>
    </div>
  );
}
