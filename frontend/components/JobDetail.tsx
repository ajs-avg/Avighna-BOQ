"use client";

import {
  AlertTriangle,
  ArrowLeft,
  BadgeCheck,
  Calculator,
  ChevronRight,
  Download,
  FileBox,
  FileImage,
  FileText,
  File as FileIcon,
  Layers,
  RefreshCw,
  Sparkles,
  Undo2,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { approve, downloadExport, getJob, isApiError, recalculate, reprocess } from "@/lib/api";
import { MEMBER_KINDS, MEMBER_KIND_META, MODULE_META, PIPELINE_STEPS, POLL_INTERVAL_MS, STATUS_META, isProcessing } from "@/lib/constants";
import { formatBytes, formatDate, formatInt, formatRelative, formatTons } from "@/lib/format";
import type { Division, JobRecord, MemberKind, SourceFormat } from "@/lib/types";
import { useUser } from "@/lib/user-context";
import { cn, downloadBlob, errorMessage, slugify } from "@/lib/utils";
import { PageHeader } from "./AppShell";
import { ConfidenceBadge } from "./ConfidenceBadge";
import { ModuleBadge } from "./ModuleBadge";
import { SendBackDialog } from "./SendBackDialog";
import { SheetsTab } from "./SheetsTab";
import { Timeline } from "./Timeline";
import { BOQSummaryCards } from "./fitout/BOQSummaryCards";
import { BOQTab } from "./fitout/BOQTab";
import { RoomsTable } from "./fitout/RoomsTable";
import { MemberTab } from "./structural/MemberTab";
import { SummaryTable } from "./structural/SummaryTable";
import { Alert } from "./ui/Alert";
import { Chip } from "./ui/Badge";
import { Button, ButtonLink } from "./ui/Button";
import { Card, CardBody, CardHeader } from "./ui/Card";
import { useConfirm } from "./ui/ConfirmDialog";
import { EmptyState } from "./ui/EmptyState";
import { ProgressBar } from "./ui/ProgressBar";
import { Skeleton, SkeletonText } from "./ui/Skeleton";
import { Spinner } from "./ui/Spinner";
import { StatusPill } from "./ui/StatusPill";
import { Tabs, type TabItem } from "./ui/Tabs";
import { useToast } from "./ui/Toast";

type TabKey = "summary" | MemberKind | "sheets" | "boq" | "rooms";
type Action = "reprocess" | "recalculate" | "approve" | "download";

export function JobDetail({ id }: { id: string }) {
  const { canApprove } = useUser();
  const toast = useToast();
  const confirm = useConfirm();

  const [job, setJob] = useState<JobRecord | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [tab, setTab] = useState<TabKey>("summary");
  const [acting, setActing] = useState<Action | null>(null);
  const [focusDivision, setFocusDivision] = useState<Division | null>(null);
  const [sendBackOpen, setSendBackOpen] = useState(false);
  const prevStatus = useRef<JobRecord["status"] | null>(null);

  const load = useCallback(async () => {
    try {
      const j = await getJob(id);
      setJob(j);
      setError(null);
    } catch (err) {
      if (isApiError(err) && err.status === 404) setNotFound(true);
      else setError(errorMessage(err));
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  const processing = job ? isProcessing(job.status) : false;

  // Poll while the pipeline runs.
  useEffect(() => {
    if (!processing) return;
    const t = window.setInterval(() => {
      getJob(id)
        .then(setJob)
        .catch(() => {
          /* keep the last good state; the next tick retries */
        });
    }, POLL_INTERVAL_MS);
    return () => window.clearInterval(t);
  }, [processing, id]);

  // Toast on terminal transitions.
  useEffect(() => {
    if (!job) return;
    const prev = prevStatus.current;
    prevStatus.current = job.status;
    if (prev && prev !== job.status) {
      if (job.status === "ready") toast.success("Measurement ready", "Review the quantities, then approve or download the Excel.");
      if (job.status === "failed") toast.error("Processing failed", job.error ?? "See the error on the job page.");
    }
  }, [job, toast]);

  const run = async (action: Action, fn: () => Promise<void>, failTitle = "Action failed") => {
    setActing(action);
    try {
      await fn();
    } catch (err) {
      // The API's `detail` (e.g. the 409 "Nothing to approve: …") is the message.
      toast.error(failTitle, errorMessage(err));
    } finally {
      setActing(null);
    }
  };

  const onReprocess = async () => {
    if (!job) return;
    const ok = await confirm({
      title: "Reprocess this job?",
      message: "The whole pipeline runs again from the uploaded drawings. Manual edits to members or items will be overwritten.",
      confirmLabel: "Reprocess",
      danger: true,
    });
    if (!ok) return;
    await run("reprocess", async () => {
      setJob(await reprocess(job.id));
      toast.info("Reprocessing started");
    });
  };

  const onRecalculate = () =>
    job &&
    run("recalculate", async () => {
      setJob(await recalculate(job.id, {}));
      toast.success("Recalculated", "Quantities refreshed with the current inputs and standards.");
    });

  const onApprove = async () => {
    if (!job) return;
    const ok = await confirm({
      title: "Approve this measurement?",
      message: `${job.project_name} — ${job.level}. Approval locks the quantities and marks the Excel as final.`,
      confirmLabel: "Approve",
    });
    if (!ok) return;
    await run(
      "approve",
      async () => {
        setJob(await approve(job.id));
        toast.success("Approved");
      },
      "Could not approve",
    );
  };

  const canSendBack = canApprove && (job?.status === "ready" || job?.status === "approved");

  const onDownload = () =>
    job &&
    run("download", async () => {
      const blob = await downloadExport(job.id);
      downloadBlob(blob, `${slugify(job.project_name)}-${slugify(job.level)}-${job.module}.xlsx`);
      toast.success("Excel downloaded");
    });

  if (notFound) {
    return (
      <Card>
        <EmptyState
          icon={<FileText />}
          title="Job not found"
          description="It may have been deleted."
          action={
            <ButtonLink href="/jobs" variant="secondary" leftIcon={<ArrowLeft />}>
              Back to jobs
            </ButtonLink>
          }
        />
      </Card>
    );
  }

  if (!job) {
    return error ? (
      <Alert tone="danger" title="Could not load the job" actions={<Button size="sm" variant="secondary" onClick={() => void load()}>Retry</Button>}>
        {error}
      </Alert>
    ) : (
      <JobSkeleton />
    );
  }

  const canDownload = job.status === "ready" || job.status === "approved";
  const readOnly = processing || job.status === "approved";
  const moduleMeta = MODULE_META[job.module];

  const tabs: TabItem<TabKey>[] =
    job.module === "structural"
      ? [
          { key: "summary", label: "Summary" },
          ...MEMBER_KINDS.map<TabItem<TabKey>>((k) => ({ key: k, label: MEMBER_KIND_META[k].plural, count: job.members.filter((m) => m.kind === k).length })),
          { key: "sheets", label: "Sheets", count: job.sheet_count },
        ]
      : [
          { key: "summary", label: "Summary" },
          { key: "boq", label: "BOQ", count: job.boq?.summary.line_count ?? job.fitout_items.length },
          { key: "rooms", label: "Rooms", count: job.rooms.length },
          { key: "sheets", label: "Sheets", count: job.sheet_count },
        ];

  const lowConfidence =
    job.module === "structural" ? job.members.filter((m) => m.confidence < 0.6).length : job.fitout_items.filter((i) => i.confidence < 0.6).length;

  return (
    <div>
      <PageHeader
        breadcrumb={
          <span className="inline-flex items-center gap-1">
            <Link href="/jobs" className="hover:text-ink">
              Jobs
            </Link>
            <ChevronRight className="size-3.5" />
            <span className="text-ink">{moduleMeta.output}</span>
          </span>
        }
        title={
          <span className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <span>
              {job.project_name} <span className="text-muted">—</span> {job.level}
            </span>
            <ModuleBadge module={job.module} />
            <StatusPill status={job.status} progress={job.progress} size="md" />
          </span>
        }
        description={
          <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
            {job.location ? <span>{job.location}</span> : null}
            {job.contractor ? <span>· {job.contractor}</span> : null}
            {job.drawn_by ? <span>· Drawn by {job.drawn_by}</span> : null}
            <span>· {job.source_files.length} file{job.source_files.length === 1 ? "" : "s"}</span>
            {job.created_by_email ? <span>· {job.created_by_email}</span> : null}
            <span title={formatDate(job.created_at)}>· {formatRelative(job.created_at)}</span>
          </span>
        }
        actions={
          <>
            <Button variant="secondary" leftIcon={<RefreshCw />} onClick={() => void onReprocess()} loading={acting === "reprocess"} disabled={processing || !!acting}>
              Reprocess
            </Button>
            <Button variant="secondary" leftIcon={<Calculator />} onClick={() => void onRecalculate()} loading={acting === "recalculate"} disabled={job.status !== "ready" || !!acting} title={job.status !== "ready" ? "Available when the job is ready for review" : undefined}>
              Recalculate
            </Button>
            {canSendBack ? (
              <Button variant="secondary" leftIcon={<Undo2 />} onClick={() => setSendBackOpen(true)} disabled={!!acting} title="Return the job to the engineer with a reason">
                Send back
              </Button>
            ) : null}
            {canApprove && job.status === "ready" ? (
              <Button leftIcon={<BadgeCheck />} onClick={() => void onApprove()} loading={acting === "approve"} disabled={!!acting}>
                Approve
              </Button>
            ) : null}
            {canDownload ? (
              <Button variant={job.status === "approved" ? "primary" : "secondary"} leftIcon={<Download />} onClick={() => void onDownload()} loading={acting === "download"} disabled={!!acting}>
                Download Excel
              </Button>
            ) : null}
          </>
        }
      />

      {processing ? (
        <Card className="mb-6 p-4">
          <div className="flex items-center justify-between gap-3">
            <p className="flex items-center gap-2 text-[13px] font-medium text-ink">
              <Spinner size={14} className="text-brand" />
              {STATUS_META[job.status].label}
              <span className="text-muted">· {job.events[job.events.length - 1]?.message ?? "Working…"}</span>
            </p>
            <span className="tnum text-[13px] font-semibold text-brand">{Math.round(job.progress)}%</span>
          </div>
          <ProgressBar value={job.progress} size="md" className="mt-2.5" indeterminate={job.progress <= 0} />
          <p className="mt-2 text-[11.5px] text-muted">Refreshing every {POLL_INTERVAL_MS / 1000} s.</p>
        </Card>
      ) : null}

      {job.status === "failed" ? (
        <Alert
          tone="danger"
          title="Processing failed"
          className="mb-6"
          actions={
            <Button size="sm" variant="danger" leftIcon={<RefreshCw />} onClick={() => void onReprocess()} loading={acting === "reprocess"}>
              Reprocess
            </Button>
          }
        >
          {job.error || "The pipeline stopped with an error. Check the drawings and try again."}
        </Alert>
      ) : null}

      {job.status === "approved" ? (
        <Alert tone="success" title="Approved" className="mb-6" icon={<BadgeCheck />}>
          {job.approved_by ? `By ${job.approved_by}` : "Approved"}
          {job.approved_at ? ` on ${formatDate(job.approved_at)}` : ""}. Quantities are locked;{" "}
          {canSendBack ? "send the job back to reopen it for edits, or reprocess" : "reprocess"} to start a new revision.
        </Alert>
      ) : null}

      {!readOnly && lowConfidence > 0 ? (
        <Alert tone="warning" className="mb-6" title={`${lowConfidence} ${job.module === "structural" ? "member" : "item"}${lowConfidence === 1 ? "" : "s"} with low confidence`}>
          Review the rows marked <ConfidenceBadge value={0.3} size="xs" showPct={false} className="mx-1 align-middle" /> before approving.
        </Alert>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0">
          <Tabs items={tabs} value={tab} onChange={(k) => setTab(k)} className="mb-5" />

          {tab === "summary" ? (
            job.module === "structural" ? (
              <StructuralSummary job={job} onGoTo={setTab} />
            ) : (
              <FitoutSummary
                job={job}
                onSelectDivision={(d) => {
                  setFocusDivision(d);
                  setTab("boq");
                }}
              />
            )
          ) : null}

          {job.module === "structural" && MEMBER_KINDS.includes(tab as MemberKind) ? (
            <MemberTab key={tab} job={job} kind={tab as MemberKind} onJobUpdate={setJob} readOnly={readOnly} />
          ) : null}

          {tab === "boq" && job.module === "fitout" ? <BOQTab job={job} onJobUpdate={setJob} readOnly={readOnly} focusDivision={focusDivision} /> : null}
          {tab === "rooms" && job.module === "fitout" ? <RoomsTable rooms={job.boq?.rooms.length ? job.boq.rooms : job.rooms} /> : null}
          {tab === "sheets" ? <SheetsTab jobId={job.id} module={job.module} refreshKey={`${job.status}-${job.sheet_count}`} /> : null}
        </div>

        <aside className="space-y-4">
          <Card>
            <CardHeader title="Pipeline" description={processing ? "Live — updates automatically." : `${job.events.length} event${job.events.length === 1 ? "" : "s"}`} className="py-3" />
            <CardBody>
              <Timeline events={job.events} status={job.status} />
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Source files" className="py-3" />
            <ul className="divide-y divide-line">
              {job.source_files.map((f) => (
                <li key={f.storage_path || f.name} className="flex items-center gap-3 px-5 py-2.5">
                  <FormatIcon format={f.format} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[13px] font-medium text-ink" title={f.name}>
                      {f.name}
                    </p>
                    <p className="text-[11.5px] text-muted">
                      {f.format.toUpperCase()} · {formatBytes(f.size_bytes)}
                    </p>
                  </div>
                </li>
              ))}
              {job.source_files.length === 0 ? <li className="px-5 py-3 text-[12.5px] text-muted">No files recorded.</li> : null}
            </ul>
          </Card>

          <Card>
            <CardHeader title="Details" className="py-3" />
            <CardBody className="py-3">
              <dl className="space-y-2 text-[12.5px]">
                <Row label="Module">{moduleMeta.label}</Row>
                <Row label="Project">{job.project_name}</Row>
                <Row label="Level">{job.level}</Row>
                {job.location ? <Row label="Location">{job.location}</Row> : null}
                {job.module === "fitout" ? <Row label="Currency">{job.currency}</Row> : null}
                {job.contractor ? <Row label="Contractor">{job.contractor}</Row> : null}
                {job.drawn_by ? <Row label="Drawn by">{job.drawn_by}</Row> : null}
                {job.drawing_refs.length ? (
                  <Row label="Drawing refs">
                    <span className="flex flex-wrap gap-1">
                      {job.drawing_refs.map((r) => (
                        <Chip key={r}>{r}</Chip>
                      ))}
                    </span>
                  </Row>
                ) : null}
                {job.module === "structural" && job.work_description ? <Row label="Work">{job.work_description}</Row> : null}
                <Row label="Sheets">{formatInt(job.sheet_count)}</Row>
                <Row label="Created">
                  <span title={formatDate(job.created_at)}>{formatDate(job.created_at)}</span>
                  {job.created_by_email ? <span className="block text-muted">{job.created_by_email}</span> : null}
                </Row>
                <Row label="Updated">{formatDate(job.updated_at)}</Row>
                {job.export_version > 0 ? <Row label="Export">v{job.export_version}</Row> : null}
                <Row label="Job ID">
                  <code className="font-mono text-[11.5px]">{job.id}</code>
                </Row>
              </dl>
            </CardBody>
          </Card>

          {job.module === "structural" ? <GeneralNotesCard job={job} /> : <LegendCard job={job} />}
        </aside>
      </div>

      <SendBackDialog
        job={job}
        open={sendBackOpen}
        onClose={() => setSendBackOpen(false)}
        onSent={(updated) => {
          setSendBackOpen(false);
          setJob(updated);
          toast.success("Sent back for rework", "The reason is recorded in the pipeline timeline.");
        }}
      />
    </div>
  );
}

/* ------------------------------------------------------------------------- */
/* Summary tabs                                                                */
/* ------------------------------------------------------------------------- */

function StructuralSummary({ job, onGoTo }: { job: JobRecord; onGoTo: (tab: TabKey) => void }) {
  if (!job.result) return <PendingPanel job={job} />;
  const s = job.result.summary;
  const dias = job.standards.diameters_in_summary;
  const warningMembers = job.result.members.filter((m) => m.warnings.length).length;
  return (
    <div className="space-y-5">
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_280px]">
        <SummaryTable summary={s} diameters={dias} />
        <div className="space-y-4">
          <div className="card relative overflow-hidden border-brand/30 bg-gradient-to-br from-brand to-brand-dark p-5 text-white shadow-[0_12px_32px_-12px_rgba(237,28,36,0.55)]">
            <div className="pointer-events-none absolute -right-8 -top-8 size-32 rounded-full bg-white/10 blur-2xl" aria-hidden />
            <p className="text-[11.5px] font-semibold uppercase tracking-[0.08em] text-white/80">Grand total · {s.level || job.level}</p>
            <p className="tnum mt-2 text-[34px] font-semibold leading-none tracking-tight">
              {formatTons(s.grand_total_t, false)}
              <span className="ml-1.5 text-[16px] font-medium text-white/80">t</span>
            </p>
            <p className="mt-2 text-[12.5px] text-white/80">
              {formatInt(job.members.length)} members · {formatInt(job.result.members.reduce((n, m) => n + m.rows.length, 0))} bar rows
            </p>
          </div>
          <Card className="p-4">
            <p className="text-[11.5px] font-semibold uppercase tracking-[0.06em] text-muted">By category</p>
            <ul className="mt-2 divide-y divide-line">
              {s.categories.map((c) => {
                const kind = MEMBER_KINDS.find((k) => MEMBER_KIND_META[k].category.toLowerCase() === c.category.toLowerCase());
                return (
                  <li key={c.category} className="flex items-center justify-between py-1.5 text-[13px]">
                    {kind ? (
                      <button type="button" className="font-medium text-ink hover:text-brand" onClick={() => onGoTo(kind)}>
                        {c.category}
                      </button>
                    ) : (
                      <span className="font-medium text-ink">{c.category}</span>
                    )}
                    <span className="tnum">{formatTons(c.total_t)}</span>
                  </li>
                );
              })}
            </ul>
          </Card>
          <Card className="p-4">
            <p className="text-[11.5px] font-semibold uppercase tracking-[0.06em] text-muted">Standards used</p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              <Chip>Ld {job.result.standards.ld_factor}d</Chip>
              <Chip>Cover B {job.result.standards.cover_beam_mm}</Chip>
              <Chip>S {job.result.standards.cover_slab_mm}</Chip>
              <Chip>C {job.result.standards.cover_column_mm}</Chip>
              <Chip>Bend {job.result.standards.bend_deduction_d}d</Chip>
              <Chip>Hook {job.result.standards.hook_length_d}d</Chip>
            </div>
            {warningMembers ? (
              <p className="mt-3 flex items-center gap-1.5 text-[12.5px] text-warning">
                <AlertTriangle className="size-3.5" /> {warningMembers} member{warningMembers === 1 ? "" : "s"} with engine warnings
              </p>
            ) : null}
          </Card>
        </div>
      </div>
    </div>
  );
}

function FitoutSummary({ job, onSelectDivision }: { job: JobRecord; onSelectDivision: (d: Division) => void }) {
  if (!job.boq) return <PendingPanel job={job} />;
  return <BOQSummaryCards boq={job.boq} currency={job.currency || job.boq.summary.currency} onSelectDivision={onSelectDivision} />;
}

function PendingPanel({ job }: { job: JobRecord }) {
  const processing = isProcessing(job.status);
  return (
    <Card>
      <EmptyState
        icon={processing ? <Sparkles /> : job.status === "failed" ? <AlertTriangle /> : <Layers />}
        title={processing ? `${STATUS_META[job.status].label}…` : job.status === "failed" ? "No result" : "No result yet"}
        description={
          processing
            ? "The drawings are being converted, read and quantified. This page refreshes automatically."
            : job.status === "failed"
              ? "The pipeline failed before producing quantities. Fix the input and reprocess."
              : "Run Recalculate to produce quantities from the extracted inputs."
        }
      />
      {processing ? (
        <div className="px-6 pb-6">
          <ol className="mx-auto flex max-w-xl flex-wrap items-center justify-center gap-x-2 gap-y-1 text-[12px]">
            {PIPELINE_STEPS.map((s, i) => {
              const idx = PIPELINE_STEPS.indexOf(job.status);
              const done = i < idx;
              const current = i === idx;
              return (
                <li key={s} className="flex items-center gap-2">
                  <span
                    className={cn(
                      "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-medium",
                      done && "border-success/30 bg-success-soft text-success",
                      current && "border-brand/30 bg-brand-soft text-brand",
                      !done && !current && "border-line text-muted",
                    )}
                  >
                    {current ? <span className="size-1.5 animate-pulse-dot rounded-full bg-brand" /> : null}
                    {STATUS_META[s].label}
                  </span>
                  {i < PIPELINE_STEPS.length - 1 ? <ChevronRight className="size-3 text-line-strong" /> : null}
                </li>
              );
            })}
          </ol>
        </div>
      ) : null}
    </Card>
  );
}

/* ------------------------------------------------------------------------- */
/* Rail cards                                                                  */
/* ------------------------------------------------------------------------- */

function GeneralNotesCard({ job }: { job: JobRecord }) {
  const n = job.general_notes;
  const hasAny = n.ld_factor != null || n.cover_beam_mm != null || n.cover_slab_mm != null || n.cover_column_mm != null || n.concrete_grade || n.steel_grade || n.notes.length > 0;
  if (!hasAny) return null;
  return (
    <Card>
      <CardHeader title="General notes" description="Read from the drawing's notes block." className="py-3" />
      <CardBody className="py-3">
        <div className="flex flex-wrap gap-1.5">
          {n.ld_factor != null ? <Chip>Ld {n.ld_factor}d</Chip> : null}
          {n.cover_beam_mm != null ? <Chip>Beam cover {n.cover_beam_mm}</Chip> : null}
          {n.cover_slab_mm != null ? <Chip>Slab cover {n.cover_slab_mm}</Chip> : null}
          {n.cover_column_mm != null ? <Chip>Column cover {n.cover_column_mm}</Chip> : null}
          {n.concrete_grade ? <Chip>{n.concrete_grade}</Chip> : null}
          {n.steel_grade ? <Chip>{n.steel_grade}</Chip> : null}
        </div>
        {n.notes.length ? (
          <ul className="mt-3 list-disc space-y-1 pl-4 text-[12.5px] text-muted">
            {n.notes.slice(0, 8).map((t, i) => (
              <li key={i}>{t}</li>
            ))}
            {n.notes.length > 8 ? <li className="list-none text-[12px]">+{n.notes.length - 8} more</li> : null}
          </ul>
        ) : null}
      </CardBody>
    </Card>
  );
}

function LegendCard({ job }: { job: JobRecord }) {
  const entries = Object.entries(job.legend);
  const [open, setOpen] = useState(false);
  if (entries.length === 0) return null;
  const shown = open ? entries : entries.slice(0, 8);
  return (
    <Card>
      <CardHeader title="Finish legend" description={`${entries.length} codes read from the drawings.`} className="py-3" />
      <CardBody className="py-3">
        <dl className="space-y-1.5 text-[12.5px]">
          {shown.map(([code, desc]) => (
            <div key={code} className="grid grid-cols-[auto_1fr] items-start gap-2">
              <dt>
                <Chip>{code}</Chip>
              </dt>
              <dd className="text-ink/85">{desc}</dd>
            </div>
          ))}
        </dl>
        {entries.length > 8 ? (
          <button type="button" className="mt-2 text-[12.5px] font-medium text-brand hover:underline" onClick={() => setOpen((v) => !v)}>
            {open ? "Show less" : `Show all ${entries.length}`}
          </button>
        ) : null}
      </CardBody>
    </Card>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[88px_1fr] gap-2">
      <dt className="text-muted">{label}</dt>
      <dd className="min-w-0 break-words text-ink">{children}</dd>
    </div>
  );
}

function FormatIcon({ format }: { format: SourceFormat }) {
  const cls = "inline-flex size-8 shrink-0 items-center justify-center rounded-lg [&>svg]:size-4";
  switch (format) {
    case "dwg":
    case "dxf":
      return (
        <span className={cn(cls, "bg-ink text-white")}>
          <FileBox />
        </span>
      );
    case "pdf":
      return (
        <span className={cn(cls, "bg-brand text-white")}>
          <FileText />
        </span>
      );
    case "image":
      return (
        <span className={cn(cls, "bg-info text-white")}>
          <FileImage />
        </span>
      );
    default:
      return (
        <span className={cn(cls, "bg-surface-3 text-muted")}>
          <FileIcon />
        </span>
      );
  }
}

function JobSkeleton() {
  return (
    <div aria-busy>
      <div className="mb-6 space-y-2">
        <Skeleton className="h-3 w-32" />
        <Skeleton className="h-7 w-96 max-w-full" />
        <Skeleton className="h-3.5 w-64" />
      </div>
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-5">
          <Skeleton className="h-11 w-full" />
          <div className="card p-5">
            <SkeletonText lines={6} />
          </div>
        </div>
        <div className="space-y-4">
          <div className="card p-5">
            <SkeletonText lines={4} />
          </div>
          <div className="card p-5">
            <SkeletonText lines={3} />
          </div>
        </div>
      </div>
    </div>
  );
}
