"use client";

import { Check, CheckCircle2, ChevronLeft, ChevronRight, HelpCircle, Maximize2, MessageSquareText, RotateCcw, Sparkles, X } from "lucide-react";
import { useEffect, useState } from "react";
import { answerQuestion, getQuestionPictureUrl, interpretAnswer, undoDecision } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { Decision, Interpretation, JobRecord, ReviewQuestion } from "@/lib/types";
import { cn, errorMessage } from "@/lib/utils";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { useConfirm } from "../ui/ConfirmDialog";
import { Input } from "../ui/Input";
import { Skeleton } from "../ui/Skeleton";
import { useToast } from "../ui/Toast";

/**
 * "Questions for you": each disagreement or open measuring rule the reader found, with a
 * crop of the drawing where the part in question is lit up. Answer with a button or in
 * your own words; the system says back what it understood and changes nothing until you
 * confirm. Every confirmed answer is recorded (who, when, your words) and can be undone.
 */

interface Choice {
  option_id?: string | null;
  custom_values?: Record<string, number>;
  understood_as: string;
  answer_text: string;
  interpreted_by: "button" | "ai" | "rules";
}

export const openQuestions = (job: JobRecord): ReviewQuestion[] => (job.questions ?? []).filter((q) => q.status === "open");

function QuestionPicture({ jobId, q }: { jobId: string; q: ReviewQuestion }) {
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (!q.picture_path) return;
    let alive = true;
    let obj: string | null = null;
    getQuestionPictureUrl(jobId, q.id)
      .then((u) => {
        obj = u;
        if (alive) setUrl(u);
        else URL.revokeObjectURL(u);
      })
      .catch(() => alive && setFailed(true));
    return () => {
      alive = false;
      if (obj) URL.revokeObjectURL(obj);
    };
  }, [jobId, q.id, q.picture_path]);

  if (!q.picture_path || failed) {
    return (
      <div className="flex aspect-[22/15] w-full items-center justify-center rounded-xl border border-dashed border-line bg-surface-2 text-[12.5px] text-muted">
        No picture for this question
      </div>
    );
  }
  if (!url) return <Skeleton className="aspect-[22/15] w-full rounded-xl" />;
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="group relative block w-full cursor-zoom-in overflow-hidden rounded-xl border border-line bg-white hover:border-brand/50"
        title="Open full size"
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={url} alt={`Drawing around ${q.element_tags.slice(0, 3).join(", ")}`} className="w-full object-contain" />
        <span className="pointer-events-none absolute right-2 top-2 inline-flex size-7 items-center justify-center rounded-md bg-white/90 text-ink opacity-0 shadow-card transition-opacity group-hover:opacity-100 [&>svg]:size-3.5">
          <Maximize2 />
        </span>
      </button>
      {open ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/85 p-4" role="dialog" aria-label="Drawing, full size" onClick={() => setOpen(false)}>
          <button type="button" onClick={() => setOpen(false)} className="fixed right-4 top-4 inline-flex size-10 items-center justify-center rounded-full bg-white text-ink shadow-card [&>svg]:size-5" aria-label="Close">
            <X />
          </button>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={url} alt="" className="max-h-full max-w-full rounded-lg bg-white" onClick={(e) => e.stopPropagation()} />
        </div>
      ) : null}
    </>
  );
}

function QuestionCard({
  job,
  q,
  n,
  total,
  readOnly,
  onJobUpdate,
}: {
  job: JobRecord;
  q: ReviewQuestion;
  n: number;
  total: number;
  readOnly: boolean;
  onJobUpdate: (j: JobRecord) => void;
}) {
  const toast = useToast();
  const [text, setText] = useState("");
  const [checking, setChecking] = useState(false);
  const [applying, setApplying] = useState(false);
  const [choice, setChoice] = useState<Choice | null>(null);
  const [notUnderstood, setNotUnderstood] = useState<Interpretation | null>(null);
  const isRule = q.kind === "rule";
  const example = q.custom
    ? q.custom.mode === "shorten"
      ? `e.g. "keep as now" or "stop 150 mm short"`
      : q.custom.fields.length > 1
        ? `e.g. "${q.options[1]?.label.split(":")[0].toLowerCase() ?? "use the schedule"}" or "it's 230 x 600"`
        : `e.g. "${q.options[1]?.label.split(":")[0].toLowerCase() ?? "use the schedule"}" or "it's 250 mm"`
    : `e.g. "${(q.options.find((o) => !o.current) ?? q.options[0])?.label.split(" — ")[0].split(":")[0].toLowerCase()}"`;

  const pick = (optionId: string) => {
    const o = q.options.find((x) => x.id === optionId);
    if (!o) return;
    setNotUnderstood(null);
    setChoice({ option_id: o.id, understood_as: `${o.label}. ${o.detail}`.trim(), answer_text: o.label, interpreted_by: "button" });
  };

  const check = async () => {
    const t = text.trim();
    if (!t || checking) return;
    setChecking(true);
    setChoice(null);
    setNotUnderstood(null);
    try {
      const r = await interpretAnswer(job.id, q.id, t);
      if (r.understood) {
        setChoice({ option_id: r.option_id ?? null, custom_values: r.custom_values, understood_as: r.understood_as, answer_text: t, interpreted_by: r.via });
      } else {
        setNotUnderstood(r);
      }
    } catch (err) {
      toast.error("Could not read the answer", errorMessage(err));
    } finally {
      setChecking(false);
    }
  };

  const apply = async () => {
    if (!choice || applying) return;
    setApplying(true);
    try {
      const updated = await answerQuestion(job.id, q.id, {
        option_id: choice.option_id ?? null,
        custom_values: choice.custom_values ?? {},
        answer_text: choice.answer_text,
        understood_as: choice.understood_as,
        interpreted_by: choice.interpreted_by,
      });
      toast.success("Decision saved", "The quantities were recalculated with your answer.");
      onJobUpdate(updated);
    } catch (err) {
      toast.error("Could not apply the answer", errorMessage(err));
      setApplying(false);
    }
  };

  return (
    <Card className={cn("overflow-hidden", isRule ? "border-info/30" : "border-warning/40")}>
      <div className={cn("flex flex-wrap items-center gap-2 border-b px-5 py-2.5", isRule ? "border-info/20 bg-info-soft/60" : "border-warning/20 bg-warning-soft/60")}>
        <span className={cn("rounded-full px-2.5 py-0.5 text-[11.5px] font-bold uppercase tracking-[0.06em] text-white", isRule ? "bg-info" : "bg-warning")}>{q.topic}</span>
        {isRule ? <span className="text-[12.5px] font-medium text-info">One answer settles {q.element_tags.length} part{q.element_tags.length === 1 ? "" : "s"}</span> : null}
        <span className="ml-auto text-[12px] font-medium text-muted">
          Question {n} of {total}
        </span>
      </div>
      <div className="space-y-4 p-5">
        <h3 className="text-[18px] font-semibold leading-snug text-ink">{q.title}</h3>
        <div>
          <QuestionPicture jobId={job.id} q={q} />
          <p className="mt-1.5 text-[11.5px] text-muted">The part being asked about is coloured; grey is the drawing around it. Click the picture to enlarge.</p>
        </div>
        <div className="min-w-0">
          <p className="text-[14px] leading-relaxed text-ink/90">{q.question}</p>
          {q.why ? (
            <p className="mt-2 text-[12.5px] leading-relaxed text-muted">
              <b className="font-semibold text-ink/70">Why it matters: </b>
              {q.why}
            </p>
          ) : null}

          <p className="mt-4 text-[11.5px] font-semibold uppercase tracking-[0.06em] text-muted">Your answer</p>
          <div className="mt-1.5 flex flex-wrap gap-2">
            {q.options.map((o) => {
              const selected = choice?.option_id === o.id && choice.interpreted_by === "button";
              return (
                <button
                  key={o.id}
                  type="button"
                  disabled={readOnly || applying}
                  onClick={() => pick(o.id)}
                  className={cn(
                    "rounded-lg border px-3 py-2 text-left text-[13px] font-medium transition-colors disabled:opacity-50",
                    selected ? "border-brand bg-brand-soft text-ink ring-2 ring-brand/25" : "border-line-strong bg-surface hover:border-brand/60 hover:bg-brand-tint",
                  )}
                >
                  {o.label}
                  {o.current ? <span className="ml-2 rounded bg-surface-3 px-1.5 py-0.5 text-[10.5px] font-semibold uppercase text-muted">now</span> : null}
                  {o.recommended ? <span className="ml-2 rounded bg-success-soft px-1.5 py-0.5 text-[10.5px] font-semibold uppercase text-success">suggested</span> : null}
                </button>
              );
            })}
          </div>

          <div className="mt-3">
            <label className="mb-1 flex items-center gap-1.5 text-[12.5px] font-medium text-ink/80" htmlFor={`ans-${q.id}`}>
              <MessageSquareText className="size-3.5" /> {q.custom ? q.custom.prompt : "Or answer in your own words"}
            </label>
            <div className="flex gap-2">
              <Input
                id={`ans-${q.id}`}
                value={text}
                disabled={readOnly || applying}
                placeholder={example}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") void check();
                }}
              />
              <Button variant="secondary" onClick={() => void check()} loading={checking} disabled={readOnly || !text.trim()}>
                Check
              </Button>
            </div>
          </div>

          {notUnderstood ? (
            <div className="mt-3 flex gap-2 rounded-lg border border-warning/40 bg-warning-soft px-3 py-2.5 text-[13px] text-ink">
              <HelpCircle className="mt-0.5 size-4 shrink-0 text-warning" />
              <span>{notUnderstood.message}</span>
            </div>
          ) : null}

          {choice ? (
            <div className="mt-3 rounded-lg border border-info/40 bg-info-soft/70 px-3.5 py-3">
              <p className="flex items-center gap-1.5 text-[11.5px] font-semibold uppercase tracking-[0.06em] text-info">
                <Sparkles className="size-3.5" /> {choice.interpreted_by === "button" ? "You picked" : "I understood"}
              </p>
              <p className="mt-1 text-[14px] font-medium leading-snug text-ink">{choice.understood_as}</p>
              {choice.interpreted_by !== "button" ? (
                <p className="mt-1 text-[11.5px] text-muted">
                  {choice.interpreted_by === "ai" ? "Read by the AI from your words." : "Read from your words by keyword matching (the AI is off on this server)."} Nothing changes until you
                  confirm.
                </p>
              ) : (
                <p className="mt-1 text-[11.5px] text-muted">Nothing changes until you confirm.</p>
              )}
              <div className="mt-2.5 flex flex-wrap gap-2">
                <Button size="sm" leftIcon={<Check />} onClick={() => void apply()} loading={applying}>
                  Yes, apply this
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setChoice(null)} disabled={applying}>
                  No, change it
                </Button>
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </Card>
  );
}

function DecidedRow({ job, d, q, readOnly, onJobUpdate }: { job: JobRecord; d: Decision; q?: ReviewQuestion; readOnly: boolean; onJobUpdate: (j: JobRecord) => void }) {
  const toast = useToast();
  const confirm = useConfirm();
  const [busy, setBusy] = useState(false);
  const undo = async () => {
    const ok = await confirm({
      title: "Undo this decision?",
      message: `"${d.understood_as}" will be taken back: the parts return to what they were before, the question opens again, and the quantities are recalculated.`,
      confirmLabel: "Undo",
      danger: true,
    });
    if (!ok) return;
    setBusy(true);
    try {
      onJobUpdate(await undoDecision(job.id, d.id));
      toast.info("Decision undone", "The question is open again.");
    } catch (err) {
      toast.error("Could not undo", errorMessage(err));
      setBusy(false);
    }
  };
  const said = d.interpreted_by !== "button" && d.answer_text && d.answer_text !== d.understood_as;
  return (
    <li className="flex items-start gap-3 px-5 py-3">
      <CheckCircle2 className="mt-0.5 size-4.5 shrink-0 text-success" />
      <div className="min-w-0 flex-1">
        <p className="text-[13px] font-semibold text-ink">{q?.title ?? d.question_key}</p>
        <p className="mt-0.5 text-[13px] text-ink/90">{d.understood_as}</p>
        <p className="mt-0.5 text-[11.5px] text-muted">
          {said ? <>They wrote: &ldquo;{d.answer_text}&rdquo; · </> : null}
          {d.decided_by} · {formatDate(d.decided_at)} · {d.applied.filter((a) => a.field || a.added || a.removed).length} change
          {d.applied.filter((a) => a.field || a.added || a.removed).length === 1 ? "" : "s"}
        </p>
      </div>
      {!readOnly ? (
        <Button size="xs" variant="ghost" leftIcon={<RotateCcw />} onClick={() => void undo()} loading={busy}>
          Undo
        </Button>
      ) : null}
    </li>
  );
}

export function QuestionsPanel({ job, readOnly, readOnlyReason, onJobUpdate }: { job: JobRecord; readOnly: boolean; readOnlyReason?: string | null; onJobUpdate: (j: JobRecord) => void }) {
  const open = openQuestions(job);
  const total = (job.questions ?? []).length;
  const [idx, setIdx] = useState(0);
  if (!total) return null;
  if (!open.length) {
    return (
      <Card className="border-success/40">
        <div className="flex items-center gap-2.5 px-5 py-3.5 text-[13.5px] font-medium text-success">
          <CheckCircle2 className="size-4.5" /> All {total} questions are answered. Your decisions are listed below.
        </div>
      </Card>
    );
  }
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-[17px] font-semibold text-ink">Questions for you ({open.length} left)</h2>
        <p className="mt-0.5 text-[13px] text-muted">
          The drawing leaves these open. Look at the coloured part, then answer with a button or in your own words. Blue ones are measuring rules — one answer fixes many parts.
        </p>
        {readOnly && readOnlyReason ? <p className="mt-1 text-[12.5px] font-medium text-warning">{readOnlyReason}</p> : null}
      </div>
      <QuestionStepper open={open} idx={Math.min(idx, open.length - 1)} setIdx={setIdx} />
      <QuestionCard
        key={open[Math.min(idx, open.length - 1)].id}
        job={job}
        q={open[Math.min(idx, open.length - 1)]}
        n={Math.min(idx, open.length - 1) + 1}
        total={open.length}
        readOnly={readOnly}
        onJobUpdate={onJobUpdate}
      />
      <QuestionStepper open={open} idx={Math.min(idx, open.length - 1)} setIdx={setIdx} bottom />
    </div>
  );
}

/** Back / Next and one dot per open question; answered questions drop out of the row. */
function QuestionStepper({ open, idx, setIdx, bottom }: { open: ReviewQuestion[]; idx: number; setIdx: (i: number) => void; bottom?: boolean }) {
  if (open.length < 2) return null;
  return (
    <div className={cn("flex items-center gap-3", bottom && "justify-center")}>
      <Button size="sm" variant="secondary" leftIcon={<ChevronLeft />} onClick={() => setIdx(Math.max(0, idx - 1))} disabled={idx === 0}>
        Back
      </Button>
      <div className="flex flex-1 flex-wrap items-center justify-center gap-1.5" role="tablist" aria-label="Questions">
        {open.map((q, i) => (
          <button
            key={q.id}
            type="button"
            role="tab"
            aria-selected={i === idx}
            title={q.title}
            onClick={() => setIdx(i)}
            className={cn(
              "inline-flex h-7 min-w-7 items-center justify-center rounded-full border px-2 text-[12px] font-semibold transition-colors",
              i === idx ? "border-brand bg-brand text-white" : q.kind === "rule" ? "border-info/40 bg-info-soft text-info hover:border-info" : "border-warning/40 bg-warning-soft text-warning hover:border-warning",
            )}
          >
            {i + 1}
          </button>
        ))}
      </div>
      <Button size="sm" variant="secondary" rightIcon={<ChevronRight />} onClick={() => setIdx(Math.min(open.length - 1, idx + 1))} disabled={idx >= open.length - 1}>
        Next
      </Button>
    </div>
  );
}

export function DecisionsPanel({ job, readOnly, onJobUpdate }: { job: JobRecord; readOnly: boolean; onJobUpdate: (j: JobRecord) => void }) {
  const live = (job.decisions ?? []).filter((d) => !d.undone).slice().reverse();
  if (!live.length) return null;
  const byId = new Map((job.questions ?? []).map((q) => [q.id, q]));
  return (
    <Card className="border-success/30">
      <div className="border-b border-line px-5 py-3">
        <h3 className="text-[14px] font-semibold text-ink">Decisions made ({live.length})</h3>
        <p className="text-[12px] text-muted">Each one is recorded with who answered, when, and their words. If the drawing is read again, these are applied again automatically.</p>
      </div>
      <ul className="divide-y divide-line">
        {live.map((d) => (
          <DecidedRow key={d.id} job={job} d={d} q={byId.get(d.question_id)} readOnly={readOnly} onJobUpdate={onJobUpdate} />
        ))}
      </ul>
    </Card>
  );
}
