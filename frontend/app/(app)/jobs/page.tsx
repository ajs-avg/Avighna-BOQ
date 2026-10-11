"use client";

import { ChevronLeft, ChevronRight, FolderOpen, Plus, RefreshCw, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { PageHeader } from "@/components/AppShell";
import { ModuleBadge } from "@/components/ModuleBadge";
import { Alert } from "@/components/ui/Alert";
import { Button, ButtonLink, IconButton } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { useConfirm } from "@/components/ui/ConfirmDialog";
import { EmptyState } from "@/components/ui/EmptyState";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { Select } from "@/components/ui/Select";
import { StatusPill } from "@/components/ui/StatusPill";
import { EmptyRow, SkeletonRows, Table, TableWrap } from "@/components/ui/Table";
import { useToast } from "@/components/ui/Toast";
import { deleteJob, listJobs } from "@/lib/api";
import { MODULE_META, STATUS_META, isProcessing } from "@/lib/constants";
import { formatDate, formatInt, formatRelative } from "@/lib/format";
import type { JobStatus, JobSummaryRecord, Module } from "@/lib/types";
import { useUser } from "@/lib/user-context";
import { errorMessage } from "@/lib/utils";

const PAGE_SIZE = 25;
const STATUSES = Object.keys(STATUS_META) as JobStatus[];

export default function JobsPage() {
  const router = useRouter();
  const toast = useToast();
  const confirm = useConfirm();
  const { profile, isAdmin } = useUser();

  const [status, setStatus] = useState<JobStatus | "">("");
  const [module, setModule] = useState<Module | "">("");
  const [page, setPage] = useState(0);
  const [items, setItems] = useState<JobSummaryRecord[] | null>(null);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(
    async (silent = false) => {
      if (!silent) setItems(null);
      else setRefreshing(true);
      setError(null);
      try {
        const res = await listJobs({ limit: PAGE_SIZE, offset: page * PAGE_SIZE, status, module });
        setItems(res.items);
        setTotal(res.total);
      } catch (err) {
        setError(errorMessage(err));
        setItems([]);
      } finally {
        setRefreshing(false);
      }
    },
    [page, status, module],
  );

  useEffect(() => {
    void load();
  }, [load]);

  // keep processing rows fresh
  useEffect(() => {
    if (!items?.some((j) => isProcessing(j.status))) return;
    const t = window.setInterval(() => void load(true), 5000);
    return () => window.clearInterval(t);
  }, [items, load]);

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const canDelete = (j: JobSummaryRecord) => isAdmin || (!!profile?.email && j.created_by_email === profile.email);

  const onDelete = async (j: JobSummaryRecord) => {
    const ok = await confirm({
      title: "Delete this job?",
      message: `"${j.project_name} — ${j.level}" and its uploaded drawings will be permanently removed.`,
      confirmLabel: "Delete job",
      danger: true,
      onConfirm: async () => {
        await deleteJob(j.id);
      },
    });
    if (ok) {
      toast.success("Job deleted");
      void load(true);
    }
  };

  return (
    <div>
      <PageHeader
        title="Jobs"
        description="Every measurement run, newest first."
        actions={
          <>
            <Button variant="secondary" leftIcon={<RefreshCw className={refreshing ? "animate-spin" : undefined} />} onClick={() => void load(true)}>
              Refresh
            </Button>
            <ButtonLink href="/new" leftIcon={<Plus />}>
              New measurement
            </ButtonLink>
          </>
        }
      />

      <Card className="overflow-hidden">
        <div className="flex flex-wrap items-center gap-3 border-b border-line px-4 py-3">
          <div className="w-44">
            <Select
              size="sm"
              value={module}
              onChange={(e) => {
                setModule(e.target.value as Module | "");
                setPage(0);
              }}
              aria-label="Filter by module"
            >
              <option value="">All modules</option>
              {(Object.keys(MODULE_META) as Module[]).map((m) => (
                <option key={m} value={m}>
                  {MODULE_META[m].label}
                </option>
              ))}
            </Select>
          </div>
          <div className="w-44">
            <Select
              size="sm"
              value={status}
              onChange={(e) => {
                setStatus(e.target.value as JobStatus | "");
                setPage(0);
              }}
              aria-label="Filter by status"
            >
              <option value="">All statuses</option>
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {STATUS_META[s].label}
                </option>
              ))}
            </Select>
          </div>
          <p className="ml-auto text-[12.5px] text-muted">
            {items === null ? "Loading…" : `${formatInt(total)} job${total === 1 ? "" : "s"}`}
          </p>
        </div>

        {error ? (
          <Alert tone="danger" title="Could not load jobs" className="m-4">
            {error}
          </Alert>
        ) : null}

        <TableWrap flush>
          <Table>
            <thead>
              <tr>
                <th>Module</th>
                <th>Project / level</th>
                <th>Status</th>
                <th>Headline</th>
                <th className="num">Files</th>
                <th className="num">Items</th>
                <th>Created by</th>
                <th>Created</th>
                <th className="w-10" />
              </tr>
            </thead>
            <tbody>
              {items === null ? (
                <SkeletonRows rows={8} cols={9} />
              ) : items.length === 0 ? (
                <EmptyRow colSpan={9}>
                  <EmptyState
                    compact
                    icon={<FolderOpen />}
                    title={status || module ? "No jobs match these filters" : "No jobs yet"}
                    description={status || module ? "Try clearing the filters." : "Upload drawings to create your first measurement job."}
                    action={
                      status || module ? (
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => {
                            setStatus("");
                            setModule("");
                            setPage(0);
                          }}
                        >
                          Clear filters
                        </Button>
                      ) : (
                        <ButtonLink href="/new" size="sm" leftIcon={<Plus />}>
                          New measurement
                        </ButtonLink>
                      )
                    }
                  />
                </EmptyRow>
              ) : (
                items.map((j) => (
                  <tr key={j.id} className="row-hover cursor-pointer" onClick={() => router.push(`/jobs/${j.id}`)}>
                    <td>
                      <ModuleBadge module={j.module} />
                    </td>
                    <td className="max-w-[260px]">
                      <Link href={`/jobs/${j.id}`} className="block truncate font-medium text-ink hover:text-brand" onClick={(e) => e.stopPropagation()}>
                        {j.project_name}
                      </Link>
                      <p className="truncate text-[12px] text-muted">{j.level}</p>
                    </td>
                    <td className="min-w-[150px]">
                      <StatusPill status={j.status} progress={j.progress} />
                      {isProcessing(j.status) ? <ProgressBar value={j.progress} size="xs" className="mt-1.5 w-28" /> : null}
                    </td>
                    <td className="max-w-[220px] truncate text-[12.5px]" title={j.headline}>
                      {j.headline || "—"}
                    </td>
                    <td className="num" title={j.file_names.join("\n")}>
                      {j.file_names.length}
                    </td>
                    <td className="num">{formatInt(j.member_count)}</td>
                    <td className="max-w-[180px] truncate text-[12.5px] text-muted" title={j.created_by_email ?? undefined}>
                      {j.created_by_email ?? "—"}
                    </td>
                    <td className="whitespace-nowrap text-[12.5px] text-muted" title={formatDate(j.created_at)}>
                      {formatRelative(j.created_at)}
                    </td>
                    <td onClick={(e) => e.stopPropagation()}>
                      {canDelete(j) ? (
                        <IconButton label="Delete job" size="xs" className="text-muted hover:bg-danger-soft hover:text-danger" onClick={() => void onDelete(j)}>
                          <Trash2 />
                        </IconButton>
                      ) : null}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </Table>
        </TableWrap>

        {pageCount > 1 ? (
          <div className="flex items-center justify-between border-t border-line px-4 py-2.5 text-[12.5px] text-muted">
            <span>
              Page {page + 1} of {pageCount}
            </span>
            <div className="flex gap-1">
              <IconButton label="Previous page" variant="secondary" size="xs" disabled={page === 0} onClick={() => setPage((p) => Math.max(0, p - 1))}>
                <ChevronLeft />
              </IconButton>
              <IconButton label="Next page" variant="secondary" size="xs" disabled={page + 1 >= pageCount} onClick={() => setPage((p) => p + 1)}>
                <ChevronRight />
              </IconButton>
            </div>
          </div>
        ) : null}
      </Card>
    </div>
  );
}
